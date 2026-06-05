from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    audio_s3_key = Column(String, nullable=False)
    transcript = Column(String, nullable=True)
    
    # Mood score details
    valence_score = Column(Float, nullable=True)
    dominance_score = Column(Float, nullable=True)
    arousal_score = Column(Float, nullable=True)
    emotion_label = Column(String, nullable=True)
    
    # Clinical and Acoustic Features
    is_risk_alert = Column(Boolean, default=False)
    speech_rate = Column(Float, nullable=True)
    pitch_variance = Column(Float, nullable=True)
    energy_variance = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="journals")
