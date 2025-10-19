# utils/retrieval_agent.py
import sqlite3
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any

class RetrievalAgent:
    def __init__(self, db_path: str = "moderation_history.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for content history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE,
                content_text TEXT,
                classification JSON,
                risk_score REAL,
                actions_taken JSON,
                timestamp DATETIME,
                user_id TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def store_moderation(self, content: str, classification: dict, 
                        risk_score: float, actions: list, user_id: str = "anonymous"):
        """Store moderation result in database"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO moderation_history 
            (content_hash, content_text, classification, risk_score, actions_taken, timestamp, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (content_hash, content, json.dumps(classification), risk_score, 
              json.dumps(actions), datetime.now(), user_id))
        conn.commit()
        conn.close()
    
    def find_similar_content(self, content: str, threshold: float = 0.8) -> List[Dict]:
        """Find historically similar moderated content"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT content_text, classification, risk_score, actions_taken, timestamp
            FROM moderation_history 
            WHERE content_hash = ? OR content_text LIKE ?
            LIMIT 5
        ''', (content_hash, f"%{content[:50]}%"))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "content": row[0],
                "classification": json.loads(row[1]),
                "risk_score": row[2],
                "previous_actions": json.loads(row[3]),
                "timestamp": row[4]
            })
        conn.close()
        return results