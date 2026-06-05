"""
Download the RAVDESS dataset from Zenodo (100% free, no API key needed).

RAVDESS: Ryerson Audio-Visual Database of Emotional Speech and Song
- 1440 speech files from 24 professional actors (12 male, 12 female)
- 8 emotions: neutral, calm, happy, sad, angry, fearful, disgust, surprised
- License: CC BY-NC-SA 4.0 (free for research and portfolio projects)
- Source: https://zenodo.org/record/1188976

Usage:
    python -m ml.data.download_ravdess --output_dir ./data/ravdess
"""

import os
import zipfile
import argparse
from pathlib import Path
from urllib.request import urlretrieve


# Direct download links for each actor from Zenodo (all free, no auth)
RAVDESS_URLS = {
    f"Actor_{i:02d}": f"https://zenodo.org/record/1188976/files/Audio_Speech_Actors_01-24.zip"
    for i in range(1, 25)
}

# Single zip containing all actors
RAVDESS_ZIP_URL = "https://zenodo.org/record/1188976/files/Audio_Speech_Actors_01-24.zip"
RAVDESS_ZIP_SIZE_MB = 215


def download_ravdess(output_dir: str = "./data/ravdess") -> str:
    """
    Downloads and extracts the RAVDESS speech audio dataset.

    Args:
        output_dir: Directory to extract the dataset into.

    Returns:
        Path to the extracted dataset directory.
    """
    output_path = Path(output_dir)
    zip_path = output_path / "ravdess_speech.zip"

    # Check if already downloaded
    actor_dirs = list(output_path.glob("Actor_*"))
    if len(actor_dirs) >= 24:
        print(f"[✓] RAVDESS already downloaded at {output_path} ({len(actor_dirs)} actors found)")
        return str(output_path)

    output_path.mkdir(parents=True, exist_ok=True)

    print(f"[↓] Downloading RAVDESS dataset (~{RAVDESS_ZIP_SIZE_MB}MB)...")
    print(f"    Source: {RAVDESS_ZIP_URL}")
    print(f"    Destination: {zip_path}")

    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = min(100, downloaded * 100 // total_size) if total_size > 0 else 0
        print(f"\r    Progress: {pct}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)", end="", flush=True)

    urlretrieve(RAVDESS_ZIP_URL, str(zip_path), reporthook=_progress)
    print("\n[✓] Download complete.")

    print("[⚙] Extracting...")
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        zf.extractall(str(output_path))

    # Clean up zip
    zip_path.unlink()

    # Move files from nested dir if needed
    nested = output_path / "Audio_Speech_Actors_01-24"
    if nested.exists():
        for actor_dir in nested.iterdir():
            actor_dir.rename(output_path / actor_dir.name)
        nested.rmdir()

    actor_count = len(list(output_path.glob("Actor_*")))
    file_count = len(list(output_path.rglob("*.wav")))
    print(f"[✓] Extracted {file_count} audio files from {actor_count} actors to {output_path}")

    return str(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download RAVDESS dataset")
    parser.add_argument("--output_dir", type=str, default="./data/ravdess")
    args = parser.parse_args()
    download_ravdess(args.output_dir)
