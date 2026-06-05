from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.journal import JournalEntry
from app.models.clinical import InviteCode
from app.core.security import get_current_clinician
import secrets

router = APIRouter()

@router.get("/patients")
def get_patients(
    db: Session = Depends(get_db),
    clinician: User = Depends(get_current_clinician)
):
    """Get all patients assigned to this clinician, with their recent risk status."""
    patients = db.query(User).filter(User.clinician_id == clinician.id).all()
    
    response = []
    for p in patients:
        # Get latest entry to check risk
        latest_entry = db.query(JournalEntry).filter(
            JournalEntry.user_id == p.id
        ).order_by(JournalEntry.created_at.desc()).first()
        
        result.append({
            "id": p.id,
            "email": p.email,
            "is_risk_alert": latest_entry.is_risk_alert if latest_entry else False,
            "last_entry_date": latest_entry.created_at if latest_entry else None,
            "latest_valence": latest_entry.valence_score if latest_entry else None
        })
        
    return result

@router.post("/invite")
def generate_invite(
    db: Session = Depends(get_db),
    clinician: User = Depends(get_current_clinician)
):
    """Generate a simple 6-character alphanumeric invite code."""
    code = secrets.token_hex(3).upper() # e.g. "A1B2C3"
    
    new_invite = InviteCode(
        code=code,
        clinician_id=clinician.id
    )
    db.add(new_invite)
    db.commit()
    db.refresh(new_invite)
    
    return {"code": code}

@router.get("/patients/{patient_id}/entries")
def get_patient_entries(
    patient_id: int,
    db: Session = Depends(get_db),
    clinician: User = Depends(get_current_clinician)
):
    """Get all journal entries for a specific patient. Includes clinical DSP features."""
    # Ensure patient belongs to clinician
    patient = db.query(User).filter(User.id == patient_id, User.clinician_id == clinician.id).first()
    if not patient:
        raise HTTPException(status_code=403, detail="Not authorized to view this patient")
        
    entries = db.query(JournalEntry).filter(JournalEntry.user_id == patient_id).order_by(JournalEntry.created_at.desc()).all()
    return entries
