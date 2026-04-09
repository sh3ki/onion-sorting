import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
APP_NAME = "Onion Sorting Dual Camera"

# Output toggles
ENABLE_LOCAL_DISPLAY = os.getenv("ENABLE_LOCAL_DISPLAY", "0") != "0"
ENABLE_WEB_DASHBOARD = True

# Flask dashboard settings
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
WEB_STREAM_MAX_FPS = 12
WEB_JPEG_QUALITY = 70

# Camera capture settings
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# Keep camera field-of-view stable (no digital zoom).
LOCK_CAMERA_FOV = True

# Disable autofocus breathing where supported (Pi Camera v3 / some USB cams).
DISABLE_AUTOFOCUS = True

# Output resolution fitting (for HDMI display like 1024x600)
FIT_OUTPUT_TO_DISPLAY = True
DISPLAY_WIDTH = 1024
DISPLAY_HEIGHT = 600

# Camera sources:
# - Use "picamera2" for Raspberry Pi CSI camera.
# - Use integer index (0, 1, 2, ...) for USB webcams.
# - Use "gstreamer:<pipeline>" for custom CSI pipelines.
STAGE1_SOURCE = 1
STAGE2_SOURCE = "picamera2"
STAGE2_OPTIONAL = True

# Backend names: default, v4l2, gstreamer, ffmpeg, any
STAGE1_BACKEND = "default"
STAGE2_BACKEND = "default"

# Optional explicit stage ROIs: (x, y, width, height), or None for full frame
STAGE1_ROI = None
STAGE2_ROI = None

# Shared vision preprocessing settings
BLUR_KERNEL_SIZE = 5
MORPH_KERNEL_SIZE = 5
MIN_CONTOUR_AREA = 500
CIRCULARITY_MIN = 0.60
CIRCULARITY_MAX = 1.20
THRESHOLD_INVERT = True

# Trigger line settings inside each ROI
# ratio is from 0.0 to 1.0 in the trigger axis direction
STAGE1_TRIGGER_AXIS = "y"
STAGE1_TRIGGER_RATIO = 0.25
STAGE1_TRIGGER_TOLERANCE_PX = 18
STAGE1_TRIGGER_COOLDOWN_SEC = 0.70

STAGE2_TRIGGER_AXIS = "y"
STAGE2_TRIGGER_RATIO = 0.25
STAGE2_TRIGGER_TOLERANCE_PX = 18
STAGE2_TRIGGER_COOLDOWN_SEC = 0.70

# Onion classes requested by user
SMALL_MAX_CM = 3.8
MEDIUM_MIN_CM = 3.8
MEDIUM_MAX_CM = 6.0
LARGE_GT_CM = 6.0

# Delay from detection line to servo gate
# stage1: 20 cm / 8.5 cm/s ~= 2.35 s
STAGE1_TRAVEL_DELAY_SEC = 2.35
# stage2: 15 cm / 8.5 cm/s ~= 1.76 s
STAGE2_TRAVEL_DELAY_SEC = 1.76

# Servo settings
SERVO_ENABLED = True
# Servo driver: "gpio" for direct Pi PWM pins, "pca9685" for I2C servo hat/controller.
SERVO_DRIVER = "pca9685"

# GPIO outputs (used only when SERVO_DRIVER="gpio")
SERVO1_PIN = 18
SERVO2_PIN = 19

# PCA9685 outputs (used only when SERVO_DRIVER="pca9685")
PCA9685_ADDRESS = 0x40
PCA9685_FREQUENCY = 50
SERVO1_CHANNEL = 0
SERVO2_CHANNEL = 1
SERVO_MIN_PULSE_US = 500
SERVO_MAX_PULSE_US = 2500

# Swing profile:
# - Rest at center (90)
# - Forward swing to 180 (90 deg forward)
# - Back swing to 90 (90 deg back to rest)
SERVO_REST_ANGLE = 90
SERVO_PUSH_ANGLE = 180
SERVO_BACK_ANGLE = 90
# Per-servo motion calibration (used to match physical swing between servos).
SERVO1_REST_ANGLE = SERVO_REST_ANGLE
SERVO1_PUSH_ANGLE = SERVO_PUSH_ANGLE
SERVO1_BACK_ANGLE = SERVO_BACK_ANGLE
SERVO1_REVERSE = False
SERVO1_TRIM_DEG = 0.0

SERVO2_REST_ANGLE = SERVO_REST_ANGLE
SERVO2_PUSH_ANGLE = SERVO_PUSH_ANGLE
SERVO2_BACK_ANGLE = SERVO_BACK_ANGLE
SERVO2_REVERSE = False
SERVO2_TRIM_DEG = 0.0
# MG996R typically needs ~0.25s for 90deg travel at 6V; keep near that for full stroke.
SERVO_HOLD_SEC = 0.28
SERVO_COOLDOWN_SEC = 0.02

# Temporarily disable camera-driven servo pushes.
AUTO_SERVO_FROM_DETECTION = False

# Manual /servo page cycle settings.
# One cycle: move CCW first, short pause, then move CW.
MANUAL_SERVO_CCW_ANGLE = 0
MANUAL_SERVO_CW_ANGLE = 180
MANUAL_SERVO_PHASE_PAUSE_SEC = 0.15
MANUAL_SERVO_MIN_INTERVAL_SEC = 0.20

# Physical tactile push-button inputs for manual servo triggering.
# Wire each button between the GPIO pin and GND (active-low with internal pull-up).
MANUAL_BUTTONS_ENABLED = True
MANUAL_BUTTON_SERVO1_PIN = 17
MANUAL_BUTTON_SERVO2_PIN = 27
MANUAL_BUTTON_ACTIVE_LOW = True
MANUAL_BUTTON_DEBOUNCE_SEC = 0.20

# Calibration settings
COIN_DIAMETER_CM = 2.5  # New 5-peso coin = 25 mm
CALIBRATION_STAGE1_FILE = BASE_DIR / "calibration_stage1.json"
CALIBRATION_STAGE2_FILE = BASE_DIR / "calibration_stage2.json"
DEFAULT_PIXELS_PER_CM_STAGE1 = 45.0
DEFAULT_PIXELS_PER_CM_STAGE2 = 45.0

# Conveyor speed used during runtime measurement.
CONVEYOR_SPEED_CM_PER_SEC = 8.5

# In-app calibration settings (Stage 1 button in dashboard)
CALIBRATION_TARGET_SAMPLES = 20
CALIBRATION_MIN_SAMPLE_INTERVAL_SEC = 0.20
CALIBRATION_MAX_DURATION_SEC = 45.0
CALIBRATION_COIN_MIN_RADIUS_PX = 12
CALIBRATION_COIN_MAX_RADIUS_PX = 220
CALIBRATION_COIN_MIN_AREA_PX = 450
CALIBRATION_COIN_MIN_CIRCULARITY = 0.82
CALIBRATION_COIN_MIN_FILL_RATIO = 0.72
CALIBRATION_COIN_MAX_FILL_RATIO = 1.22
CALIBRATION_COIN_EDGE_MARGIN_RATIO = 1.25
CALIBRATION_COIN_MAX_CENTER_SHIFT_PX = 10.0
CALIBRATION_COIN_MAX_DIAMETER_DELTA_PX = 4.0

# Temporal smoothing for moving onions.
DIAMETER_SMOOTHING_FRAMES = 6
TRACK_MAX_CENTER_JUMP_PX = 75
TRACK_LOST_RESET_FRAMES = 5

# UI colors (BGR)
COLOR_OK = (40, 220, 40)
COLOR_WARN = (0, 220, 255)
COLOR_ALERT = (40, 40, 220)
COLOR_INFO = (200, 200, 200)
COLOR_LINE = (255, 180, 60)
