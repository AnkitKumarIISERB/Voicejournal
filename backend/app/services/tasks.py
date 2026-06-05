"""
Celery background tasks for audio processing.

Task 1: transcribe_audio  — Whisper transcription (runs locally, $0)
Task 2: analyze_mood      — WavLM acoustic + text sentiment analysis
Task 3: process_journal   — Orchestrates both tasks sequentially

These tasks are triggered when a user uploads an audio file.
Results are written directly to the database.
"""

import os
import tempfile
from app.services.celery_app import celery_app, get_whisper, get_wavlm, get_text_analyzer
from app.services.storage import load_audio
from app.db.session import SessionLocal
from app.db.base import Base  # Import all models to resolve SQLAlchemy string references
from app.models.journal import JournalEntry
from app.services.dsp import extract_acoustic_features
from pathlib import Path


@celery_app.task(bind=True, name="tasks.process_journal", max_retries=3)
def process_journal(self, entry_id: int):
    """
    Main orchestrator task. Called when a new audio file is uploaded.

    Pipeline:
        1. Decrypt audio from storage
        2. Transcribe with Whisper
        3. Analyze acoustic emotion with WavLM
        4. Analyze text sentiment from transcript
        5. Combine scores and save to database
    """
    db = SessionLocal()
    tmp_path = None

    try:
        entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not entry:
            print(f"[Task] Entry {entry_id} not found, skipping")
            return {"status": "error", "detail": "Entry not found"}

        # Step 1: Decrypt audio to a temp file
        audio_bytes = load_audio(entry.audio_s3_key)
        ext = Path(entry.audio_s3_key).suffix or ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(audio_bytes)
        tmp.close()
        tmp_path = tmp.name

        # Step 2: Transcribe with Whisper
        whisper_model = get_whisper()
        transcript = ""
        if whisper_model:
            print(f"[Task] Transcribing entry {entry_id}...")
            result = whisper_model.transcribe(tmp_path)
            transcript = result["text"].strip()
            entry.transcript = transcript
            print(f"[Task] Transcript: {transcript[:100]}...")
        else:
            print("[Task] Whisper not loaded, skipping transcription")

        # Step 3: Acoustic emotion via WavLM
        acoustic_valence = 0.0
        acoustic_emotion = "neutral"
        acoustic_confidence = 0.0

        wavlm_model = get_wavlm()
        if wavlm_model:
            print(f"[Task] Running WavLM acoustic analysis...")
            acoustic_result = wavlm_model.predict_from_file(tmp_path, device="cpu")
            acoustic_valence = acoustic_result["valence"]
            acoustic_emotion = acoustic_result["dominant_emotion"]
            acoustic_confidence = acoustic_result["confidence"]
            print(f"[Task] Acoustic: {acoustic_emotion} (valence={acoustic_valence}, conf={acoustic_confidence})")
        else:
            print("[Task] WavLM not loaded, skipping acoustic analysis")

        # Step 4: Text sentiment
        text_valence = 0.0
        text_emotion = "neutral"
        text_confidence = 0.0

        text_analyzer = get_text_analyzer()
        if text_analyzer and transcript:
            print(f"[Task] Running text sentiment analysis...")
            text_result = text_analyzer.predict(transcript)
            text_valence = text_result["valence"]
            text_emotion = text_result["dominant_emotion"]
            text_confidence = text_result["confidence"]
            print(f"[Task] Text: {text_emotion} (valence={text_valence}, conf={text_confidence})")

        # Step 5: Combine scores (60% acoustic, 40% text)
        if wavlm_model and text_analyzer and transcript:
            combined_valence = 0.6 * acoustic_valence + 0.4 * text_valence
            # Pick emotion from the higher-confidence model
            if acoustic_confidence >= text_confidence:
                combined_emotion = acoustic_emotion
            else:
                combined_emotion = text_emotion
        elif wavlm_model:
            combined_valence = acoustic_valence
            combined_emotion = acoustic_emotion
        elif text_analyzer and transcript:
            combined_valence = text_valence
            combined_emotion = text_emotion
        else:
            combined_valence = 0.0
            combined_emotion = "neutral"

        # Clamp valence to [-1, 1]
        combined_valence = max(-1.0, min(1.0, combined_valence))

        # Step 5.5: Deterministic Acoustic Feature Extraction (Clinical Explanability)
        print(f"[Task] Extracting clinical DSP features...")
        dsp_features = extract_acoustic_features(tmp_path)
        entry.speech_rate = dsp_features["speech_rate"]
        entry.pitch_variance = dsp_features["pitch_variance"]
        entry.energy_variance = dsp_features["energy_variance"]

        # Save to database
        entry.valence_score = round(combined_valence, 4)
        entry.emotion_label = combined_emotion
        entry.arousal_score = round(acoustic_confidence, 4)  # Reuse as confidence metric
        entry.dominance_score = round(text_confidence, 4)

        db.commit()
        db.refresh(entry)

        # Step 6: Risk Alert Logic
        # Check the last 3 entries for this user. If all 3 have valence < 0.3, flag it.
        # Also flag if pitch variance is extraordinarily low (flat affect threshold)
        recent_entries = db.query(JournalEntry).filter(
            JournalEntry.user_id == entry.user_id,
            JournalEntry.valence_score.isnot(None)
        ).order_by(JournalEntry.created_at.desc()).limit(3).all()

        is_alert = False
        if len(recent_entries) == 3:
            if all(e.valence_score < 0.3 for e in recent_entries):
                is_alert = True
        
        # Immediate alert for severe flat affect combined with negative mood
        if entry.pitch_variance < 50.0 and combined_valence < -0.2:
            is_alert = True

        if is_alert:
            entry.is_risk_alert = True
            db.commit()
            print(f"[Task] ⚠️ RISK ALERT TRIGGERED for User {entry.user_id}")

        print(f"[Task] ✓ Entry {entry_id} processed: emotion={combined_emotion}, valence={combined_valence:.4f}")

        return {
            "status": "completed",
            "entry_id": entry_id,
            "transcript": transcript[:200] if transcript else None,
            "emotion": combined_emotion,
            "valence": round(combined_valence, 4),
        }

    except Exception as exc:
        db.rollback()
        print(f"[Task] ✗ Error processing entry {entry_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)

    finally:
        db.close()
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
