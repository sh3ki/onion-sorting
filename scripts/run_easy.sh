#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/onion-sorting"
RUN_SETUP=1
RUN_TEST=1
HEADLESS=0
KIOSK=1

usage() {
  echo "Usage: bash scripts/run_easy.sh [options]"
  echo "Options:"
  echo "  --project-dir <path>   Project directory (default: ~/onion-sorting)"
  echo "  --skip-setup           Skip dependency setup"
  echo "  --skip-test            Skip smoke test"
  echo "  --headless             Do not force HDMI display variables"
  echo "  --no-kiosk             Do not launch Chromium dashboard kiosk"
  echo "  -h, --help             Show this help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --skip-setup)
      RUN_SETUP=0
      shift
      ;;
    --skip-test)
      RUN_TEST=0
      shift
      ;;
    --headless)
      HEADLESS=1
      shift
      ;;
    --no-kiosk)
      KIOSK=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "[ERROR] Project directory not found: $PROJECT_DIR"
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -f "scripts/setup_raspi.sh" ]]; then
  echo "[ERROR] Missing scripts/setup_raspi.sh"
  exit 1
fi

if [[ $RUN_SETUP -eq 1 ]]; then
  echo "[STEP] Setup environment"
  bash scripts/setup_raspi.sh "$PROJECT_DIR"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ $RUN_TEST -eq 1 ]]; then
  echo "[STEP] Run camera smoke test"
  bash scripts/test_raspi.sh "$PROJECT_DIR"
fi

if [[ $HEADLESS -eq 0 ]]; then
  # Force dashboard/kiosk on HDMI screen when launched via SSH.
  export DISPLAY=:0
  export XAUTHORITY="$HOME/.Xauthority"
fi

KIOSK_BROWSER=""
if command -v chromium-browser >/dev/null 2>&1; then
  KIOSK_BROWSER="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
  KIOSK_BROWSER="chromium"
fi

if [[ $HEADLESS -eq 0 && $KIOSK -eq 1 && -n "$KIOSK_BROWSER" ]]; then
  echo "[STEP] Starting app in kiosk mode (single-screen dashboard)"
  APP_STARTED_BY_SCRIPT=0
  APP_PID=""

  if curl -sf "http://127.0.0.1:5000/health" >/dev/null 2>&1; then
    echo "[INFO] Existing app already running. Reusing http://127.0.0.1:5000"
  else
    ENABLE_LOCAL_DISPLAY=0 python main.py &
    APP_PID=$!
    APP_STARTED_BY_SCRIPT=1

    for _ in {1..30}; do
      if curl -sf "http://127.0.0.1:5000/health" >/dev/null 2>&1; then
        break
      fi
      if ! kill -0 "$APP_PID" >/dev/null 2>&1; then
        echo "[ERROR] App exited before dashboard became ready."
        exit 1
      fi
      sleep 0.4
    done

    if ! curl -sf "http://127.0.0.1:5000/health" >/dev/null 2>&1; then
      echo "[ERROR] Dashboard health endpoint did not become ready."
      if [[ -n "$APP_PID" ]]; then
        kill "$APP_PID" >/dev/null 2>&1 || true
      fi
      exit 1
    fi
  fi

  "$KIOSK_BROWSER" --kiosk --noerrdialogs --disable-infobars --app="http://127.0.0.1:5000" &
  BROWSER_PID=$!

  if [[ $APP_STARTED_BY_SCRIPT -eq 1 ]]; then
    echo "[INFO] App started. Use dashboard Close Program button to stop."
    wait "$APP_PID" 2>/dev/null || true
    kill "$BROWSER_PID" >/dev/null 2>&1 || true
    wait "$BROWSER_PID" 2>/dev/null || true
  else
    echo "[INFO] Existing app kept running. Close browser any time; app stays alive."
    wait "$BROWSER_PID" 2>/dev/null || true
  fi
else
  echo "[STEP] Starting onion sorting app"
  echo "Press Q on the HDMI window to stop."
  python main.py
fi
