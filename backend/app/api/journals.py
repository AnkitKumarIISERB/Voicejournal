"""
Journal API endpoints.

POST /journals/upload     — Upload an audio file and start analysis
GET  /journals/           — List all journal entries for the current user
GET  /journals/{id}       — Get a specific journal entry with analysis results
GET  /journals/trends     — Get 30-day mood trend data for the dashboard
DELETE /journals/{id}     — Delete a journal entry and its audio file
"""

from datetime import datetime, timedelta, timezone
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.user import User
from app.models.journal import JournalEntry
from app.schemas.schemas import (
    JournalEntryResponse,
    JournalEntryList,
    AnalysisStatus,
    MoodScoreResponse,
    MoodTrend,
    MoodTrendResponse,
)
from app.core.security import get_current_user
from app.services.storage import save_audio, delete_audio
from app.services.tasks import process_journal
from app.core.limiter import limiter
from fastapi import Request

router = APIRouter(prefix="/journals", tags=["Journals"])

# Max upload size: 10MB (covers ~5 min of audio at standard quality)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}


@router.post("/upload", response_model=AnalysisStatus, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a voice journal entry.

    The audio file is encrypted and stored locally. A background Celery task
    is dispatched to transcribe the audio and analyze the mood.

    Returns 202 Accepted with the entry ID — the client can poll /journals/{id}
    or listen on the WebSocket for completion.
    """
    # Validate file extension
    import os

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)}MB",
        )

    # Save encrypted audio
    storage_key = save_audio(content, current_user.id, file.filename or "recording.wav")

    # Create database entry
    entry = JournalEntry(
        user_id=current_user.id,
        audio_s3_key=storage_key,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Dispatch async processing task
    process_journal.delay(entry.id)

    return AnalysisStatus(
        entry_id=entry.id,
        status="pending",
    )


@router.get("/", response_model=JournalEntryList)
def list_entries(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all journal entries for the current user, newest first."""
    total = db.query(JournalEntry).filter(JournalEntry.user_id == current_user.id).count()
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == current_user.id)
        .order_by(desc(JournalEntry.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return JournalEntryList(entries=entries, total=total)


@router.get("/trends", response_model=MoodTrendResponse)
def get_mood_trends(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get mood trend data for the dashboard chart.
    Returns daily average valence and dominant emotion for the past N days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.created_at >= cutoff,
            JournalEntry.valence_score.isnot(None),
        )
        .order_by(JournalEntry.created_at)
        .all()
    )

    if not entries:
        return MoodTrendResponse(trends=[], average_valence=0.0, most_common_emotion="neutral")

    # Group by date
    daily = {}
    emotions = []
    for entry in entries:
        date_str = entry.created_at.strftime("%Y-%m-%d")
        if date_str not in daily:
            daily[date_str] = {"valences": [], "emotions": []}
        daily[date_str]["valences"].append(entry.valence_score)
        daily[date_str]["emotions"].append(entry.emotion_label or "neutral")
        emotions.append(entry.emotion_label or "neutral")

    trends = []
    for date_str, data in daily.items():
        avg_valence = sum(data["valences"]) / len(data["valences"])
        dominant = Counter(data["emotions"]).most_common(1)[0][0]
        trends.append(MoodTrend(date=date_str, valence=round(avg_valence, 4), emotion=dominant))

    overall_avg = sum(e.valence_score for e in entries) / len(entries)
    most_common = Counter(emotions).most_common(1)[0][0]

    return MoodTrendResponse(
        trends=trends,
        average_valence=round(overall_avg, 4),
        most_common_emotion=most_common,
    )


from app.services.ai_summary import generate_weekly_summary

@router.get("/weekly-summary")
async def get_weekly_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an AI summary of the past 7 days of journal entries."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.created_at >= cutoff,
            JournalEntry.transcript.isnot(None)
        )
        .order_by(JournalEntry.created_at)
        .all()
    )

    entries_data = [
        {
            "transcript": e.transcript,
            "emotion": e.emotion_label or "neutral",
            "date": e.created_at.strftime("%Y-%m-%d")
        }
        for e in entries
    ]

    summary = await generate_weekly_summary(entries_data)
    
    return {
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


import numpy as np

@router.get("/prediction")
def get_mood_prediction(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Predict tomorrow's mood valence using linear regression on the last 14 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.created_at >= cutoff,
            JournalEntry.valence_score.isnot(None)
        )
        .order_by(JournalEntry.created_at)
        .all()
    )

    if len(entries) < 3:
        return {
            "predicted_valence": None,
            "trend": "insufficient_data",
            "message": "Need at least 3 recent entries to predict mood."
        }

    # x = days passed since cutoff, y = valence
    x = []
    y = []
    for e in entries:
        days_since = (e.created_at - cutoff).total_seconds() / (24 * 3600)
        x.append(days_since)
        y.append(e.valence_score)

    # Linear regression: y = mx + c
    m, c = np.polyfit(x, y, 1)
    
    # Predict tomorrow (day 15 from cutoff)
    tomorrow_x = 15
    predicted_y = m * tomorrow_x + c
    predicted_y = max(-1.0, min(1.0, predicted_y)) # clamp between -1 and 1

    trend = "stable"
    if m > 0.05:
        trend = "improving"
    elif m < -0.05:
        trend = "declining"

    return {
        "predicted_valence": round(predicted_y, 4),
        "trend": trend,
        "message": "Based on a 14-day linear regression."
    }


from app.services.anomaly_detection import check_mood_anomaly, get_mood_streak

@router.get("/biomarkers/{entry_id}")
def get_voice_biomarkers(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get voice biomarker analysis for a specific journal entry."""
    entry = db.query(JournalEntry).filter(
        JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id
    ).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    try:
        from app.services.storage import load_audio
        from app.services.voice_biomarkers import extract_biomarkers
        import tempfile, os

        audio_bytes = load_audio(entry.audio_s3_key)
        ext = os.path.splitext(entry.audio_s3_key)[1] or ".wav"
        
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        biomarkers = extract_biomarkers(tmp_path, entry.transcript)
        os.unlink(tmp_path)
        
        return biomarkers
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Biomarker analysis failed: {str(e)}")


@router.get("/anomaly-check")
def check_anomaly(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if the user's recent mood shows anomalies or crisis indicators."""
    # Get the latest entry
    latest = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.valence_score.isnot(None),
        )
        .order_by(JournalEntry.created_at.desc())
        .first()
    )

    if not latest:
        return {"is_anomaly": False, "alert_level": "none", "message": None}

    result = check_mood_anomaly(
        db, current_user.id, latest.valence_score, latest.emotion_label or "neutral"
    )
    return result


@router.get("/streak")
def get_streak(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's journaling streak and stats."""
    return get_mood_streak(db, current_user.id)


@router.post("/chat")
async def chat_with_journal(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Conversational AI: Ask questions about your mood history."""
    body = await request.json()
    question = body.get("question", "")
    voice_id = body.get("voice_id", "")
    chat_history = body.get("chat_history", [])

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    # Gather context from recent entries
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.created_at >= cutoff,
            JournalEntry.transcript.isnot(None),
        )
        .order_by(JournalEntry.created_at.desc())
        .limit(20)
        .all()
    )

    context = ""
    for e in entries:
        date_str = e.created_at.strftime("%Y-%m-%d")
        context += f"[{date_str}] Emotion: {e.emotion_label or 'unknown'}, Valence: {e.valence_score}, Transcript: \"{e.transcript}\"\n"

    prompt = f"""You are a highly empathetic, insightful AI therapist, life coach, and incredibly close best friend. You have access to the user's recent mood journal entries and their voice-analyzed emotional states.

Here are their recent journal entries (last 30 days):
{context if context else "No entries found."}

Instructions:
1. Act as a deeply caring therapist and a loyal best friend whom the user can talk to about anything, including life problems. Do NOT just repeat their data back to them blindly. Use it to understand their mental state.
2. Provide deep psychological insights, gentle guidance, and extremely friendly, actionable advice tailored to their current emotions.
3. Validate their feelings and ask thought-provoking follow-up questions to help them reflect.
4. Keep your responses conversational, supportive, and concise (2-4 sentences max).
"""

    if voice_id in ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"]:
        gender_instruction = ""
        if voice_id == "hi-IN-SwaraNeural":
            gender_instruction = "Your name is Kiaa and you are a young FEMALE therapist and best friend. You MUST use feminine verb conjugations for yourself in Hindi (e.g., 'Main samajh rahi hoon', 'Main aapki dost hoon'). "
        else:
            gender_instruction = "Your name is Veer and you are a young MALE therapist and best friend. You MUST use masculine verb conjugations for yourself in Hindi (e.g., 'Main samajh raha hoon', 'Main aapka dost hoon'). "
            
        prompt += f"""\n\n{gender_instruction}The user prefers to speak in Hindi. You MUST return your response as a JSON object with two fields:
{{
  "answer": "Your casual, urban Hinglish therapist/friend response (e.g. 'Arre yaar, mujhe lagta hai ki aap kaafi thake hue hain aaj. Kya hum is baare mein baat karein?')",
  "tts_text": "The EXACT same response written in pure Devanagari script so the TTS engine can read it fluently (e.g. 'अरे यार, मुझे लगता है कि आप काफी थके हुए हैं आज। क्या हम इस बारे में बात करें?')"
}}
Do NOT output anything other than the raw JSON object. Keep it incredibly empathetic, natural, and friendly."""

    # Try Groq API
    from app.core.config import settings
    # Personas for English voices
    if voice_id == "en-US-JennyNeural":
        prompt += "\n\nYour name is Jenny. You are a sweet, energetic FEMALE therapist and best friend."
    elif voice_id == "en-US-AriaNeural":
        prompt += "\n\nYour name is Aria. You are a calm, grounded FEMALE therapist and best friend."
    elif voice_id == "en-GB-SoniaNeural":
        prompt += "\n\nYour name is Sonia. You are a sweet British FEMALE therapist and best friend."
    elif voice_id == "en-US-SteffanNeural":
        prompt += "\n\nYour name is Steffan. You are a calm, reassuring MALE therapist and best friend."

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        
        messages_payload = [{"role": "system", "content": prompt}]
        # Append entire chat history
        for msg in chat_history:
            if msg.get("role") in ["user", "assistant"]:
                messages_payload.append({"role": msg["role"], "content": msg["content"]})
        # Append latest question
        messages_payload.append({"role": "user", "content": question})

        completion = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.7,
            max_tokens=300,
        )
        answer = completion.choices[0].message.content.strip()
        tts_text = answer
        
        if voice_id in ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"]:
            import json
            try:
                # Groq might wrap in markdown ```json
                clean_json = answer.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                answer = data.get("answer", answer)
                tts_text = data.get("tts_text", answer)
            except Exception as e:
                print(f"Failed to parse JSON for Hinglish: {e}")
    except Exception as e:
        print(f"Groq Chat error: {e}")
        # Fallback: simple pattern matching
        if not entries:
            answer = "You haven't recorded any journal entries in the last 30 days. Start journaling to build your mood history!"
        elif "happy" in question.lower() or "good" in question.lower():
            happy_count = sum(1 for e in entries if e.emotion_label == "happy")
            answer = f"In the last 30 days, you had {happy_count} happy entries out of {len(entries)} total. Keep it up!"
        elif "sad" in question.lower() or "bad" in question.lower():
            sad_count = sum(1 for e in entries if e.emotion_label in ("sad", "fearful"))
            answer = f"You had {sad_count} entries where you felt sad or anxious out of {len(entries)} total entries. Remember, it's okay to have tough days."
        else:
            emotions = [e.emotion_label for e in entries if e.emotion_label]
            if emotions:
                most_common = max(set(emotions), key=emotions.count)
                avg_val = sum(e.valence_score for e in entries if e.valence_score is not None) / max(len([e for e in entries if e.valence_score is not None]), 1)
                answer = f"Over the last 30 days, your most common emotion was '{most_common}' with an average valence of {avg_val:.2f}."
                tts_text = answer
            else:
                answer = "Your entries are still being processed. Check back soon!"
                tts_text = answer

    return {"answer": answer, "tts_text": tts_text, "entries_analyzed": len(entries)}


@router.post("/chat/tts")
async def chat_tts(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Generate audio from text using Microsoft Edge TTS."""
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice_id", "en-US-JennyNeural")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        import edge_tts
        import tempfile
        import os
        from fastapi.responses import FileResponse
        from starlette.background import BackgroundTask

        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        communicate = edge_tts.Communicate(text, voice, rate="-5%", pitch="-2Hz")
        await communicate.save(path)
        
        # Return audio file and clean up after sending
        return FileResponse(
            path, 
            media_type="audio/mpeg", 
            filename="response.mp3",
            background=BackgroundTask(os.remove, path)
        )
    except Exception as e:
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate speech")


@router.get("/{entry_id}", response_model=JournalEntryResponse)
def get_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific journal entry. Allows clinicians to view their patients' entries."""
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
        
    # Permission check
    if current_user.role == "clinician":
        # Ensure the entry belongs to a patient assigned to this clinician
        patient = db.query(User).filter(User.id == entry.user_id).first()
        if not patient or patient.clinician_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this patient's data")
            
        # Log the HIPAA-style access
        from app.services.audit import log_clinician_action
        log_clinician_action(db, clinician_id=current_user.id, action="view", patient_id=patient.id, target_entry_id=entry.id)
        
    elif entry.user_id != current_user.id:
        # Patients can only view their own entries
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return entry


from fastapi.responses import StreamingResponse
from app.services.storage import load_audio
import io

@router.get("/{entry_id}/audio")
def get_entry_audio(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream the decrypted audio file for playback."""
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    # Permission check
    if current_user.role == "clinician":
        patient = db.query(User).filter(User.id == entry.user_id).first()
        if not patient or patient.clinician_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    try:
        audio_bytes = load_audio(entry.audio_s3_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found on server")

    # Determine content type based on extension
    import os
    ext = os.path.splitext(entry.audio_s3_key)[1].lower()
    content_type = "audio/webm" if ext == ".webm" else f"audio/{ext.strip('.')}"

    return StreamingResponse(
        io.BytesIO(audio_bytes), 
        media_type=content_type,
        headers={"Accept-Ranges": "bytes"}
    )



@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a journal entry and its associated audio file."""
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    # Delete audio from storage
    delete_audio(entry.audio_s3_key)

    db.delete(entry)
    db.commit()
