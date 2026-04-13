# Onion Sorting Code Package (Dual Camera + Dual Servo)

This folder is ready to copy to Raspberry Pi.

System design:
- Stage 1: Raspberry Pi CSI camera detects Large onions and triggers Servo 1.
- Stage 2: USB webcam detects Medium onions and triggers Servo 2.
- Small onions are not pushed.
- HDMI local display and Flask browser stream show side-by-side camera feeds.

Stage 2 webcam can be optional:
- Set STAGE2_OPTIONAL = True in config.py.
- The app runs single-camera fallback mode.
- Stage 1 measurement is reused for Medium and Small decisions.

## 1. Files

- main.py: Main runtime loop
- calibration.py: Camera calibration tool using new 5-peso coin (25 mm)
- camera_manager.py: CSI and USB camera access
- vision.py: Detection and classification logic
- scheduler.py: Delayed event scheduling
- servo_control.py: Servo actuation with GPIO or mock mode
- dashboard.py: Flask dashboard and MJPEG stream
- config.py: All configurable settings
- templates/index.html: Dashboard page
- static/style.css: Dashboard style

## 2. Raspberry Pi Setup

Install system dependencies:

sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-picamera2

Create environment and install Python dependencies:

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

## 3. Configure Cameras

Default config:
- Stage 1 source: picamera2
- Stage 2 source: USB camera index 0

No webcam yet:
- Keep STAGE2_OPTIONAL = True.
- You can still run setup, stage 1 calibration, and full app testing.

If USB camera is not index 0, edit STAGE2_SOURCE in config.py.

## 4. Calibrate Cameras

Run stage 1 calibration:

python calibration.py --stage 1

Run stage 2 calibration:

python calibration.py --stage 2

If no webcam is connected, skip stage 2 calibration until later.

Controls in calibration window:
- Space: capture coin sample
- R: reset samples
- S: save calibration
- Q: quit

Dashboard one-click calibration (recommended for operation):
- Click `Calibrate Stage 1` or `Calibrate Stage 2` in the web dashboard.
- Keep the conveyor stopped.
- Place one still new 5-peso coin on the black conveyor background.
- The app auto-captures exactly 20 valid still-coin frames and averages them.
- The resulting pixels-per-cm value is saved and immediately used for onion sizing.

Saved files:
- calibration_stage1.json
- calibration_stage2.json

## 5. Run App

python main.py

Local display:
- HDMI window shows side-by-side feeds.

Browser dashboard:
- Open http://<raspberry-pi-ip>:5000

Press Q in the display window to exit.

## 5.1 One-command run (recommended)

cd ~/onion-sorting
chmod +x scripts/run_easy.sh scripts/install_autostart_gui.sh scripts/remove_autostart_gui.sh
bash scripts/run_easy.sh

Default behavior:
- Starts app and dashboard together.
- Opens Chromium kiosk on HDMI (single screen).
- Calibration button is available in the live feed page.

If you only want OpenCV window mode:

bash scripts/run_easy.sh --no-kiosk

Quick run after first setup:

bash scripts/run_easy.sh --skip-setup --skip-test

## 5.2 Auto-start on HDMI desktop login

bash scripts/install_autostart_gui.sh ~/onion-sorting

Remove auto-start:

bash scripts/remove_autostart_gui.sh

## 6. Requested Onion Size Classes

Current thresholds in config.py:
- Small: diameter < 3.0 cm
- Medium: 3.0 cm <= diameter <= 5.0 cm
- Large: diameter > 5.0 cm

## 7. Servo Notes

- Servo 1: Large gate
- Servo 2: Medium gate
- Use external 5V for servos and shared ground with Pi.
- If GPIO is not available (for example on laptop), servo code runs in mock mode.

## 8. Performance Targets (Raspberry Pi 4)

At 640x480 per camera:
- Side-by-side display: around 15 to 22 FPS combined
- Browser stream: around 8 to 15 FPS per client

Tune if needed:
- Lower WEB_JPEG_QUALITY in config.py
- Lower WEB_STREAM_MAX_FPS in config.py
- Tighten ROIs in config.py

Display fit for 1024x600:
- FIT_OUTPUT_TO_DISPLAY = True
- DISPLAY_WIDTH = 1024
- DISPLAY_HEIGHT = 600
