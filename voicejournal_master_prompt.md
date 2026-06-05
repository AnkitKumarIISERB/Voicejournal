# VoiceJournal — Master Build & Deployment Prompt

> **How to use this prompt:**
> Paste the relevant Phase section into Claude (or any AI coding agent) as your working prompt.
> Complete every acceptance criterion before moving to the next phase.
> Do not skip phases — each one is a prerequisite for the next.
> When you see `[YOUR_X]` placeholders, replace them with your actual values before running.

---

## Context (read before every session)

You are a senior full-stack engineer helping finish and deploy **VoiceJournal** — a B2B Healthcare SaaS platform for AI-powered audio mood journaling. The system does the following:

1. Patients record 1–3 minute voice notes in the browser.
2. A Celery async worker transcribes audio with OpenAI Whisper (with auto-translation to English), extracts acoustic features with `librosa`, runs a fine-tuned WavLM emotion model, and a DistilRoBERTa text sentiment model, then fuses scores 60/40 (acoustic/text) to produce a mood valence score and risk alert flag.
3. Clinicians see a real-time dashboard of their patients' mood arcs, risk alerts, and can generate PDF reports.
4. Patients can chat with a multilingual AI companion (Groq/Llama 3.1) that speaks with an MS Edge TTS voice — with a Hinglish dual-payload trick for Indian avatars (Roman UI text + Devanagari for TTS).

**Current state of the codebase:**
- Backend: FastAPI, SQLite (needs PostgreSQL), SQLAlchemy, python-jose JWT, AES-256 audio encryption, Celery (broker not configured), RBAC with audit logging, WebSocket notifications
- Frontend: React 18 + Vite + TailwindCSS, Web Audio API waveform recording, Recharts mood arc, jsPDF reports, 6 AI chat avatars
- ML: Whisper (local), librosa DSP, fine-tuned WavLM-Base-Plus, DistilRoBERTa, 60/40 fusion, 3-entry consecutive risk alert logic
- Missing: PostgreSQL, Redis, Docker Compose, CI/CD, tests, `/health`+`/metrics`, context-aware chat, real-time clinician risk alerts, README

**Monorepo structure:**
```
voicejournal/
├── backend/
│   ├── app/
│   │   ├── api/         # auth.py, journals.py
│   │   ├── core/        # security.py (AES), config.py
│   │   ├── models/      # SQLAlchemy ORM models
│   │   └── services/    # celery_app.py, tasks.py
│   ├── tests/
│   ├── alembic/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/  # AudioRecorder, JournalChat, MoodGlobe, CrisisAlert
│   │   └── pages/       # Dashboard, ClinicianDashboard
│   └── package.json
└── ml/
    ├── inference.py
    ├── models/          # wavlm_classifier.py, sentiment_model.py
    └── data/
```

**Rules for every phase:**
- Never hardcode secrets. Use environment variables via `pydantic-settings` and `.env` files.
- Always write `async` FastAPI endpoints where I/O is involved.
- Use `structlog` for all logging — no bare `print()` statements.
- Every new function must have a docstring.
- Commit message format: `type(scope): description` — e.g. `feat(backend): add Redis Celery broker`.
- After each phase, verify all acceptance criteria before saying "phase complete."

---

## Phase 1 — PostgreSQL Migration (replaces SQLite)

**Goal:** Replace SQLite with PostgreSQL so the app works correctly with multiple processes (API + Celery worker both need DB access), supports concurrent writes, and is production-deployable.

### Step 1.1 — Update dependencies

In `backend/requirements.txt`, replace `aiosqlite` (if present) with:
```
asyncpg==0.29.0
psycopg2-binary==2.9.9
```

Ensure these are also present:
```
alembic==1.13.1
sqlalchemy[asyncio]==2.0.30
```

### Step 1.2 — Update database connection

Create `backend/app/core/database.py` with the following content. Do not use synchronous SQLAlchemy — use the async engine throughout:

```python
"""Async PostgreSQL database engine and session factory."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    """FastAPI dependency that provides an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Step 1.3 — Update config

In `backend/app/core/config.py`, ensure `DATABASE_URL` uses the `postgresql+asyncpg://` scheme:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voicejournal"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str  # 32-byte Fernet key — generate with Fernet.generate_key()
    AWS_S3_BUCKET: str = ""
    GROQ_API_KEY: str = ""
    DEBUG: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

### Step 1.4 — Create `.env.example`

Create `backend/.env.example` (commit this; never commit `.env`):
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/voicejournal
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
SECRET_KEY=generate-with-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ENCRYPTION_KEY=generate-with-Fernet.generate_key()
AWS_S3_BUCKET=your-bucket-name
GROQ_API_KEY=your-groq-api-key
DEBUG=false
```

### Step 1.5 — Update all ORM models

Audit every file in `backend/app/models/`. Ensure:
- All models inherit from `Base` (imported from `app.core.database`, not a local declaration).
- Primary keys use `uuid.uuid4` as default: `id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)`.
- All `created_at` columns use `server_default=func.now()`.
- Add a `updated_at` column with `onupdate=func.now()` to any model that gets updated (User, JournalEntry).
- The `AuditLog` model has: `id`, `clinician_id` (FK), `patient_id` (FK), `action` (String), `resource_id` (String, nullable), `ip_address` (String, nullable), `timestamp` (DateTime, server_default).

### Step 1.6 — Generate and verify Alembic migration

```bash
cd backend
alembic revision --autogenerate -m "migrate_to_postgresql_schema"
alembic upgrade head
```

Inspect the generated migration file in `alembic/versions/`. Verify it contains `CREATE TABLE` statements (not `ALTER TABLE` for type changes that Alembic can't auto-detect). If anything looks wrong, edit the migration manually.

### Step 1.7 — Update Celery to use sync SQLAlchemy for worker tasks

Celery tasks cannot use async SQLAlchemy. Create a separate sync engine for use only in `backend/app/services/tasks.py`:

```python
"""Synchronous DB session for Celery workers (cannot use asyncpg in Celery tasks)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Convert asyncpg URL to psycopg2 for sync workers
SYNC_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

sync_engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
```

Use `SyncSessionLocal` in all Celery tasks. Never use `AsyncSession` inside a Celery task.

**Acceptance criteria for Phase 1:**
- [ ] `alembic upgrade head` runs without errors against a local PostgreSQL instance.
- [ ] FastAPI app starts with `DATABASE_URL` pointing to PostgreSQL (no SQLite references remain).
- [ ] Celery worker can write to the same PostgreSQL database using the sync engine.
- [ ] `.env` is in `.gitignore`. `.env.example` is committed.
- [ ] `grep -r "sqlite" backend/` returns zero results.

---

## Phase 2 — Redis Integration (Celery broker + WebSocket pub/sub)

**Goal:** Add Redis as the Celery message broker and result backend, and implement Redis pub/sub so WebSocket notifications work correctly when multiple API instances run simultaneously.

### Step 2.1 — Update Celery app configuration

In `backend/app/services/celery_app.py`, update to use Redis:

```python
"""Celery application factory with Redis broker."""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "voicejournal",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.services.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # Re-queue on worker crash
    worker_prefetch_multiplier=1, # One task at a time (ML tasks are heavy)
    task_routes={
        "app.services.tasks.analyze_mood": {"queue": "ml_queue"},
    },
)
```

### Step 2.2 — Create Redis pub/sub WebSocket manager

Create `backend/app/services/ws_manager.py`:

```python
"""
WebSocket connection manager using Redis pub/sub for multi-instance fan-out.

Pattern: Celery worker publishes to Redis channel → WebSocket manager
subscribes → pushes to connected browser clients.
This means adding a second API instance never silently drops notifications.
"""
import asyncio
import json
import structlog
from typing import Dict, Set
from fastapi import WebSocket
import redis.asyncio as aioredis
from app.core.config import settings

logger = structlog.get_logger()

class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._redis: aioredis.Redis | None = None

    async def startup(self):
        """Call on FastAPI startup. Creates Redis connection and starts listener."""
        self._redis = aioredis.from_url(
            settings.CELERY_BROKER_URL, decode_responses=True
        )
        asyncio.create_task(self._listen())
        logger.info("ws_manager.started")

    async def shutdown(self):
        """Call on FastAPI shutdown."""
        if self._redis:
            await self._redis.aclose()

    async def connect(self, websocket: WebSocket, user_id: str):
        """Register a new WebSocket connection for a user."""
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)
        logger.info("ws.connected", user_id=user_id)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def publish(self, channel: str, message: dict):
        """Publish a message to a Redis channel (called by Celery worker)."""
        if self._redis:
            await self._redis.publish(channel, json.dumps(message))

    async def _listen(self):
        """Background task: subscribes to all user channels and fans out to WS clients."""
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe("user:*")  # Subscribe to all user channels
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    user_id = message["channel"].split(":", 1)[1]
                    await self._broadcast_to_user(user_id, data)
                except Exception as e:
                    logger.error("ws.fan_out_error", error=str(e))

    async def _broadcast_to_user(self, user_id: str, message: dict):
        """Send a message to all WebSocket connections for a user."""
        dead = set()
        for ws in self._connections.get(user_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            await self.disconnect(ws, user_id)

ws_manager = WebSocketManager()
```

### Step 2.3 — Wire up manager in main FastAPI app

In `backend/app/main.py`, add lifespan events:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.ws_manager import ws_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ws_manager.startup()
    yield
    await ws_manager.shutdown()

app = FastAPI(title="VoiceJournal API", lifespan=lifespan)
```

### Step 2.4 — Update WebSocket endpoint

Replace any existing WebSocket endpoint in `backend/app/api/journals.py` with:

```python
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time notifications.
    Celery tasks publish to Redis; this endpoint delivers to the browser.
    """
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()  # Keep alive; ignore client messages
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
```

### Step 2.5 — Update Celery tasks to publish via Redis directly

In `backend/app/services/tasks.py`, after saving mood scores to the database, publish a notification. Because Celery tasks are sync, use the sync Redis client:

```python
import redis
import json
from app.core.config import settings

def _notify_user(user_id: str, payload: dict):
    """Publish a notification to a user's Redis channel."""
    r = redis.from_url(settings.CELERY_BROKER_URL)
    r.publish(f"user:{user_id}", json.dumps(payload))
    r.close()
```

Call `_notify_user(str(entry.user_id), {"status": "completed", "entry_id": str(entry_id), "valence": round(final_valence, 3), "is_risk_alert": is_risk_alert})` at the end of the `analyze_mood` task.

### Step 2.6 — Real-time clinician risk alert

This is the feature that closes the full loop. When `is_risk_alert = True` is written, also notify the patient's linked clinician(s):

```python
# After determining is_risk_alert in tasks.py
if is_risk_alert:
    # Query the clinician linked to this patient
    clinician_ids = _get_clinician_ids_for_patient(session, patient_id)
    for clinician_id in clinician_ids:
        _notify_user(str(clinician_id), {
            "type": "risk_alert",
            "patient_id": str(patient_id),
            "patient_name": patient_name,
            "entry_id": str(entry_id),
            "valence": round(final_valence, 3),
            "message": f"Risk alert: {patient_name} has shown 3 consecutive low-valence entries."
        })
```

In the frontend `ClinicianDashboard.tsx`, listen for `type === "risk_alert"` messages on the WebSocket and trigger the `CrisisAlert` component to appear with the patient's name and a link to their entry.

**Acceptance criteria for Phase 2:**
- [ ] `celery -A app.services.celery_app worker --loglevel=info -Q ml_queue` starts without errors.
- [ ] Submitting a journal entry returns `202 Accepted` immediately.
- [ ] WebSocket notification arrives in the browser within 3 seconds of Celery task completion.
- [ ] Clinician dashboard shows a live `CrisisAlert` banner when a patient triggers a risk alert — without page refresh.
- [ ] Adding a second API process does not drop any WebSocket notifications (test by running two uvicorn instances on different ports and connecting to each).

---

## Phase 3 — Docker Compose (full local stack)

**Goal:** One command — `docker compose up` — starts the entire system. A reviewer must be able to clone the repo and have a running app in under 5 minutes.

### Step 3.1 — Create `docker-compose.yml` in the project root

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: voicejournal
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/voicejournal
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - audio_storage:/app/audio_storage
    command: >
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+psycopg2://postgres:postgres@postgres:5432/voicejournal
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - audio_storage:/app/audio_storage
      - ml_models:/app/ml/models
    command: celery -A app.services.celery_app worker --loglevel=info -Q ml_queue --concurrency=1
    deploy:
      resources:
        limits:
          memory: 2G  # WavLM + Whisper need headroom

  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file: ./backend/.env
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
    depends_on:
      - redis
    command: celery -A app.services.celery_app beat --loglevel=info

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      VITE_API_URL: http://localhost:8000
      VITE_WS_URL: ws://localhost:8000

volumes:
  postgres_data:
  audio_storage:
  ml_models:
```

### Step 3.2 — Create `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

# System deps for librosa, psycopg2, and audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download Whisper model so it's baked into the image
RUN python -c "import whisper; whisper.load_model('tiny')"

EXPOSE 8000
```

### Step 3.3 — Create `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### Step 3.4 — Create `frontend/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Step 3.5 — Create `Makefile` in the project root

```makefile
.PHONY: up down build test lint migrate logs shell-backend

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

test:
	cd backend && python -m pytest tests/ -v --tb=short

lint:
	cd backend && ruff check app/ tests/

migrate:
	docker compose exec backend alembic upgrade head

logs:
	docker compose logs -f backend celery_worker

shell-backend:
	docker compose exec backend bash

seed:
	docker compose exec backend python scripts/seed_demo_data.py
```

### Step 3.6 — Create demo seed script

Create `backend/scripts/seed_demo_data.py`. This script creates:
- 1 demo clinician account (`clinician@demo.com` / `demo1234`)
- 2 demo patient accounts (`patient1@demo.com` / `demo1234`, `patient2@demo.com` / `demo1234`)
- 14 pre-generated journal entries for patient1 with realistic valence scores (trending downward to trigger a risk alert on the last 3 entries)
- An invite code linking patient1 to the demo clinician

This is critical for demos — a recruiter should be able to log in as the clinician and immediately see a populated, realistic dashboard.

**Acceptance criteria for Phase 3:**
- [ ] `make up` starts all 5 services without errors.
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok", "db": "ok", "redis": "ok"}`.
- [ ] `curl http://localhost:3000` returns the React app HTML.
- [ ] `make seed` populates the demo data successfully.
- [ ] Demo clinician login shows patient1's mood arc and a risk alert badge.
- [ ] `make down && make up` (full restart) preserves PostgreSQL data via the named volume.

---

## Phase 4 — Tests and CI/CD

**Goal:** A pytest suite with meaningful coverage and a GitHub Actions pipeline that runs on every push to `main` and every pull request.

### Step 4.1 — Install test dependencies

Add to `backend/requirements.txt`:
```
pytest==8.2.2
pytest-asyncio==0.23.7
httpx==0.27.0
pytest-cov==5.0.0
factory-boy==3.3.0
faker==25.2.0
```

### Step 4.2 — Create `backend/tests/conftest.py`

```python
"""
Shared pytest fixtures.
Uses an in-memory SQLite database for speed in unit tests,
and a real PostgreSQL test database for integration tests.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a clean async DB session backed by in-memory SQLite for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Provides a test HTTP client with the DB dependency overridden."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
def demo_patient_payload():
    return {"email": "patient@test.com", "password": "testpass123", "role": "patient"}

@pytest.fixture
def demo_clinician_payload():
    return {"email": "clinician@test.com", "password": "testpass123", "role": "clinician"}
```

### Step 4.3 — Write test suite

Create the following test files. Write every test from scratch — do not mock business logic unless testing a unit in isolation.

**`backend/tests/test_auth.py`** — must cover:
- `POST /auth/register` with valid patient payload → `201`, returns user with correct role
- `POST /auth/register` with duplicate email → `409`
- `POST /auth/login` with correct credentials → `200`, returns `access_token` and `refresh_token`
- `POST /auth/login` with wrong password → `401`
- `POST /auth/refresh` with valid refresh token → new `access_token`
- `GET /auth/me` with valid token → returns current user
- `GET /auth/me` with expired/invalid token → `401`

**`backend/tests/test_journals.py`** — must cover:
- `POST /journals/upload` with a valid WAV file (use a 1-second sine wave generated by `scipy.io.wavfile`) → `202 Accepted`, returns `entry_id`
- `POST /journals/upload` without auth → `401`
- `GET /journals/` → returns list of entries for the authenticated user only
- `GET /journals/{entry_id}` for an entry belonging to a different user → `403`

**`backend/tests/test_risk_logic.py`** — unit tests for the fusion and risk alert logic in isolation (no DB, no HTTP):
```python
from app.services.tasks import compute_final_valence, check_risk_alert

def test_fusion_60_40():
    """Acoustic weight is 60%, text weight is 40%."""
    result = compute_final_valence(acoustic_valence=1.0, text_valence=0.0)
    assert result == pytest.approx(0.6, abs=0.001)

def test_fusion_both_high():
    result = compute_final_valence(acoustic_valence=0.8, text_valence=0.9)
    assert result == pytest.approx(0.84, abs=0.001)

def test_risk_alert_triggers_on_three_consecutive_low():
    history = [0.25, 0.20, 0.28]  # All < 0.3
    assert check_risk_alert(history) is True

def test_risk_alert_no_trigger_on_two_low():
    """Edge case: only 2 entries exist — must NOT trigger alert."""
    history = [0.20, 0.25]
    assert check_risk_alert(history) is False

def test_risk_alert_no_trigger_if_one_entry_normal():
    history = [0.25, 0.35, 0.20]  # Middle entry is above threshold
    assert check_risk_alert(history) is False

def test_risk_alert_no_trigger_on_empty_history():
    assert check_risk_alert([]) is False
```

**`backend/tests/test_clinician.py`** — must cover:
- Clinician can see patients linked via invite code
- Clinician cannot see patients not linked to them → `403`
- Audit log row is created when clinician accesses patient transcript
- Patient cannot access the clinician dashboard endpoint → `403`

**`backend/tests/test_health.py`**:
```python
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
```

### Step 4.4 — Extract pure functions from `tasks.py`

The risk logic tests above require `compute_final_valence` and `check_risk_alert` to be importable pure functions. Refactor `tasks.py` so these are defined at the top of the file and called by the Celery task — not embedded inside it. This makes them testable without a Celery context.

```python
def compute_final_valence(acoustic_valence: float, text_valence: float) -> float:
    """Fuse acoustic and text valence scores 60/40."""
    return round(0.6 * acoustic_valence + 0.4 * text_valence, 4)

def check_risk_alert(recent_valences: list[float]) -> bool:
    """
    Return True if the last 3 entries all have valence < 0.3.
    Returns False if fewer than 3 entries exist (edge case: new patients).
    """
    if len(recent_valences) < 3:
        return False
    return all(v < 0.3 for v in recent_valences[-3:])
```

### Step 4.5 — Add `/health` and `/metrics` endpoints

In `backend/app/api/health.py`:

```python
"""Health check and Prometheus metrics endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from app.core.database import get_db
from app.core.config import settings
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe. Checks DB and Redis connectivity.
    Returns 200 if all systems healthy, 503 otherwise.
    """
    checks = {"status": "ok", "db": "unknown", "redis": "unknown"}
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = "error"
        checks["status"] = "degraded"
        logger.error("health.db_error", error=str(e))
    try:
        r = aioredis.from_url(settings.CELERY_BROKER_URL)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = "error"
        checks["status"] = "degraded"
        logger.error("health.redis_error", error=str(e))
    status_code = 200 if checks["status"] == "ok" else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=checks, status_code=status_code)
```

Add Prometheus metrics in `backend/app/main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

# After creating the FastAPI app:
Instrumentator().instrument(app).expose(app)
```

Add `prometheus-fastapi-instrumentator==6.1.0` to `requirements.txt`.

### Step 4.6 — Create GitHub Actions workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: voicejournal_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install system dependencies
        run: sudo apt-get install -y ffmpeg libsndfile1

      - name: Install Python dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run linter (ruff)
        run: |
          cd backend
          ruff check app/ tests/

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/voicejournal_test
          CELERY_BROKER_URL: redis://localhost:6379/0
          CELERY_RESULT_BACKEND: redis://localhost:6379/1
          SECRET_KEY: test-secret-key-not-for-production
          ENCRYPTION_KEY: ${{ secrets.TEST_ENCRYPTION_KEY }}
        run: |
          cd backend
          pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=65

      - name: Build Docker images
        run: docker compose build

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - uses: actions/checkout@v4
      # Deployment steps go here in Phase 6
      - name: Deploy placeholder
        run: echo "Deployment configured in Phase 6"
```

**Acceptance criteria for Phase 4:**
- [ ] `make test` runs all tests and exits 0.
- [ ] `pytest tests/ --cov=app --cov-fail-under=65` passes.
- [ ] `ruff check app/ tests/` returns zero violations.
- [ ] GitHub Actions shows a green checkmark on the `main` branch.
- [ ] The CI badge URL is added to the README: `![CI](https://github.com/[YOUR_USERNAME]/voicejournal/actions/workflows/ci.yml/badge.svg)`
- [ ] `test_risk_alert_no_trigger_on_two_low` passes — the edge case is fixed.

---

## Phase 5 — Context-Aware AI Chat + Structured Logging

**Goal:** Make the AI chat companion clinically meaningful by injecting the patient's mood data into every LLM request. Add structured logging throughout the app.

### Step 5.1 — Add structured logging with `structlog`

Add `structlog==24.1.0` to `requirements.txt`.

Create `backend/app/core/logging.py`:

```python
"""Configure structlog for JSON-formatted production logging."""
import logging
import structlog

def configure_logging(debug: bool = False):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

Call `configure_logging(debug=settings.DEBUG)` at the top of `backend/app/main.py`.

Replace every `print()` and `logging.info()` call in the codebase with `structlog.get_logger()`. Use bound loggers: `logger = structlog.get_logger().bind(user_id=str(user_id))`.

### Step 5.2 — Build the mood context builder

Create `backend/app/services/mood_context.py`:

```python
"""
Builds a structured mood context summary for the LLM system prompt.
Converts raw database entries into a narrative the LLM uses to give
personalised, data-informed responses.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.journal import JournalEntry
import structlog

logger = structlog.get_logger()

async def build_mood_context(user_id: str, session: AsyncSession) -> str:
    """
    Returns a plain-English summary of the patient's last 7 days of mood data.
    Injected as context into every AI chat system prompt.
    """
    result = await session.execute(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id)
        .where(JournalEntry.valence.isnot(None))
        .order_by(desc(JournalEntry.created_at))
        .limit(7)
    )
    entries = result.scalars().all()

    if not entries:
        return "The patient has not yet submitted any journal entries."

    lines = []
    for entry in reversed(entries):
        date_str = entry.created_at.strftime("%A, %b %d")
        valence_label = (
            "very low" if entry.valence < 0.2 else
            "low" if entry.valence < 0.4 else
            "moderate" if entry.valence < 0.6 else
            "good" if entry.valence < 0.8 else "high"
        )
        risk_note = " [RISK ALERT]" if entry.is_risk_alert else ""
        lines.append(
            f"- {date_str}: valence {entry.valence:.2f} ({valence_label}){risk_note}. "
            f"Emotion: {entry.emotion_label or 'unknown'}. "
            f"Speech rate: {entry.speech_rate_wps:.1f} words/sec." if entry.speech_rate_wps else ""
        )

    trend = entries[0].valence - entries[-1].valence  # Positive = improving
    trend_str = "improving" if trend > 0.1 else "declining" if trend < -0.1 else "stable"

    return (
        f"PATIENT MOOD DATA (last {len(entries)} entries, most recent first):\n"
        + "\n".join(lines)
        + f"\n\nOverall trend: {trend_str}. "
        + ("Current risk alert is ACTIVE." if entries[0].is_risk_alert else "No current risk alert.")
    )
```

### Step 5.3 — Inject mood context into chat system prompt

Update the chat endpoint in `backend/app/api/journals.py`. The system prompt must change from a generic therapist persona to one grounded in the patient's actual data:

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI companion chat endpoint. Injects the patient's real mood data
    into the system prompt so responses are personalised, not generic.
    """
    mood_context = await build_mood_context(str(current_user.id), db)

    avatar = request.avatar  # e.g. "jenny", "kiaa", "veer"
    is_indian = avatar in ("kiaa", "veer")
    gender_note = ""
    if avatar == "kiaa":
        gender_note = "You are female. Use feminine Hindi verb forms (e.g. 'main sun rahi hoon', 'mujhe achha lag raha hai')."
    elif avatar == "veer":
        gender_note = "You are male. Use masculine Hindi verb forms (e.g. 'main sun raha hoon', 'mujhe achha lag raha hai')."

    if is_indian:
        system_prompt = f"""You are a warm, empathetic mental health companion named {avatar.capitalize()}.
{gender_note}
You are speaking with a patient whose recent mood data is:

{mood_context}

Respond in casual urban Hinglish (mix of Hindi and English in Roman script).
You MUST respond ONLY with a JSON object (no markdown, no preamble):
{{"answer": "<Hinglish response for display>", "tts_text": "<same response in pure Devanagari script for TTS>"}}

Reference the patient's mood data naturally when relevant — for example, if their valence has been declining, acknowledge that things have been tough lately. If there is a risk alert, gently check in about how they are feeling. Never be clinical or robotic."""
    else:
        system_prompt = f"""You are a warm, empathetic mental health companion named {avatar.capitalize()}.
You are speaking with a patient whose recent mood data is:

{mood_context}

Respond naturally in conversational English. Reference their mood data when relevant — acknowledge struggles, celebrate improvements. If there is a risk alert, gently check in. Never be clinical or robotic. Keep responses under 3 sentences."""

    messages = [{"role": "system", "content": system_prompt}] + request.history

    # ... rest of Groq API call unchanged
```

**Acceptance criteria for Phase 5:**
- [ ] Chat endpoint returns responses that reference the patient's actual valence scores (test manually with seeded demo data).
- [ ] A patient with a risk alert gets a noticeably different tone of response than a patient with a good mood arc (test by logging in as both demo patients).
- [ ] Hinglish dual-payload still works correctly — `tts_text` is Devanagari, `answer` is Roman.
- [ ] Zero `print()` statements in the codebase — `grep -r "print(" backend/app/` returns nothing.
- [ ] All API requests are logged with `user_id`, `endpoint`, `duration_ms`, and `status_code`.

---

## Phase 6 — Pre-Deployment Checklist & Production Config

**Goal:** Harden the application for public deployment. Complete every item on this checklist before starting Phase 7.

### Step 6.1 — Security hardening

Add to `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://voicejournal.vercel.app"],  # Replace with your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.render.com", "localhost"])
```

Add `slowapi==0.1.9` to `requirements.txt`.

Apply rate limiting to the most sensitive endpoints:
```python
@router.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):

@router.post("/journals/upload")
@limiter.limit("10/minute")
async def upload_audio(request: Request, ...):
```

### Step 6.2 — Audio storage with Cloudflare R2 (free, no credit card needed)

Cloudflare R2 is S3-compatible and has a permanent free tier: 10GB storage, 1M Class A operations/month, 10M Class B operations/month. No egress fees. No credit card required for the free tier.

Add `boto3==1.34.0` to `requirements.txt`. R2 uses the boto3 S3 client with a custom endpoint — no new library needed.

Update `backend/app/core/config.py` — replace all AWS fields with R2 fields:

```python
# Replace AWS_* fields with:
R2_ACCOUNT_ID: str = ""           # Cloudflare account ID
R2_ACCESS_KEY_ID: str = ""        # R2 API token Access Key ID
R2_SECRET_ACCESS_KEY: str = ""    # R2 API token Secret Access Key
R2_BUCKET_NAME: str = "voicejournal-audio"
R2_ENDPOINT_URL: str = ""         # Set to: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

Create `backend/app/services/storage.py`:

```python
"""
Abstracted audio storage service.
Uses Cloudflare R2 in production (R2_ACCOUNT_ID set) — free tier, S3-compatible.
Falls back to local filesystem in development (no credentials needed).
"""
import boto3
from botocore.config import Config
from pathlib import Path
from app.core.config import settings
import structlog

logger = structlog.get_logger()
AUDIO_DIR = Path("audio_storage")

def _get_r2_client():
    """Return a boto3 S3 client pointed at Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

def save_audio(data: bytes, filename: str) -> str:
    """Save encrypted audio. Returns the storage key."""
    if settings.R2_ACCOUNT_ID:
        key = f"audio/{filename}"
        _get_r2_client().put_object(
            Bucket=settings.R2_BUCKET_NAME, Key=key, Body=data
        )
        logger.info("storage.r2_upload", key=key)
        return key
    else:
        AUDIO_DIR.mkdir(exist_ok=True)
        path = AUDIO_DIR / filename
        path.write_bytes(data)
        return str(path)

def load_audio(storage_key: str) -> bytes:
    """Load encrypted audio from R2 or local filesystem."""
    if settings.R2_ACCOUNT_ID and not storage_key.startswith("/"):
        response = _get_r2_client().get_object(
            Bucket=settings.R2_BUCKET_NAME, Key=storage_key
        )
        return response["Body"].read()
    else:
        return Path(storage_key).read_bytes()
```

Replace all direct file reads/writes in `tasks.py` and `journals.py` with `save_audio()` and `load_audio()`.

**How to set up R2 (takes 5 minutes, free, no credit card):**
1. [dash.cloudflare.com](https://dash.cloudflare.com) → R2 → Create Bucket → name: `voicejournal-audio`
2. R2 → Manage R2 API Tokens → Create API Token → Permissions: Object Read & Write → Bucket: `voicejournal-audio`
3. Copy: Account ID, Access Key ID, Secret Access Key
4. Your endpoint URL: `https://[ACCOUNT_ID].r2.cloudflarestorage.com`

Update `.env.example`:
```
R2_ACCOUNT_ID=your-cloudflare-account-id
R2_ACCESS_KEY_ID=your-r2-access-key-id
R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
R2_BUCKET_NAME=voicejournal-audio
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
```

Also update the Mermaid diagram in Step 8.2 — replace `AWS S3\nAES-256` with `Cloudflare R2\nAES-256 · free tier`.

### Step 6.3 — Production environment variables

Generate production secrets:
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create a `backend/.env.production.example` with all required variables documented. Never commit actual values.

### Step 6.4 — Final pre-deployment checks

Run this checklist manually. All must pass:

```bash
# No secrets in code
grep -r "password\|secret\|api_key\|token" backend/app/ --include="*.py" | grep -v "settings\." | grep -v "test" | grep -v "Bearer"

# No debug mode
grep -r "DEBUG=True\|debug=True" backend/ --include="*.env"

# No SQLite references
grep -r "sqlite" backend/ --include="*.py"

# Tests pass
cd backend && pytest tests/ -v

# Docker builds cleanly
docker compose build --no-cache

# Health check responds correctly
docker compose up -d
sleep 10
curl -f http://localhost:8000/health

# Seed data loads
make seed
```

**Acceptance criteria for Phase 6:**
- [ ] All grep checks above return empty results.
- [ ] Login endpoint rejects on the 6th attempt within a minute with `429 Too Many Requests`.
- [ ] `docker compose build --no-cache` completes without errors.
- [ ] `curl http://localhost:8000/health` returns `{"status":"ok","db":"ok","redis":"ok"}`.
- [ ] Audio uploaded via the API is retrievable from S3 (or local storage fallback) after a container restart.
- [ ] CORS blocks requests from `http://evil.example.com` (test with curl `-H "Origin: http://evil.example.com"`).

---

## Phase 7 — Deployment (100% Free, No Credit Card Required)

**Goal:** The application is live at a public URL. Every service used here has a permanent free tier — no trial periods, no credit card.

**Free stack overview:**

| Component | Service | Free Tier Limits | Credit Card? |
|---|---|---|---|
| PostgreSQL | Supabase | 500MB, 2 projects | No |
| Redis | Upstash | 10k commands/day, 256MB | No |
| API (FastAPI) | Render | 512MB RAM, sleeps after 15min | No |
| Celery worker | Railway | 500 hours/month | No (GitHub login) |
| Audio storage | Cloudflare R2 | 10GB, 1M ops/month | No |
| Frontend | Vercel | Unlimited deploys | No |
| CI/CD | GitHub Actions | 2,000 min/month | No |

**Important note on the Celery worker:** WavLM + Whisper need ~1.2GB RAM. Railway's free tier gives 512MB. Two workarounds are documented in Step 7.5 — use whichever fits your situation. For portfolio demos, both are acceptable and you should document the trade-off in your README (it shows production awareness, not a weakness).

---

### Step 7.1 — PostgreSQL (Supabase — free, no credit card)

1. Go to [supabase.com](https://supabase.com) → Sign up with GitHub → New Project → name: `voicejournal-prod` → generate a strong password → region: closest to you.
2. Wait ~2 minutes for provisioning.
3. Settings → Database → scroll to **Connection String** → select **URI** tab → select **Transaction pooler** (port 6543, not 5432 — the pooler handles connection limits on the free tier).
4. Copy the URI. It looks like: `postgresql://postgres:[PASSWORD]@[HOST]:6543/postgres`
5. For `DATABASE_URL` in production, change the scheme to `asyncpg`: `postgresql+asyncpg://postgres:[PASSWORD]@[HOST]:6543/postgres`

> Free tier limits: 500MB database, 2 projects, unlimited API calls. More than enough for a portfolio demo with hundreds of journal entries.

---

### Step 7.2 — Redis (Upstash — free, no credit card)

1. Go to [upstash.com](https://upstash.com) → Sign up with GitHub → Create Database → name: `voicejournal-redis` → Region: same as your Render region → TLS: enabled.
2. Copy the **Redis URL** from the dashboard. Format: `rediss://:[PASSWORD]@[HOST]:[PORT]`
3. This URL is both your `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

> Free tier limits: 10,000 commands/day, 256MB. For a portfolio demo (a few users submitting journal entries), this comfortably handles Celery task queuing and WebSocket pub/sub. At 10 tasks/day × ~50 Redis operations each = 500 ops/day, well within the limit.

---

### Step 7.3 — Cloudflare R2 audio storage (free, no credit card)

Complete the setup described in Phase 6 Step 6.2. By now you should already have:
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME` = `voicejournal-audio`
- `R2_ENDPOINT_URL` = `https://[ACCOUNT_ID].r2.cloudflarestorage.com`

If not, go to [dash.cloudflare.com](https://dash.cloudflare.com) → R2 → set it up now (5 minutes). No credit card required.

---

### Step 7.4 — Backend API (Render free tier)

1. [render.com](https://render.com) → Sign up with GitHub → New → Web Service → connect your GitHub repo.
2. Set root directory to `backend/`.
3. **Runtime:** Python 3
4. **Build Command:**
   ```
   pip install -r requirements.txt && python -c "import whisper; whisper.load_model('tiny')"
   ```
   Pre-downloading the Whisper model at build time avoids a 30s cold start on first request.
5. **Start Command:**
   ```
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
6. **Instance Type:** Free (512MB RAM — sufficient for the API; ML runs in the worker)
7. **Environment Variables** — add all of these in the Render dashboard:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@[HOST]:6543/postgres
   CELERY_BROKER_URL=rediss://:[PASSWORD]@[HOST]:[PORT]
   CELERY_RESULT_BACKEND=rediss://:[PASSWORD]@[HOST]:[PORT]
   SECRET_KEY=[output of: openssl rand -hex 32]
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   REFRESH_TOKEN_EXPIRE_DAYS=7
   ENCRYPTION_KEY=[output of: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"]
   R2_ACCOUNT_ID=[your cloudflare account id]
   R2_ACCESS_KEY_ID=[your r2 access key]
   R2_SECRET_ACCESS_KEY=[your r2 secret key]
   R2_BUCKET_NAME=voicejournal-audio
   R2_ENDPOINT_URL=https://[ACCOUNT_ID].r2.cloudflarestorage.com
   GROQ_API_KEY=[your groq api key — free at console.groq.com]
   DEBUG=false
   ```
8. **Health Check Path:** `/health`
9. Click Deploy. First deploy takes 3–5 minutes (pip install + Whisper download).
10. Test: `curl https://[your-app].onrender.com/health`

**Render free tier cold start:** The free instance sleeps after 15 minutes of inactivity and takes ~30 seconds to wake up on the next request. For portfolio demos, warn your recruiter: "The free tier cold-starts after inactivity — if you get a slow first response, wait 30 seconds." This is a known trade-off you document in the README. Optionally, use a free uptime monitor (UptimeRobot, free tier) to ping `/health` every 14 minutes and prevent sleeping — add the UptimeRobot setup instructions to your README.

---

### Step 7.5 — Celery worker (two free options — pick one)

**The problem:** WavLM + Whisper load ~1.2GB of model weights into RAM. Railway's free tier only gives 512MB, which causes OOM kills. Two solutions:

---

**Option A: Railway with model quantization (recommended for always-on demo)**

Quantize both models to fit within 512MB. This slightly reduces accuracy but is acceptable for a portfolio demo, and the trade-off is a great interview talking point.

Add to `requirements.txt`:
```
optimum==1.19.1
```

Create `backend/scripts/quantize_models.py`:
```python
"""
Quantize WavLM and download Whisper tiny for memory-constrained deployment.
Run once during Docker build: python scripts/quantize_models.py
"""
from optimum.onnxruntime import ORTModelForAudioClassification
from transformers import AutoFeatureExtractor
import whisper
import os

print("Downloading Whisper tiny (39MB)...")
whisper.load_model("tiny")  # ~39MB — fits comfortably in 512MB

print("Loading WavLM for ONNX export...")
model_id = "ml/models/wavlm_classifier"  # Your fine-tuned model
if os.path.exists(model_id):
    ort_model = ORTModelForAudioClassification.from_pretrained(
        model_id, export=True
    )
    ort_model.save_pretrained("ml/models/wavlm_onnx")
    print("WavLM exported to ONNX — ~4x smaller, ~2x faster on CPU.")
else:
    print(f"Model not found at {model_id} — skipping ONNX export.")
```

Update the Celery worker's model loading in `ml/inference.py` to load the ONNX model when `wavlm_onnx/` exists, falling back to the original PyTorch model.

**Railway deployment:**
1. [railway.app](https://railway.app) → Sign up with GitHub (required for free tier — 500 hours/month) → New Project → Deploy from GitHub Repo.
2. Select your repo → root directory: `backend/`.
3. **Custom Start Command:**
   ```
   celery -A app.services.celery_app worker --loglevel=info -Q ml_queue --concurrency=1
   ```
4. Add the same environment variables as the Render API service.
5. Railway auto-detects Python and runs `pip install -r requirements.txt`.

> Railway free tier: 500 hours/month = ~16 hours/day. For a portfolio demo this is more than sufficient. The worker sleeps when there are no tasks, so hours are consumed only when actively processing.

---

**Option B: Local worker + cloud API (recommended if Option A is too complex)**

Run the Celery worker on your own laptop. The FastAPI API lives on Render and connects to the same Upstash Redis and Supabase PostgreSQL. The worker connects to the same services from your machine.

```bash
# On your laptop, in the backend/ directory:
export DATABASE_URL="postgresql+asyncpg://postgres:[PASSWORD]@[HOST]:6543/postgres"
export CELERY_BROKER_URL="rediss://:[PASSWORD]@[HOST]:[PORT]"
export CELERY_RESULT_BACKEND="rediss://:[PASSWORD]@[HOST]:[PORT]"
export ENCRYPTION_KEY="[your key]"
# ... other env vars

celery -A app.services.celery_app worker --loglevel=info -Q ml_queue --concurrency=1
```

The worker connects to the cloud Redis broker, picks up tasks that the cloud API enqueues, runs your ML models locally (full RAM available), and writes results back to the cloud PostgreSQL.

**For live demos:** Keep your laptop open and the worker running. For recruiter demos, start the worker 5 minutes beforehand. This is honest — document it in the README as "ML inference runs on a local worker due to free-tier memory constraints; a production deployment would use a dedicated 2GB instance."

**For an always-on demo without your laptop:** Set up the worker on **Google Colab**:
```python
# In a Colab cell:
!pip install -r /content/voicejournal/backend/requirements.txt -q
import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://...'
os.environ['CELERY_BROKER_URL'] = 'rediss://...'
# ... set all env vars
!cd /content/voicejournal/backend && celery -A app.services.celery_app worker --loglevel=info -Q ml_queue --concurrency=1
```
Colab gives you a free T4 GPU (15GB RAM), which also dramatically speeds up WavLM inference. Keep the tab open; Colab sessions last 12 hours.

---

### Step 7.6 — Frontend (Vercel — free forever)

1. [vercel.com](https://vercel.com) → Sign up with GitHub → New Project → import your GitHub repo → set root to `frontend/`.
2. **Framework Preset:** Vite
3. **Environment Variables:**
   ```
   VITE_API_URL=https://[your-app].onrender.com
   VITE_WS_URL=wss://[your-app].onrender.com
   ```
4. Deploy. Vercel auto-deploys on every push to `main`.
5. Your public URL: `https://voicejournal-[hash].vercel.app`. You can rename this in Project Settings → Domains.

---

### Step 7.7 — Keep Render API awake with UptimeRobot (free)

Render's free tier sleeps after 15 minutes. For demos, prevent this:

1. [uptimerobot.com](https://uptimerobot.com) → Sign up free → Add New Monitor.
2. Monitor Type: HTTP(s) → Friendly Name: `VoiceJournal API` → URL: `https://[your-app].onrender.com/health` → Monitoring Interval: 5 minutes.
3. Click Create Monitor. UptimeRobot pings your `/health` endpoint every 5 minutes, keeping Render awake 24/7.

Add to README:
> The API is kept alive with UptimeRobot pings every 5 minutes. On Render's free tier, without this, the first request after 15 minutes of inactivity takes ~30 seconds (cold start).

---

### Step 7.8 — Configure GitHub Actions deploy step

Update `.github/workflows/ci.yml` deploy job:

```yaml
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - name: Trigger Render deploy (API)
        run: curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"

      - name: Trigger Railway deploy (Celery worker) — only if using Option A
        if: env.RAILWAY_TOKEN != ''
        run: |
          npm install -g @railway/cli
          railway up --service celery-worker
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

Get Render deploy hook: your Render service → Settings → Deploy Hooks → copy URL → add as `RENDER_DEPLOY_HOOK_URL` in GitHub Secrets.

---

### Step 7.9 — Post-deployment smoke test

```bash
export BASE_URL="https://[your-app].onrender.com"

# Health (if this fails, wait 30s for cold start and retry)
curl -f $BASE_URL/health

# Register a test user
curl -X POST $BASE_URL/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"smoketest123","role":"patient"}'

# Login and capture token
TOKEN=$(curl -s -X POST $BASE_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"smoketest123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Authenticated request
curl -f -H "Authorization: Bearer $TOKEN" $BASE_URL/auth/me

# Check Prometheus metrics are exposed
curl -f $BASE_URL/metrics | head -5

echo "All smoke tests passed."
```

**Acceptance criteria for Phase 7:**
- [ ] `https://[your-app].onrender.com/health` returns `{"status":"ok","db":"ok","redis":"ok"}` from the public internet.
- [ ] `https://voicejournal-[hash].vercel.app` loads the React app.
- [ ] Demo clinician login works and shows the pre-seeded patient data.
- [ ] Submitting a journal entry returns `202 Accepted` and the Celery worker picks it up.
- [ ] Mood score appears on the dashboard within 60 seconds of submission (worker processes it).
- [ ] Risk alert on the clinician dashboard appears in real time (test with seeded demo data).
- [ ] UptimeRobot shows green uptime for the API.
- [ ] GitHub Actions CI badge on the README is green.
- [ ] Vercel re-deploys automatically when you push a commit to `main`.
- [ ] Audio files are retrievable from Cloudflare R2 (check the R2 dashboard — objects should appear after a journal submission).

---

## Phase 8 — README and Portfolio Presentation

**Goal:** The README is a technical cover letter. A recruiter or engineer should be able to read it in 3 minutes and understand exactly what was built, why it's impressive, and how to try it.

### Step 8.1 — Write `README.md` in the project root

Structure:

```markdown
# VoiceJournal

[![CI](https://github.com/[YOUR_USERNAME]/voicejournal/actions/workflows/ci.yml/badge.svg)](...)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://voicejournal.vercel.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> AI-powered clinical audio mood journal — record your voice, get back your emotional state, powered by WavLM + DistilRoBERTa score fusion.

[Live Demo](https://voicejournal.vercel.app) · [API Docs](https://[your-app].onrender.com/docs) · [Demo Video](https://loom.com/[YOUR_LINK])

**Demo credentials:**
- Clinician: `clinician@demo.com` / `demo1234`
- Patient 1 (risk alert active): `patient1@demo.com` / `demo1234`
- Patient 2 (stable): `patient2@demo.com` / `demo1234`

## What it does
[2-3 paragraph description]

## Architecture
[Mermaid diagram — see Step 8.2]

## ML Pipeline
[Explain WavLM fine-tuning, Whisper translate mode, 60/40 fusion, risk alert logic]

## The Hinglish TTS Trick
[Explain the dual-payload pattern — this is always a conversation starter]

## Tech Stack
[Table: Layer | Technology | Why]

## Technical Decisions
[3-4 short paragraphs explaining non-obvious choices: why asyncpg, why Redis pub/sub vs polling, why 60/40 weighting, why Whisper tiny vs base]

## Running Locally
[make up, make seed, open localhost:3000]

## Running Tests
[make test]

## Known Limitations & Future Work
- Whisper tiny model trades accuracy for speed on free-tier CPU
- TURN server not configured for WebRTC (not applicable — no peer audio)
- Would add TimescaleDB for time-series queries at production scale

## License
MIT
```

### Step 8.2 — Add Mermaid architecture diagram

Add this to the README under "Architecture":

````markdown
```mermaid
graph TD
    A[Patient Browser\nWeb Audio API] -->|multipart POST| B[FastAPI]
    C[Clinician Browser] -->|WebSocket| B
    B -->|202 Accepted| A
    B -->|enqueue task| D[Redis\nCelery Broker]
    D --> E[Celery Worker]
    E -->|Whisper| F[Transcription\n+ Translation]
    E -->|librosa| G[DSP Features\npitch · RMS · rate]
    E -->|WavLM| H[Acoustic Emotion\nfine-tuned]
    F --> I[DistilRoBERTa\nText Sentiment]
    G --> J[Score Fusion\n60% acoustic + 40% text]
    H --> J
    I --> J
    J -->|write result| K[(PostgreSQL)]
    J -->|publish| D
    D -->|fan-out| B
    B -->|push notification| C
    B -->|save encrypted audio| L[AWS S3\nAES-256]
```
````

### Step 8.3 — Record a Loom demo video

Record a 90-second Loom demo in this exact sequence:
1. Log in as the clinician → show the patient list with risk alert badge (5s)
2. Switch to patient1 tab → show their 14-day mood arc chart (5s)
3. Click the risk alert entry → show the AI feedback breakdown (pitch variance, valence score, emotion label) (10s)
4. Open the AI chat → show the context-aware response referencing actual mood data (15s)
5. Open the Hinglish avatar → say something in Hindi → show the Devanagari TTS trick in action (15s)
6. Switch back to clinician tab → open a new patient2 tab → record a voice entry → watch the real-time notification appear on the clinician dashboard live (30s)
7. Show the GitHub repo: green CI badge, clean commit history, Mermaid diagram (10s)

**Acceptance criteria for Phase 8:**
- [ ] README renders correctly on GitHub (Mermaid diagram visible, badges green, links work).
- [ ] Demo credentials login and show populated data.
- [ ] Loom video is under 2 minutes and shows the real-time notification flow live.
- [ ] API docs at `/docs` are fully populated with descriptions for every endpoint.
- [ ] GitHub repo has: pinned, description set, topics tagged (`fastapi`, `celery`, `websockets`, `machine-learning`, `pytorch`, `redis`, `healthcare`).

---

## Resume Bullets (copy these after completing all phases)

```
VoiceJournal | FastAPI · Celery · WavLM · Whisper · React · PostgreSQL · Redis · Docker · Cloudflare R2
github.com/[YOU]/voicejournal  ·  voicejournal.vercel.app  ·  [Loom Demo]

• Architected a multimodal ML pipeline fusing fine-tuned WavLM acoustic emotion scores
  (60%) with DistilRoBERTa text sentiment (40%); Whisper auto-translates 10+ languages
  to English enabling universal journaling without language-specific models.

• Built real-time clinician risk alerts via Redis pub/sub fan-out over WebSocket; risk
  flags propagate from Celery worker to clinician dashboard in <2s without polling.

• Implemented HIPAA-inspired clinical security: AES-256 audio encryption at rest
  (Cloudflare R2), JWT refresh token rotation, RBAC with per-access audit logging,
  and rate-limited auth (slowapi + Redis).

• Shipped a Hinglish TTS dual-payload system: LLM outputs Romanized Hinglish for UI
  display + pure Devanagari for MS Edge TTS, achieving native-quality Hindi speech
  synthesis with correct gender-conjugated grammar.
```

---

## Quick Reference — Phase Completion Checklist

| Phase | Description | Key Deliverable | Done? |
|---|---|---|---|
| 1 | PostgreSQL migration | No SQLite, async SQLAlchemy, Alembic | ☐ |
| 2 | Redis + WebSocket pub/sub | Real-time notifications, clinician alert | ☐ |
| 3 | Docker Compose | `make up` starts full stack, demo seed | ☐ |
| 4 | Tests + CI/CD | 65%+ coverage, green Actions badge | ☐ |
| 5 | Context-aware chat + logging | Mood data in LLM prompt, structlog | ☐ |
| 6 | Production hardening | Rate limiting, S3, CORS, security audit | ☐ |
| 7 | Deployment | Live URL, smoke tests pass, auto-deploy | ☐ |
| 8 | README + portfolio | Mermaid diagram, Loom demo, badges | ☐ |

**Total estimated time: 8–12 focused days of part-time work.**
