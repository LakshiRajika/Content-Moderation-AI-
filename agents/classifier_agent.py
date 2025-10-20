# agents/classifier_agent.py
import os
import json
import re
from typing import Union, Dict, Any
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

load_dotenv()

class ClassifierAgent:
    """
    ClassifierAgent - uses Google Gemini (genai client) to produce a structured
    classification for content. This version:
      - Uses a neutral / explicit instruction for JSON output
      - Parses and validates the returned JSON
      - Clamps scores to [0.0, 1.0]
      - Applies light rule-based boosts/overrides for clear, short phrases
      - Applies a defensive normalization if the model output looks malformed
    """

    DEFAULT_MODEL = "gemini-2.5-flash"

    # Simple rule lists for robust fallback/boosts
    _threat_patterns = [
        r"\bi will kill you\b", r"\bi will kill\b", r"\bkill you\b",
        r"\bi'm going to kill\b", r"\bi am going to kill\b", r"\bi will hurt you\b"
    ]
    _hate_patterns = [
        r"\bi hate you\b", r"\bi hate\b", r"\byou are (stupid|idiot|retard)\b", r"\bfuck you\b"
    ]
    _sexual_request_patterns = [
        r"\bsend nudes\b", r"\bsend pics\b", r"\bshow me nude\b", r"\bsend pictures\b",
        r"\bwant to see your (body|nudes|pics)\b"
    ]
    _spam_patterns = [
        r"\bfree\b", r"\bclick here\b", r"\bbuy now\b", r"\bsubscribe\b", r"\bwin\b", r"\bprize\b"
    ]

    def __init__(self, model_name: str = None):
        self.model_name = model_name or self.DEFAULT_MODEL
        # Initialize client (client reads GEMINI_API_KEY from env)
        api_key = os.getenv("GEMINI_API_KEY")
        self.demo_mode = False
        if not api_key:
            # Enable demo mode so app can run without external API
            self.demo_mode = True
            self.client = None
        else:
            self.client = genai.Client()

        # Schema keys used by the rest of the app (keep consistent with UI)
        self.expected_keys = [
            "sexual",
            "violence",
            "hate_speech",
            "profanity",
            "spam",
            "threat"
        ]

    def _build_prompt(self, text: str) -> list:
        """
        Returns contents (list) to send to genai.models.generate_content.
        We send the instruction + the text to classify as two content parts.
        """
        instruction = (
            "You are a content moderation classifier. For the input text, produce a JSON object "
            "with numeric confidence scores between 0.0 and 1.0 for the following keys: "
            f"{', '.join(self.expected_keys)}. "
            "Return ONLY valid JSON and nothing else. Example:\n"
            '{ "sexual": 0.0, "violence": 0.0, "hate_speech": 0.0, "profanity": 0.0, "spam": 0.0, "threat": 0.0 }\n'
            "Round scores to two decimal places where possible."
        )
        return [instruction, f"Text to analyze: \"{text}\""]

    def classify_content(self, content: Union[str, types.Part], content_type: str = "text") -> Dict[str, Any]:
        """
        Main entrypoint.
        - content: text string or types.Part for images
        - content_type: 'text' or 'image'
        Returns:
          {"status": "success", "classification": {...}, "model_output": "<raw text>"} on success
          {"status": "error", "message": "..."} on failure
        """
        if content_type not in ("text", "image"):
            return {"status": "error", "message": f"Unsupported content_type: {content_type}"}

        # For images: include a short instruction and the Part
        contents = None
        if content_type == "text":
            contents = self._build_prompt(content)
        else:
            # For images, prompt + image part
            contents = [
                "You are a content moderation classifier. For the attached image, return JSON with numeric scores for the keys: "
                f"{', '.join(self.expected_keys)}. Return ONLY valid JSON."
            , content, "Return the JSON now."]

        # Prepare response schema -- optional but helpful when using types.GenerateContentConfig
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        except Exception:
            # If types.GenerateContentConfig not available or raising, proceed without
            config = None

        try:
            # If demo mode, return heuristic, deterministic JSON without external calls
            if getattr(self, "demo_mode", False):
                raw_text = json.dumps(self._demo_classify(content if isinstance(content, str) else ""))
            else:
                # Call the model
                if config:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=config
                    )
                    raw_text = getattr(response, "text", "") or str(response)
                else:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents
                    )
                    raw_text = getattr(response, "text", "") or str(response)

            # Defensive extract: sometimes the model adds commentary before/after JSON
            text = raw_text.strip()
            # Find first '{' and last '}' to try to isolate JSON
            if "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}")
                json_text = text[start:end+1]
            else:
                # No JSON-looking content -> fail
                json_text = text

            # Parse JSON
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError:
                # If direct parse fails, attempt line-by-line extraction for key: value pairs
                parsed = self._loose_parse_kv(json_text)

            # Normalize parsed dict to expected keys
            classification = {}
            for k in self.expected_keys:
                v = parsed.get(k) if isinstance(parsed, dict) else None
                classification[k] = self._to_float_safe(v)

            # Clamp 0..1
            for k in classification:
                classification[k] = max(0.0, min(1.0, float(classification[k])))

            # Defensive postprocessing:
            classification = self._defensive_postprocess(classification, content if isinstance(content, str) else "")

            return {
                "status": "success",
                "classification": classification,
                "model_output": raw_text
            }

        except APIError as e:
            return {"status": "error", "message": f"Gemini API error: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"Classification failed: {e}"}

    def _demo_classify(self, text: str) -> Dict[str, float]:
        """Lightweight local heuristic for demo mode without external API."""
        text_l = (text or "").lower()
        scores = {k: 0.0 for k in self.expected_keys}

        # Simple keyword heuristics
        if any(p in text_l for p in ["kill", "hurt", "attack", "murder", "rape"]):
            scores["violence"] = max(scores["violence"], 0.6)
        if any(p in text_l for p in ["i will kill", "i will hurt", "threaten", "bomb"]):
            scores["threat"] = max(scores["threat"], 0.7)
        if any(p in text_l for p in ["fuck", "shit", "bitch", "asshole"]):
            scores["profanity"] = max(scores["profanity"], 0.6)
        if any(p in text_l for p in ["send nudes", "nude", "sex", "porn"]):
            scores["sexual"] = max(scores["sexual"], 0.7)
        if any(p in text_l for p in ["free", "click here", "buy now", "win prize", "subscribe"]):
            scores["spam"] = max(scores["spam"], 0.6)
        if any(p in text_l for p in ["idiot", "retard", "hate you", "stupid"]):
            scores["hate_speech"] = max(scores["hate_speech"], 0.6)

        # Slight boost for excessive exclamations or ALL CAPS
        if text_l.count("!") > 3:
            scores["profanity"] = max(scores["profanity"], 0.5)
        if text and text.isupper() and len(text) > 8:
            scores["hate_speech"] = max(scores["hate_speech"], 0.5)

        # Clamp and round
        for k in scores:
            scores[k] = round(max(0.0, min(1.0, float(scores[k]))), 2)
        return scores

    def _to_float_safe(self, v) -> float:
        """Convert various model outputs to float safely."""
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove trailing '%' if present
            s = v.strip()
            if s.endswith("%"):
                try:
                    return float(s[:-1]) / 100.0
                except Exception:
                    pass
            # try parse as float
            try:
                return float(s)
            except Exception:
                # sometimes model gives '0.00' with weird chars
                digits = re.findall(r"[-+]?\d*\.\d+|\d+", s)
                if digits:
                    try:
                        return float(digits[0])
                    except Exception:
                        return 0.0
        return 0.0

    def _loose_parse_kv(self, text: str) -> Dict[str, float]:
        """
        Tries a lenient parse of lines like 'hate_speech: 0.12' to recover numbers
        if JSON parse fails.
        """
        result = {}
        # remove braces and quotes to simplify
        clean = text.replace("{", " ").replace("}", " ").replace('"', "").replace("'", "")
        for part in re.split(r"[\n,;]+", clean):
            if ":" in part:
                k, v = part.split(":", 1)
                key = k.strip()
                val = v.strip()
                result[key] = self._to_float_safe(val)
        return result

    def _defensive_postprocess(self, classification: Dict[str, float], text: str) -> Dict[str, float]:
        """
        - Apply small rule-based boosts for explicit short phrases
        - Detect obviously malformed outputs (e.g., lots of 1.0s) and normalize
        """
        text_l = (text or "").lower()

        # Apply rule-based small overrides (only increase, never decrease model score)
        # Threats
        for patt in self._threat_patterns:
            if re.search(patt, text_l):
                classification["threat"] = max(classification.get("threat", 0.0), 0.9)
                classification["violence"] = max(classification.get("violence", 0.0), 0.7)
                break

        # Hate
        for patt in self._hate_patterns:
            if re.search(patt, text_l):
                classification["hate_speech"] = max(classification.get("hate_speech", 0.0), 0.8)
                break

        # Sexual requests
        for patt in self._sexual_request_patterns:
            if re.search(patt, text_l):
                classification["sexual"] = max(classification.get("sexual", 0.0), 0.8)
                break

        # Spam patterns
        for patt in self._spam_patterns:
            if re.search(patt, text_l):
                classification["spam"] = max(classification.get("spam", 0.0), 0.6)
                break

        # Defensive normalization:
        # If many categories have extremely high scores (>= 0.98), assume the model
        # returned degenerate values and rescale proportionally so top score remains <= 0.98.
        high_count = sum(1 for v in classification.values() if v >= 0.98)
        if high_count >= 3:
            s = sum(classification.values())
            if s > 0:
                # scale down proportionally to keep values sensible while preserving ratios
                for k in classification:
                    classification[k] = round(classification[k] / s, 4)

        # Final clamp & round
        for k in classification:
            classification[k] = round(max(0.0, min(1.0, float(classification[k]))), 4)

        return classification
