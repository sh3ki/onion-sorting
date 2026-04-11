import time
from typing import Any, Optional, Tuple

import cv2
import config

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None


_BACKEND_MAP = {
    "default": cv2.CAP_ANY,
    "any": cv2.CAP_ANY,
    "v4l2": cv2.CAP_V4L2,
    "gstreamer": cv2.CAP_GSTREAMER,
    "ffmpeg": cv2.CAP_FFMPEG,
}


class _PiCamera2Stream:
    def __init__(self, width: int, height: int, fps: int):
        if Picamera2 is None:
            raise RuntimeError("picamera2 is not installed. Install python3-picamera2 on Raspberry Pi.")
        self._cam = Picamera2()
        cam_config = self._cam.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameRate": fps},
        )
        self._cam.configure(cam_config)

        # Keep full sensor FOV if supported to avoid digital zoom/crop changes.
        try:
            if bool(getattr(config, "LOCK_CAMERA_FOV", True)):
                max_crop = self._cam.camera_properties.get("ScalerCropMaximum")
                if max_crop is not None:
                    self._cam.set_controls({"ScalerCrop": max_crop})
        except Exception:
            pass

        # Disable autofocus breathing for stable apparent size if supported.
        try:
            if bool(getattr(config, "DISABLE_AUTOFOCUS", True)):
                controls = self._cam.camera_controls or {}
                if "AfMode" in controls:
                    # 0 = Manual for libcamera AF mode enum.
                    self._cam.set_controls({"AfMode": 0})
        except Exception:
            pass

        self._cam.start()
        time.sleep(0.25)

    def read(self) -> Tuple[bool, Optional[Any]]:
        frame_rgb = self._cam.capture_array()
        if frame_rgb is None:
            return False, None
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        return True, frame_bgr

    def release(self) -> None:
        try:
            self._cam.stop()
        finally:
            self._cam.close()


class CameraStream:
    def __init__(
        self,
        source: Any,
        width: int,
        height: int,
        fps: int,
        backend: str = "default",
        name: str = "camera",
    ):
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.backend = (backend or "default").lower()
        self.name = name
        self._picam = None
        self._cap = None
        self._open()

    def _open(self) -> None:
        if isinstance(self.source, str) and self.source.lower() == "picamera2":
            self._picam = _PiCamera2Stream(self.width, self.height, self.fps)
            return

        if isinstance(self.source, str) and self.source.startswith("gstreamer:"):
            pipeline = self.source.split(":", 1)[1]
            self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        else:
            backend_flag = _BACKEND_MAP.get(self.backend, cv2.CAP_ANY)
            self._cap = cv2.VideoCapture(self.source, backend_flag)

        if not self._cap or not self._cap.isOpened():
            raise RuntimeError(f"Failed to open {self.name} with source={self.source}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # USB webcams are more stable in dual-camera mode when using MJPG.
        if isinstance(self.source, str) and self.source.startswith("/dev/"):
            try:
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            except Exception:
                pass

        # Best-effort lock for stable view on USB cameras.
        if bool(getattr(config, "DISABLE_AUTOFOCUS", True)):
            try:
                self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            except Exception:
                pass
        if bool(getattr(config, "LOCK_CAMERA_FOV", True)):
            try:
                self._cap.set(cv2.CAP_PROP_ZOOM, 0)
            except Exception:
                pass

        for _ in range(3):
            self._cap.read()

    def read(self) -> Tuple[bool, Optional[Any]]:
        if self._picam is not None:
            return self._picam.read()

        if self._cap is None:
            return False, None

        ok, frame = self._cap.read()
        if not ok or frame is None:
            return False, None
        return True, frame

    def release(self) -> None:
        if self._picam is not None:
            self._picam.release()
            self._picam = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None
