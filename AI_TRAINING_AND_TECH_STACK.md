# Onion Sorting AI Training and Tech Stack Documentation

## 1) Purpose

This document explains the onion sorting project in two aligned layers:

- Training layer: onion detection AI was trained in Roboflow.
- Runtime layer (actual project code): contour-based computer vision with calibrated geometry is used to measure onion diameter and trigger sorting.

The result is practical and correct for size sorting: AI can help detect candidate onion regions, while contour + calibration provides stable physical size measurement in centimeters.

## 2) High-Level System Flow

1. Two cameras capture onions moving on a conveyor.
2. A detector identifies onion shape in each frame.
3. Contour analysis fits a circle and estimates diameter in pixels.
4. Calibration converts pixels to centimeters.
5. Onion is classified as SMALL, MEDIUM, or LARGE.
6. Trigger lines and delayed events activate servo gates.
7. A Flask dashboard shows live video, status, and calibration controls.

## 3) Libraries and Technologies Used

### Core Python Libraries

- OpenCV (`cv2`)
  - Main computer vision engine: camera capture, color conversion, thresholding, morphology, contour extraction, circle fitting, drawing overlays, MJPEG encoding.
  - Used heavily in vision, calibration, camera handling, smoke testing, and dashboard frame encoding.

- NumPy (`numpy`)
  - Array operations and robust statistics support for segmentation and calibration sample filtering.

- Flask
  - Web server and API for live monitoring, calibration buttons, and manual servo endpoints.

### Hardware and I/O Libraries

- `RPi.GPIO`
  - GPIO control for direct servo PWM mode and physical manual push buttons.

- `adafruit-blinka` + `adafruit-circuitpython-pca9685`
  - I2C-based servo control through PCA9685 board.
  - Imported as `board`, `busio`, and `adafruit_pca9685.PCA9685`.

- `picamera2` (system package on Raspberry Pi)
  - CSI camera support with stable field-of-view and autofocus control where available.

### AI Platform (Training Source)

- Roboflow
  - Dataset management, annotation, augmentation, and cloud model training.
  - The onion detector is trained in Roboflow, then exported and integrated with the contour measurement pipeline.

## 4) Roboflow Training Workflow

Training process:

1. Data collection
   - Capture frame samples from both stage cameras under normal conveyor lighting.
   - Include motion blur cases, glare, shadows, and partial onion visibility.

2. Annotation in Roboflow
   - Label onion objects (bounding boxes or segmentation masks).
   - Keep labeling consistent at onion boundaries.

3. Dataset versioning and preprocessing
   - Resize to a fixed resolution.
   - Apply augmentations (brightness, blur, rotation, slight hue shifts).
   - Split into train/validation/test sets.

4. Model training
   - Train an onion detector model in Roboflow (for example, YOLO family).
   - Select best model version by validation metrics.

5. Export and deployment
   - Export model for edge runtime (for example ONNX/TFLite).
   - Use the model to find onion candidate regions in each frame.

6. Final size decision (critical)
   - Even with AI detection, final onion sizing uses contour + calibrated pixels-to-cm conversion.
   - This keeps size classes physically meaningful and repeatable.

## 5) Correct Runtime Sizing Process (Contour + Calibration)

This is the correct measurement flow used by the current system:

1. Capture frame from Stage 1 and Stage 2 cameras.
2. Segment onion candidate pixels in HSV color space.
3. Clean masks with morphology (open/close).
4. Extract contours and pick the best valid onion contour.
5. Fit enclosing circle, compute diameter in pixels.
6. Smooth diameter across recent frames.
7. Convert to centimeters with per-stage `pixels_per_cm`.
8. Classify:
   - `SMALL`: diameter below threshold
   - `MEDIUM`: within medium range
   - `LARGE`: above large threshold
9. Trigger stage event when onion center crosses configured trigger line.
10. Schedule servo action after travel delay to match conveyor movement.

## 6) Calibration Process

Calibration is stage-specific and stored separately.

1. Place reference coin (configured 20-peso equivalent diameter in config).
2. Detect the coin contour and estimate diameter in pixels.
3. Collect multiple stable samples.
4. Apply outlier filtering.
5. Compute and save `pixels_per_cm` to JSON.
6. Runtime uses these values for real-world onion diameter computation.

Calibration files:

- `calibration_stage1.json`
- `calibration_stage2.json`

## 7) File-by-File Mapping: Responsibilities, Libraries, and Tools

| File | Main Responsibility | Libraries / Tools Used |
|---|---|---|
| `main.py` | App orchestration, dual-camera loop, detection cycle, calibration state machine, status publishing, event/servo integration | `cv2`, `numpy`, `threading`, `subprocess`, `json`, `zlib`, local modules (`vision`, `camera_manager`, `dashboard`, `scheduler`, `servo_control`) |
| `vision.py` | Onion segmentation, contour filtering, circle fit, diameter smoothing, size classification, trigger-line logic | `cv2`, `numpy`, `math`, `deque`, `dataclasses` |
| `calibration.py` | Interactive calibration capture and save for each stage | `cv2`, `numpy`, `argparse`, `statistics`, `json` |
| `camera_manager.py` | Camera abstraction for CSI, USB, and optional gstreamer sources | `cv2`, optional `picamera2`, project `config` |
| `servo_control.py` | Servo control abstraction for GPIO PWM or PCA9685 driver | `RPi.GPIO`, `board`, `busio`, `adafruit_pca9685`, `threading`, `time` |
| `scheduler.py` | Delayed event execution (servo timing, async callbacks) | `heapq`, `threading`, `dataclasses`, `time` |
| `dashboard.py` | Flask web app, MJPEG streaming, API endpoints for status/calibration/manual servo | `flask`, `cv2`, `threading` |
| `config.py` | Central system configuration (camera, thresholds, servo, calibration, dashboard) | `os`, `pathlib` |
| `scripts/dual_camera_smoke.py` | Camera smoke test and snapshot tool | `cv2`, `argparse`, `time` |
| `templates/index.html` | Main web dashboard UI | Flask template engine, HTML/CSS/JS |
| `templates/servo.html` | Manual servo control page UI | Flask template engine, HTML/CSS/JS |
| `static/style.css` | Dashboard styling | CSS |
| `requirements.txt` | Python dependency list for runtime | `flask`, `numpy`, `opencv-python`, `RPi.GPIO`, `adafruit-blinka`, `adafruit-circuitpython-pca9685` |

## 8) Where Roboflow Fits in This Project

In this project:

- Roboflow is the training and dataset platform.
- Runtime still relies on contour-based measurement for accurate physical sizing.
- This hybrid approach is correct for conveyor grading because centimeter calibration is explicit and auditable.

If you later add direct model inference in code, place it before contour filtering as a candidate-region step, then keep contour + calibration as the final sizing authority.
