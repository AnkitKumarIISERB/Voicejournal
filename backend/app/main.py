"""
VoiceJournal API — Main Application Entry Point

An AI-powered audio mood journal that analyzes voice recordings
using WavLM (acoustic emotion) + Whisper (transcription) + text sentiment.

All models run locally. Zero API costs. Zero cloud dependency for dev.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.middleware import RequestLoggingMiddleware
from app.core.limiter import limiter
from app.api.auth import router as auth_router
from app.api.journals import router as journals_router
from app.api.clinical import router as clinical_router
from app.api.websockets import router as ws_router
from app.db.base import Base
from app.db.session import engine

# Create tables on startup (for SQLite dev mode)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered audio mood journal. Record voice entries, get emotional analysis.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Logging middleware
app.add_middleware(RequestLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(journals_router, prefix=settings.API_V1_STR)
app.include_router(clinical_router, prefix=f"{settings.API_V1_STR}/clinical", tags=["Clinical B2B"])
app.include_router(ws_router)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "voicejournal-api"}


@app.get("/", tags=["System"])
def root():
    """Root endpoint — redirects to API docs."""
    return {
        "message": "VoiceJournal API",
        "docs": "/docs",
        "health": "/health",
    }
