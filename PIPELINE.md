# VoiceJournal: End-to-End Clinical Architecture & Pipeline

This document explains the complete, start-to-finish data flow and architecture of **VoiceJournal** — an AI-powered clinical audio diary and depression-risk monitoring tool.

The entire system is designed as a **B2B Healthcare SaaS** platform, achieving research-grade multimodal ML analysis while enforcing strict clinical security standards.

---

## 1. The User Interface (Frontend)
**Tech Stack:** React 18, Vite, TailwindCSS (v3), Recharts, jsPDF

* **Multi-Tenant Routing:** The frontend handles two distinct roles:
  * **Patients:** See their personal mood arcs, record audio, and review insights.
  * **Clinicians:** See a unified dashboard of all their onboarded patients, Risk Alert badges, and advanced acoustic overlays.
* **Recording:** The patient clicks the microphone icon. The **Web Audio API** captures the stream and renders a real-time waveform on an HTML5 `<canvas>`.
* **Submission:** Audio chunks are packaged into a binary Blob (`.webm` or `.wav`) and sent to the FastAPI backend via a `multipart/form-data` POST request.
* **Reporting:** Clinicians can trigger a one-click PDF export (`jsPDF` + `html2canvas`) to generate a clinical summary report for patient files.

---

## 2. API & Storage (Backend)
**Tech Stack:** FastAPI, SQLite, SQLAlchemy, python-jose (JWT)

* **Role-Based Access Control (RBAC):** The backend verifies JWT access tokens and enforces strict role separation. Patients can only access their own data. Clinicians can only access patients explicitly bound to them via an **Invite Code**.
* **HIPAA-Style Audit Logging:** Every time a clinician pulls a patient's transcript or audio, an `AuditLog` row is created, tracking the `clinician_id`, `patient_id`, action type, and timestamp.
* **Secure Storage:** The backend encrypts the incoming audio using **AES-256 (Fernet)** and saves it to the local filesystem (simulating a secure S3 bucket).
* **Offloading:** The backend hands the `entry_id` off to **Celery** (a background task queue) and immediately returns a `202 Accepted` response.

---

## 3. Multimodal ML & DSP Inference (Async Worker)
**Tech Stack:** Celery, PyTorch, HuggingFace Transformers, Librosa

This is the core intelligence of the application. The Celery worker pre-loads all deep learning models into RAM at startup to eliminate latency. When it receives an `analyze_mood` task:

1. **Decryption:** The worker decrypts the audio file from disk to a temporary location.
2. **Deterministic Acoustic Extraction (DSP):**
   * **Librosa** extracts explainable acoustic features from the raw waveform:
     * **Pitch Variance (F0):** To measure "flat affect" (a core indicator of depression).
     * **Energy Variance (RMS):** To measure lethargy vs. agitation.
     * **Speech Rate:** Words/syllables per second.
3. **Speech-to-Text (Transcription & Translation):**
   * The audio is passed through **OpenAI's Whisper** (Small/Tiny model running locally).
   * **Universal Translation:** Whisper is explicitly configured with `task="translate"`. This means users can journal in Hindi, Spanish, or French, and Whisper will automatically transcribe and translate the audio to English in the background so that the English-only Emotion AI models can process it seamlessly.
4. **Acoustic Emotion Recognition (Deep Learning):**
   * The audio is passed through our **Fine-tuned WavLM-Base-Plus** model (trained separately on an A16 GPU using RAVDESS).
   * WavLM extracts a high-level emotion label (e.g., "sad", "happy") and an acoustic valence score.
5. **Text Sentiment Analysis:**
   * The transcript is passed into **DistilRoBERTa** (`j-hartmann/emotion-english-distilroberta-base`) to extract a textual valence score.
6. **Score Fusion & Risk Alert Logic:**
   * The system combines the scores (`60% Acoustic Valence + 40% Text Valence`).
   * **Clinical Risk Alert:** The system queries the database for the patient's last 3 entries. If all 3 have a valence `< 0.3`, OR if the current pitch variance is exceptionally low (severe flat affect), the entry is flagged with `is_risk_alert = True`.
   * All metrics are saved to the database.

---

## 4. Real-time Notification (WebSockets)
**Tech Stack:** FastAPI WebSockets

* While Celery processes the audio, the frontend maintains an open WebSocket connection.
* Once Celery finishes, the backend pushes a JSON message `{"status": "completed"}` through the WebSocket, instantly updating the patient's and clinician's dashboards without page reloads.

---

## 5. Conversational AI Companions (Smart Therapists)
**Tech Stack:** Llama 3.1 (Groq API), Microsoft Edge TTS, React

Beyond just journaling, users can chat interactively with the AI to reflect on their mood data.
* **Empathetic Personas:** The AI assumes the role of a highly empathetic therapist and best friend. There are 6 distinct avatars/voices available:
  * 4 English voices (e.g., Jenny, Aria, Sonia, Steffan) with distinct personalities.
  * 2 Indian voices (Kiaa, Veer).
* **Continuous Memory:** The frontend sends the entire chat history with every request, allowing the LLM to retain unlimited context within the session.
* **The "Hinglish" Dual-Payload Trick:** When an Indian avatar is selected, the LLM is instructed via a strict system prompt to output a JSON object containing two versions of the response:
  1. `answer`: A casual, urban "Hinglish" response for the UI display (e.g., *"Aap kaise ho?"*).
  2. `tts_text`: The exact same response translated into pure Devanagari script (e.g., *"आप कैसे हो?"*).
  * *Why?* Native Hindi Text-to-Speech models sound robotic when forced to read Roman characters. By passing the hidden Devanagari text to the MS Edge TTS engine, the avatars speak with flawless, human-like fluency and correct emotional prosody, while the user reads the friendly Romanized text.
* **Gender-Aware Grammar:** The prompt explicitly tells the LLM the gender of the selected Indian avatar (Kiaa=Female, Veer=Male) so that Hindi verbs are conjugated perfectly (e.g., "Main sun *rahi* hoon" vs "Main sun *raha* hoon").

---

## Summary of the "Production-Ready" Standards Met:
1. **Clinical Security:** AES-256 for data-at-rest, strictly enforced RBAC for clinicians vs. patients, and HIPAA-style audit logging.
2. **Explainable AI:** Fusing deterministic DSP features (pitch/energy via Librosa) with Deep Learning embeddings (WavLM) allows clinicians to actually understand *why* the AI flagged a patient.
3. **Scalability:** Heavy ML and DSP tasks are offloaded to asynchronous Celery workers. The REST API never blocks.
4. **Workflow Completeness:** From Invite Codes to PDF Report generation, the platform mimics real-world B2B health tech SaaS applications.

---

## 6. Directory Structure & Codebase Overview

The repository is modularized into three distinct domains: `backend`, `frontend`, and `ml`.

### `/frontend` (React + Vite)
The user-facing portal for both Patients and Clinicians.
* `src/components/`
  * `AudioRecorder.tsx`: The heart of patient input. Handles Web Audio API streaming, real-time waveform visualization, and POSTing binary blobs.
  * `JournalChat.tsx`: The conversational AI interface. Handles speech-to-text input, dual-payload Hinglish parsing, and streams Microsoft Edge TTS audio blobs.
  * `MoodGlobe.tsx` & `EmotionHeatmap.tsx`: Dynamic, CSS-animated visualizations of the user's emotional state over time.
  * `CrisisAlert.tsx`: A persistent warning banner that alerts clinicians when a patient triggers a deep-learning risk flag.
* `src/pages/`
  * `Dashboard.tsx`: Patient portal for journaling and personal insights.
  * `ClinicianDashboard.tsx`: Unified hub for therapists to review patient data, generate PDF reports, and monitor risk alerts.

### `/backend` (FastAPI)
The central nervous system linking the database, frontend, and ML workers.
* `app/api/`: RESTful endpoints.
  * `auth.py`: Handles JWT generation, login, and registration.
  * `journals.py`: Handles audio uploads, triggers Celery tasks, and manages the Groq LLM Chat/TTS interactions.
* `app/core/`: Security and configuration.
  * `security.py`: AES-256 encryption/decryption utilities for clinical audio data.
* `app/services/`: Background logic.
  * `celery_app.py`: Defines the async task queue.
  * `tasks.py`: The worker script that executes the multimodal ML pipeline.

### `/ml` (Machine Learning & DSP)
The research-grade audio and text analysis models.
* `inference.py`: The unified interface that Celery calls to run predictions. Uses Whisper for translation, Librosa for acoustic feature extraction, and WavLM/DistilRoBERTa for emotion.
* `models/`: Contains the model definitions and weights.
  * `wavlm_classifier.py`: Custom PyTorch wrapper around `microsoft/wavlm-base-plus`.
  * `sentiment_model.py`: HuggingFace pipeline for textual emotion extraction.
* `data/`: Scripts used to download and process the RAVDESS dataset for fine-tuning the WavLM model on an A16 GPU.

---

## 7. Zero-Cost Deployment Architecture (Production)

The entire production deployment is designed to be **100% Free** using modern PaaS providers and clever architecture.

### Backend + ML Worker (Render.com)
* Render's free tier allows a single Web Service. Running a separate Background Worker and Redis instance would incur costs.
* **The Single-Container Solution**: We created a custom Dockerfile and a `start.sh` entrypoint script. When Render boots the Web Service, `start.sh` launches **both** Uvicorn (FastAPI) and the Celery worker concurrently in the background. 
* **Zero-Cost Queuing**: Because they run in the exact same container, they share the same disk. This allows Celery to use the `filesystem://` broker (reading and writing tasks to `/tmp/celery-broker`), entirely eliminating the need for a costly Redis server.

### Database (Supabase)
* **PostgreSQL Serverless**: The application uses Supabase's free tier for its PostgreSQL database. 
* **Transaction Pooler**: Because serverless environments handle connections differently, we connect to Supabase via its built-in PgBouncer transaction pooler on port `6543`. This ensures the database doesn't run out of connections when Celery and FastAPI both scale up their connection pools.
* **Alembic Migrations**: Schema updates are managed purely via Alembic to keep the database perfectly synced with SQLAlchemy models.

### Frontend (Vercel)
* **Static Hosting**: The React + Vite frontend is compiled into pure static HTML/JS/CSS and deployed automatically to Vercel (or Netlify).
* **Environment Variables**: The frontend connects to the backend by reading `VITE_API_URL` from the Vercel environment.
