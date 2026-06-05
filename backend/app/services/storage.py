"""
Local file storage service.

Replaces S3 for development. Stores audio files on the local filesystem
with AES-256 encryption. Zero cost, zero cloud dependency.

In production, swap this for the S3 implementation by changing the
STORAGE_BACKEND env var. The interface is identical.
"""

import os
import uuid
from pathlib import Path
from cryptography.fernet import Fernet
from app.core.config import settings


# Storage directory — created automatically
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Generate or load encryption key from env
# In production, this MUST come from an env var, never hardcoded
_ENCRYPTION_KEY = settings.ENCRYPTION_KEY
_fernet = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


def save_audio(file_bytes: bytes, user_id: int, original_filename: str) -> str:
    """
    Save an uploaded audio file to local storage with encryption.

    Args:
        file_bytes: Raw audio bytes from the upload.
        user_id: Owner's user ID (used for path isolation).
        original_filename: Original filename for extension detection.

    Returns:
        storage_key: A unique key to retrieve the file later.
    """
    # Generate a unique key
    ext = Path(original_filename).suffix or ".wav"
    storage_key = f"user_{user_id}/{uuid.uuid4().hex}{ext}"

    # Create user directory
    file_path = UPLOAD_DIR / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Encrypt and write
    encrypted = _fernet.encrypt(file_bytes)
    file_path.write_bytes(encrypted)

    return storage_key


def load_audio(storage_key: str) -> bytes:
    """
    Load and decrypt an audio file from local storage.

    Args:
        storage_key: The key returned by save_audio.

    Returns:
        Decrypted audio bytes.
    """
    file_path = UPLOAD_DIR / storage_key
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {storage_key}")

    encrypted = file_path.read_bytes()
    return _fernet.decrypt(encrypted)


def get_audio_path_decrypted(storage_key: str) -> str:
    """
    Decrypt an audio file to a temp location and return the path.
    Used by the ML pipeline which needs a file path, not raw bytes.

    The caller is responsible for cleaning up the temp file.
    """
    import tempfile

    audio_bytes = load_audio(storage_key)
    ext = Path(storage_key).suffix or ".wav"

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(audio_bytes)
    tmp.close()

    return tmp.name


def delete_audio(storage_key: str) -> bool:
    """Delete an audio file from storage. Returns True if deleted."""
    file_path = UPLOAD_DIR / storage_key
    if file_path.exists():
        file_path.unlink()
        return True
    return False
