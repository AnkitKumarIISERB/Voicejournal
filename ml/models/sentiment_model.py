"""
Text-based sentiment analysis using a pre-trained transformer pipeline.
No fine-tuning needed — we use this as a complementary signal alongside
the acoustic WavLM model. Zero cost, zero training required.
"""

from transformers import pipeline
from typing import Dict, Any


class TextSentimentAnalyzer:
    """
    Uses a pre-trained sentiment/emotion model from HuggingFace.
    Runs entirely offline after the first download (~260MB).
    """

    LABEL_MAP = {
        "sadness": "sad",
        "joy": "happy",
        "love": "happy",
        "anger": "angry",
        "fear": "fearful",
        "surprise": "surprised",
    }

    def __init__(self, model_name: str = "j-hartmann/emotion-english-distilroberta-base", device: int = -1):
        """
        Args:
            model_name: A pre-trained emotion classification model from HuggingFace Hub.
                        Default is a well-known model trained on 6 emotions + neutral.
            device: -1 for CPU, 0+ for GPU index.
        """
        self.pipe = pipeline(
            "text-classification",
            model=model_name,
            top_k=None,  # Return all label scores
            device=device,
        )

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Predict emotion distribution from text.

        Returns:
            {
                "dominant_emotion": "sad",
                "confidence": 0.87,
                "all_scores": {"sad": 0.87, "angry": 0.05, ...},
                "valence": -0.74  # Computed: negative emotions = negative valence
            }
        """
        if not text or not text.strip():
            return {
                "dominant_emotion": "neutral",
                "confidence": 1.0,
                "all_scores": {"neutral": 1.0},
                "valence": 0.0,
            }

        results = self.pipe(text)[0]  # List of {label, score} dicts
        scores = {r["label"]: round(r["score"], 4) for r in results}

        dominant = max(scores, key=scores.get)
        confidence = scores[dominant]

        # Compute valence: positive emotions -> +1, negative -> -1
        valence_weights = {
            "joy": 1.0,
            "love": 0.8,
            "surprise": 0.3,
            "neutral": 0.0,
            "fear": -0.5,
            "anger": -0.7,
            "disgust": -0.6,
            "sadness": -1.0,
        }
        valence = sum(scores.get(k, 0) * v for k, v in valence_weights.items())
        valence = max(-1.0, min(1.0, valence))  # Clamp

        return {
            "dominant_emotion": dominant,
            "confidence": round(confidence, 4),
            "all_scores": scores,
            "valence": round(valence, 4),
        }
