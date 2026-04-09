#!/usr/bin/env bash
set -euo pipefail

DESKTOP_FILE="$HOME/.config/autostart/onion-sorting.desktop"

if [[ -f "$DESKTOP_FILE" ]]; then
  rm -f "$DESKTOP_FILE"
  echo "Removed autostart: $DESKTOP_FILE"
else
  echo "Autostart file not found: $DESKTOP_FILE"
fi
