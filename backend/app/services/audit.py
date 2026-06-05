from sqlalchemy.orm import Session
from app.models.clinical import AuditLog

def log_clinician_action(db: Session, clinician_id: int, action: str, patient_id: int, target_entry_id: int = None):
    """
    Logs an action taken by a clinician for compliance and auditing.
    """
    log_entry = AuditLog(
        clinician_id=clinician_id,
        action=action,
        patient_id=patient_id,
        target_entry_id=target_entry_id
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
