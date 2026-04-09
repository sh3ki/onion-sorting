import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

import cv2
import numpy as np

import config
from camera_manager import CameraStream


def detect_coin_circle(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=80,
        param1=120,
        param2=30,
        minRadius=10,
        maxRadius=220,
    )

    if circles is None:
        return None

    circles = circles[0]
    best = max(circles, key=lambda c: c[2])
    x, y, r = int(best[0]), int(best[1]), float(best[2])
    return x, y, r


def stage_source(stage: int):
    if stage == 1:
        return config.STAGE1_SOURCE, config.STAGE1_BACKEND, config.CALIBRATION_STAGE1_FILE
    return config.STAGE2_SOURCE, config.STAGE2_BACKEND, config.CALIBRATION_STAGE2_FILE


def save_calibration(path: Path, samples):
    avg_px = mean(samples)
    std_px = pstdev(samples) if len(samples) > 1 else 0.0
    pixels_per_cm = avg_px / config.COIN_DIAMETER_CM

    payload = {
        "pixels_per_cm": round(pixels_per_cm, 6),
        "coin_diameter_cm": config.COIN_DIAMETER_CM,
        "coin_diameter_mm": int(config.COIN_DIAMETER_CM * 10),
        "sample_count": len(samples),
        "mean_coin_diameter_px": round(avg_px, 4),
        "std_coin_diameter_px": round(std_px, 4),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Calibrate one stage camera using new 5-peso coin (25mm).")
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
    window_name = f"Calibration Stage {args.stage}"
    print("Controls: [Space]=capture sample, [R]=reset samples, [S]=save, [Q]=quit")

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

            circle = detect_coin_circle(frame)
            if circle is not None:
                x, y, r = circle
                diameter_px = 2.0 * r
                cv2.circle(frame, (x, y), int(r), (0, 220, 255), 2)
                cv2.circle(frame, (x, y), 3, (0, 220, 255), -1)
                cv2.putText(
                    frame,
                    f"coin diameter px: {diameter_px:.2f}",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 220, 255),
                    2,
                    cv2.LINE_AA,
                )
            else:
                diameter_px = None
                cv2.putText(
                    frame,
                    "coin not detected",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (40, 40, 220),
                    2,
                    cv2.LINE_AA,
                )

            if samples:
                avg_px = mean(samples)
                est_ppcm = avg_px / config.COIN_DIAMETER_CM
                cv2.putText(
                    frame,
                    f"samples={len(samples)} avg_px={avg_px:.2f} ppcm={est_ppcm:.2f}",
                    (20, 68),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (220, 220, 220),
                    2,
                    cv2.LINE_AA,
                )

            cv2.putText(
                frame,
                "Space=capture  R=reset  S=save  Q=quit",
                (20, frame.shape[0] - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(" ") and diameter_px is not None:
                samples.append(diameter_px)
                print(f"sample #{len(samples)} captured: {diameter_px:.2f} px")
            elif key == ord("r"):
                samples.clear()
                print("samples cleared")
            elif key == ord("s"):
                if len(samples) < 5:
                    print("collect at least 5 samples before saving")
                    continue
                payload = save_calibration(output_file, samples)
                print(f"saved calibration to {output_file}")
                print(json.dumps(payload, indent=2))
                break
            elif key in (ord("q"), 27):
                break

    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
