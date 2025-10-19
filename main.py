# main.py
from flask import Flask, request, jsonify, render_template, g
import os
from dotenv import load_dotenv
from agents.classifier_agent import ClassifierAgent
from agents.risk_agent import RiskAgent
from agents.action_agent import ActionAgent
from utils.nlp_processor import NLPProcessor
from utils.retrieval_agent import RetrievalAgent
from utils.security_middleware import security_middleware, token_required
from google.genai import types

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')

# Initialize All Agents
try:
    classifier_agent = ClassifierAgent()
    risk_agent = RiskAgent()
    action_agent = ActionAgent()
    nlp_processor = NLPProcessor()
    retrieval_agent = RetrievalAgent()
except Exception as e:
    print(f"Error initializing agents: {e}")
    exit()

HARMFUL_CATEGORIES = [
    'violence',
    'hate_speech',
    'profanity',
    'sexual',
    'spam',
    'threat'
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authentication endpoint"""
    username = request.json.get('username', 'demo_user')
    password = request.json.get('password', 'demo_pass')
    
    # Simple demo authentication - replace with proper auth in production
    if username and password:
        token = security_middleware.generate_token(username)
        return jsonify({
            "token": token, 
            "user": username,
            "message": "Login successful"
        })
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/moderate', methods=['POST'])
@token_required
def moderate_content():
    """Enhanced moderation endpoint with all features"""
    content_text = security_middleware.sanitize_input(request.form.get('content', '').strip())
    uploaded_file = request.files.get('image')
    user_id = g.user.get('user_id', 'anonymous')

    content_to_agent = content_text
    content_type = 'text'

    if uploaded_file:
        try:
            image_bytes = uploaded_file.read()
            mime_type = uploaded_file.mimetype
            content_to_agent = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            content_type = 'image'
        except Exception as e:
            return jsonify({"error": f"Failed to process image file: {e}"}), 400

    if not content_to_agent or (content_type == 'text' and not content_text):
        return jsonify({"error": "Please provide text, an image, or both."}), 400

    try:
        # --- 1. NLP Processing (NEW) ---
        nlp_analysis = {}
        if content_type == 'text' and content_text:
            nlp_analysis = {
                "entities": nlp_processor.extract_entities(content_text),
                "summary": nlp_processor.summarize_content(content_text)
            }

        # --- 2. Information Retrieval (NEW) ---
        similar_content = []
        if content_type == 'text' and content_text:
            similar_content = retrieval_agent.find_similar_content(content_text)

        # --- 3. Classification ---
        classification_result = classifier_agent.classify_content(content_to_agent, content_type)
        if classification_result['status'] == 'error':
            return jsonify({"error": classification_result['message']}), 500
        classification = classification_result['classification']

        # --- 4. Add Normal Score ---
        max_harm_score = max([classification.get(cat, 0.0) for cat in HARMFUL_CATEGORIES] or [0.0])
        classification['normal'] = round(1.0 - max_harm_score, 4)

        # --- 5. Risk Assessment ---
        risk_result = risk_agent.evaluate(classification, text=content_text)

        # --- 6. Determine Actions ---
        action_result = action_agent.determine_actions(risk_result, classification)

        # --- 7. Store in Retrieval System (NEW) ---
        if content_type == 'text' and content_text:
            retrieval_agent.store_moderation(
                content_text, classification, risk_result["score"], 
                action_result["actions"], user_id
            )

        # --- 8. Final Enhanced Response ---
        return jsonify({
            "classification": classification,
            "risk_score": {
                "score": risk_result["score"],
                "level": risk_result["level"],
                "reasons": risk_result.get("reasons", []),
            },
            "action": action_result,
            "nlp_analysis": nlp_analysis,  # NEW
            "historical_context": {        # NEW
                "similar_cases_found": len(similar_content),
                "previous_decisions": similar_content[:2]  # Top 2 most relevant
            },
            "audit_id": risk_result["audit_id"],
            "user_id": user_id
        })

    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"}), 500

@app.route('/api/history', methods=['GET'])
@token_required
def get_moderation_history():
    """Get user's moderation history"""
    user_id = g.user.get('user_id')
    # Implementation to fetch user-specific history
    return jsonify({"message": "History endpoint", "user": user_id})

if __name__ == '__main__':
    app.run(debug=True, port=5000)