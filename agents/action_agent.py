from typing import Dict, List, Any

class ActionAgent:
    """
    ActionAgent: Determines moderation actions based on risk assessment.
    Converts risk scores, category contributions, and explanations
    into user-friendly actions, recommended policies, and reasons for display.
    """

    ACTION_MAP = {
        "High": {
            "sexual": ["Block content", "Ban user"],
            "threat": ["Block content", "Ban user"],
            "violence": ["Block content", "Ban user"],
            "hate_speech": ["Block content", "Ban user"],
            "profanity": ["Flag for human review"],
            "spam": ["Auto-delete content"]
        },
        "Medium": {
            "sexual": ["Flag for human review", "Shadow-ban user"],
            "threat": ["Flag for human review", "Shadow-ban user"],
            "violence": ["Flag for human review"],
            "hate_speech": ["Flag for human review"],
            "profanity": ["Warn user"],
            "spam": ["Warn user", "Auto-delete content"]
        },
        "Low": {
            "sexual": ["No action required"],
            "threat": ["No action required"],
            "violence": ["No action required"],
            "hate_speech": ["No action required"],
            "profanity": ["No action required"],
            "spam": ["No action required"]
        }
    }

    CATEGORY_EXPLANATIONS = {
        "sexual": "This content includes sexual requests or explicit material.",
        "threat": "This content contains threats or harmful intent.",
        "violence": "This content promotes violence or harm.",
        "hate_speech": "This content contains hateful language.",
        "profanity": "This content includes strong or offensive language.",
        "spam": "This content appears to be spam or promotional."
    }

    CATEGORY_POLICIES = {
        "sexual": ["Do not allow sexual requests or explicit content."],
        "threat": ["Threatening content must be blocked and reported."],
        "violence": ["Violence-promoting content must be blocked immediately."],
        "hate_speech": ["Hateful or discriminatory content must be blocked."],
        "profanity": ["Offensive language should be flagged for review."],
        "spam": ["Spam content should be removed automatically or warned."]
    }

    CATEGORY_THRESHOLDS = {
        "sexual": 0.6,
        "threat": 0.5,
        "violence": 0.5,
        "hate_speech": 0.5,
        "profanity": 0.7,
        "spam": 0.6
    }

    def __init__(self):
        pass

    def get_policy(self, category: str) -> List[str]:
        """Return platform policy for the category."""
        return self.CATEGORY_POLICIES.get(category, ["Follow platform moderation rules."])

    def determine_actions(self, risk_result: Dict[str, Any], classification: Dict[str, float]) -> Dict[str, Any]:
        selected_actions = set()
        policy_texts = set()
        friendly_reasons = []

        risk_level = risk_result.get("level", "Low")
        reasons = risk_result.get("reasons", [])
        contributions = risk_result.get("top_contributors", [])

        # Process each contributor
        for contrib in contributions:
            category = contrib.get("category")
            score = contrib.get("score", 0.0)
            threshold = self.CATEGORY_THRESHOLDS.get(category, 0.5)
            if score >= threshold:
                # Actions
                selected_actions.update(self.ACTION_MAP.get(risk_level, {}).get(category, []))
                # Policies
                for pol in self.get_policy(category):
                    policy_texts.add(pol)
                # Friendly explanation
                explanation = self.CATEGORY_EXPLANATIONS.get(category)
                if explanation:
                    friendly_reasons.append(explanation)

        # Escalate if multiple high-risk categories
        high_risk_count = len([c for c in contributions if c.get("score",0) >= 0.5])
        if high_risk_count > 1:
            selected_actions.add("Flag for human review")

        # Fallback if no high-contributors
        if not selected_actions:
            for acts in self.ACTION_MAP.get(risk_level, {}).values():
                selected_actions.update(acts)
            friendly_reasons = [self._simplify_reason(r) for r in reasons] if reasons else ["No issues detected."]

        banner_message = " ⚠️ ".join(friendly_reasons)

        return {
            "actions": list(selected_actions),
            "banner_message": banner_message,
            "policies": list(policy_texts)
        }

    def _simplify_reason(self, reason: str) -> str:
        reason = reason.lower()
        if "sexual" in reason: return "This content may contain sexual material."
        if "threat" in reason: return "This content may contain threatening language."
        if "violence" in reason: return "This content may promote violence."
        if "hate_speech" in reason or "hate" in reason: return "This content may contain hateful language."
        if "profanity" in reason: return "This content contains offensive language."
        if "spam" in reason: return "This content may be spam."
        return "This content may violate platform rules."
