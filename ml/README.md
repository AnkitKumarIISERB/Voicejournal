# VoiceJournal — ML Training Pipeline

## Architecture Overview

This is a **multimodal emotion recognition system** that combines two signals to assess mood from voice recordings:

```
                 ┌──────────────────┐
                 │   Audio Input    │
                 │  (.wav / .mp3)   │
                 └────────┬─────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────▼─────────┐  ┌─────────▼─────────┐
    │   Whisper (local)  │  │  WavLM (trained)   │
    │   Transcription    │  │  Acoustic Emotion  │
    └─────────┬─────────┘  └─────────┬──────────┘
              │                       │
    ┌─────────▼──────────┐           │
    │  Text Sentiment    │           │
    │  (pre-trained,     │           │
    │   no training)     │           │
    └─────────┬──────────┘           │
              │                       │
              └───────────┬───────────┘
                          │
               ┌──────────▼──────────┐
               │   Combined Score    │
               │  (60% acoustic +   │
               │   40% text)        │
               └─────────────────────┘
```

## Models Used

| Model | Purpose | Source | Cost |
|---|---|---|---|
| `microsoft/wavlm-base-plus` | Acoustic emotion from raw audio | HuggingFace | **Free** |
| `openai/whisper-small` | Speech-to-text transcription | OpenAI (local) | **Free** |
| `j-hartmann/emotion-english-distilroberta-base` | Text emotion classification | HuggingFace | **Free** (pre-trained, no training needed) |

## Dataset

| Dataset | Purpose | Size | License | Cost |
|---|---|---|---|---|
| [RAVDESS](https://zenodo.org/record/1188976) | Train WavLM emotion classifier | 1440 files, 24 actors, 8 emotions | CC BY-NC-SA 4.0 | **Free** |

## Training on Your A16 GPU Server

```bash
# Step 1: Install dependencies
pip install -r requirements.txt

# Step 2: Download the RAVDESS dataset (215MB, free, no account needed)
python -m ml.data.download_ravdess --output_dir ./data/ravdess

# Step 3: Train WavLM emotion classifier
python -m ml.train \
    --data_dir ./data/ravdess \
    --output_dir ./checkpoints \
    --epochs 30 \
    --batch_size 16 \
    --lr 1e-4 \
    --freeze_base

# Step 4: Test inference on a sample file
python -c "
from ml.inference import VoiceJournalAnalyzer
analyzer = VoiceJournalAnalyzer(wavlm_checkpoint='./checkpoints/best_model')
result = analyzer.analyze('./data/ravdess/Actor_01/03-01-04-01-01-01-01.wav')
print(result)
"
```

## File Structure

```
ml/
├── __init__.py
├── requirements.txt
├── train.py                    # Main training script (WavLM fine-tuning)
├── inference.py                # Multimodal inference pipeline
├── models/
│   ├── __init__.py
│   ├── wavlm_classifier.py     # WavLM + classification head
│   └── sentiment_model.py      # Pre-trained text sentiment (no training)
├── data/
│   ├── __init__.py
│   ├── dataset.py              # RAVDESS PyTorch Dataset + DataLoader
│   └── download_ravdess.py     # Dataset download script
└── notebooks/
    └── (Colab training notebook — coming soon)
```

## Total Cost: $0

Every component is free and open-source. No API keys. No subscriptions. No cloud compute charges.
