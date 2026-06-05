FROM python:3.11-slim

# Install system dependencies, including ffmpeg for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure start script is executable
RUN chmod +x start.sh

# Expose FastAPI port
EXPOSE 8000

# Run the startup script that boots both Uvicorn and Celery
CMD ["./start.sh"]
