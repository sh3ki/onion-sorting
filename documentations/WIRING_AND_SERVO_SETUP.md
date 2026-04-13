# Onion Sorting Wiring and Servo Setup

This guide is for:
- Raspberry Pi + PCA9685
- 2x MG996R servos
- Stage 1 and Stage 2 gate actuation

## 1) Hardware Wiring

### A. Raspberry Pi to PCA9685 (logic/I2C side)

- Pi pin 3 (GPIO2 SDA) -> PCA9685 SDA
- Pi pin 5 (GPIO3 SCL) -> PCA9685 SCL
- Pi pin 1 (3.3V) -> PCA9685 VCC
- Pi pin 6 (GND) -> PCA9685 GND
- PCA9685 OE -> GND (or leave if board already pulls it low)

### B. External servo power (required)

Do not power MG996R servos from Pi 5V.

- External PSU +5V to +6V -> PCA9685 V+ terminal
- External PSU GND -> PCA9685 GND terminal
- Common ground is required:
  - PSU GND
  - PCA9685 GND
  - Pi GND
  must be connected together.

Recommended PSU for 2x MG996R: at least 5V 5A (higher headroom is better).

### C. Servo channels on PCA9685

Configured channels in the project:
- Servo 1 (Stage 1 gate) -> PCA9685 channel 0
- Servo 2 (Stage 2 gate) -> PCA9685 channel 1

Typical MG996R wire colors:
- Brown/Black -> GND
- Red -> V+
- Orange/Yellow -> Signal

Connect each servo to the matching 3-pin channel row:
- GND to GND row
- V+ to V+ row
- Signal to SIG row

## 2) Current Software Servo Configuration

From config.py:
- SERVO_DRIVER = "pca9685"
- PCA9685_ADDRESS = 0x40
- PCA9685_FREQUENCY = 50
- SERVO1_CHANNEL = 0
- SERVO2_CHANNEL = 1
- SERVO_REST_ANGLE = 0
- SERVO_PUSH_ANGLE = 90
- SERVO_HOLD_SEC = 0.25
- SERVO_COOLDOWN_SEC = 0.25

Timing based on conveyor settings:
- Conveyor speed = 8.5 cm/s
- Stage 1 camera to servo = 20 cm -> delay = 2.35 s
- Stage 2 camera to servo = 18 cm -> delay = 2.12 s

## 3) Enable I2C on Raspberry Pi

PCA9685 will not work until I2C is enabled.

1. Run:
   sudo raspi-config
2. Go to Interface Options -> I2C -> Enable
3. Reboot:
   sudo reboot

After reboot, verify PCA9685 detection:
- sudo apt install -y i2c-tools
- i2cdetect -y 1

Expected: address 40 appears in the scan.

## 4) Quick Validation Commands

From /home/onion/onion-sorting:

- Start app:
  DISPLAY=:0 XAUTHORITY=/home/onion/.Xauthority ENABLE_LOCAL_DISPLAY=1 .venv/bin/python main.py

- Check logs for servo init:
  grep -E "\[servo\]" run.log

Success message should look like:
- [servo] PCA9685 enabled addr=0x40 freq=50Hz channels={'servo1': 0, 'servo2': 1}

If I2C is still disabled, you will see mock fallback.

## 5) Web Camera (Stage 2) Troubleshooting

Current observed state on the Pi:
- No USB webcam is enumerated in lsusb.
- Only CSI/internal video nodes are present.

Why detection fails:
- Stage 2 uses USB camera index from OpenCV.
- If Linux does not detect any USB webcam device, OpenCV cannot open it.

Check sequence:

1. Physically reconnect webcam (try another USB port and cable).
2. Run:
   lsusb
   A webcam should appear with a camera vendor/device line.
3. Run:
   v4l2-ctl --list-devices
   You should see webcam entries and /dev/videoX capture node(s).
4. Test quickly:
   python3 - << 'PY'
import cv2
for i in range(0, 12):
    c = cv2.VideoCapture(i)
    ok, _ = c.read()
    print(i, c.isOpened(), ok)
    c.release()
PY
5. Set STAGE2_SOURCE in config.py to the working index.

If still missing in lsusb:
- Check power budget (webcam may need more current)
- Remove unneeded USB devices
- Use powered USB hub
- Confirm webcam works on another machine

## 6) Throughput Feasibility

With 90 degree push and return:
- Current minimum cycle per servo is roughly hold + travel + cooldown.
- Practical target is to keep onions spaced at least around 7-8 cm on the same gate lane.

If onions are too close and misses happen:
- Reduce conveyor speed slightly, or
- Shorten push stroke/hold time, or
- Increase physical spacing upstream.
