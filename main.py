# main.py
from flask import Flask, request, jsonify, render_template, g
import os
from dotenv import load_dotenv
from agents.classifier_agent import ClassifierAgent
from agents.risk_agent import RiskAgent
from agents.action_agent import ActionAgent
from agents.audit_agent import AuditAgent
from utils.nlp_processor import NLPProcessor
from utils.retrieval_agent import RetrievalAgent
from utils.security_middleware import security_middleware, token_required
import time
from google.genai import types

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')

# Initialize All Agents
try:
    classifier_agent = ClassifierAgent()
    risk_agent = RiskAgent()
    action_agent = ActionAgent()
    audit_agent = AuditAgent()
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
def moderate_content():
    """Enhanced moderation endpoint with all features"""
    content_text = security_middleware.sanitize_input(request.form.get('content', '').strip())
    uploaded_file = request.files.get('image')
    
    # Get user_id from request or use a session-based approach
    user_id = request.headers.get('X-User-ID', 'anonymous')
    if user_id == 'anonymous':
        # Try to get from session or generate a session-based ID
        import hashlib
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.remote_addr or 'unknown'
        session_hash = hashlib.md5(f"{ip_address}{user_agent}".encode()).hexdigest()[:8]
        user_id = f"user_{session_hash}"

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
        start_time = time.time()
        
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
        classification_start = time.time()
        classification_result = classifier_agent.classify_content(content_to_agent, content_type)
        classification_time = int((time.time() - classification_start) * 1000)
        
        if classification_result['status'] == 'error':
            return jsonify({"error": classification_result['message']}), 500
        classification = classification_result['classification']

        # --- 4. Add Normal Score ---
        max_harm_score = max([classification.get(cat, 0.0) for cat in HARMFUL_CATEGORIES] or [0.0])
        classification['normal'] = round(1.0 - max_harm_score, 4)

        # --- 5. Risk Assessment ---
        risk_start = time.time()
        risk_result = risk_agent.evaluate(classification, text=content_text)
        risk_time = int((time.time() - risk_start) * 1000)

        # --- 6. Determine Actions ---
        action_start = time.time()
        action_result = action_agent.determine_actions(risk_result, classification)
        action_time = int((time.time() - action_start) * 1000)

        # --- 7. Store in Retrieval System (NEW) ---
        if content_type == 'text' and content_text:
            retrieval_agent.store_moderation(
                content_text, classification, risk_result["score"], 
                action_result["actions"], user_id
            )

        # --- 8. AUDIT LOGGING (NEW, NON-BLOCKING) ---
        audit_id = None
        try:
            total_processing_time = int((time.time() - start_time) * 1000)
            audit_id = audit_agent.log_moderation_decision(
                user_id=user_id,
                content=content_text or "",
                content_type=content_type,
                classification=classification,
                risk_result=risk_result,
                action_result=action_result,
                nlp_analysis=nlp_analysis,
                processing_time_ms=total_processing_time,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

            # Log individual agent decisions (best-effort)
            try:
                audit_agent.log_agent_decision(
                    audit_id=audit_id,
                    agent_name="classifier",
                    decision_type="content_classification",
                    input_data={"content_type": content_type, "content_preview": (content_text or "")[:100]},
                    output_data=classification,
                    processing_time_ms=classification_time
                )
                audit_agent.log_agent_decision(
                    audit_id=audit_id,
                    agent_name="risk_assessor",
                    decision_type="risk_evaluation",
                    input_data={"classification": classification},
                    output_data=risk_result,
                    processing_time_ms=risk_time
                )
                audit_agent.log_agent_decision(
                    audit_id=audit_id,
                    agent_name="action_agent",
                    decision_type="action_determination",
                    input_data={"risk_result": risk_result, "classification": classification},
                    output_data=action_result,
                    processing_time_ms=action_time
                )
            except Exception:
                pass
        except Exception:
            # Never block moderation on audit failures
            pass

        # --- 9. Final Enhanced Response ---
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
            "audit_id": audit_id or risk_result.get("audit_id"),
            "user_id": user_id
        })

    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"}), 500

@app.route('/api/history', methods=['GET'])
def get_moderation_history():
    """Get user's moderation history"""
    user_data = getattr(g, 'user', None)
    user_id = user_data.get('user_id') if isinstance(user_data, dict) else 'anonymous'
    # Implementation to fetch user-specific history
    return jsonify({"message": "History endpoint", "user": user_id})

# --- AUDIT DASHBOARD ROUTES ---

@app.route('/audit-dashboard')
def audit_dashboard():
    """Audit dashboard for admin/moderators"""
    return render_template('audit_dashboard.html')

@app.route('/api/audit/summary')
def get_audit_summary():
    """Get audit summary statistics"""
    days = request.args.get('days', 30, type=int)
    try:
        summary = audit_agent.get_audit_summary(days=days)
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit/trail')
def get_audit_trail():
    """Get detailed audit trail"""
    user_id = request.args.get('user_id')
    risk_level = request.args.get('risk_level')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 100, type=int)
    days = request.args.get('days', 30, type=int)
    
    # Calculate date range if days is provided
    if not start_date and days:
        from datetime import datetime, timedelta
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    try:
        trail = audit_agent.get_detailed_audit_trail(
            user_id=user_id,
            risk_level=risk_level,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        return jsonify(trail)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit/export')
def export_audit_report():
    """Export audit data in CSV or JSON format"""
    format_type = request.args.get('format', 'csv')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    days = request.args.get('days', 30, type=int)
    
    # Calculate date range if days is provided
    if not start_date and days:
        from datetime import datetime, timedelta
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    try:
        report_data = audit_agent.export_audit_report(
            format_type=format_type,
            start_date=start_date,
            end_date=end_date
        )
        
        if format_type.lower() == 'csv':
            from flask import Response
            return Response(
                report_data,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=audit_report.csv'}
            )
        elif format_type.lower() == 'pdf':
            from flask import Response
            return Response(
                report_data,
                mimetype='application/pdf',
                headers={'Content-Disposition': 'attachment; filename=audit_report.pdf'}
            )
        elif format_type.lower() == 'json':
            from flask import Response
            return Response(
                report_data,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=audit_report.json'}
            )
        else:
            return jsonify(report_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit/performance')
def get_agent_performance():
    """Get agent performance metrics"""
    days = request.args.get('days', 30, type=int)
    try:
        metrics = audit_agent.get_agent_performance_metrics(days=days)
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)