# agents/risk_agent.py
import json
import re
import uuid
from typing import Dict, Any, Optional

class RiskAgent:
    """
    RiskAgent: convert classifier category scores + text features into:
      - numeric risk score (0.0 - 1.0)
      - risk level: Low / Medium / High
      - reasons / contributions for explainability
      - audit_id
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
        # load optional JSON config if provided (thresholds/weights/levels)
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
                # keep defaults if config unreadable
                pass

        # patterns for text-based boosts
        self._threat_patterns = [
            r"\bkill you\b", r"\bi will kill\b", r"\bi will hurt\b",
            r"\b(i want to die|kill myself|suicide)\b", r"\bmurder\b", r"\brape\b"
        ]
        self._sexual_request_patterns = [
            r"\bsend nudes\b", r"\bsend pics\b", r"\bshow me nude\b", r"\bsend pictures\b"
        ]

    def evaluate(self, classification: Dict[str, Any], text: str = "") -> Dict[str, Any]:
        """
        Evaluate risk given classifier `classification` (dict category->0..1)
        and optional plaintext `text`.
        Returns dict: {
          "score": float,
          "level": "Low"/"Medium"/"High",
          "reasons": [...],
          "contributions": {category: contribution},
          "top_contributors": [{category, contribution, score}],
          "audit_id": str
        }
        """
        text_l = (text or "").lower()

        # Normalize classification values
        normalized = {}
        for k, v in (classification or {}).items():
            try:
                normalized[k] = float(v)
            except Exception:
                normalized[k] = 0.0

        risk_score = 0.0
        contributions = {}
        reasons = []

        # Combine weighted contributions for harmful categories only
        for cat, weight in self.weights.items():
            cat_score = normalized.get(cat, 0.0)
            contribution = round(cat_score * weight, 4)
            contributions[cat] = contribution
            threshold = self.thresholds.get(cat, 0.4)
            if cat_score > threshold:
                risk_score += contribution
                reasons.append(f"{cat} > {threshold:.2f} (score {cat_score:.2f})")

        # Text-based boosts
        text_boost = self._evaluate_text_features(text_l)
        if text_boost > 0:
            risk_score += text_boost
            reasons.append(f"text features boost +{text_boost:.2f}")

        # Keyword overrides / minimum risk for critical phrases
        risk_score = self._apply_keyword_boosts(text_l, risk_score)

        # clamp 0..1
        risk_score = max(0.0, min(1.0, risk_score))

        # risk level
        level = self._get_level(risk_score)

        # top contributors list for explainability
        sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        top_contributors = [
            {"category": k, "contribution": v, "score": normalized.get(k, 0.0)}
            for k, v in sorted_contribs if v > 0
        ]

        return {
            "score": round(risk_score, 4),
            "level": level,
            "reasons": reasons,
            "contributions": contributions,
            "top_contributors": top_contributors,
            "audit_id": str(uuid.uuid4())[:8]
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

    def _apply_keyword_boosts(self, text_l: str, current_score: float) -> float:
        # self-harm phrases => at least 0.85
        if re.search(r"\b(kill myself|want to die|i want to die|suicide)\b", text_l):
            return max(current_score, 0.85)
        # direct threats => at least 0.8
        if re.search(r"\b(i will kill you|i'm going to kill|i will murder|i will hurt you)\b", text_l):
            return max(current_score, 0.80)
        # sexual exploitation requests => at least 0.6
        if re.search(r"\b(send nudes|send pics|show me nude|send pictures)\b", text_l):
            return max(current_score, 0.6)
        return current_score

    def _get_level(self, score: float) -> str:
        if score < self.levels.get("low", 0.3):
            return "Low"
        if score < self.levels.get("medium", 0.7):
            return "Medium"
        return "High"
