import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

import cv2
import numpy as np

import config
from camera_manager import CameraStream


def _deviation_filter_samples(samples_px):
    if not samples_px:
        return []
    if len(samples_px) <= 2:
        return [float(v) for v in samples_px]

    values = np.array(samples_px, dtype=np.float32)
    center = float(np.median(values))
    mad = float(np.median(np.abs(values - center)))
    if mad <= 1e-6:
        return [float(v) for v in values]

    robust_sigma = 1.4826 * mad
    sigma_k = float(getattr(config, "CALIBRATION_OUTLIER_SIGMA", 2.2))
    keep = np.abs(values - center) <= (sigma_k * robust_sigma)
    filtered = values[keep]
    if len(filtered) < max(3, len(values) - 2):
        return [float(v) for v in values]
    return [float(v) for v in filtered]


def detect_coin_candidate(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur_k = max(3, int(getattr(config, "CALIBRATION_GAUSSIAN_KERNEL", 5)))
    if blur_k % 2 == 0:
        blur_k += 1
    gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = gray.shape[:2]

    _, mask_gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    glare_min = int(getattr(config, "CALIBRATION_GLARE_VALUE_MIN", 235))
    mask_glare = cv2.inRange(hsv[:, :, 2], glare_min, 255)
    mask = cv2.bitwise_or(mask_gray, mask_glare)

    mk = max(3, int(getattr(config, "CALIBRATION_MORPH_KERNEL", 5)))
    if mk % 2 == 0:
        mk += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (mk, mk))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return None

    best = None
    best_score = -1e9
    max_area = float(h * w) * 0.45

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 200 or area > max_area:
            continue

        peri = cv2.arcLength(contour, True)
        if peri <= 0:
            continue

        circularity = float((4.0 * math.pi * area) / (peri * peri))
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = float(area / hull_area) if hull_area > 0 else 0.0

        if len(contour) < 5:
            continue

        ellipse = cv2.fitEllipse(contour)
        cx, cy = ellipse[0]
        major_axis = float(max(ellipse[1]))
        minor_axis = float(min(ellipse[1]))

        if minor_axis <= 0:
            continue
        if major_axis < (2.0 * float(config.CALIBRATION_COIN_MIN_RADIUS_PX)):
            continue
        if major_axis > (2.0 * float(config.CALIBRATION_COIN_MAX_RADIUS_PX)):
            continue

        aspect_ratio = major_axis / max(minor_axis, 1e-6)
        mean_diameter = 0.5 * (major_axis + minor_axis)
        edge_margin = (mean_diameter * 0.5) * float(config.CALIBRATION_COIN_EDGE_MARGIN_RATIO)
        if not (edge_margin <= cx <= (w - edge_margin) and edge_margin <= cy <= (h - edge_margin)):
            continue

        ellipse_area = float(np.pi * (major_axis * 0.5) * max(minor_axis * 0.5, 1e-6))
        fill_ratio = float(area / ellipse_area) if ellipse_area > 0.0 else 0.0

        valid_shape = bool(
            solidity >= float(getattr(config, "CALIBRATION_COIN_MIN_SOLIDITY", 0.72))
            and aspect_ratio <= float(getattr(config, "CALIBRATION_COIN_MAX_ASPECT_RATIO", 2.3))
            and circularity >= float(config.CALIBRATION_COIN_MIN_CIRCULARITY)
            and fill_ratio >= float(config.CALIBRATION_COIN_MIN_FILL_RATIO)
        )
        if not valid_shape:
            continue

        score = (area * 0.0025) + (solidity * 2.5) + (circularity * 1.5) + (1.2 / max(1.0, aspect_ratio))
        if score > best_score:
            best_score = score
            best = {
                "center": (int(round(cx)), int(round(cy))),
                "major_axis": major_axis,
                "minor_axis": minor_axis,
                "diameter_px": mean_diameter,
                "circularity": circularity,
                "solidity": solidity,
                "aspect_ratio": aspect_ratio,
            }

    return best


def stage_source(stage: int):
    if stage == 1:
        return config.STAGE1_SOURCE, config.STAGE1_BACKEND, config.CALIBRATION_STAGE1_FILE
    return config.STAGE2_SOURCE, config.STAGE2_BACKEND, config.CALIBRATION_STAGE2_FILE


def save_calibration(path: Path, samples):
    filtered = _deviation_filter_samples(samples)
    avg_px = mean(filtered)
    std_px = pstdev(filtered) if len(filtered) > 1 else 0.0
    cm_per_pixel = float(config.COIN_DIAMETER_CM) / float(avg_px)
    pixels_per_cm = 1.0 / cm_per_pixel

    payload = {
        "pixels_per_cm": round(pixels_per_cm, 6),
        "cm_per_pixel": round(cm_per_pixel, 8),
        "coin_diameter_cm": float(config.COIN_DIAMETER_CM),
        "coin_diameter_mm": int(float(config.COIN_DIAMETER_CM) * 10),
        "sample_count": int(len(filtered)),
        "raw_sample_count": int(len(samples)),
        "mean_coin_diameter_px": round(avg_px, 4),
        "std_coin_diameter_px": round(std_px, 4),
        "filtered_out": int(max(0, len(samples) - len(filtered))),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Calibrate one stage using a 20-peso coin (2.7 cm).")
    parser.add_argument("--stage", type=int, choices=[1, 2], required=True, help="Calibration stage: 1 or 2")
    args = parser.parse_args()

    source, backend, output_file = stage_source(args.stage)

    cam = CameraStream(
        source=source,
        width=config.FRAME_WIDTH,
        height=config.FRAME_HEIGHT,
        fps=config.TARGET_FPS,
        backend=backend,
        name=f"stage{args.stage}-camera",
    )

    samples = []
    target_samples = int(config.CALIBRATION_TARGET_SAMPLES)
    min_interval = float(config.CALIBRATION_MIN_SAMPLE_INTERVAL_SEC)
    last_sample_ts = 0.0
    last_center = None
    last_diameter = None
    window_name = f"Calibration Stage {args.stage} (20-peso = {config.COIN_DIAMETER_CM:.1f}cm)"
    print("Controls: [R]=reset samples, [Q]=quit")
    print(f"Auto-capturing {target_samples} stable centered frames")

    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                frame = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
                cv2.putText(
                    frame,
                    "Camera frame not available",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (40, 40, 220),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
                continue

            candidate = detect_coin_candidate(frame)
            diameter_px = None
            accepted = False
            status = "coin not detected"

            if candidate is not None:
                cx, cy = candidate["center"]
                major = float(candidate["major_axis"])
                minor = float(candidate["minor_axis"])
                diameter_px = float(candidate["diameter_px"])
                radius = max(1, int(round(0.5 * diameter_px)))

                stable = True
                if last_center is not None and last_diameter is not None:
                    dx = float(cx - last_center[0])
                    dy = float(cy - last_center[1])
                    center_shift = float(np.hypot(dx, dy))
                    diameter_delta = abs(diameter_px - float(last_diameter))
                    stable = (
                        center_shift <= float(config.CALIBRATION_COIN_MAX_CENTER_SHIFT_PX)
                        and diameter_delta <= float(config.CALIBRATION_COIN_MAX_DIAMETER_DELTA_PX)
                    )

                last_center = (cx, cy)
                last_diameter = diameter_px

                can_sample = (time.monotonic() - last_sample_ts) >= min_interval
                accepted = stable and can_sample
                if accepted and len(samples) < target_samples:
                    samples.append(diameter_px)
                    last_sample_ts = time.monotonic()
                    status = f"sample {len(samples)}/{target_samples} captured"
                elif not stable:
                    status = f"coin moved: hold still ({len(samples)}/{target_samples})"
                else:
                    status = f"hold still... ({len(samples)}/{target_samples})"

                color = (40, 220, 40) if accepted else (0, 220, 255)
                cv2.ellipse(frame, ((float(cx), float(cy)), (major, minor), 0.0), color, 2)
                cv2.circle(frame, (cx, cy), radius, color, 2)
                cv2.circle(frame, (cx, cy), 3, color, -1)
                cv2.putText(
                    frame,
                    f"d_px={(diameter_px):.2f} maj={major:.1f} min={minor:.1f}",
                    (20, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.72,
                    color,
                    2,
                    cv2.LINE_AA,
                )

            if candidate is None:
                cv2.putText(
                    frame,
                    "coin not detected",
                    (20, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.72,
                    (40, 40, 220),
                    2,
                    cv2.LINE_AA,
                )

            if samples:
                avg_px = mean(samples)
                est_cm_per_px = float(config.COIN_DIAMETER_CM) / avg_px
                cv2.putText(
                    frame,
                    f"samples={len(samples)}/{target_samples} avg_px={avg_px:.2f} cm/px={est_cm_per_px:.5f}",
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.62,
                    (220, 220, 220),
                    2,
                    cv2.LINE_AA,
                )

            cv2.putText(
                frame,
                status,
                (20, 102),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (220, 220, 220),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                frame,
                "R=reset  Q=quit",
                (20, frame.shape[0] - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("r"):
                samples.clear()
                last_center = None
                last_diameter = None
                print("samples cleared")
            elif key in (ord("q"), 27):
                break

            if len(samples) >= target_samples:
                payload = save_calibration(output_file, samples)
                print(f"saved calibration to {output_file}")
                print(json.dumps(payload, indent=2))
                break

    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
