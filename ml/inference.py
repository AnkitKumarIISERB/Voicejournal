"""
Multimodal Inference Pipeline for VoiceJournal.

Combines:
  1. Whisper (free, local) — transcribes audio to text
  2. WavLM Emotion Classifier (your trained model) — analyzes vocal tone
  3. Text Sentiment Model (pre-trained, no training needed) — analyzes word meaning

The final mood score is a weighted combination of acoustic and text signals.
This is what the Celery worker calls in production.
"""

import os
import torch
import whisper
from typing import Dict, Any, Optional
from pathlib import Path

from ml.models.wavlm_classifier import WavLMEmotionClassifier
from ml.models.sentiment_model import TextSentimentAnalyzer


class VoiceJournalAnalyzer:
    """
    The main inference class used by the backend.

    Combines acoustic emotion recognition (WavLM) with text sentiment analysis
    to produce a comprehensive mood assessment from a voice recording.

    All models run locally. Zero API costs.
    """

    def __init__(
        self,
        wavlm_checkpoint: str,
        whisper_model: str = "small",
        device: str = "cpu",
        acoustic_weight: float = 0.6,
        text_weight: float = 0.4,
    ):
        """
        Args:
            wavlm_checkpoint: Path to your trained WavLM model directory.
            whisper_model: Whisper model size. Use "tiny" or "base" for free-tier servers.
            device: "cpu" for free-tier hosting, "cuda" if GPU available.
            acoustic_weight: Weight for acoustic emotion in combined score (default 0.6).
            text_weight: Weight for text sentiment in combined score (default 0.4).
        """
        self.device = device
        self.acoustic_weight = acoustic_weight
        self.text_weight = text_weight

        print(f"[VoiceJournalAnalyzer] Loading models on {device}...")

        # 1. Whisper for transcription (free, runs locally)
        print(f"  Loading Whisper ({whisper_model})...")
        self.whisper = whisper.load_model(whisper_model, device=device)

        # 2. WavLM for acoustic emotion (your trained model)
        print(f"  Loading WavLM from {wavlm_checkpoint}...")
        self.wavlm = WavLMEmotionClassifier.load_trained(wavlm_checkpoint, device=device)

        # 3. Text sentiment (pre-trained, zero training needed)
        print(f"  Loading text sentiment model...")
        self.text_analyzer = TextSentimentAnalyzer(device=0 if device == "cuda" else -1)

        print("[VoiceJournalAnalyzer] All models loaded ✓")

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Full analysis pipeline for a single voice journal entry.

        Args:
            audio_path: Path to the audio file (.wav, .mp3, .m4a, etc.)

        Returns:
            {
                "transcript": "I had a really rough day today...",
                "acoustic_analysis": {
                    "dominant_emotion": "sad",
                    "confidence": 0.91,
                    "all_scores": {...},
                    "valence": -1.0,
                },
                "text_analysis": {
                    "dominant_emotion": "sadness",
                    "confidence": 0.87,
                    "all_scores": {...},
                    "valence": -0.74,
                },
                "combined": {
                    "valence": -0.90,
                    "dominant_emotion": "sad",
                    "confidence": 0.89,
                    "mood_label": "low",
                }
            }
        """
        result = {}

        # Step 1: Transcribe with Whisper (Translate to English automatically)
        whisper_result = self.whisper.transcribe(audio_path, task="translate")
        transcript = whisper_result["text"].strip()
        result["transcript"] = transcript

        # Step 2: Acoustic emotion via WavLM
        acoustic = self.wavlm.predict_from_file(audio_path, device=self.device)
        result["acoustic_analysis"] = acoustic

        # Step 3: Text sentiment
        text = self.text_analyzer.predict(transcript)
        result["text_analysis"] = text

        # Step 4: Combine scores
        combined_valence = (
            self.acoustic_weight * acoustic["valence"]
            + self.text_weight * text["valence"]
        )
        combined_valence = max(-1.0, min(1.0, combined_valence))

        # Pick dominant emotion from the higher-confidence model
        if acoustic["confidence"] >= text["confidence"]:
            dominant = acoustic["dominant_emotion"]
            confidence = acoustic["confidence"]
        else:
            dominant = text["dominant_emotion"]
            confidence = text["confidence"]

        # Map valence to human-readable mood label
        if combined_valence >= 0.5:
            mood_label = "great"
        elif combined_valence >= 0.1:
            mood_label = "good"
        elif combined_valence >= -0.1:
            mood_label = "neutral"
        elif combined_valence >= -0.5:
            mood_label = "low"
        else:
            mood_label = "very_low"

        result["combined"] = {
            "valence": round(combined_valence, 4),
            "dominant_emotion": dominant,
            "confidence": round(confidence, 4),
            "mood_label": mood_label,
        }

        return result
