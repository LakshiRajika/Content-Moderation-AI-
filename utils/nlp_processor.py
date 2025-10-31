# utils/nlp_processor.py
import re
from collections import defaultdict

class NLPProcessor:
    def __init__(self):
        # Simple rule-based entity extraction (fallback without spaCy)
        self.entity_patterns = {
            "persons": [
                r'\b(?:Mr|Ms|Mrs|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
                r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
            ],
            "organizations": [
                r'\b(?:Inc|LLC|Corp|Corporation|Company|Ltd|Limited)\b',
                r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\s+(?:Company|Corp|Inc|LLC)\b'
            ],
            "locations": [
                r'\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)\b',
                r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\s*(?:City|Town|Village)\b',
                r'\b(?:New|Los|San|Las)\s+[A-Z][a-zA-Z]+\b'
            ]
        }
    
    def extract_entities(self, text: str) -> dict:
        """Extract named entities using rule-based patterns"""
        entities = {
            "persons": [],
            "organizations": [], 
            "locations": [],
            "other": []
        }
        
        # Email detection
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if emails:
            entities["other"].extend([f"Email: {email}" for email in emails])
        
        # URL detection
        urls = re.findall(r'https?://[^\s]+|www\.[^\s]+', text)
        if urls:
            entities["other"].extend([f"URL: {url}" for url in urls])
        
        # Phone numbers
        phones = re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text)
        if phones:
            entities["other"].extend([f"Phone: {phone}" for phone in phones])
        
        # Rule-based entity extraction
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if match not in entities[entity_type]:
                        entities[entity_type].append(match)
        
        # Simple person name detection (capitalized words in sequence)
        potential_names = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text)
        for name in potential_names:
            if name not in entities["persons"] and len(name.split()) == 2:
                entities["persons"].append(name)
        
        # Clean up empty categories
        for category in list(entities.keys()):
            if not entities[category]:
                del entities[category]
        
        return entities
    
    def summarize_content(self, text: str, max_sentences: int = 2) -> str:
        """Generate a simple content summary using sentence extraction"""
        if not text or len(text.strip()) == 0:
            return "No content to summarize."
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= max_sentences:
            return text
        
        # Simple algorithm: take first and last sentences
        summary_sentences = []
        if sentences:
            summary_sentences.append(sentences[0])  # First sentence
        if len(sentences) > 1:
            summary_sentences.append(sentences[-1])  # Last sentence
        
        return ". ".join(summary_sentences) + "."
    
    def analyze_sentiment(self, text: str) -> dict:
        """Simple sentiment analysis using keyword matching"""
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'like']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'hate', 'dislike', 'angry', 'mad']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "positive_words": positive_count,
            "negative_words": negative_count,
            "score": (positive_count - negative_count) / max(len(text.split()), 1)
        }