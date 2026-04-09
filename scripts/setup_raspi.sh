#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$HOME/onion-sorting}"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "[ERROR] Project directory not found: $PROJECT_DIR"
  echo "Pass your project path as argument, for example:"
  echo "  bash scripts/setup_raspi.sh \"$HOME/onion sorting\""
  exit 1
fi

cd "$PROJECT_DIR"

echo "[1/4] Updating apt index"
sudo apt update

echo "[2/4] Installing system packages"
sudo apt install -y \
  python3-pip \
  python3-venv \
  python3-picamera2 \
  curl \
  libopenblas-dev \
  libjpeg-dev

# Optional image/math libs vary across Raspberry Pi OS releases.
OPTIONAL_PACKAGES=(
  libopenjp2-7-dev
  libatlas-base-dev
  libatlas3-base
  libtiff5
  libtiff6
)

for pkg in "${OPTIONAL_PACKAGES[@]}"; do
  if apt-cache show "$pkg" >/dev/null 2>&1; then
    echo "Installing optional package: $pkg"
    sudo apt install -y "$pkg" || true
  fi
done

echo "[3/4] Creating Python virtual environment"
python3 -m venv --system-site-packages .venv

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[4/4] Installing Python dependencies"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo "[VERIFY] Checking Python imports"
python - <<'PY'
import cv2
import flask
import numpy

print("opencv:", cv2.__version__)
print("flask:", flask.__version__)
print("numpy:", numpy.__version__)
print("Import check OK")
PY

echo "Setup complete."
