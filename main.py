import json
import os
import subprocess
import threading
import time
import zlib
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

import cv2
import numpy as np

try:
    import RPi.GPIO as GPIO_BUTTONS
except Exception:
    GPIO_BUTTONS = None

import config
from camera_manager import CameraStream
from dashboard import SharedState, create_app
from scheduler import TimedEventScheduler
from servo_control import ServoController
from vision import DetectionResult, StageDetector


def load_pixels_per_cm(path: Path, fallback: float) -> float:
    if not path.exists():
        print(f"[calibration] missing {path.name}, using fallback {fallback:.2f}")
        return fallback

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ppcm = float(data.get("pixels_per_cm", fallback))
        if ppcm <= 0:
            raise ValueError("pixels_per_cm must be > 0")
        return ppcm
    except Exception as exc:
        print(f"[calibration] failed to read {path.name}: {exc}; using fallback {fallback:.2f}")
        return fallback


def save_stage1_calibration(path: Path, samples_px):
    avg_px = mean(samples_px)
    std_px = pstdev(samples_px) if len(samples_px) > 1 else 0.0
    pixels_per_cm = avg_px / config.COIN_DIAMETER_CM

    payload = {
        "pixels_per_cm": round(pixels_per_cm, 6),
        "coin_diameter_cm": config.COIN_DIAMETER_CM,
        "coin_diameter_mm": int(config.COIN_DIAMETER_CM * 10),
        "sample_count": len(samples_px),
        "mean_coin_diameter_px": round(avg_px, 4),
        "std_coin_diameter_px": round(std_px, 4),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def detect_coin_candidate(frame_bgr):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        7,
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = gray.shape[:2]
    best = None
    best_score = -1.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < float(config.CALIBRATION_COIN_MIN_AREA_PX):
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue

        circularity = float((4.0 * np.pi * area) / (perimeter * perimeter))
        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        radius = float(radius)
        if radius < float(config.CALIBRATION_COIN_MIN_RADIUS_PX):
            continue
        if radius > float(config.CALIBRATION_COIN_MAX_RADIUS_PX):
            continue

        circle_area = float(np.pi * radius * radius)
        if circle_area <= 0.0:
            continue
        fill_ratio = float(area / circle_area)

        edge_margin = float(radius * float(config.CALIBRATION_COIN_EDGE_MARGIN_RATIO))
        inside_frame = edge_margin <= cx <= (w - edge_margin) and edge_margin <= cy <= (h - edge_margin)

        valid_shape = (
            circularity >= float(config.CALIBRATION_COIN_MIN_CIRCULARITY)
            and float(config.CALIBRATION_COIN_MIN_FILL_RATIO) <= fill_ratio <= float(config.CALIBRATION_COIN_MAX_FILL_RATIO)
            and inside_frame
        )

        score = (min(circularity, 1.25) * 2.0) + (1.0 - min(abs(fill_ratio - 1.0), 1.0)) + (radius * 0.002)
        if score > best_score:
            best_score = score
            best = {
                "center": (int(round(cx)), int(round(cy))),
                "radius": radius,
                "diameter_px": radius * 2.0,
                "circularity": circularity,
                "fill_ratio": fill_ratio,
                "valid_shape": bool(valid_shape),
                "method": "contour",
            }

    if best is not None and bool(best.get("valid_shape", False)):
        return best

    # Fallback: reflective coins can produce poor binary contours but still form
    # strong circular edges. Use Hough circles so calibration can continue.
    gray_hough = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gray_hough = cv2.medianBlur(gray_hough, 5)
    circles = cv2.HoughCircles(
        gray_hough,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(24, int(min(h, w) * 0.12)),
        param1=110,
        param2=18,
        minRadius=int(config.CALIBRATION_COIN_MIN_RADIUS_PX),
        maxRadius=int(config.CALIBRATION_COIN_MAX_RADIUS_PX),
    )

    if circles is not None and len(circles) > 0:
        hough_best = None
        hough_score = -1e9
        cx0 = w / 2.0
        cy0 = h / 2.0

        for circle in circles[0]:
            cx, cy, radius = float(circle[0]), float(circle[1]), float(circle[2])
            if radius <= 0:
                continue

            edge_margin = float(radius * float(config.CALIBRATION_COIN_EDGE_MARGIN_RATIO))
            inside_frame = edge_margin <= cx <= (w - edge_margin) and edge_margin <= cy <= (h - edge_margin)
            if not inside_frame:
                continue

            center_dist = float(np.hypot(cx - cx0, cy - cy0))
            score = (radius * 0.03) - (center_dist * 0.01)
            if score > hough_score:
                hough_score = score
                hough_best = {
                    "center": (int(round(cx)), int(round(cy))),
                    "radius": radius,
                    "diameter_px": radius * 2.0,
                    "circularity": 1.0,
                    "fill_ratio": 1.0,
                    "valid_shape": True,
                    "method": "hough",
                }

        if hough_best is not None:
            return hough_best

    return best


def draw_coin_overlay(frame_bgr, candidate: dict, accepted: bool):
    if candidate is None:
        return

    center = candidate["center"]
    radius = max(1, int(round(candidate["radius"])))
    color = (50, 220, 50) if accepted else (0, 200, 255)
    cv2.circle(frame_bgr, center, radius, color, 2, cv2.LINE_AA)
    cv2.circle(frame_bgr, center, 3, color, -1, cv2.LINE_AA)

    method = str(candidate.get("method", "contour")).upper()
    label = f"Coin {method} circ={candidate['circularity']:.3f} fill={candidate['fill_ratio']:.2f}"
    y = max(24, center[1] - radius - 8)
    cv2.putText(
        frame_bgr,
        label,
        (max(8, center[0] - radius), y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        color,
        2,
        cv2.LINE_AA,
    )


def new_cal_state() -> dict:
    return {
        "active": False,
        "target": int(config.CALIBRATION_TARGET_SAMPLES),
        "samples": [],
        "message": "Idle",
        "started_at": 0.0,
        "last_sample_ts": 0.0,
        "last_center": None,
        "last_diameter_px": None,
    }


def process_calibration_state(stage: int, cal_state: dict, frame, detector, out_file: Path, now: float, analysis_frame=None) -> float:
    if not cal_state["active"]:
        return detector.pixels_per_cm

    if frame is None:
        cal_state["message"] = f"Stage {stage}: camera frame unavailable"
        return detector.pixels_per_cm

    if (now - cal_state["started_at"]) > float(config.CALIBRATION_MAX_DURATION_SEC):
        cal_state["active"] = False
        cal_state["message"] = f"Stage {stage}: timeout. Keep coin still and centered, then retry."
        return detector.pixels_per_cm

    source_for_detection = analysis_frame if analysis_frame is not None else frame
    candidate = detect_coin_candidate(source_for_detection)
    if candidate is None:
        cal_state["message"] = f"Stage {stage}: no valid coin contour detected"
    else:
        accepted = bool(candidate["valid_shape"])
        stable = True

        last_center = cal_state.get("last_center")
        last_diameter_px = cal_state.get("last_diameter_px")
        if last_center is not None and last_diameter_px is not None:
            dx = float(candidate["center"][0] - last_center[0])
            dy = float(candidate["center"][1] - last_center[1])
            center_shift = float(np.hypot(dx, dy))
            diameter_delta = abs(float(candidate["diameter_px"]) - float(last_diameter_px))
            stable = (
                center_shift <= float(config.CALIBRATION_COIN_MAX_CENTER_SHIFT_PX)
                and diameter_delta <= float(config.CALIBRATION_COIN_MAX_DIAMETER_DELTA_PX)
            )

        cal_state["last_center"] = tuple(candidate["center"])
        cal_state["last_diameter_px"] = float(candidate["diameter_px"])

        accepted = accepted and stable
        draw_coin_overlay(frame, candidate, accepted)

        if not candidate["valid_shape"]:
            cal_state["message"] = (
                f"Stage {stage}: coin not round enough "
                f"(circ={candidate['circularity']:.3f})"
            )
        elif not stable:
            cal_state["message"] = (
                f"Stage {stage}: coin moved. Keep still "
                f"{len(cal_state['samples'])}/{cal_state['target']}"
            )
        elif (now - cal_state["last_sample_ts"]) >= float(config.CALIBRATION_MIN_SAMPLE_INTERVAL_SEC):
            cal_state["samples"].append(float(candidate["diameter_px"]))
            cal_state["last_sample_ts"] = now
            cal_state["message"] = (
                f"Stage {stage}: sampling {len(cal_state['samples'])}/{cal_state['target']} "
                f"(circ={candidate['circularity']:.3f})"
            )
        else:
            cal_state["message"] = (
                f"Stage {stage}: hold still... "
                f"{len(cal_state['samples'])}/{cal_state['target']}"
            )

    if len(cal_state["samples"]) >= cal_state["target"]:
        payload = save_stage1_calibration(out_file, cal_state["samples"])
        new_ppcm = float(payload["pixels_per_cm"])
        detector.pixels_per_cm = new_ppcm
        cal_state["active"] = False
        cal_state["message"] = f"Stage {stage}: done. pixels_per_cm={new_ppcm:.3f}"
        print(f"[calibration] Stage {stage} saved: {out_file}")

    return detector.pixels_per_cm


def make_blank_frame(width: int, height: int, label: str):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        frame,
        label,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (50, 50, 220),
        2,
        cv2.LINE_AA,
    )
    return frame


def combine_side_by_side(left, right):
    h = min(left.shape[0], right.shape[0])
    left_resized = cv2.resize(left, (int(left.shape[1] * h / left.shape[0]), h))
    right_resized = cv2.resize(right, (int(right.shape[1] * h / right.shape[0]), h))
    return np.hstack([left_resized, right_resized])


def fit_to_display(frame, target_w: int, target_h: int):
    src_h, src_w = frame.shape[:2]
    if src_h <= 0 or src_w <= 0:
        return frame

    scale = min(target_w / float(src_w), target_h / float(src_h))
    out_w = max(1, int(src_w * scale))
    out_h = max(1, int(src_h * scale))
    resized = cv2.resize(frame, (out_w, out_h))

    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x0 = (target_w - out_w) // 2
    y0 = (target_h - out_h) // 2
    canvas[y0 : y0 + out_h, x0 : x0 + out_w] = resized
    return canvas


def run_web_server(shared_state: SharedState):
    app = create_app(shared_state, app_name=config.APP_NAME)
    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


def open_camera(name: str, source, backend: str, required: bool = True):
    try:
        return CameraStream(
            source=source,
            width=config.FRAME_WIDTH,
            height=config.FRAME_HEIGHT,
            fps=config.TARGET_FPS,
            backend=backend,
            name=name,
        )
    except RuntimeError as first_error:
        if not isinstance(source, int):
            if required:
                raise
            print(f"[camera] {name}: optional camera unavailable ({first_error})")
            return None

        tried = [source]
        for candidate in range(4):
            if candidate == source:
                continue
            tried.append(candidate)
            try:
                print(f"[camera] {name}: fallback trying index {candidate}")
                return CameraStream(
                    source=candidate,
                    width=config.FRAME_WIDTH,
                    height=config.FRAME_HEIGHT,
                    fps=config.TARGET_FPS,
                    backend=backend,
                    name=name,
                )
            except RuntimeError:
                continue

        if required:
            raise RuntimeError(f"Failed to open {name}. Tried camera indices: {tried}") from first_error

        print(f"[camera] {name}: optional camera unavailable. Tried indices: {tried}")
        return None


def classify_diameter(diameter_cm: float) -> str:
    if diameter_cm <= 0:
        return "NO_OBJECT"
    if diameter_cm >= config.LARGE_GT_CM:
        return "LARGE"
    if config.MEDIUM_MIN_CM <= diameter_cm <= config.MEDIUM_MAX_CM:
        return "MEDIUM"
    return "SMALL"


def close_local_kiosk_browser() -> None:
    if os.name != "posix":
        return

    try:
        subprocess.run(
            [
                "bash",
                "-lc",
                "pkill -f 'chromium.*127.0.0.1:5000' || true; "
                "pkill -f 'chromium-browser.*127.0.0.1:5000' || true",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def frame_signature(frame) -> int:
    small = cv2.resize(frame, (64, 48), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return zlib.crc32(gray.tobytes())


def main():
    stage1_ppcm = load_pixels_per_cm(config.CALIBRATION_STAGE1_FILE, config.DEFAULT_PIXELS_PER_CM_STAGE1)
    stage2_ppcm = load_pixels_per_cm(config.CALIBRATION_STAGE2_FILE, config.DEFAULT_PIXELS_PER_CM_STAGE2)

    cam1 = open_camera("stage1-camera", config.STAGE1_SOURCE, config.STAGE1_BACKEND, required=True)
    cam2 = open_camera(
        "stage2-camera",
        config.STAGE2_SOURCE,
        config.STAGE2_BACKEND,
        required=not config.STAGE2_OPTIONAL,
    )
    single_camera_mode = cam2 is None
    if single_camera_mode:
        print("[mode] Stage2 camera missing -> single-camera fallback enabled")

    detector1 = StageDetector(
        stage_name="STAGE1",
        stage_kind="large_gate",
        pixels_per_cm=stage1_ppcm,
        small_max_cm=config.SMALL_MAX_CM,
        medium_min_cm=config.MEDIUM_MIN_CM,
        medium_max_cm=config.MEDIUM_MAX_CM,
        large_gt_cm=config.LARGE_GT_CM,
        min_contour_area=config.MIN_CONTOUR_AREA,
        circularity_min=config.CIRCULARITY_MIN,
        circularity_max=config.CIRCULARITY_MAX,
        blur_kernel_size=config.BLUR_KERNEL_SIZE,
        morph_kernel_size=config.MORPH_KERNEL_SIZE,
        threshold_invert=config.THRESHOLD_INVERT,
        trigger_axis=config.STAGE1_TRIGGER_AXIS,
        trigger_ratio=config.STAGE1_TRIGGER_RATIO,
        trigger_tolerance_px=config.STAGE1_TRIGGER_TOLERANCE_PX,
        trigger_cooldown_sec=config.STAGE1_TRIGGER_COOLDOWN_SEC,
        diameter_smoothing_frames=config.DIAMETER_SMOOTHING_FRAMES,
        track_max_center_jump_px=config.TRACK_MAX_CENTER_JUMP_PX,
        track_lost_reset_frames=config.TRACK_LOST_RESET_FRAMES,
        roi=config.STAGE1_ROI,
    )

    detector2 = StageDetector(
        stage_name="STAGE2",
        stage_kind="medium_gate",
        pixels_per_cm=stage2_ppcm,
        small_max_cm=config.SMALL_MAX_CM,
        medium_min_cm=config.MEDIUM_MIN_CM,
        medium_max_cm=config.MEDIUM_MAX_CM,
        large_gt_cm=config.LARGE_GT_CM,
        min_contour_area=config.MIN_CONTOUR_AREA,
        circularity_min=config.CIRCULARITY_MIN,
        circularity_max=config.CIRCULARITY_MAX,
        blur_kernel_size=config.BLUR_KERNEL_SIZE,
        morph_kernel_size=config.MORPH_KERNEL_SIZE,
        threshold_invert=config.THRESHOLD_INVERT,
        trigger_axis=config.STAGE2_TRIGGER_AXIS,
        trigger_ratio=config.STAGE2_TRIGGER_RATIO,
        trigger_tolerance_px=config.STAGE2_TRIGGER_TOLERANCE_PX,
        trigger_cooldown_sec=config.STAGE2_TRIGGER_COOLDOWN_SEC,
        diameter_smoothing_frames=config.DIAMETER_SMOOTHING_FRAMES,
        track_max_center_jump_px=config.TRACK_MAX_CENTER_JUMP_PX,
        track_lost_reset_frames=config.TRACK_LOST_RESET_FRAMES,
        roi=config.STAGE2_ROI,
    )

    scheduler = TimedEventScheduler()
    scheduler.start()

    servo = ServoController(
        enabled=config.SERVO_ENABLED,
        driver=config.SERVO_DRIVER,
        servo1_pin=config.SERVO1_PIN,
        servo2_pin=config.SERVO2_PIN,
        servo1_channel=config.SERVO1_CHANNEL,
        servo2_channel=config.SERVO2_CHANNEL,
        rest_angle=config.SERVO_REST_ANGLE,
        push_angle=config.SERVO_PUSH_ANGLE,
        back_angle=config.SERVO_BACK_ANGLE,
        servo1_rest_angle=config.SERVO1_REST_ANGLE,
        servo1_push_angle=config.SERVO1_PUSH_ANGLE,
        servo1_back_angle=config.SERVO1_BACK_ANGLE,
        servo1_reverse=config.SERVO1_REVERSE,
        servo1_trim_deg=config.SERVO1_TRIM_DEG,
        servo2_rest_angle=config.SERVO2_REST_ANGLE,
        servo2_push_angle=config.SERVO2_PUSH_ANGLE,
        servo2_back_angle=config.SERVO2_BACK_ANGLE,
        servo2_reverse=config.SERVO2_REVERSE,
        servo2_trim_deg=config.SERVO2_TRIM_DEG,
        hold_sec=config.SERVO_HOLD_SEC,
        cooldown_sec=config.SERVO_COOLDOWN_SEC,
        pca9685_address=config.PCA9685_ADDRESS,
        pca9685_frequency=config.PCA9685_FREQUENCY,
        servo_min_pulse_us=config.SERVO_MIN_PULSE_US,
        servo_max_pulse_us=config.SERVO_MAX_PULSE_US,
    )

    shared_state = SharedState(
        stream_max_fps=config.WEB_STREAM_MAX_FPS,
        jpeg_quality=config.WEB_JPEG_QUALITY,
    )

    if config.ENABLE_WEB_DASHBOARD:
        web_thread = threading.Thread(target=run_web_server, args=(shared_state,), daemon=True)
        web_thread.start()
        print(f"[web] dashboard started at http://{config.WEB_HOST}:{config.WEB_PORT}")

    calibration_stage1 = new_cal_state()
    calibration_stage2 = new_cal_state()

    counters = {"large": 0, "medium": 0, "small": 0}
    fps = 0.0
    prev_ts = time.monotonic()

    cam1_last_sig = None
    cam1_stale_count = 0
    cam2_last_sig = None
    cam2_stale_count = 0
    stale_limit_frames = 90
    manual_next_ready_ts = {"servo1": 0.0, "servo2": 0.0}
    manual_button_next_ready_ts = {"servo1": 0.0, "servo2": 0.0}
    manual_button_prev_state = {"servo1": False, "servo2": False}
    manual_button_pins = {
        "servo1": int(config.MANUAL_BUTTON_SERVO1_PIN),
        "servo2": int(config.MANUAL_BUTTON_SERVO2_PIN),
    }
    manual_buttons_ready = False

    if bool(config.MANUAL_BUTTONS_ENABLED):
        if GPIO_BUTTONS is None:
            print("[buttons] RPi.GPIO unavailable. Physical tactile buttons disabled.")
        else:
            try:
                GPIO_BUTTONS.setwarnings(False)
                GPIO_BUTTONS.setmode(GPIO_BUTTONS.BCM)
                pull = GPIO_BUTTONS.PUD_UP if bool(config.MANUAL_BUTTON_ACTIVE_LOW) else GPIO_BUTTONS.PUD_DOWN
                for pin in manual_button_pins.values():
                    GPIO_BUTTONS.setup(pin, GPIO_BUTTONS.IN, pull_up_down=pull)
                manual_buttons_ready = True
                print(f"[buttons] enabled pins={manual_button_pins} active_low={bool(config.MANUAL_BUTTON_ACTIVE_LOW)}")
            except Exception as exc:
                manual_buttons_ready = False
                print(f"[buttons] init failed: {exc}. Physical tactile buttons disabled.")

    win_name = "Onion Sorting"

    try:
        while True:
            if shared_state.consume_stop_request():
                print("[app] Stop requested from dashboard")
                close_local_kiosk_browser()
                break

            now = time.monotonic()
            dt = now - prev_ts
            prev_ts = now
            if dt > 0:
                inst_fps = 1.0 / dt
                fps = inst_fps if fps == 0.0 else (fps * 0.90 + inst_fps * 0.10)

            cal_req = shared_state.consume_calibration_request()
            if cal_req:
                stage = int(cal_req.get("stage", 0))
                target = int(config.CALIBRATION_TARGET_SAMPLES)
                if stage == 1:
                    calibration_stage1 = new_cal_state()
                    calibration_stage1["active"] = True
                    calibration_stage1["target"] = target
                    calibration_stage1["message"] = "Stage 1: place still 5-peso coin on black belt"
                    calibration_stage1["started_at"] = now
                    print(f"[calibration] Stage 1 started (target={target})")
                elif stage == 2:
                    if cam2 is None:
                        calibration_stage2["message"] = "Stage 2: USB camera unavailable"
                    else:
                        calibration_stage2 = new_cal_state()
                        calibration_stage2["active"] = True
                        calibration_stage2["target"] = target
                        calibration_stage2["message"] = "Stage 2: place still 5-peso coin on black belt"
                        calibration_stage2["started_at"] = now
                        print(f"[calibration] Stage 2 started (target={target})")

            cal_cancel_req = shared_state.consume_calibration_cancel_request()
            if cal_cancel_req:
                stage = int(cal_cancel_req.get("stage", 0))
                if stage == 1:
                    calibration_stage1 = new_cal_state()
                    calibration_stage1["message"] = "Stage 1: calibration canceled"
                    print("[calibration] Stage 1 canceled by user")
                elif stage == 2:
                    calibration_stage2 = new_cal_state()
                    calibration_stage2["message"] = "Stage 2: calibration canceled"
                    print("[calibration] Stage 2 canceled by user")

            if manual_buttons_ready:
                debounce_sec = max(0.0, float(config.MANUAL_BUTTON_DEBOUNCE_SEC))
                active_low = bool(config.MANUAL_BUTTON_ACTIVE_LOW)
                for servo_key, pin in manual_button_pins.items():
                    try:
                        level = int(GPIO_BUTTONS.input(pin))
                    except Exception:
                        continue

                    is_pressed = (level == 0) if active_low else (level == 1)
                    was_pressed = bool(manual_button_prev_state[servo_key])

                    if is_pressed and (not was_pressed) and (now >= float(manual_button_next_ready_ts[servo_key])):
                        shared_state.request_manual_servo(servo_key)
                        manual_button_next_ready_ts[servo_key] = now + debounce_sec

                    manual_button_prev_state[servo_key] = is_pressed

            while True:
                manual_req = shared_state.consume_manual_servo_request()
                if not manual_req:
                    break

                servo_key = str(manual_req.get("servo", "")).strip().lower()
                if servo_key not in manual_next_ready_ts:
                    continue

                run_at = max(now, float(manual_next_ready_ts[servo_key]))
                delay = max(0.0, run_at - now)
                phase_pause = float(config.MANUAL_SERVO_PHASE_PAUSE_SEC)
                min_interval = float(config.MANUAL_SERVO_MIN_INTERVAL_SEC)

                # Dispatch each servo cycle in its own worker so servo1/servo2 can move in parallel.
                def start_manual_cycle(target_servo=servo_key, pause_sec=phase_pause):
                    threading.Thread(
                        target=servo.manual_cycle,
                        args=(
                            target_servo,
                            config.MANUAL_SERVO_CCW_ANGLE,
                            config.MANUAL_SERVO_CW_ANGLE,
                            pause_sec,
                        ),
                        daemon=True,
                    ).start()

                scheduler.schedule(delay, start_manual_cycle)
                manual_next_ready_ts[servo_key] = run_at + phase_pause + min_interval

            ok1, frame1 = cam1.read()
            if ok1 and frame1 is not None:
                sig1 = frame_signature(frame1)
                if cam1_last_sig is not None and sig1 == cam1_last_sig:
                    cam1_stale_count += 1
                else:
                    cam1_stale_count = 0
                cam1_last_sig = sig1

                if cam1_stale_count >= stale_limit_frames:
                    print("[camera] stage1-camera: feed appears frozen, reopening stream")
                    try:
                        cam1.release()
                    except Exception:
                        pass
                    cam1 = open_camera("stage1-camera", config.STAGE1_SOURCE, config.STAGE1_BACKEND, required=True)
                    ok1, frame1 = cam1.read()
                    cam1_stale_count = 0
                    cam1_last_sig = None

            raw_stage1_frame = frame1.copy() if (ok1 and frame1 is not None) else None
            ok2, frame2 = (False, None)
            if cam2 is not None:
                ok2, frame2 = cam2.read()
                if ok2 and frame2 is not None:
                    sig2 = frame_signature(frame2)
                    if cam2_last_sig is not None and sig2 == cam2_last_sig:
                        cam2_stale_count += 1
                    else:
                        cam2_stale_count = 0
                    cam2_last_sig = sig2

                    if cam2_stale_count >= stale_limit_frames:
                        print("[camera] stage2-camera: feed appears frozen, reopening stream")
                        try:
                            cam2.release()
                        except Exception:
                            pass
                        try:
                            cam2 = open_camera(
                                "stage2-camera",
                                config.STAGE2_SOURCE,
                                config.STAGE2_BACKEND,
                                required=False,
                            )
                        except Exception:
                            cam2 = None
                        if cam2 is not None:
                            ok2, frame2 = cam2.read()
                        else:
                            ok2, frame2 = False, None
                        cam2_stale_count = 0
                        cam2_last_sig = None
            raw_stage2_frame = frame2.copy() if (ok2 and frame2 is not None) else None

            if not ok1 or frame1 is None:
                frame1 = make_blank_frame(config.FRAME_WIDTH, config.FRAME_HEIGHT, "Stage1 camera not available")
                det1 = DetectionResult(stage_name="STAGE1")
            else:
                frame1, det1 = detector1.process(frame1, timestamp=now)

            stage2_using_stage1 = False
            if not ok2 or frame2 is None:
                if ok1 and frame1 is not None:
                    stage2_using_stage1 = True
                    frame2 = frame1.copy()
                    cv2.putText(
                        frame2,
                        "STAGE2 USING STAGE1 FEED (USB unavailable)",
                        (12, frame2.shape[0] - 16),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.52,
                        (80, 220, 255),
                        2,
                        cv2.LINE_AA,
                    )
                    det2 = DetectionResult(stage_name="STAGE2", class_label="FROM_STAGE1")
                else:
                    frame2 = make_blank_frame(config.FRAME_WIDTH, config.FRAME_HEIGHT, "Stage2 camera not available")
                    det2 = DetectionResult(stage_name="STAGE2")
            else:
                frame2, det2 = detector2.process(frame2, timestamp=now)

            stage1_ppcm = process_calibration_state(
                stage=1,
                cal_state=calibration_stage1,
                frame=frame1,
                detector=detector1,
                out_file=config.CALIBRATION_STAGE1_FILE,
                now=now,
                analysis_frame=raw_stage1_frame,
            )

            stage2_frame_for_cal = frame2 if (cam2 is not None and ok2 and frame2 is not None and not stage2_using_stage1) else None
            stage2_analysis_for_cal = (
                raw_stage2_frame
                if (cam2 is not None and ok2 and raw_stage2_frame is not None and not stage2_using_stage1)
                else None
            )
            stage2_ppcm = process_calibration_state(
                stage=2,
                cal_state=calibration_stage2,
                frame=stage2_frame_for_cal,
                detector=detector2,
                out_file=config.CALIBRATION_STAGE2_FILE,
                now=now,
                analysis_frame=stage2_analysis_for_cal,
            )

            cal_text = f"CAL1: {calibration_stage1['message']}"
            cv2.rectangle(frame1, (0, frame1.shape[0] - 34), (frame1.shape[1], frame1.shape[0]), (15, 15, 15), -1)
            cv2.putText(
                frame1,
                cal_text,
                (10, frame1.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (230, 230, 230),
                1,
                cv2.LINE_AA,
            )

            cal2_text = f"CAL2: {calibration_stage2['message']}"
            cv2.rectangle(frame2, (0, frame2.shape[0] - 34), (frame2.shape[1], frame2.shape[0]), (15, 15, 15), -1)
            cv2.putText(
                frame2,
                cal2_text,
                (10, frame2.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (230, 230, 230),
                1,
                cv2.LINE_AA,
            )

            if det1.triggered:
                class_from_stage1 = classify_diameter(det1.diameter_cm)
                if class_from_stage1 == "LARGE":
                    counters["large"] += 1
                elif stage2_using_stage1 and class_from_stage1 == "MEDIUM":
                    counters["medium"] += 1
                elif stage2_using_stage1 and class_from_stage1 == "SMALL":
                    counters["small"] += 1

            if (not stage2_using_stage1) and det2.triggered:
                if det2.class_label == "MEDIUM":
                    counters["medium"] += 1
                elif det2.class_label == "SMALL":
                    counters["small"] += 1

            combined = combine_side_by_side(frame1, frame2)

            servo_states = servo.get_states()
            status_line = (
                f"FPS:{fps:5.1f}  "
                f"L:{counters['large']} M:{counters['medium']} S:{counters['small']}  "
                f"S1:{servo_states.get('servo1','?')} S2:{servo_states.get('servo2','?')}"
            )
            cv2.rectangle(combined, (0, 0), (combined.shape[1], 34), (20, 20, 20), -1)
            cv2.putText(
                combined,
                status_line,
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (240, 240, 240),
                2,
                cv2.LINE_AA,
            )

            output_frame = combined
            if config.FIT_OUTPUT_TO_DISPLAY:
                output_frame = fit_to_display(combined, int(config.DISPLAY_WIDTH), int(config.DISPLAY_HEIGHT))

            shared_state.set_frame(output_frame, stream="combined")
            shared_state.set_frame(frame1, stream="stage1")
            shared_state.set_frame(frame2, stream="stage2")
            shared_state.set_status(
                {
                    "fps": round(fps, 2),
                    "counts": counters,
                    "servo": servo_states,
                    "stage1": {
                        "class": det1.class_label,
                        "diameter_cm": round(det1.diameter_cm, 3),
                        "pixels_per_cm": round(stage1_ppcm, 3),
                    },
                    "stage2": {
                        "class": det2.class_label if not stage2_using_stage1 else classify_diameter(det1.diameter_cm),
                        "diameter_cm": round(det2.diameter_cm, 3) if not stage2_using_stage1 else round(det1.diameter_cm, 3),
                        "pixels_per_cm": round(stage2_ppcm, 3),
                    },
                    "mode": "single_camera" if stage2_using_stage1 else "dual_camera",
                    "conveyor_speed_cm_s": round(float(config.CONVEYOR_SPEED_CM_PER_SEC), 2),
                    "calibration_stage1": {
                        "active": bool(calibration_stage1["active"]),
                        "sample_target": int(calibration_stage1["target"]),
                        "samples_collected": int(len(calibration_stage1["samples"])),
                        "message": str(calibration_stage1["message"]),
                        "coin_mm": int(config.COIN_DIAMETER_CM * 10),
                    },
                    "calibration_stage2": {
                        "active": bool(calibration_stage2["active"]),
                        "sample_target": int(calibration_stage2["target"]),
                        "samples_collected": int(len(calibration_stage2["samples"])),
                        "message": str(calibration_stage2["message"]),
                        "coin_mm": int(config.COIN_DIAMETER_CM * 10),
                    },
                }
            )

            if config.ENABLE_LOCAL_DISPLAY:
                cv2.imshow(win_name, output_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
            else:
                time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        close_local_kiosk_browser()
        cam1.release()
        if cam2 is not None:
            cam2.release()
        scheduler.stop()
        if manual_buttons_ready and GPIO_BUTTONS is not None:
            try:
                GPIO_BUTTONS.cleanup(list(manual_button_pins.values()))
            except Exception:
                pass
        servo.cleanup()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
