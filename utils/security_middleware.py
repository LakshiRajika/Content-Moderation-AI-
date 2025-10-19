# utils/security_middleware.py
import re
import jwt
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import request, jsonify, g

class SecurityMiddleware:
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.sanitization_patterns = [
            (r'<script.*?>.*?</script>', ''),  # Remove script tags
            (r'javascript:', ''),  # Remove javascript protocol
            (r'on\w+=".*?"', ''),  # Remove event handlers
        ]
    
    def sanitize_input(self, text: str) -> str:
        """Sanitize user input to prevent XSS"""
        if not text:
            return text
        
        sanitized = text
        for pattern, replacement in self.sanitization_patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Additional HTML escaping
        sanitized = (sanitized.replace('&', '&amp;')
                             .replace('<', '&lt;')
                             .replace('>', '&gt;')
                             .replace('"', '&quot;')
                             .replace("'", '&#x27;'))
        return sanitized
    
    def generate_token(self, user_id: str, role: str = "user") -> str:
        """Generate JWT token for authentication"""
        payload = {
            'user_id': user_id,
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_token(self, token: str) -> dict:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Token required"}), 401
        
        user_data = security_middleware.verify_token(token)
        if not user_data:
            return jsonify({"error": "Invalid token"}), 401
        
        g.user = user_data
        return f(*args, **kwargs)
    return decorated

# Global instance
security_middleware = SecurityMiddleware()