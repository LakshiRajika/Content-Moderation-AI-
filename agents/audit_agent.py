import sqlite3
import os
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class AuditAgent:
    """
    AuditAgent: Handles audit logging, visualization data, and reporting.
    Dual mode:
      - Remote REST API when AUDIT_API_BASE_URL is set (with retries, timeouts, TLS verify toggle)
      - Local SQLite fallback when API is not configured or fails
    Optional Gemini summary enrichment when AUDIT_USE_GEMINI_SUMMARY=true
    """

    def __init__(self, db_path: str = "moderation_history.db"):
        self.db_path = db_path
        # API mode configuration (optional)
        self.api_base_url = os.getenv("AUDIT_API_BASE_URL")
        self.api_key = os.getenv("AUDIT_API_KEY")
        self.api_enabled = bool(self.api_base_url)

        # HTTP configuration
        self.api_timeout = float(os.getenv("AUDIT_API_TIMEOUT", "10"))
        self.api_retries = int(os.getenv("AUDIT_API_RETRIES", "3"))
        self.api_verify_tls = os.getenv("AUDIT_API_VERIFY_TLS", "true").lower() != "false"
        self.api_health_path = os.getenv("AUDIT_API_HEALTH_PATH", "/health")

        # requests session with retries
        self.session = requests.Session() if self.api_enabled else None
        if self.api_enabled and self.session:
            retry_cfg = Retry(
                total=self.api_retries,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                raise_on_status=False
            )
            adapter = HTTPAdapter(max_retries=retry_cfg)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

        # Initialize local DB if API not configured
        if not self.api_enabled:
            self.init_audit_tables()

    def init_audit_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT UNIQUE NOT NULL,
                timestamp DATETIME NOT NULL,
                user_id TEXT NOT NULL,
                session_id TEXT,
                content_hash TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content_preview TEXT,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                classification_scores TEXT NOT NULL,
                actions_taken TEXT NOT NULL,
                policies_applied TEXT,
                nlp_analysis TEXT,
                processing_time_ms INTEGER,
                agent_versions TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                input_data TEXT,
                output_data TEXT,
                confidence_score REAL,
                processing_time_ms INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (audit_id) REFERENCES audit_logs (audit_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_description TEXT,
                severity TEXT NOT NULL,
                user_id TEXT,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def generate_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def log_moderation_decision(self,
                              user_id: str,
                              content: str,
                              content_type: str,
                              classification: Dict[str, float],
                              risk_result: Dict[str, Any],
                              action_result: Dict[str, Any],
                              nlp_analysis: Dict[str, Any] = None,
                              session_id: str = None,
                              processing_time_ms: int = None,
                              ip_address: str = None,
                              user_agent: str = None) -> str:
        # Remote API first
        if self.api_enabled:
            try:
                payload = {
                    "user_id": user_id,
                    "content": content,
                    "content_type": content_type,
                    "classification": classification,
                    "risk_result": risk_result,
                    "action_result": action_result,
                    "nlp_analysis": nlp_analysis,
                    "session_id": session_id,
                    "processing_time_ms": processing_time_ms,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "timestamp": datetime.now().isoformat()
                }

                # Optional Gemini summary enrichment
                if os.getenv("AUDIT_USE_GEMINI_SUMMARY", "false").lower() == "true":
                    try:
                        decision_payload = {
                            "user_id": user_id,
                            "content_preview": (content[:200] + "...") if content and len(content) > 200 else (content or ""),
                            "content_type": content_type,
                            "classification": classification,
                            "risk_result": risk_result,
                            "action_result": action_result,
                        }
                        summary_text = self._summarize_decision_with_gemini(decision_payload)
                        if summary_text:
                            if not payload.get("nlp_analysis"):
                                payload["nlp_analysis"] = {}
                            payload["nlp_analysis"]["gemini_summary"] = summary_text
                    except Exception:
                        pass

                resp = self._post("/audit/log", json=payload)
                if resp and isinstance(resp, dict) and resp.get("audit_id"):
                    return resp["audit_id"]
            except Exception:
                pass

        # Local insert
        audit_id = str(uuid.uuid4())
        content_hash = self.generate_content_hash(f"image_{audit_id}") if content_type == 'image' else self.generate_content_hash(content)
        timestamp = datetime.now()

        classification_json = json.dumps(classification)
        actions_json = json.dumps(action_result.get('actions', []))
        policies_json = json.dumps(action_result.get('policies', []))
        nlp_json = json.dumps(nlp_analysis) if nlp_analysis else None

        content_preview = f"[Image Content - {content_type}]" if content_type == 'image' else (content[:100] + "..." if len(content) > 100 else content)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO audit_logs (
                    audit_id, timestamp, user_id, session_id, content_hash,
                    content_type, content_preview, risk_score, risk_level,
                    classification_scores, actions_taken, policies_applied,
                    nlp_analysis, processing_time_ms, ip_address, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                audit_id, timestamp, user_id, session_id, content_hash,
                content_type, content_preview, risk_result.get('score', 0.0),
                risk_result.get('level', 'Unknown'), classification_json,
                actions_json, policies_json, nlp_json, processing_time_ms,
                ip_address, user_agent
            ))
            conn.commit()
            return audit_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def log_agent_decision(self,
                          audit_id: str,
                          agent_name: str,
                          decision_type: str,
                          input_data: Dict[str, Any],
                          output_data: Dict[str, Any],
                          confidence_score: float = None,
                          processing_time_ms: int = None):
        if self.api_enabled:
            try:
                payload = {
                    "audit_id": audit_id,
                    "agent_name": agent_name,
                    "decision_type": decision_type,
                    "input_data": input_data,
                    "output_data": output_data,
                    "confidence_score": confidence_score,
                    "processing_time_ms": processing_time_ms,
                    "timestamp": datetime.now().isoformat()
                }
                self._post("/audit/agent-decision", json=payload)
                return
            except Exception:
                pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO agent_decisions (
                    audit_id, agent_name, decision_type, input_data,
                    output_data, confidence_score, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                audit_id, agent_name, decision_type,
                json.dumps(input_data), json.dumps(output_data),
                confidence_score, processing_time_ms
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def log_system_event(self,
                        event_type: str,
                        event_description: str,
                        severity: str = "INFO",
                        user_id: str = None,
                        metadata: Dict[str, Any] = None):
        if self.api_enabled:
            try:
                payload = {
                    "event_type": event_type,
                    "event_description": event_description,
                    "severity": severity,
                    "user_id": user_id,
                    "metadata": metadata,
                    "timestamp": datetime.now().isoformat()
                }
                self._post("/audit/system-event", json=payload)
                return
            except Exception:
                pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO system_events (
                    event_type, event_description, severity, user_id, metadata
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                event_type, event_description, severity, user_id,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_audit_summary(self, days: int = 30) -> Dict[str, Any]:
        if self.api_enabled:
            try:
                data = self._get("/audit/summary", params={"days": days})
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
        '''.format(days))
        total_decisions = cursor.fetchone()[0]

        cursor.execute('''
            SELECT content_type, COUNT(*) FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY content_type
        '''.format(days))
        content_type_distribution = dict(cursor.fetchall())

        cursor.execute('''
            SELECT risk_level, COUNT(*) FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY risk_level
        '''.format(days))
        risk_distribution = dict(cursor.fetchall())

        cursor.execute('''
            SELECT AVG(risk_score) FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
        '''.format(days))
        avg_risk_score = cursor.fetchone()[0] or 0.0

        cursor.execute('''
            SELECT classification_scores FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
        '''.format(days))
        category_scores = []
        for row in cursor.fetchall():
            try:
                scores = json.loads(row[0])
                category_scores.append(scores)
            except Exception:
                continue

        category_averages = {}
        categories = ['violence', 'hate_speech', 'threat', 'sexual', 'profanity', 'spam', 'normal']
        for category in categories:
            scores = [s.get(category, 0) for s in category_scores if s.get(category) is not None]
            category_averages[category] = round(sum(scores) / len(scores), 3) if scores else 0

        cursor.execute('''
            SELECT actions_taken, COUNT(*) FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY actions_taken
            ORDER BY COUNT(*) DESC
            LIMIT 5
        '''.format(days))
        common_actions = cursor.fetchall()

        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        '''.format(days))
        daily_activity = cursor.fetchall()

        cursor.execute('''
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count 
            FROM audit_logs 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY strftime('%H', timestamp)
            ORDER BY hour
        '''.format(days))
        hourly_activity = cursor.fetchall()

        conn.close()

        return {
            "total_decisions": total_decisions,
            "content_type_distribution": content_type_distribution,
            "risk_distribution": risk_distribution,
            "category_averages": category_averages,
            "average_risk_score": round(avg_risk_score, 3),
            "common_actions": common_actions,
            "daily_activity": daily_activity,
            "hourly_activity": hourly_activity,
            "period_days": days
        }

    def get_detailed_audit_trail(self,
                                user_id: str = None,
                                risk_level: str = None,
                                start_date: str = None,
                                end_date: str = None,
                                limit: int = 100) -> List[Dict[str, Any]]:
        if self.api_enabled:
            try:
                params = {
                    "user_id": user_id,
                    "risk_level": risk_level,
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit
                }
                data = self._get("/audit/trail", params={k: v for k, v in params.items() if v is not None})
                if isinstance(data, list):
                    return data
            except Exception:
                pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            record['classification_scores'] = json.loads(record['classification_scores'])
            record['actions_taken'] = json.loads(record['actions_taken'])
            record['policies_applied'] = json.loads(record['policies_applied'])
            if record['nlp_analysis']:
                record['nlp_analysis'] = json.loads(record['nlp_analysis'])
            results.append(record)

        conn.close()
        return results

    def export_audit_report(self,
                           format_type: str = "csv",
                           start_date: str = None,
                           end_date: str = None) -> str:
        if self.api_enabled:
            try:
                params = {"format": format_type, "start_date": start_date, "end_date": end_date}
                url = self._build_url("/audit/export")
                headers = self._headers()
                resp = self.session.get(
                    url,
                    headers=headers,
                    params={k: v for k, v in params.items() if v is not None},
                    timeout=self.api_timeout,
                    verify=self.api_verify_tls
                )
                resp.raise_for_status()
                return resp.text
            except Exception:
                pass

        import csv
        import io
        audit_data = self.get_detailed_audit_trail(start_date=start_date, end_date=end_date, limit=10000)
        if format_type.lower() == "csv":
            output = io.StringIO()
            if audit_data:
                import csv as _csv
                writer = _csv.DictWriter(output, fieldnames=audit_data[0].keys())
                writer.writeheader()
                for row in audit_data:
                    flat_row = {}
                    for key, value in row.items():
                        if isinstance(value, (dict, list)):
                            flat_row[key] = json.dumps(value)
                        else:
                            flat_row[key] = value
                    writer.writerow(flat_row)
            return output.getvalue()
        elif format_type.lower() == "json":
            return json.dumps(audit_data, indent=2, default=str)
        elif format_type.lower() == "pdf":
            return self._generate_pdf_report(audit_data, start_date, end_date)
        else:
            raise ValueError("Unsupported format. Use 'csv', 'json', or 'pdf'")

    # --- API helpers ---
    def _build_url(self, path: str) -> str:
        base = (self.api_base_url or "").rstrip("/")
        return f"{base}{path}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, path: str, json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = self._build_url(path)
        headers = self._headers()
        headers["Idempotency-Key"] = str(uuid.uuid4())
        resp = self.session.post(
            url,
            headers=headers,
            json=json,
            timeout=self.api_timeout,
            verify=self.api_verify_tls
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ok"}

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        url = self._build_url(path)
        resp = self.session.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.api_timeout,
            verify=self.api_verify_tls
        )
        resp.raise_for_status()
        return resp.json()

    def check_health(self) -> Dict[str, Any]:
        if not self.api_enabled:
            return {"status": "disabled"}
        try:
            data = self._get(self.api_health_path, params={})
            return {"status": "ok", "remote": data}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _summarize_decision_with_gemini(self, decision: dict) -> str:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client()
            instruction = (
                "Summarize this moderation decision in 2-3 sentences. "
                "Highlight risk level, top categories, and actions taken. Respond in plain text."
            )
            contents = [instruction, json.dumps(decision, ensure_ascii=False)]
            resp = client.models.generate_content(
                model=os.getenv("AUDIT_GEMINI_MODEL", "gemini-2.5-flash"),
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="text/plain")
            )
            return (getattr(resp, "text", "") or "").strip()[:1000]
        except Exception:
            return ""

 