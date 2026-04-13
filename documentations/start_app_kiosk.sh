#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f "scripts/run_easy.sh" ]]; then
  echo "[ERROR] Missing scripts/run_easy.sh in $PROJECT_DIR"
  exit 1
fi

chmod +x scripts/run_easy.sh

echo "[launcher] Starting onion app + kiosk"
echo "[launcher] Project: $PROJECT_DIR"

exec bash scripts/run_easy.sh --skip-setup --skip-test
