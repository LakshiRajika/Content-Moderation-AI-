# agents/risk_agent.py
import json
import uuid
import re
from typing import Dict, Any, Optional

class RiskAgent:
    """
    RiskAgent: Calculates numeric risk score and risk level.
    No longer decides actions.
    """

    DEFAULT_THRESHOLDS = {
        "violence": 0.30,
        "hate_speech": 0.40,
        "profanity": 0.50,
        "sexual": 0.40,
        "spam": 0.60,
        "threat": 0.30
    }

    DEFAULT_WEIGHTS = {
        "violence": 0.70,
        "hate_speech": 0.50,
        "profanity": 0.25,
        "sexual": 0.60,
        "spam": 0.20,
        "threat": 0.80
    }

    LEVELS = {"low": 0.30, "medium": 0.70}

    def __init__(self, config_path: Optional[str] = None):
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        self.weights = dict(self.DEFAULT_WEIGHTS)
        self.levels = dict(self.LEVELS)

        if config_path:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.thresholds.update(cfg.get("thresholds", {}))
                self.weights.update(cfg.get("weights", {}))
                self.levels.update(cfg.get("levels", {}))
            except Exception:
                pass

        # Patterns for small text-based boosts
        self._threat_patterns = [
            r"\bkill you\b", r"\bi will kill\b", r"\bi will hurt\b",
            r"\b(i want to die|kill myself|suicide)\b", r"\bmurder\b", r"\brape\b"
        ]
        self._sexual_request_patterns = [
            r"\bsend nudes\b", r"\bsend pics\b", r"\bshow me nude\b", r"\bsend pictures\b"
        ]

    def evaluate(self, classification: Dict[str, Any], text: str = "") -> Dict[str, Any]:
        text_l = (text or "").lower()
        normalized = {k: float(v or 0.0) for k, v in (classification or {}).items()}

        risk_score = 0.0
        reasons = []
        contributions = {}

        for cat, weight in self.weights.items():
            cat_score = normalized.get(cat, 0.0)
            contribution = round(cat_score * weight, 4)
            contributions[cat] = contribution
            threshold = self.thresholds.get(cat, 0.4)
            if cat_score > threshold:
                risk_score += contribution
                reasons.append(f"{cat} > {threshold:.2f} (score {cat_score:.2f})")

        # Text-based boost
        risk_score += self._evaluate_text_features(text_l)
        risk_score = min(risk_score, 1.0)

        level = self._get_level(risk_score)

        return {
            "score": round(risk_score, 4),
            "level": level,
            "reasons": reasons,
            "audit_id": str(uuid.uuid4())[:8],
            "contributions": contributions
        }

    def _evaluate_text_features(self, text_l: str) -> float:
        boost = 0.0
        for patt in self._threat_patterns:
            if re.search(patt, text_l):
                boost += 0.25
                break
        for patt in self._sexual_request_patterns:
            if re.search(patt, text_l):
                boost += 0.20
                break
        if text_l.count("!") > 2:
            boost += 0.05
        if text_l.isupper() and len(text_l) > 10:
            boost += 0.10
        return min(boost, 1.0)

    def _get_level(self, score: float) -> str:
        if score < self.levels.get("low", 0.3):
            return "Low"
        if score < self.levels.get("medium", 0.7):
            return "Medium"
        return "High"
