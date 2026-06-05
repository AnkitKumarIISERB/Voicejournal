#!/bin/bash
set -e

# ==============================================================================
# VoiceJournal - Automated Remote Training Script
# ==============================================================================
# This script securely uploads the ML code to your A16 server, trains the WavLM 
# model until it reaches optimal F1 score, downloads the trained weights, 
# and then completely erases all data/code from the remote server.
# ==============================================================================

SERVER="ankit@10.206.2.177"
REMOTE_DIR="depression"
LOCAL_ML_DIR="/Users/ankityadav/Documents/projects/voicejournal/ml"
LOCAL_CHECKPOINT_DIR="/Users/ankityadav/Documents/projects/voicejournal/backend/checkpoints/best_model"

echo "========================================================"
echo "🚀 Initializing Secure Remote Training Pipeline"
echo "========================================================"
echo "Setting up SSH multiplexing so you only have to enter your password ONCE."
mkdir -p ~/.ssh/controlmasters
export SSH_OPTS="-o ControlMaster=auto -o ControlPath=~/.ssh/controlmasters/%%r@%%h:%%p -o ControlPersist=10m"

# 0. Initialize connection (This will prompt for password)
echo ""
echo "Please enter your password for $SERVER to begin:"
ssh $SSH_OPTS $SERVER "echo '✓ Connection established.'"

# 1. Upload
echo ""
echo "[1/4] 📤 Uploading ML codebase to server..."
ssh $SSH_OPTS $SERVER "mkdir -p ~/$REMOTE_DIR"
# Copy contents of local ml dir into remote ml dir
rsync -avz -e "ssh $SSH_OPTS" "$LOCAL_ML_DIR" $SERVER:~/$REMOTE_DIR/

# 2. Train
echo ""
echo "[2/4] 🧠 Starting training on A16 GPU..."
echo "      (This will stream logs in real-time. Do not close this terminal.)"
ssh $SSH_OPTS $SERVER << 'EOF'
  set -e
  cd ~/depression
  
  echo "--> Setting up isolated Python environment..."
  python3 -m venv venv
  source venv/bin/activate
  
  echo "--> Installing dependencies..."
  # torch, torchaudio, transformers, etc.
  pip install -r ml/requirements.txt
  
  echo "--> Downloading RAVDESS dataset..."
  python -m ml.data.download_ravdess
  
  echo "--> Training WavLM model (tracking Macro F1 score)..."
  python -m ml.train
EOF

# 3. Download
echo ""
echo "[3/4] 📥 Downloading best model weights..."
mkdir -p "$LOCAL_CHECKPOINT_DIR"
scp $SSH_OPTS $SERVER:~/$REMOTE_DIR/checkpoints/best_model/* "$LOCAL_CHECKPOINT_DIR/"
scp $SSH_OPTS $SERVER:~/$REMOTE_DIR/checkpoints/classification_report.txt "$LOCAL_CHECKPOINT_DIR/../"
echo "✓ Model downloaded to backend/checkpoints/best_model/"

# 4. Cleanup
echo ""
echo "[4/4] 🧹 Shredding and removing data from remote server..."
ssh $SSH_OPTS $SERVER "rm -rf ~/$REMOTE_DIR"
echo "✓ Remote server wiped clean."

# Close multiplex connection
ssh -O exit $SSH_OPTS $SERVER 2>/dev/null || true

echo ""
echo "========================================================"
echo "🎉 SUCCESS! Production-ready model is now local."
echo "You can view the classification_report.txt in the checkpoints folder"
echo "to verify the F1 score and accuracy."
echo "========================================================"
