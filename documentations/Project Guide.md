# Project Guide: Dual-Camera Onion Sorting System (Complete Beginner Guide)

This guide is written as a complete start-to-finish manual for your exact final setup:
- 1 Raspberry Pi 4
- 1 Raspberry Pi Camera Module (CSI)
- 1 USB webcam
- 2 servo motors
- HDMI touchscreen local display
- Browser dashboard with side-by-side stream

Follow this in order. Do not skip steps.

---

## 1. Final Build Goal

You will build a two-stage sorting system:

1. Stage 1 (Large Sorting Gate)
- Camera 1 (Raspberry Pi camera) checks onions.
- If onion is Large, Servo 1 pushes it to Large funnel.
- If not Large, onion continues.

2. Stage 2 (Medium Sorting Gate)
- Camera 2 (USB webcam) checks onions that passed Stage 1.
- If onion is Medium, Servo 2 pushes it to Medium funnel.
- If not Medium, onion goes to Small output.

Class limits:
- Small: diameter < 3.0 cm
- Medium: 3.0 cm to 5.0 cm
- Large: diameter > 5.0 cm

Visual outputs:
- HDMI touchscreen shows both cameras side-by-side.
- Browser dashboard also shows both cameras side-by-side.

---

## 2. Hardware Checklist

Prepare all items first.

Required:
1. Raspberry Pi 4 Model B
2. Official Pi power adapter (5V 3A)
3. MicroSD card (32 GB or larger)
4. Raspberry Pi Camera Module v2 or v3
5. USB webcam (UVC compatible)
6. 7-inch HDMI touchscreen
7. 2 servo motors
8. External 5V servo supply (3A recommended or higher)
9. Conveyor and 3 funnels (Large, Medium, Small)
10. Jumper wires, mounting brackets, screws
11. Stable light source
12. New Philippine 5 peso coin (25 mm or 2.5 cm) for calibration

Recommended:
1. PCA9685 servo driver board or pigpio method
2. USB powered hub for stable webcam power
3. Switch for emergency stop

---

## 3. Physical Layout and Measurements

Do this before software.

1. Mount Camera 1 above Stage 1 inspection zone.
2. Mount Camera 2 above Stage 2 inspection zone.
3. Place Servo 1 gate after Stage 1 detection zone.
4. Place Servo 2 gate after Stage 2 detection zone.
5. Mark two detection lines on conveyor.
6. Measure and write down:
- D1 = Stage 1 detection line to Servo 1 gate (cm)
- D2 = Stage 2 detection line to Servo 2 gate (cm)
7. Measure belt speed:
- Mark 20 cm path, time object travel.
- BeltSpeed = distance / time in cm/s.

You need D1, D2, and belt speed for accurate actuation delay.

---

## 4. Wiring Guide (Important)

### 4.1 Camera wiring

1. Turn off Raspberry Pi.
2. Connect CSI camera ribbon to Pi camera port.
3. Lock CSI latch.
4. Connect USB webcam to Pi USB 3.0 port (blue port).

### 4.2 Display wiring

1. Connect HDMI from Pi to touchscreen.
2. Connect USB touch cable if required by your display model.
3. Power display according to manufacturer instructions.

### 4.3 Servo wiring

Suggested GPIO pins:
- Servo 1 signal: GPIO18 (physical pin 12)
- Servo 2 signal: GPIO19 (physical pin 35)

Power wiring:
1. Servo red wires -> external 5V positive
2. Servo brown or black wires -> external 5V ground
3. Pi GND -> external 5V ground (common ground required)

Critical rule:
- Do not power both servos directly from Pi 5V pin.

---

## 5. Install Raspberry Pi OS (Click-by-Click)

On your laptop or desktop:

1. Open Raspberry Pi Imager.
2. Click CHOOSE DEVICE.
3. Select Raspberry Pi 4.
4. Click CHOOSE OS.
5. Select Raspberry Pi OS (64-bit).
6. Click CHOOSE STORAGE.
7. Select your microSD card.
8. Click NEXT.
9. Click EDIT SETTINGS when prompted.
10. Set:
- Hostname (example: onionpi)
- Username and password
- Wi-Fi SSID and password (if Wi-Fi)
- Locale and timezone
- Enable SSH (recommended)
11. Click SAVE.
12. Click YES to write image.
13. Wait until flash and verify complete.

On Raspberry Pi:
1. Insert microSD.
2. Connect display, keyboard, mouse (or use SSH).
3. Power on.
4. Log in.

---

## 6. First Boot Setup (Exact Commands)

Open Terminal and run:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git libatlas-base-dev
```

Open Raspberry Pi configuration:

```bash
sudo raspi-config
```

Inside raspi-config:
1. Go to Interface Options.
2. Enable camera if option is shown.
3. Go to Localisation Options and confirm timezone and keyboard.
4. Finish and reboot.

After reboot, verify cameras:

CSI camera check:

```bash
libcamera-hello -t 3000
```

USB camera check:

```bash
ls /dev/video*
```

You should see at least one video device (for example /dev/video0 or /dev/video2).

---

## 7. Create Project Folder and Python Environment

```bash
mkdir -p ~/onion-sorting
cd ~/onion-sorting
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install opencv-python numpy flask RPi.GPIO
pip freeze > requirements.txt
```

---

## 8. Create Project Files

Create this structure:

```text
onion-sorting/
  main.py
  config.py
  camera_manager.py
  vision_stage1.py
  vision_stage2.py
  calibration.py
  scheduler.py
  servo_control.py
  dashboard.py
  templates/
    index.html
  static/
    style.css
  calibration_stage1.json
  calibration_stage2.json
  requirements.txt
  README.md
```

File purpose:
- config.py: all constants and thresholds
- camera_manager.py: capture from CSI and USB cams
- vision_stage1.py: large-stage detection logic
- vision_stage2.py: medium-stage detection logic
- calibration.py: separate calibration for each camera
- scheduler.py: delayed actuation queue
- servo_control.py: servo movement and safety locks
- dashboard.py: Flask web app and MJPEG stream
- main.py: orchestrates everything and local HDMI display

---

## 9. Configure Constants (Do This Carefully)

In config.py set:

Camera settings:
- CSI_CAMERA_INDEX = 0
- USB_CAMERA_INDEX = 1 (adjust after test)
- FRAME_WIDTH = 640
- FRAME_HEIGHT = 480

Class limits:
- SMALL_MAX_CM = 3.0
- MEDIUM_MIN_CM = 3.0
- MEDIUM_MAX_CM = 5.0
- LARGE_GT_CM = 5.0  (use condition diameter > LARGE_GT_CM)

Servo GPIO:
- SERVO1_PIN = 18
- SERVO2_PIN = 19
- SERVO_REST_ANGLE = 0
- SERVO_PUSH_ANGLE = 70
- SERVO_HOLD_SEC = 0.30
- SERVO_COOLDOWN_SEC = 0.40

Travel measurements:
- D1_CM = your measured distance to Gate 1
- D2_CM = your measured distance to Gate 2
- BELT_SPEED_CM_S = measured belt speed

Delay formulas:

T1 = D1_CM / BELT_SPEED_CM_S
T2 = D2_CM / BELT_SPEED_CM_S

Use T1 for Servo 1 scheduling and T2 for Servo 2 scheduling.

---

## 10. Calibrate Both Cameras Separately

You must calibrate each camera because the scale is different.

Reference object:
- New Philippine 5 peso coin (25 mm or 2.5 cm diameter)

For Stage 1 camera:
1. Place coin in Stage 1 detection zone.
2. Run calibration script for camera 1.
3. Capture 20 to 50 valid circle frames.
4. Compute average coin diameter in pixels.
5. Save:

PixelsPerCmStage1 = AverageCoinPxStage1 / 2.5

For Stage 2 camera:
1. Move coin to Stage 2 detection zone.
2. Run same process for camera 2.
3. Save:

PixelsPerCmStage2 = AverageCoinPxStage2 / 2.5

Store values in:
- calibration_stage1.json
- calibration_stage2.json

---

## 11. Vision Pipeline for Each Stage

For each frame in each stage:
1. Convert to grayscale.
2. Apply Gaussian blur.
3. Threshold image.
4. Morphological open and close.
5. Find contours.
6. Filter by area and circularity.
7. Fit minimum enclosing circle.
8. Compute diameter in cm.
9. Classify based on stage rule.

Formula:

DiameterCm = DiameterPx / PixelsPerCm

Recommended circularity range:
- 0.6 to 1.2

---

## 12. Stage Rules and Actuation

Stage 1 rule (Camera 1 + Servo 1):
- If diameter > 5.0 cm -> Large -> schedule Servo 1
- Else -> no Servo 1 action

Stage 2 rule (Camera 2 + Servo 2):
- If 3.0 <= diameter <= 5.0 cm -> Medium -> schedule Servo 2
- Else -> no Servo 2 action (Small)

Important:
- Use event queue and timestamps.
- Do not block camera loop while servo is moving.

---

## 13. Build Side-by-Side Display Output

Create one combined frame every loop:

1. Resize Camera 1 annotated frame to common size.
2. Resize Camera 2 annotated frame to common size.
3. Concatenate horizontally.
4. Draw top bar text:
- Combined FPS
- Stage 1 class
- Stage 2 class
- Counters (Large, Medium, Small)
- Servo states

Show this combined frame on HDMI using OpenCV window.

---

## 14. Build Browser Dashboard

Use Flask in dashboard.py with these routes:

1. GET /
- Returns index.html

2. GET /video_feed
- Streams combined side-by-side frame as MJPEG

3. GET /api/status
- Returns JSON with fps, counts, servo states, camera status

4. POST /api/reset
- Resets counters (optional)

In index.html show:
- Live stream image from /video_feed
- Status cards for fps, counts, servos, calibration values

Open dashboard from tablet browser:

http://PI_IP_ADDRESS:5000

Find Pi IP:

```bash
hostname -I
```

---

## 15. Run Everything

Start app:

```bash
cd ~/onion-sorting
source .venv/bin/activate
python main.py
```

If Flask runs inside main.py, dashboard is already live.
If separate, start dashboard.py in another terminal.

---

## 16. Expected Performance (Your Exact Setup)

Setup:
- 1 CSI camera + 1 USB webcam
- 2 detection pipelines
- 2 servos
- side-by-side HDMI display
- browser MJPEG stream

Realistic targets on Raspberry Pi 4 at 640x480 per camera:
- HDMI side-by-side display: 15 to 22 FPS combined
- Stage 1 processing: 18 to 30 FPS (CSI usually higher)
- Stage 2 processing: 15 to 25 FPS (USB dependent)
- Browser stream: 8 to 15 FPS per client

Typical latency:
- HDMI: 60 to 140 ms
- Browser: 180 to 500 ms

If FPS is low:
1. Lower MJPEG quality to 60 to 70.
2. Limit browser stream to 8 to 12 FPS.
3. Use ROI crop for detection zones.
4. Keep resolution at 640x480.
5. Move servo code to worker thread.

---

## 17. Full Test Plan (Order Matters)

Test 1: Camera connectivity
1. Verify CSI preview works.
2. Verify USB webcam appears in /dev/video.

Test 2: Dual capture
1. Show both raw feeds side-by-side.
2. Run for 10 minutes to check stability.

Test 3: Calibration
1. Run stage 1 calibration.
2. Run stage 2 calibration.
3. Validate with known circular objects.

Test 4: Stage 1 classification only
1. Disable servos.
2. Confirm Large detection reliability.

Test 5: Stage 2 classification only
1. Disable Servo 1 logic.
2. Confirm Medium detection reliability.

Test 6: Servo manual test
1. Trigger Servo 1 and Servo 2 from keyboard command.
2. Verify angle and return behavior.

Test 7: Scheduler delay test
1. Feed timed test objects.
2. Confirm gate push aligns with onion arrival.

Test 8: Full integration
1. Mixed onion sizes.
2. Record sorting accuracy and missed triggers.

Metrics to record:
- FPS (display and stream)
- Detection rate
- Sorting accuracy
- False push count
- Missed push count

---

## 18. Common Problems and Fixes

Problem: USB camera not opening
- Try different USB port.
- Use powered hub.
- Check camera index values.

Problem: Wrong onion size readings
- Recalibrate both cameras.
- Ensure camera mounts did not move.

Problem: Servo causes Pi reboot
- Use stronger external 5V supply.
- Confirm common ground wiring.

Problem: Browser lag
- Lower MJPEG quality.
- Reduce stream fps.
- Close extra browser clients.

Problem: Missed sorting timing
- Re-measure D1, D2, belt speed.
- Update delay formulas.

---

## 19. Safety and Reliability Checklist

1. All grounds connected correctly.
2. No exposed short-circuit points.
3. Servo linkages secured.
4. Emergency stop available.
5. Conveyor speed not too high.
6. Stable lighting before testing.

---

## 20. Final Acceptance Checklist

Project is complete when all are true:

1. Both cameras run continuously without crash.
2. HDMI shows both feeds side-by-side.
3. Browser shows same side-by-side stream.
4. Stage 1 correctly diverts Large onions.
5. Stage 2 correctly diverts Medium onions.
6. Small onions pass to Small output.
7. System runs at least 30 minutes stable.
8. FPS and accuracy results are documented.

---

## 21. Suggested Build Sequence for You

Do this exact order:

1. Finish hardware mounting and wiring.
2. Install OS and dependencies.
3. Verify both cameras.
4. Build side-by-side capture only.
5. Add calibration for both cameras.
6. Add Stage 1 detection and Servo 1.
7. Add Stage 2 detection and Servo 2.
8. Add dashboard streaming.
9. Tune thresholds and delay.
10. Run full tests and collect report data.

If you follow this order, the project is much easier to complete as a beginner.