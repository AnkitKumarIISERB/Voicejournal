"""
VoiceJournal — WavLM Emotion Classifier Training Script

Fine-tunes microsoft/wavlm-base-plus on the RAVDESS speech emotion dataset.
Designed to run on your A16 GPU server or any CUDA-capable machine.

Usage (on your A16 server):
    # 1. Download the dataset (free, ~215MB)
    python -m ml.data.download_ravdess --output_dir ./data/ravdess

    # 2. Train the model
    python -m ml.train \
        --data_dir ./data/ravdess \
        --output_dir ./checkpoints \
        --epochs 30 \
        --batch_size 16 \
        --lr 1e-4 \
        --freeze_base

Cost: $0 (runs on your own hardware, uses free open-source data and models)
"""

import os
import argparse
import json
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import classification_report, confusion_matrix
from tqdm import tqdm
from pathlib import Path

from ml.models.wavlm_classifier import WavLMEmotionClassifier, EMOTION_LABELS
from ml.data.dataset import create_dataloaders


def train_one_epoch(model, loader, criterion, optimizer, device, epoch):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    pbar = tqdm(loader, desc=f"Epoch {epoch} [Train]")
    for batch in pbar:
        input_values = batch["input_values"].to(device)
        labels = batch["labels"].to(device)

        optimizer.zero_grad()
        logits = model(input_values)
        loss = criterion(logits, labels)
        loss.backward()

        # Gradient clipping to prevent explosion
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()

        total_loss += loss.item()
        preds = logits.argmax(dim=-1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{correct/total:.4f}")

    return total_loss / len(loader), correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device, epoch):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []

    pbar = tqdm(loader, desc=f"Epoch {epoch} [Val]  ")
    for batch in pbar:
        input_values = batch["input_values"].to(device)
        labels = batch["labels"].to(device)

        logits = model(input_values)
        loss = criterion(logits, labels)

        total_loss += loss.item()
        all_preds.extend(logits.argmax(dim=-1).cpu().tolist())
        all_labels.extend(labels.cpu().tolist())

    avg_loss = total_loss / len(loader)
    accuracy = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)
    from sklearn.metrics import f1_score
    f1 = f1_score(all_labels, all_preds, average="macro")

    return avg_loss, accuracy, f1, all_preds, all_labels


def main():
    parser = argparse.ArgumentParser(description="Train WavLM Emotion Classifier")
    parser.add_argument("--data_dir", type=str, default="./data/ravdess", help="Path to RAVDESS dataset")
    parser.add_argument("--output_dir", type=str, default="./checkpoints", help="Where to save model weights")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--freeze_base", action="store_true", help="Freeze WavLM encoder weights")
    parser.add_argument("--max_duration", type=float, default=5.0, help="Max audio duration in seconds")
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Reproducibility
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Device] Using: {device}")
    if torch.cuda.is_available():
        print(f"[GPU]    {torch.cuda.get_device_name(0)}")

    # Initialize model
    print("[Model]  Loading microsoft/wavlm-base-plus...")
    model = WavLMEmotionClassifier(
        model_name="microsoft/wavlm-base-plus",
        num_labels=len(EMOTION_LABELS),
        freeze_base=args.freeze_base,
        dropout=0.3,
    ).to(device)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[Params] Trainable: {trainable_params:,} / Total: {total_params:,}")

    # Create data loaders
    print(f"[Data]   Loading RAVDESS from {args.data_dir}...")
    train_loader, val_loader = create_dataloaders(
        data_dir=args.data_dir,
        feature_extractor=model.feature_extractor,
        batch_size=args.batch_size,
        max_duration=args.max_duration,
        num_workers=args.num_workers,
    )

    # Training setup
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=0.01,
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)

    # Training loop
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    best_val_f1 = 0.0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "val_f1": []}

    print(f"\n{'='*60}")
    print(f"Starting training for {args.epochs} epochs")
    print(f"{'='*60}\n")

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device, epoch)
        val_loss, val_acc, val_f1, val_preds, val_labels = evaluate(model, val_loader, criterion, device, epoch)
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)

        lr = optimizer.param_groups[0]["lr"]
        print(f"\n  Epoch {epoch}/{args.epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} F1: {val_f1:.4f} | "
              f"LR: {lr:.2e}")

        # Save best model
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            save_path = output_path / "best_model"
            save_path.mkdir(exist_ok=True)
            torch.save(model.state_dict(), save_path / "wavlm_emotion_classifier.pt")
            model.feature_extractor.save_pretrained(str(save_path))
            print(f"  ✓ New best model saved (val_f1={val_f1:.4f})")

    # Final evaluation report
    print(f"\n{'='*60}")
    print(f"Training Complete! Best Val Macro F1: {best_val_f1:.4f}")
    print(f"{'='*60}\n")

    # Classification report on best model
    _, _, _, final_preds, final_labels = evaluate(model, val_loader, criterion, device, "Final")
    report = classification_report(final_labels, final_preds, target_names=EMOTION_LABELS, digits=4)
    print("\nClassification Report:\n")
    print(report)

    # Save training history
    with open(output_path / "training_history.json", "w") as f:
        json.dump(history, f, indent=2)

    # Save classification report
    with open(output_path / "classification_report.txt", "w") as f:
        f.write(report)

    print(f"\n[✓] All artifacts saved to {output_path}/")
    print(f"    - best_model/wavlm_emotion_classifier.pt")
    print(f"    - training_history.json")
    print(f"    - classification_report.txt")


if __name__ == "__main__":
    main()


'''
============================================================
Training Complete! Best Val Macro F1: 0.8044
============================================================

Epoch Final [Val]  : 100%|_____________________________________________________________________________________________________________________________________________________| 19/19 [00:11<00:00,  1.71it/s]

Classification Report:

              precision    recall  f1-score   support

     neutral     0.8182    0.9000    0.8571        20
        calm     0.8182    0.9000    0.8571        40
       happy     0.9167    0.5500    0.6875        40
         sad     0.6739    0.7750    0.7209        40
       angry     0.7857    0.8250    0.8049        40
     fearful     0.8000    0.8000    0.8000        40
     disgust     0.8421    0.8000    0.8205        40
   surprised     0.7045    0.7750    0.7381        40

    accuracy                         0.7833       300
   macro avg     0.7949    0.7906    0.7858       300
weighted avg     0.7934    0.7833    0.7810       300


[_] All artifacts saved to checkpoints/
    - best_model/wavlm_emotion_classifier.pt
    - training_history.json
    - classification_report.txt
(secap) (base) ankit@LIPG512:~/depression$ 
'''