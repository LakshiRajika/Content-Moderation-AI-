# Content-Moderation-AI-

# 🛡️ CEnSORX - AI Content Moderation Platform

> Enterprise-grade AI content moderation for social media platforms and online communities

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![Google Gemini](https://img.shields.io/badge/Google-Gemini_AI-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📖 Project Overview

CEnSORX is a comprehensive AI-powered content moderation platform that automatically detects and handles harmful, toxic, or risky content in real-time. Built with a multi-agent architecture, it helps social media companies, community platforms, and enterprises maintain safe online environments by automatically analyzing text and images across multiple safety categories.

**Live Demo**: [https://your-demo-link.com](https://your-demo-link.com)

## 🚀 Key Features

### 🤖 AI-Powered Moderation
- **Multi-Agent Pipeline** - Specialized agents for classification, risk assessment, and action determination
- **Real-time Analysis** - Instant text and image moderation with sub-second response times
- **Six Safety Categories** - Violence, hate speech, threats, explicit content, profanity, and spam detection

### 📊 Management & Analytics
- **Interactive Dashboard** - Comprehensive audit trail with visual analytics
- **Human Review Queue** - Streamlined workflow for borderline cases
- **Export Capabilities** - CSV, JSON, and PDF reports for compliance

### 🔧 Enterprise Ready
- **Configurable Rules** - Customizable thresholds and action mappings
- **NLP Insights** - Entity extraction, sentiment analysis, and content summarization
- **Security Features** - JWT authentication, input sanitization, audit logging


## Run locally

1. Create and activate a virtual environment (Windows PowerShell):
```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

3. Configure environment variables (create a `.env` file or set in shell):
```
SECRET_KEY=change-me
# Enable Gemini-powered classification
GEMINI_API_KEY=<your-google-gemini-api-key>
# Optional: use a remote Audit API; fallback to local SQLite if unset/unreachable
AUDIT_API_BASE_URL=https://your-audit-service.example.com
AUDIT_API_KEY=<optional-bearer-token>
AUDIT_API_TIMEOUT=10            # seconds (default 10)
AUDIT_API_RETRIES=3             # default 3
AUDIT_API_VERIFY_TLS=true       # set to false for self-signed dev certs
AUDIT_API_HEALTH_PATH=/health   # health endpoint path
AUDIT_USE_GEMINI_SUMMARY=false  # set true to enrich audit logs with Gemini
AUDIT_GEMINI_MODEL=gemini-2.5-flash
```

4. Start the app:
```powershell
python main.py
```
Open http://127.0.0.1:5000

## Notes
- If `GEMINI_API_KEY` is set, the classifier uses Gemini; otherwise it runs in demo mode.
- If `AUDIT_API_BASE_URL` is set, `AuditAgent` will send/receive logs via REST and gracefully fallback to local SQLite on errors. 
