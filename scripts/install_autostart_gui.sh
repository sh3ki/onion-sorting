#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$HOME/onion-sorting}"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/onion-sorting.desktop"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "[ERROR] Project directory not found: $PROJECT_DIR"
  exit 1
fi

mkdir -p "$AUTOSTART_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Onion Sorting
Comment=Auto start onion sorting app on desktop login
Exec=bash -lc 'cd "$PROJECT_DIR" && bash scripts/run_easy.sh --skip-test'
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod 644 "$DESKTOP_FILE"

echo "Autostart installed: $DESKTOP_FILE"
echo "The app will start automatically after GUI login on the HDMI display."
