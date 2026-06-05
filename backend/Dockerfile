FROM python:3.11-slim

# Install system dependencies, including ffmpeg for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Install PyTorch CPU Version (to drastically reduce image size for Render Free Tier)
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 2. Copy both requirements files
COPY backend/requirements.txt ./backend/
COPY ml/requirements.txt ./ml/

# 3. Install dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir -r ml/requirements.txt

# 4. Copy the code for both backend and ml modules
COPY backend/ ./backend/
COPY ml/ ./ml/

# Ensure python can find both the `app` folder (inside backend) and the `ml` folder (in root)
ENV PYTHONPATH="/app/backend:/app"

WORKDIR /app/backend

# Ensure start script is executable
RUN chmod +x start.sh

# Expose FastAPI port
EXPOSE 8000

# Run the startup script that boots both Uvicorn and Celery
CMD ["./start.sh"]
