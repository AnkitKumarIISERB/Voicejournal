"""
Audio dataset loaders for speech emotion recognition training.

Primary dataset: RAVDESS (Ryerson Audio-Visual Database of Emotional Speech and Song)
- 1440 audio files from 24 professional actors
- 8 emotions: neutral, calm, happy, sad, angry, fearful, disgust, surprised
- Free to use (CC BY-NC-SA 4.0)
- Available on HuggingFace or direct download from Zenodo

This module handles downloading, caching, preprocessing, and batching.
"""

import os
import torch
import librosa
import numpy as np
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from transformers import AutoFeatureExtractor
from typing import Tuple, Optional


# RAVDESS filename encoding:
# Modality-VocalChannel-Emotion-Intensity-Statement-Repetition-Actor
# Emotion codes: 01=neutral, 02=calm, 03=happy, 04=sad, 05=angry, 06=fearful, 07=disgust, 08=surprised
RAVDESS_EMOTION_MAP = {
    "01": 0,  # neutral
    "02": 1,  # calm
    "03": 2,  # happy
    "04": 3,  # sad
    "05": 4,  # angry
    "06": 5,  # fearful
    "07": 6,  # disgust
    "08": 7,  # surprised
}


class RAVDESSDataset(Dataset):
    """
    PyTorch Dataset for RAVDESS audio emotion recognition.

    Expects the RAVDESS dataset to be organized as:
        data_dir/
            Actor_01/
                03-01-01-01-01-01-01.wav
                ...
            Actor_02/
                ...

    Each audio file is loaded, resampled to 16kHz, and processed through
    the WavLM feature extractor.
    """

    def __init__(
        self,
        data_dir: str,
        feature_extractor: AutoFeatureExtractor,
        max_duration: float = 5.0,
        sample_rate: int = 16000,
        augment: bool = False,
    ):
        """
        Args:
            data_dir: Root directory containing Actor_XX subdirectories.
            feature_extractor: WavLM's feature extractor for preprocessing.
            max_duration: Maximum audio duration in seconds (clips are padded/truncated).
            sample_rate: Target sample rate (WavLM requires 16kHz).
        """
        self.feature_extractor = feature_extractor
        self.sample_rate = sample_rate
        self.max_length = int(max_duration * sample_rate)
        self.augment = augment
        self.sample_rate = sample_rate
        self.max_length = int(max_duration * sample_rate)

        self.samples = []
        data_path = Path(data_dir)

        if not data_path.exists():
            raise FileNotFoundError(
                f"RAVDESS data directory not found: {data_dir}\n"
                f"Download it from: https://zenodo.org/record/1188976\n"
                f"Or run: python -m ml.data.download_ravdess"
            )

        for wav_file in sorted(data_path.rglob("*.wav")):
            filename = wav_file.stem
            parts = filename.split("-")
            if len(parts) >= 3:
                emotion_code = parts[2]
                if emotion_code in RAVDESS_EMOTION_MAP:
                    self.samples.append({
                        "path": str(wav_file),
                        "label": RAVDESS_EMOTION_MAP[emotion_code],
                        "actor": parts[-1],
                    })

        if len(self.samples) == 0:
            raise ValueError(f"No valid .wav files found in {data_dir}")

        print(f"[RAVDESSDataset] Loaded {len(self.samples)} samples from {data_dir}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        sample = self.samples[idx]

        # Load audio at 16kHz mono
        waveform, _ = librosa.load(sample["path"], sr=self.sample_rate, mono=True)

        # Pad or truncate to fixed length
        if len(waveform) > self.max_length:
            waveform = waveform[: self.max_length]
        elif len(waveform) < self.max_length:
            waveform = np.pad(waveform, (0, self.max_length - len(waveform)))

        # Apply augmentation (Time Cutout and Noise injection)
        if self.augment:
            # Add slight gaussian noise
            noise = np.random.normal(0, 0.005, waveform.shape)
            waveform = waveform + noise
            
            # Time Cutout (SpecAugment equivalent for 1D raw audio)
            # Zero out 1 to 3 random segments of 50ms to 200ms
            num_masks = np.random.randint(1, 4)
            for _ in range(num_masks):
                mask_len = np.random.randint(int(0.05 * self.sample_rate), int(0.2 * self.sample_rate))
                start_idx = np.random.randint(0, self.max_length - mask_len)
                waveform[start_idx:start_idx+mask_len] = 0.0

        # Process through WavLM feature extractor
        inputs = self.feature_extractor(
            waveform,
            sampling_rate=self.sample_rate,
            return_tensors="pt",
            padding=False,
        )

        return {
            "input_values": inputs["input_values"].squeeze(0),
            "labels": torch.tensor(sample["label"], dtype=torch.long),
        }


def create_dataloaders(
    data_dir: str,
    feature_extractor: AutoFeatureExtractor,
    batch_size: int = 16,
    val_split: float = 0.2,
    max_duration: float = 5.0,
    num_workers: int = 4,
    seed: int = 42,
) -> Tuple[DataLoader, DataLoader]:
    """
    Creates train and validation DataLoaders from the RAVDESS dataset.

    Uses actor-based splitting: actors 1-19 for training, 20-24 for validation.
    This ensures no data leakage (the model never hears a validation actor during training).
    """
    train_dataset = RAVDESSDataset(
        data_dir=data_dir,
        feature_extractor=feature_extractor,
        max_duration=max_duration,
        augment=True,
    )
    val_dataset = RAVDESSDataset(
        data_dir=data_dir,
        feature_extractor=feature_extractor,
        max_duration=max_duration,
        augment=False,
    )

    # Actor-based split (no leakage)
    train_indices = [i for i, s in enumerate(train_dataset.samples) if int(s["actor"]) <= 19]
    val_indices = [i for i, s in enumerate(val_dataset.samples) if int(s["actor"]) > 19]

    train_subset = torch.utils.data.Subset(train_dataset, train_indices)
    val_subset = torch.utils.data.Subset(val_dataset, val_indices)

    print(f"[Split] Train: {len(train_subset)} | Val: {len(val_subset)}")

    train_loader = DataLoader(
        train_subset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_subset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )

    return train_loader, val_loader
