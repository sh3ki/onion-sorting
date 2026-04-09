#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$HOME/onion-sorting}"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "[ERROR] Project directory not found: $PROJECT_DIR"
  echo "Pass your project path as argument, for example:"
  echo "  bash scripts/test_raspi.sh \"$HOME/onion sorting\""
  exit 1
fi

cd "$PROJECT_DIR"

if [ ! -f .venv/bin/activate ]; then
  echo "[ERROR] Virtual environment missing. Run setup first:"
  echo "  bash scripts/setup_raspi.sh"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[1/4] CSI preview check"
if libcamera-hello -t 2000 >/dev/null 2>&1; then
  echo "CSI camera preview OK"
else
  echo "WARNING: libcamera-hello failed"
fi

echo "[2/4] USB camera devices"
ls /dev/video* || true

echo "[3/4] Python dual camera smoke test"
python scripts/dual_camera_smoke.py --seconds 12 --no-preview

echo "[4/4] Next steps"
echo "- Run calibration for stage 1: python calibration.py --stage 1"
echo "- Run calibration for stage 2: python calibration.py --stage 2 (only when USB webcam is connected)"
echo "- Start full app: python main.py"
