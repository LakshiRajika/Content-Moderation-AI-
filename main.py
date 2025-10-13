# main.py
from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
from agents.classifier_agent import ClassifierAgent
from agents.risk_agent import RiskAgent  # ✅ Import the RiskAgent
from google.genai import types

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')

# Initialize Agents
try:
    classifier_agent = ClassifierAgent()
    risk_agent = RiskAgent()  # ✅ Initialize RiskAgent
except ValueError as e:
    print(f"Error initializing agents: {e}")
    exit()

# --- HARMFUL CATEGORIES ---
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
    """Serves the main HTML page."""
    return render_template('index.html')


@app.route('/moderate', methods=['POST'])
def moderate_content():
    """
    Handles multimodal content moderation (text and/or image).
    """

    content_text = request.form.get('content', '').strip()
    uploaded_file = request.files.get('image')
    user_id = request.form.get('user_id', 'anonymous')

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

    # --- 1. CLASSIFICATION STAGE ---
    classification_result = classifier_agent.classify_content(content_to_agent, content_type)

    if classification_result['status'] == 'error':
        return jsonify({"error": classification_result['message']}), 500

    classification = classification_result['classification']

    # --- 2. ADD NORMAL SCORE ---
    harmful_scores_values = [classification.get(cat, 0.0) for cat in HARMFUL_CATEGORIES]
    max_harm_score = max(harmful_scores_values) if harmful_scores_values else 0.0
    normal_score = round(1.0 - max_harm_score, 4)
    classification['normal'] = normal_score

    # --- 3. RISK ASSESSMENT STAGE (using RiskAgent) ---
    risk_result = risk_agent.evaluate(classification, text=content_text)

    # --- 4. DETERMINE ACTIONS BASED ON RISK LEVEL ---
    if risk_result['level'] == "High":
        actions = ["Block content", "Ban user"]
    elif risk_result['level'] == "Medium":
        actions = ["Flag for human review", "Shadow-ban user"]
    else:
        actions = ["No action required"]

    # --- 5. FINAL RESPONSE ---
    return jsonify({
        "classification": classification,
        "risk_score": {
            "score": risk_result["score"],
            "level": risk_result["level"],
            "reasons": risk_result["reasons"]
        },
        "action": {
            "actions": actions
        },
        "audit_id": risk_result["audit_id"]
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
