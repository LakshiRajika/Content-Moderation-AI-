import os
import json
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ClassifierAgent:
    """
    Agent responsible for classifying content (text or image) across various
    safety and risk categories using the Gemini API.
    """
    
    def __init__(self, model_name: str = 'gemini-2.5-flash'):
        """
        Initializes the ClassifierAgent, setting up the Gemini client.
        
        Args:
            model_name: The Gemini model to use for classification.
        """
        self.model_name = model_name
        self.client = self._initialize_client()
        self.classification_schema = self._define_classification_schema()

    def _initialize_client(self):
        """Initializes the Gemini client, checking for the API key."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        # The client automatically picks up the API key from the environment
        return genai.Client()

    def _define_classification_schema(self):
        """
        Defines the JSON schema for the desired classification output.
        NOTE: Renamed 'harmful_violence' to 'violence' for consistency with Flask app.
        """
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "sexual": types.Schema(
                    type=types.Type.NUMBER,
                    description="Confidence score (0.0 to 1.0) that the content is sexually explicit or suggestive.",
                ),
                "violence": types.Schema(
                    type=types.Type.NUMBER,
                    description="Confidence score (0.0 to 1.0) that the content depicts or encourages physical harm or violence.",
                ),
                "hate_speech": types.Schema(
                    type=types.Type.NUMBER,
                    description="Confidence score (0.0 to 1.0) that the content is hate speech targeting a protected group.",
                ),
                "profanity": types.Schema(
                    type=types.Type.NUMBER,
                    description="Confidence score (0.0 to 1.0) that the content contains strong profanity or vulgar language.",
                ),
                "spam": types.Schema(
                    type=types.Type.NUMBER,
                    description="Confidence score (0.0 to 1.0) that the content is spam or unsolicited advertising.",
                ),
                "threat": types.Schema(
                    type=types.Type.NUMBER,
                    description="Confidence score (0.0 to 1.0) that the content is a direct or indirect threat against a person or group.",
                ),
            },
            required=["sexual", "violence", "hate_speech", "profanity", "spam", "threat"],
        )

    def classify_content(self, content: str | types.Part, content_type: str) -> dict:
        """
        Analyzes the given content and returns a structured classification.

        Args:
            content: The content (text string or types.Part for image) to analyze.
            content_type: 'text' or 'image'

        Returns:
            A dictionary of classification categories and their confidence scores (0.0 to 1.0).
            Returns an error dict if the API call fails.
        """
        
        # --- CORRECTED: System Instruction moved INSIDE the method ---
        system_instruction = (
            "You are a highly conservative content moderation classifier. "
            "Your primary goal is to assign HIGH confidence scores (close to 1.0) "
            "to any content that violates the defined safety categories, even for simple, direct hostility. "
            "Assign a score between 0.0 (not present) and 1.0 (highly present) for each field. "
            
            "CRITICAL GUIDELINES (Score 0.9 or higher if applicable):\n"
            "1. **violence**: Score 1.0 if the content encourages physical harm or injury.\n"
            "2. **hate_speech**: Score 1.0 if the content expresses ANTAGONISM, ANGER, or SEVERE DENIGRATION toward an individual or group. 'I hate you' and similar direct statements of hostility must be scored highly here.\n"
            "3. **threat**: Score 1.0 if the content contains verbal aggression, bullying, or an implied negative consequence.\n"
            
            "Ensure the final output is ONLY a valid JSON object matching the provided schema, with NO other text or explanation."
        )
        # --- END System Instruction ---

        try:
            # Prepare the prompt parts
            prompt_parts = []
            if content_type == 'text':
                # Use the new strong system instruction and the text content
                prompt_parts = [system_instruction, f"Analyze the following text: \"{content}\""]
            else: # Image
                prompt_parts = [system_instruction, content, "Analyze this image and provide a classification score."]

            # Configure the API call for structured JSON output
            config = types.GenerateContentConfig(
                # Removed system_instruction from config as it's now in prompt_parts
                response_mime_type="application/json",
                response_schema=self.classification_schema,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    ),
                ]
            )

            # Generate content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt_parts,
                config=config,
            )
            
            # The response text will be a JSON string conforming to the schema
            classification_data = json.loads(response.text)
            
            # The classification is successful, return the data
            return {
                "status": "success",
                "classification": classification_data,
                "model_output": response.text, # For debugging/auditing
            }

        except APIError as e:
            print(f"Gemini API Error: {e}")
            return {"status": "error", "message": f"Gemini API Error: {e}"}
        except Exception as e:
            print(f"General Error in ClassifierAgent: {e}")
            return {"status": "error", "message": f"Classification failed: {e}"}

# Example Usage (optional, for testing):
if __name__ == '__main__':
    try:
        classifier = ClassifierAgent()
        
        # 1. Text Classification Example (Harmless)
        print("--- Testing harmless text ---")
        harmless_text = "I love watching movies with my friends on the weekend."
        result_harmless = classifier.classify_content(harmless_text, 'text')
        print(json.dumps(result_harmless, indent=2))
        
        print("\n" + "="*50 + "\n")

        # 2. Text Classification Example (Harmful)
        print("--- Testing harmful text ---")
        harmful_text = "I am going to get you, you are a horrible person and should be banned."
        result_harmful = classifier.classify_content(harmful_text, 'text')
        print(json.dumps(result_harmful, indent=2))
        
    except ValueError as e:
        print(f"Setup Error: {e}")