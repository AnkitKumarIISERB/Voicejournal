"""
Celery worker configuration.

For local development: uses filesystem broker (no Redis needed, $0).
For production: swap to Redis via the CELERY_BROKER_URL env var.

The ML models are loaded ONCE at worker startup using the worker_process_init
signal. This avoids cold-start latency on every task.
"""

import os
from celery import Celery
from celery.signals import worker_process_init

# Use filesystem broker for local dev (no Redis needed)
# In production, set CELERY_BROKER_URL=redis://...
BROKER_URL = os.environ.get("CELERY_BROKER_URL", "filesystem://")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "file:///tmp/celery-results")

# Create filesystem broker directories if needed
if BROKER_URL == "filesystem://":
    os.makedirs("/tmp/celery-broker/out", exist_ok=True)
    os.makedirs("/tmp/celery-broker/processed", exist_ok=True)
    os.makedirs("/tmp/celery-results", exist_ok=True)

celery_app = Celery(
    "voicejournal",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["app.services.tasks"],
)

# Filesystem broker config
if BROKER_URL == "filesystem://":
    celery_app.conf.broker_transport_options = {
        "data_folder_in": "/tmp/celery-broker/out",
        "data_folder_out": "/tmp/celery-broker/out",
        "data_folder_processed": "/tmp/celery-broker/processed",
    }

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ──────────────────────────────────────────────
# Pre-load ML models at worker startup
# This is a production optimization that avoids
# 5-10s cold start on every task.
# ──────────────────────────────────────────────

_whisper_model = None
_wavlm_model = None
_text_analyzer = None


@worker_process_init.connect
def preload_models(**kwargs):
    """
    Load all ML models once when the Celery worker process starts.
    This signal fires before any tasks are consumed.
    """
    global _whisper_model, _wavlm_model, _text_analyzer

    is_free_tier = os.environ.get("RENDER_FREE_TIER", "false").lower() == "true"
    
    if is_free_tier:
        print("[Worker Init] RENDER_FREE_TIER is true. Skipping heavy PyTorch models (Whisper/WavLM/RoBERTa) to save RAM.")
        return

    import whisper

    print("[Worker Init] Loading Whisper model...")
    _whisper_model = whisper.load_model(
        os.environ.get("WHISPER_MODEL_SIZE", "tiny"),
        device="cpu",
    )
    print("[Worker Init] Whisper loaded ✓")

    # WavLM - only load if a trained checkpoint exists
    checkpoint_path = os.environ.get("WAVLM_CHECKPOINT", "./checkpoints/best_model")
    if os.path.exists(checkpoint_path):
        from ml.models.wavlm_classifier import WavLMEmotionClassifier

        print(f"[Worker Init] Loading WavLM from {checkpoint_path}...")
        _wavlm_model = WavLMEmotionClassifier.load_trained(checkpoint_path, device="cpu")
        print("[Worker Init] WavLM loaded ✓")
    else:
        print(f"[Worker Init] WavLM checkpoint not found at {checkpoint_path}, skipping acoustic analysis")

    # Text sentiment — pre-trained, downloads ~260MB on first run then cached
    from ml.models.sentiment_model import TextSentimentAnalyzer

    print("[Worker Init] Loading text sentiment model...")
    _text_analyzer = TextSentimentAnalyzer(device=-1)  # CPU
    print("[Worker Init] Text sentiment loaded ✓")

    print("[Worker Init] All models ready!")


def get_whisper():
    return _whisper_model


def get_wavlm():
    return _wavlm_model


def get_text_analyzer():
    return _text_analyzer
