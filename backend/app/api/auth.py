"""
Authentication API endpoints.

POST /auth/register  — Create a new user
POST /auth/login     — Get access + refresh tokens
POST /auth/refresh   — Exchange refresh token for new access token
GET  /auth/me        — Get current user info (protected)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.schemas import UserCreate, UserResponse, Token
from app.core.limiter import limiter
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    clinician_id = None
    if user_in.invite_code:
        from app.models.clinical import InviteCode
        invite = db.query(InviteCode).filter(InviteCode.code == user_in.invite_code, InviteCode.is_used == False).first()
        if not invite:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite code")
        
        clinician_id = invite.clinician_id
        invite.is_used = True

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        clinician_id=clinician_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login and receive access + refresh tokens.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
@limiter.limit("5/minute")
def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Provide a refresh token.",
        )

    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return current_user


@router.get("/export")
@limiter.limit("2/minute")
def export_user_data(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """GDPR Data Export: Return all user data in JSON format."""
    from app.models.journal import JournalEntry
    
    entries = db.query(JournalEntry).filter(JournalEntry.user_id == current_user.id).all()
    
    export_data = {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "created_at": current_user.created_at.isoformat(),
        },
        "journal_entries": [
            {
                "id": e.id,
                "transcript": e.transcript,
                "emotion_label": e.emotion_label,
                "valence_score": e.valence_score,
                "created_at": e.created_at.isoformat()
            }
            for e in entries
        ]
    }
    
    return export_data

