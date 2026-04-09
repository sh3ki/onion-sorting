# Project Instructions (Complete Detailed Build Guide)

This is your complete step-by-step instruction manual for building the onion sorting project with:
- 1 Raspberry Pi 4
- 1 Raspberry Pi camera module (CSI)
- 1 USB webcam (optional)
- 2 servo motors
- HDMI touchscreen display
- Browser dashboard stream

Use this document as your build checklist and execution plan.

---

## 1. Final Output You Need To Make

You are making one complete working system with these outputs:

1. Physical system
- Conveyor path
- Stage 1 Large gate (Servo 1)
- Stage 2 Medium gate (Servo 2)
- 3 output funnels: Large, Medium, Small
- Fixed camera mount for CSI camera
- Optional fixed camera mount for USB stage 2 camera
- Stable lighting setup

2. Electrical system
- Raspberry Pi power and display power
- CSI camera connected
- USB webcam connected
- Two servos powered by external 5V supply
- Shared ground between external servo supply and Raspberry Pi

3. Software system
- Dual camera capture and processing
- Stage 1 decision (Large vs Not Large)
- Stage 2 decision (Medium vs Small)
- Delayed servo actuation scheduler
- Side-by-side HDMI display
- Side-by-side browser stream and status dashboard

If USB webcam is not available yet:
- The software can run in single-camera fallback mode.
- Stage 1 camera handles full size classification.
- Servo 1 still pushes Large and Servo 2 can still push Medium using stage-delay timing.

4. Measurement and classification rules
- Small: diameter < 3.0 cm
- Medium: 3.0 cm <= diameter <= 5.0 cm
- Large: diameter > 5.0 cm

5. Calibration rule
- New 5-peso coin = 25 mm diameter = 2.5 cm
- Pixel-to-cm conversion per camera:
  PixelsPerCm = CoinDiameterPixels / 2.5

---

## 2. Materials You Need Before Starting

### 2.1 Core hardware
1. Raspberry Pi 4 Model B
2. MicroSD card 32GB or larger
3. Official Raspberry Pi 5V 3A power adapter
4. Raspberry Pi Camera Module v2 or v3
5. USB webcam (UVC compatible)
6. HDMI touchscreen
7. 2x servo motors
8. External 5V power supply for servos (3A or higher recommended)
9. Conveyor mechanism
10. 3 output chutes/funnels
11. Jumper wires and terminal connectors
12. Mounting brackets and screws
13. Consistent lighting (LED strip/bar/ring)
14. New 5-peso coin for calibration

### 2.2 Build tools
+////////////1. Screwdrivers
2. Wire stripper or cutter
3. Ruler/tape measure (for D1, D2 distances)
4. Marker tape for detection zones

---

## 3. Mechanical Build (Do This First)

### 3.1 Conveyor and gate layout
1. Set conveyor direction.
2. Mark Stage 1 detection zone on the conveyor.
3. Install Servo 1 gate after Stage 1 detection zone.
4. Mark Stage 2 detection zone farther down conveyor.
5. Install Servo 2 gate after Stage 2 detection zone.
6. Install 3 funnels at outputs: Large, Medium, Small.

### 3.2 Camera mounting
1. Mount CSI camera above Stage 1 zone.
2. Mount USB webcam above Stage 2 zone (optional).
3. Keep both cameras stable and vibration-free.
4. Avoid camera tilt changes after calibration.

### 3.3 Required distance measurements
Measure and record these values:
1. D1: distance from Stage 1 trigger line to Servo 1 gate (cm)
2. D2: distance from Stage 2 trigger line to Servo 2 gate (cm)
3. Belt speed (cm/s)

How to measure belt speed:
1. Mark a 20 cm segment on conveyor.
2. Place one test object.
3. Time travel in seconds.
4. BeltSpeed = 20 / time_seconds

---

## 4. Wiring Instructions (Critical)

### 4.1 CSI camera
1. Turn off Pi.
2. Insert ribbon cable into CSI connector.
3. Lock connector latch.

### 4.2 USB webcam
1. Plug webcam into a USB 3.0 port.

### 4.3 HDMI touchscreen
1. Connect HDMI cable from Pi to touchscreen.
2. Connect touch USB cable if required.
3. Power display per display model requirements.

### 4.4 Servo wiring
Use suggested GPIO pins:
1. Servo 1 signal -> GPIO18 (physical pin 12)
2. Servo 2 signal -> GPIO19 (physical pin 35)

Power wiring:
1. Servo V+ -> external 5V positive
2. Servo GND -> external 5V ground
3. Raspberry Pi GND -> same external 5V ground

Important:
- Never power both servos directly from Pi 5V pin.
- Common ground between Pi and servo supply is mandatory.
                                            //////////////////////////////
### 4.5 Complete Wiring Map (Pin-by-Pin)

Raspberry Pi power and display:
1. Raspberry Pi USB-C power adapter -> Pi power input.
2. Pi micro-HDMI port -> HDMI touchscreen input.
3. Pi USB port -> touchscreen USB touch input (if your display needs touch over USB).

CSI camera connection:
1. CSI ribbon from camera -> Pi CSI camera connector.
2. Keep cable orientation correct (metal contacts toward connector pins).

Servo 1 (Large gate):
1. Servo 1 signal wire (orange or yellow) -> GPIO18 (Pin 12).
2. Servo 1 V+ (red) -> External 5V +.
3. Servo 1 GND (brown or black) -> External 5V GND.

Servo 2 (Medium gate):
1. Servo 2 signal wire (orange or yellow) -> GPIO19 (Pin 35).
2. Servo 2 V+ (red) -> External 5V +.
3. Servo 2 GND (brown or black) -> External 5V GND.

Ground reference (critical):
1. Pi GND (for example Pin 6) -> External 5V GND.
2. This common ground is required for stable PWM control.

Optional USB webcam:
1. USB webcam -> Pi USB 3.0 port.
2. If webcam is not present, keep STAGE2_OPTIONAL = True.

Power reliability notes:
1. Use a strong Pi power adapter (official 5V 3A recommended).
2. Use separate external 5V supply for servos.
3. If servos jitter or Pi undervoltage appears, improve power and wiring thickness.

---

## 5. Raspberry Pi OS Installation (Click-by-Click)

On your PC/laptop:
1. Open Raspberry Pi Imager.
2. Click CHOOSE DEVICE -> Raspberry Pi 4.
3. Click CHOOSE OS -> Raspberry Pi OS (64-bit).
4. Click CHOOSE STORAGE -> select microSD.
5. Click NEXT -> EDIT SETTINGS.
6. Configure:
- hostname (example: onionpi)
- username and password
- Wi-Fi SSID and password (if needed)
- locale and timezone
- enable SSH (recommended)
7. Save.
8. Click YES to write image.
9. Wait for flash and verification.

On Raspberry Pi:
1. Insert microSD.
2. Connect display/keyboard/mouse (or SSH).
3. Power on and log in.

---

## 6. First-Time Raspberry Pi Setup

Open terminal and run:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git python3-picamera2
```

Open raspi-config:

```bash
sudo raspi-config
```

Inside menu:
1. Interface Options -> camera (enable if shown)
2. Localisation Options -> timezone and keyboard
3. Finish -> reboot

After reboot, check camera devices:

```bash
libcamera-hello -t 3000
ls /dev/video*
```

Expected:
- CSI preview opens for 3 seconds
- USB camera appears in /dev/video list when webcam is connected

---

## 7. Copy Project Files To Raspberry Pi

Copy everything from your project folder to Pi, including:
- main.py
- config.py
- calibration.py
- camera_manager.py
- vision.py
- scheduler.py
- servo_control.py
- dashboard.py
- templates folder
- static folder
- requirements.txt
- calibration_stage1.json
- calibration_stage2.json

You can use:
1. USB drive copy
2. WinSCP
3. SCP command

Example SCP from Windows terminal:

```bash
scp -r "onion sorting" pi@<PI_IP>:/home/pi/
```

After copy, if your folder name has a space, consider renaming for easier commands:

```bash
mv ~/"onion sorting" ~/onion-sorting
```

---

## 8. Python Environment and Dependencies

On Raspberry Pi:

```bash
cd ~/onion-sorting
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If OpenCV wheel fails, run:

```bash
sudo apt install -y libatlas-base-dev libopenblas-dev
```

Then reinstall requirements.

Faster option using included setup script:

```bash
cd ~/onion-sorting
chmod +x scripts/setup_raspi.sh scripts/test_raspi.sh
bash scripts/setup_raspi.sh ~/onion-sorting
```

Quick start for your account details (hostname onionpi, username onion):

```bash
ssh onion@onionpi
cd ~/onion-sorting
chmod +x scripts/setup_raspi.sh scripts/test_raspi.sh
bash scripts/setup_raspi.sh ~/onion-sorting
bash scripts/test_raspi.sh ~/onion-sorting
source .venv/bin/activate
python calibration.py --stage 1
python calibration.py --stage 2
python main.py
```

Simplest one-command launcher on Raspberry Pi:

```bash
cd ~/onion-sorting
chmod +x scripts/run_easy.sh scripts/install_autostart_gui.sh scripts/remove_autostart_gui.sh
bash scripts/run_easy.sh
```

If you get command not found, you are likely not in the project folder or missing the scripts/ prefix.
Use exactly:

```bash
cd ~/onion-sorting
bash scripts/run_easy.sh
```

What this does automatically:
1. Runs setup
2. Runs camera smoke test
3. Starts sorting app and dashboard in one run
4. Opens single-screen HDMI kiosk dashboard (with Calibrate button)

If you only want to start quickly after setup is done:

```bash
bash scripts/run_easy.sh --skip-setup --skip-test
```

If you want auto-start on every desktop login (HDMI screen):

```bash
bash scripts/install_autostart_gui.sh ~/onion-sorting
```

To remove auto-start later:

```bash
bash scripts/remove_autostart_gui.sh
```

---

## 9. Configure The App (Most Important Settings)

Open config.py and set these correctly:

1. Camera sources
- STAGE1_SOURCE = "picamera2"
- STAGE2_SOURCE = USB index (0, 1, or 2)
- STAGE2_OPTIONAL = True if no USB webcam yet

2. Onion classes (already set)
- SMALL_MAX_CM = 3.0
- MEDIUM_MIN_CM = 3.0
- MEDIUM_MAX_CM = 5.0
- LARGE_GT_CM = 5.0

3. Travel delay
- STAGE1_TRAVEL_DELAY_SEC = based on D1 and belt speed
- STAGE2_TRAVEL_DELAY_SEC = based on D2 and belt speed

4. Servo pins and angles
- SERVO1_PIN, SERVO2_PIN
- SERVO_PUSH_ANGLE and SERVO_REST_ANGLE

5. Stream settings
- WEB_STREAM_MAX_FPS = 8 to 12 for stable browser performance
- WEB_JPEG_QUALITY = 60 to 75

6. 1024x600 display fit settings
- FIT_OUTPUT_TO_DISPLAY = True
- DISPLAY_WIDTH = 1024
- DISPLAY_HEIGHT = 600

Delay formulas you should use:

T1 = D1 / BeltSpeed

T2 = D2 / BeltSpeed

Set T1 and T2 in config.py values.

---

## 10. Calibrate Both Cameras (Required)

Use new 5-peso coin (2.5 cm diameter).

Preferred calibration method (all in one screen, no separate calibration app):
1. Start the system with:

```bash
bash scripts/run_easy.sh --skip-setup --skip-test
```

2. On the HDMI dashboard feed, press:
- Calibrate Stage 1 (New 5-peso 25mm)
- Calibrate Stage 2 (New 5-peso 25mm) when USB webcam is connected

3. Place the coin flat and centered in Stage 1 view.
4. Keep camera and coin steady while samples are captured.
5. Wait until status says calibration done.
6. The app saves Stage 1 calibration automatically to calibration_stage1.json.
7. The app saves Stage 2 calibration automatically to calibration_stage2.json when stage 2 button is used.

Button behavior:
1. Stage 1 button calibrates CSI camera only.
2. Stage 2 button calibrates USB camera only.
3. If USB camera is missing, stage 2 button shows camera unavailable status.

Legacy manual calibration (optional backup):

Stage 1 calibration:

```bash
source .venv/bin/activate
python calibration.py --stage 1
```

Stage 2 calibration:

```bash
source .venv/bin/activate
python calibration.py --stage 2
```

If USB webcam is not connected yet:
- Skip stage 2 calibration for now.
- Keep STAGE2_OPTIONAL = True in config.py.

Calibration controls:
1. Space = capture sample
2. R = reset samples
3. S = save calibration
4. Q = quit

Collect at least 10 to 20 samples each stage.

Output files:
- calibration_stage1.json
- calibration_stage2.json

---

## 11. System Bring-Up Sequence

Do this exact order:

1. Run cameras only (no servos physically connected to gates).
2. Start app:

```bash
source .venv/bin/activate
python main.py
```

3. Verify HDMI display shows side-by-side feeds.
4. Open browser dashboard:
- http://<PI_IP>:5000
5. Verify live stream and status values update.

Then continue:
6. Enable servo movements with test objects.
7. Tune push angle and hold time.
8. Attach gates and run full conveyor test.

You can also run the automated smoke test before full app:

```bash
bash scripts/test_raspi.sh ~/onion-sorting
```

This smoke test will:
1. Check CSI preview
2. Show USB camera devices
3. Run dual camera Python capture test
4. Save last-frame snapshots for both cameras

---

## 12. Testing Plan You Should Follow

### Test A: Camera stability
- Run for 10 minutes.
- Confirm no camera dropouts.

### Test B: Detection quality
- One onion at a time.
- Check measured diameter stability.

### Test C: Classification boundaries
Test sample objects near thresholds:
- 2.9 cm (should be Small)
- 3.0 cm (should be Medium)
- 5.0 cm (should be Medium)
- 5.1 cm (should be Large)

### Test D: Servo timing
- Confirm gate push happens exactly when onion arrives.
- Tune travel delay values in config.py.

### Test E: Integrated sorting
- Run mixed onions continuously.
- Record counts for Small/Medium/Large.

---

## 13. Performance Targets

For Raspberry Pi 4 at 640x480 each camera:
1. HDMI side-by-side display: 15 to 22 FPS combined
2. Browser stream: 8 to 15 FPS per client

If performance is low:
1. Lower WEB_STREAM_MAX_FPS.
2. Lower WEB_JPEG_QUALITY.
3. Use ROI for both stages in config.py.
4. Reduce heavy image processing steps.

---

## 14. Troubleshooting Quick Fixes

1. CSI camera not working
- Re-seat ribbon cable.
- Run libcamera-hello.

2. USB webcam wrong index
- Change STAGE2_SOURCE in config.py.
- Restart app.

3. Servos jitter or Pi restarts
- Use external 5V supply.
- Check common ground.

4. Wrong sizes detected
- Recalibrate both stages.
- Ensure camera positions did not move.

5. Browser lag
- Lower stream fps and JPEG quality.
- Keep one client only during testing.

---

## 15. Final Acceptance Checklist

Project is ready when all are true:
1. Both cameras stream reliably.
2. HDMI shows side-by-side feeds.
3. Browser dashboard is accessible and stable.
4. Large onions go to Large funnel via Servo 1.
5. Medium onions go to Medium funnel via Servo 2.
6. Small onions pass to Small output.
7. System runs for 30 minutes without crash.
8. Accuracy and FPS data are recorded.

---

## 16. Suggested Build Timeline

Week 1:
- Mechanical structure, mounting, wiring
- OS and dependency setup

Week 2:
- Calibration and camera verification
- Detection and classification validation

Week 3:
- Servo integration and delay tuning
- Full conveyor tests

Week 4:
- Stability runs, metrics collection
- Report writing and final demo preparation

---

## 17. What You Should Do Next Right Now

1. Confirm your camera indices on Raspberry Pi.
2. Calibrate Stage 1 and Stage 2 using new 5-peso coin.
3. Start main.py and check HDMI + browser outputs.
4. Tune travel delays and servo angles with test onions.
5. Run full mixed-size sorting test and record results.
