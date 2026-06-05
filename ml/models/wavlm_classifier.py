"""
WavLM-based acoustic emotion classifier.

Uses microsoft/wavlm-base-plus as the feature extractor backbone,
with a classification head fine-tuned on speech emotion data.
This captures HOW someone speaks — tone, pitch, hesitations, flat affect —
which is far more informative for mood/depression detection than text alone.

Trained on your A16 GPU server. Inference runs on CPU for free-tier hosting.
"""

import torch
import torch.nn as nn
from transformers import WavLMModel, AutoFeatureExtractor


# The 8 emotion labels from the RAVDESS dataset (our training data)
EMOTION_LABELS = [
    "neutral",
    "calm",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprised",
]

# Map each emotion to a valence score for mood tracking
EMOTION_VALENCE = {
    "neutral": 0.0,
    "calm": 0.3,
    "happy": 1.0,
    "sad": -1.0,
    "angry": -0.7,
    "fearful": -0.5,
    "disgust": -0.6,
    "surprised": 0.2,
}


class WavLMEmotionClassifier(nn.Module):
    """
    Fine-tunable WavLM model with a classification head for speech emotion recognition.

    Architecture:
        WavLM (frozen or fine-tuned) -> Mean Pooling -> Dropout -> Linear -> ReLU -> Linear -> Softmax

    This is the core ML component of VoiceJournal. It processes raw 16kHz audio
    waveforms and outputs emotion probabilities + a valence score.
    """

    def __init__(
        self,
        model_name: str = "microsoft/wavlm-base-plus",
        num_labels: int = 8,
        freeze_base: bool = True,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.wavlm = WavLMModel.from_pretrained(model_name)
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
        hidden_size = self.wavlm.config.hidden_size  # 768 for base

        if freeze_base:
            for param in self.wavlm.parameters():
                param.requires_grad = False

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
            nn.Linear(256, num_labels),
        )

        self.num_labels = num_labels

    def forward(self, input_values: torch.Tensor, attention_mask: torch.Tensor = None) -> torch.Tensor:
        """
        Forward pass.

        Args:
            input_values: Raw waveform tensor [batch, seq_len] at 16kHz.
            attention_mask: Optional mask for padded sequences.

        Returns:
            Logits tensor of shape [batch, num_labels].
        """
        outputs = self.wavlm(input_values=input_values, attention_mask=attention_mask)
        hidden_states = outputs.last_hidden_state  # [batch, seq, 768]

        # Mean pooling over the time dimension
        if attention_mask is not None:
            mask = attention_mask.unsqueeze(-1).expand_as(hidden_states).float()
            pooled = (hidden_states * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        else:
            pooled = hidden_states.mean(dim=1)

        logits = self.classifier(pooled)
        return logits

    @torch.no_grad()
    def predict_from_file(self, audio_path: str, device: str = "cpu") -> dict:
        """
        Run inference on a single audio file. Used by the Celery worker in production.

        Args:
            audio_path: Path to a .wav file (will be resampled to 16kHz).

        Returns:
            {
                "dominant_emotion": "sad",
                "confidence": 0.91,
                "all_scores": {"neutral": 0.02, "calm": 0.01, ...},
                "valence": -1.0,
                "arousal": 0.3
            }
        """
        import librosa

        self.eval()
        self.to(device)

        # Load and resample to 16kHz (WavLM requirement)
        waveform, sr = librosa.load(audio_path, sr=16000, mono=True)

        inputs = self.feature_extractor(
            waveform,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True,
        )
        input_values = inputs["input_values"].to(device)

        logits = self.forward(input_values)
        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()

        scores = {EMOTION_LABELS[i]: round(float(probs[i]), 4) for i in range(len(EMOTION_LABELS))}
        dominant = max(scores, key=scores.get)

        return {
            "dominant_emotion": dominant,
            "confidence": round(float(scores[dominant]), 4),
            "all_scores": scores,
            "valence": EMOTION_VALENCE.get(dominant, 0.0),
        }

    @classmethod
    def load_trained(cls, checkpoint_path: str, device: str = "cpu") -> "WavLMEmotionClassifier":
        """Load a trained model from a checkpoint directory."""
        model = cls(freeze_base=True)
        state_dict = torch.load(
            f"{checkpoint_path}/wavlm_emotion_classifier.pt",
            map_location=device,
            weights_only=True,
        )
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        return model
