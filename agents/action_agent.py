from typing import Dict, List, Any

class ActionAgent:
    """
    ActionAgent: Determines moderation actions based on risk assessment.
    Converts risk scores, category contributions, and explanations
    into user-friendly actions, recommended policies, and reasons for display.
    """

    ACTION_MAP = {
        "High": {
            "sexual": ["Block content", "Ban user", "Flag for human review"],
            "threat": ["Block content", "Ban user", "Flag for human review"],
            "violence": ["Block content", "Ban user", "Flag for human review"],
            "hate_speech": ["Block content", "Ban user", "Flag for human review"],
            "profanity": ["Block content", "Flag for human review"],
            "spam": ["Auto-delete content", "Flag for human review"]
        },
        "Medium": {
            "sexual": ["Flag for human review"],
            "threat": ["Flag for human review"],
            "violence": ["Flag for human review"],
            "hate_speech": ["Flag for human review"],
            "profanity": ["Warn user", "Flag for human review"],
            "spam": ["Warn user", "Flag for human review"]
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
        "profanity": 0.6,  # INCREASED from 0.4 to 0.6
        "spam": 0.6
    }

    def __init__(self):
        pass

    def get_policy(self, category: str) -> List[str]:
        """Return platform policy for the category."""
        return self.CATEGORY_POLICIES.get(category, ["Follow platform moderation rules."])

    def determine_actions(self, risk_result: Dict[str, Any], classification: Dict[str, float], nlp_analysis: Dict[str, Any] | None = None) -> Dict[str, Any]:
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
                # Get actions for this risk level and category
                category_actions = self.ACTION_MAP.get(risk_level, {}).get(category, [])
                selected_actions.update(category_actions)
                
                # Policies
                for pol in self.get_policy(category):
                    policy_texts.add(pol)
                
                # Friendly explanation
                explanation = self.CATEGORY_EXPLANATIONS.get(category)
                if explanation:
                    friendly_reasons.append(explanation)

        # IMPROVED LOGIC: More proportional actions
        if risk_level == "High":
            selected_actions.add("Flag for human review")
            selected_actions.add("Block content")  # Auto-block only High risk
        elif risk_level == "Medium":
            selected_actions.add("Flag for human review")  # Just flag for review
            # Don't auto-block Medium risk

        # Fallback if no actions selected
        if not selected_actions:
            selected_actions.add("No action required")
            friendly_reasons = ["No safety issues detected"]

        # IMPROVED BANNER MESSAGES
        if risk_level == "High":
            banner_message = "Content violates safety guidelines - review required"
        elif risk_level == "Medium":
            banner_message = "Content may need review - check for context"
        else:
            banner_message = "Content appears safe"

        # Override with specific reasons if available
        if friendly_reasons:
            banner_message = " ⚠️ ".join(friendly_reasons)

        # Detailed multi-sentence explanation including NLP analysis
        explanation = self._build_explanation(
            risk_level=risk_level,
            reasons=reasons,
            selected_actions=list(selected_actions),
            nlp_analysis=nlp_analysis or {},
            classification=classification,
            top_contributors=contributions
        )

        return {
            "actions": list(selected_actions),
            "banner_message": banner_message,
            "policies": list(policy_texts),
            "explanation": explanation
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

    def _build_explanation(
        self,
        *,
        risk_level: str,
        reasons: List[str],
        selected_actions: List[str],
        nlp_analysis: Dict[str, Any],
        classification: Dict[str, float],
        top_contributors: List[Dict[str, Any]]
    ) -> str:
        # Sentence 1: Overview with risk level
        sentence1 = f"This content is assessed as {risk_level} risk based on aggregated category scores and heuristics."

        # Sentence 2: Top contributors
        if isinstance(top_contributors, list) and top_contributors:
            top_parts = []
            for c in top_contributors[:3]:
                cat = c.get("category", "unknown")
                score = c.get("score", 0.0)
                top_parts.append(f"{cat} ({score:.2f})")
            sentence2 = "Top contributing factors include " + ", ".join(top_parts) + "."
        else:
            # Fallback: infer from classification
            top_items = sorted(
                ((k, v) for k, v in classification.items() if k != "normal"),
                key=lambda kv: kv[1], reverse=True
            )[:3]
            if top_items:
                sentence2 = "Top contributing factors include " + ", ".join([f"{k} ({v:.2f})" for k, v in top_items]) + "."
            else:
                sentence2 = "No specific harmful categories were prominent."

        # Sentence 3: NLP analysis summary/entities
        summary_text = ""
        if isinstance(nlp_analysis, dict):
            summary = nlp_analysis.get("summary")
            entities = nlp_analysis.get("entities") or []
            ent_text = ", ".join([e.get("text", str(e)) if isinstance(e, dict) else str(e) for e in entities[:4]])
            if summary and ent_text:
                summary_text = f"NLP analysis notes: {summary} Key entities: {ent_text}."
            elif summary:
                summary_text = f"NLP analysis notes: {summary}"
            elif ent_text:
                summary_text = f"Detected entities include: {ent_text}."
        if not summary_text:
            summary_text = "NLP analysis did not surface additional notable context."

        # Sentence 4: Actions and rationale
        if selected_actions:
            actions_text = ", ".join(selected_actions)
            sentence4 = f"Recommended actions: {actions_text}. These are aligned with platform safety policies for the detected risk profile."
        else:
            sentence4 = "No immediate action is recommended given the current signal strengths."

        # Final concise explanation (avoid repeating simplified reasons already reflected in banner)
        return " ".join([s for s in [sentence1, sentence2, summary_text, sentence4] if s])