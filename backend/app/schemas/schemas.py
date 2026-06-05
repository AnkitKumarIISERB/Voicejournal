"""
Pydantic schemas for request/response validation.
Separating schemas from DB models is a FastAPI best practice
that interviewers specifically look for.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, List
from datetime import datetime


# ──────────────────────────────────────────────
# Auth Schemas
# ──────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    invite_code: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[int] = None
    type: Optional[str] = None  # "access" or "refresh"


# ──────────────────────────────────────────────
# Journal Schemas
# ──────────────────────────────────────────────

class JournalEntryCreate(BaseModel):
    """Metadata sent alongside the audio file upload."""
    pass  # Audio file is sent as multipart form data, no JSON body needed


class MoodScoreResponse(BaseModel):
    valence_score: Optional[float] = None
    dominance_score: Optional[float] = None
    arousal_score: Optional[float] = None
    emotion_label: Optional[str] = None


class JournalEntryResponse(BaseModel):
    id: int
    audio_s3_key: str
    transcript: Optional[str] = None
    valence_score: Optional[float] = None
    dominance_score: Optional[float] = None
    arousal_score: Optional[float] = None
    emotion_label: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JournalEntryList(BaseModel):
    entries: List[JournalEntryResponse]
    total: int


# ──────────────────────────────────────────────
# Analysis Schemas
# ──────────────────────────────────────────────

class AnalysisStatus(BaseModel):
    """Returned when checking the status of an async analysis job."""
    entry_id: int
    status: str  # "pending", "processing", "completed", "failed"
    transcript: Optional[str] = None
    mood: Optional[MoodScoreResponse] = None


class MoodTrend(BaseModel):
    """A single data point in the mood arc chart."""
    date: str
    valence: float
    emotion: str


class MoodTrendResponse(BaseModel):
    """30-day mood trend data for the Recharts dashboard."""
    trends: List[MoodTrend]
    average_valence: float
    most_common_emotion: str
