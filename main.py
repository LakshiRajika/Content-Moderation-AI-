from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
from agents.classifier_agent import ClassifierAgent
from google.genai import types # Import the types module to handle image parts

# from agents.risk_agent import RiskAgent (To be implemented later)
# from agents.audit_agent import AuditAgent (To be implemented later)

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')

# Initialize Agents
try:
    classifier_agent = ClassifierAgent()
except ValueError as e:
    print(f"Error initializing agents: {e}")
    exit()

# --- HARMFUL CATEGORIES (The 6 scores returned by the AI agent) ---
HARMFUL_CATEGORIES = [
    'violence', 
    'hate_speech', 
    'profanity', 
    'sexual', 
    'spam', 
    'threat'
]
# ------------------------------------------------------------------

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/moderate', methods=['POST'])
def moderate_content():
    """
    Handles multimodal content moderation (text and/or image).
    """
    
    # Extract data from FormData (used for file uploads), not request.json
    content_text = request.form.get('content', '').strip()
    uploaded_file = request.files.get('image')
    user_id = request.form.get('user_id', 'anonymous')

    content_to_agent = content_text
    content_type = 'text'

    if uploaded_file:
        try:
            # Read file bytes and determine MIME type
            image_bytes = uploaded_file.read()
            mime_type = uploaded_file.mimetype
            
            # Create the types.Part object for Gemini
            content_to_agent = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            content_type = 'image'
        except Exception as e:
            return jsonify({"error": f"Failed to process image file: {e}"}), 400
    
    # Require at least text or an image
    if not content_to_agent or (content_type == 'text' and not content_text):
        return jsonify({"error": "Please provide text, an image, or both."}), 400
    
    # 1. CLASSIFICATION STAGE
    classification_result = classifier_agent.classify_content(content_to_agent, content_type)
    
    if classification_result['status'] == 'error':
        return jsonify({"error": classification_result['message']}), 500

    classification = classification_result['classification']
    
    # --- CALCULATE AND ADD 'NORMAL' SCORE ---
    harmful_scores_values = [
        classification.get(cat, 0.0) 
        for cat in HARMFUL_CATEGORIES
    ]
    
    max_harm_score = max(harmful_scores_values) if harmful_scores_values else 0.0
    normal_score = round(1.0 - max_harm_score, 4)
    classification['normal'] = normal_score
    
    # --- RISK ASSESSMENT STAGE (Robust Mock Logic) ---
    
    if max_harm_score > 0.8:
        risk_level = "High"
        actions = ["Block content", "Ban user"]
    elif max_harm_score > 0.3:
        risk_level = "Medium"
        actions = ["Flag for human review", "Temporarily shadow-ban user"]
    else:
        risk_level = "Low"
        actions = ["No action required"]

    if len(HARMFUL_CATEGORIES) > 0:
        avg_harmful_score = sum(harmful_scores_values) / len(HARMFUL_CATEGORIES)
    else:
        avg_harmful_score = 0.0

    risk_score = {
        "score": round(avg_harmful_score, 4), 
        "level": risk_level, 
        "reasons": [f"Max risk is {max_harm_score*100:.2f}%"]
    }

    # Final response structure expected by your script.js
    return jsonify({
        "classification": classification,
        "risk_score": {
            "score": risk_score["score"],
            "level": risk_score["level"],
            "reasons": risk_score["reasons"]
        },
        "action": {
            "actions": actions
        },
        "audit_id": "mock_audit_123" 
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)