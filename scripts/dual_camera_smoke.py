import argparse
import time
from pathlib import Path
import sys
import os

import cv2

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from camera_manager import CameraStream  # noqa: E402


def open_stream(name: str, source, backend: str) -> CameraStream:
    return CameraStream(
        source=source,
        width=config.FRAME_WIDTH,
        height=config.FRAME_HEIGHT,
        fps=config.TARGET_FPS,
        backend=backend,
        name=name,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Dual camera smoke test")
    parser.add_argument("--seconds", type=int, default=12, help="Test duration")
    parser.add_argument("--save-dir", default="smoke_outputs", help="Snapshot output directory")
    parser.add_argument("--no-preview", action="store_true", help="Disable OpenCV preview window")
    args = parser.parse_args()

    preview_enabled = (not args.no_preview) and bool(os.environ.get("DISPLAY"))
    stage2_optional = bool(getattr(config, "STAGE2_OPTIONAL", False))

    out_dir = ROOT / args.save_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cam1 = open_stream("stage1-camera", config.STAGE1_SOURCE, config.STAGE1_BACKEND)
    cam2 = None
    try:
        cam2 = open_stream("stage2-camera", config.STAGE2_SOURCE, config.STAGE2_BACKEND)
    except Exception as exc:
        if not stage2_optional:
            raise
        print(f"WARNING: stage2 camera missing but optional: {exc}")

    t0 = time.monotonic()
    frames1 = 0
    frames2 = 0
    last1 = None
    last2 = None

    try:
        while (time.monotonic() - t0) < args.seconds:
            ok1, frame1 = cam1.read()
            ok2, frame2 = (False, None)
            if cam2 is not None:
                ok2, frame2 = cam2.read()

            if ok1 and frame1 is not None:
                frames1 += 1
                last1 = frame1
            if ok2 and frame2 is not None:
                frames2 += 1
                last2 = frame2

            if preview_enabled and last1 is not None and (last2 is not None or stage2_optional):
                if last2 is None:
                    last2 = last1.copy()
                    cv2.putText(
                        last2,
                        "STAGE2 OPTIONAL MODE",
                        (10, 56),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        (0, 220, 255),
                        2,
                        cv2.LINE_AA,
                    )
                h = min(last1.shape[0], last2.shape[0])
                a = cv2.resize(last1, (int(last1.shape[1] * h / last1.shape[0]), h))
                b = cv2.resize(last2, (int(last2.shape[1] * h / last2.shape[0]), h))
                combined = cv2.hconcat([a, b])
                cv2.putText(
                    combined,
                    "Dual camera smoke test - press Q to stop",
                    (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (230, 230, 230),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("Dual Camera Smoke", combined)

            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break

    finally:
        cam1.release()
        if cam2 is not None:
            cam2.release()
        if preview_enabled:
            cv2.destroyAllWindows()

    duration = max(1e-6, time.monotonic() - t0)
    fps1 = frames1 / duration
    fps2 = frames2 / duration

    if last1 is not None:
        cv2.imwrite(str(out_dir / "stage1_last.jpg"), last1)
    if last2 is not None:
        cv2.imwrite(str(out_dir / "stage2_last.jpg"), last2)

    print(f"Stage1 frames: {frames1}, avg FPS: {fps1:.2f}")
    print(f"Stage2 frames: {frames2}, avg FPS: {fps2:.2f}")
    print(f"Snapshots saved in: {out_dir}")

    if frames1 <= 0:
        print("ERROR: Stage1 camera returned zero frames.")
        return 2

    if (not stage2_optional) and frames2 <= 0:
        print("ERROR: At least one camera returned zero frames.")
        return 2

    print("Dual camera smoke test OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
