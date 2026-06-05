#!/bin/bash

# Exit on error
set -e

echo "Starting VoiceJournal Backend (Single-Container Mode)..."

# Ensure Celery filesystem broker directories exist
echo "Setting up filesystem broker..."
mkdir -p /tmp/celery-broker/out
mkdir -p /tmp/celery-broker/processed
mkdir -p /tmp/celery-results
chmod -R 777 /tmp/celery-broker
chmod -R 777 /tmp/celery-results

# Run Alembic migrations to ensure DB is up to date
echo "Running database migrations..."
alembic upgrade head

# Start Celery worker in the background
echo "Starting Celery worker..."
celery -A app.services.celery_app worker --loglevel=info --concurrency=1 &

# Start Uvicorn in the foreground (Render uses the PORT environment variable)
echo "Starting FastAPI server on port ${PORT:-10000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
