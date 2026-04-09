import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class DetectionResult:
    stage_name: str
    class_label: str = "NO_OBJECT"
    diameter_cm: float = 0.0
    center: Optional[Tuple[int, int]] = None
    radius_px: float = 0.0
    triggered: bool = False


class StageDetector:
    def __init__(
        self,
        stage_name: str,
        stage_kind: str,
        pixels_per_cm: float,
        small_max_cm: float,
        medium_min_cm: float,
        medium_max_cm: float,
        large_gt_cm: float,
        min_contour_area: int,
        circularity_min: float,
        circularity_max: float,
        blur_kernel_size: int,
        morph_kernel_size: int,
        threshold_invert: bool,
        trigger_axis: str,
        trigger_ratio: float,
        trigger_tolerance_px: int,
        trigger_cooldown_sec: float,
        diameter_smoothing_frames: int,
        track_max_center_jump_px: float,
        track_lost_reset_frames: int,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ):
        self.stage_name = stage_name
        self.stage_kind = stage_kind
        self.pixels_per_cm = max(1e-6, float(pixels_per_cm))
        self.small_max_cm = float(small_max_cm)
        self.medium_min_cm = float(medium_min_cm)
        self.medium_max_cm = float(medium_max_cm)
        self.large_gt_cm = float(large_gt_cm)
        self.min_contour_area = int(min_contour_area)
        self.circularity_min = float(circularity_min)
        self.circularity_max = float(circularity_max)
        self.blur_kernel_size = int(blur_kernel_size)
        self.morph_kernel_size = int(morph_kernel_size)
        self.threshold_invert = bool(threshold_invert)
        self.trigger_axis = trigger_axis.lower()
        self.trigger_ratio = float(np.clip(trigger_ratio, 0.0, 1.0))
        self.trigger_tolerance_px = int(trigger_tolerance_px)
        self.trigger_cooldown_sec = float(trigger_cooldown_sec)
        self.diameter_smoothing_frames = max(1, int(diameter_smoothing_frames))
        self.track_max_center_jump_px = float(track_max_center_jump_px)
        self.track_lost_reset_frames = max(1, int(track_lost_reset_frames))
        self.roi = roi
        self._last_trigger_ts = 0.0
        self._diameter_cm_window = deque(maxlen=self.diameter_smoothing_frames)
        self._last_center = None
        self._lost_frames = 0

    def process(self, frame: np.ndarray, timestamp: Optional[float] = None) -> Tuple[np.ndarray, DetectionResult]:
        ts = timestamp if timestamp is not None else time.monotonic()
        display = frame.copy()
        h, w = display.shape[:2]

        x0, y0, rw, rh = self._resolve_roi(w, h)
        roi_frame = frame[y0 : y0 + rh, x0 : x0 + rw]

        cv2.rectangle(display, (x0, y0), (x0 + rw, y0 + rh), (120, 120, 120), 1)
        line_px = self._draw_trigger_line(display, x0, y0, rw, rh)

        mask = self._segment(roi_frame)
        contour = self._pick_best_contour(mask)

        result = DetectionResult(stage_name=self.stage_name)

        if contour is None:
            self._mark_lost()
            self._draw_stage_label(display, result.class_label, result.diameter_cm)
            return display, result

        area = cv2.contourArea(contour)
        if area < self.min_contour_area:
            self._mark_lost()
            self._draw_stage_label(display, result.class_label, result.diameter_cm)
            return display, result

        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        if radius <= 1.0:
            self._mark_lost()
            self._draw_stage_label(display, result.class_label, result.diameter_cm)
            return display, result

        center_global = (int(x0 + cx), int(y0 + cy))
        radius_px = float(radius)
        diameter_px = radius_px * 2.0
        raw_diameter_cm = diameter_px / self.pixels_per_cm
        diameter_cm = self._update_tracked_diameter(center_global, raw_diameter_cm)
        class_label = self._classify(diameter_cm)
        result.class_label = class_label
        result.diameter_cm = diameter_cm
        result.center = center_global
        result.radius_px = radius_px

        color = self._class_color(class_label)
        cv2.circle(display, center_global, int(radius_px), color, 2)
        cv2.circle(display, center_global, 3, color, -1)

        if self._crossed_trigger(center_global, line_px, ts):
            result.triggered = True
            cv2.putText(
                display,
                f"{self.stage_name}: EVENT",
                (x0 + 8, y0 + 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 220, 40),
                2,
                cv2.LINE_AA,
            )

        self._draw_stage_label(display, class_label, diameter_cm)
        return display, result

    def _update_tracked_diameter(self, center: Tuple[int, int], diameter_cm: float) -> float:
        if self._last_center is not None:
            dx = float(center[0] - self._last_center[0])
            dy = float(center[1] - self._last_center[1])
            jump_px = math.hypot(dx, dy)
            if jump_px > self.track_max_center_jump_px:
                self._diameter_cm_window.clear()

        self._last_center = center
        self._lost_frames = 0
        self._diameter_cm_window.append(float(diameter_cm))
        return float(sum(self._diameter_cm_window) / len(self._diameter_cm_window))

    def _mark_lost(self) -> None:
        self._lost_frames += 1
        if self._lost_frames >= self.track_lost_reset_frames:
            self._diameter_cm_window.clear()
            self._last_center = None

    def _resolve_roi(self, frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
        if self.roi is None:
            return 0, 0, frame_w, frame_h

        x, y, w, h = self.roi
        x = max(0, min(frame_w - 1, int(x)))
        y = max(0, min(frame_h - 1, int(y)))
        w = max(1, min(frame_w - x, int(w)))
        h = max(1, min(frame_h - y, int(h)))
        return x, y, w, h

    def _segment(self, roi_frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        k = self._odd(self.blur_kernel_size)
        gray = cv2.GaussianBlur(gray, (k, k), 0)

        thresh_mode = cv2.THRESH_BINARY_INV if self.threshold_invert else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, 0, 255, thresh_mode | cv2.THRESH_OTSU)

        mk = self._odd(self.morph_kernel_size)
        kernel = np.ones((mk, mk), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return mask

    def _pick_best_contour(self, mask: np.ndarray):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_area = 0.0
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_contour_area:
                continue
            peri = cv2.arcLength(c, True)
            if peri <= 0:
                continue
            circularity = (4.0 * math.pi * area) / (peri * peri)
            if not (self.circularity_min <= circularity <= self.circularity_max):
                continue
            if area > best_area:
                best = c
                best_area = area
        return best

    def _classify(self, diameter_cm: float) -> str:
        if self.stage_kind == "large_gate":
            return "LARGE" if diameter_cm >= self.large_gt_cm else "NOT_LARGE"
        if self.stage_kind == "medium_gate":
            return "MEDIUM" if self.medium_min_cm <= diameter_cm <= self.medium_max_cm else "SMALL"
        return "UNKNOWN"

    def _draw_trigger_line(self, frame: np.ndarray, x0: int, y0: int, w: int, h: int) -> int:
        if self.trigger_axis == "x":
            line_x = x0 + int(self.trigger_ratio * w)
            cv2.line(frame, (line_x, y0), (line_x, y0 + h), (255, 180, 60), 2)
            return line_x

        line_y = y0 + int(self.trigger_ratio * h)
        cv2.line(frame, (x0, line_y), (x0 + w, line_y), (255, 180, 60), 2)
        return line_y

    def _crossed_trigger(self, center: Tuple[int, int], line_px: int, timestamp: float) -> bool:
        axis_value = center[0] if self.trigger_axis == "x" else center[1]
        near_line = abs(axis_value - line_px) <= self.trigger_tolerance_px
        if not near_line:
            return False

        if (timestamp - self._last_trigger_ts) < self.trigger_cooldown_sec:
            return False

        self._last_trigger_ts = timestamp
        return True

    def _draw_stage_label(self, frame: np.ndarray, label: str, diameter_cm: float) -> None:
        cv2.putText(
            frame,
            f"{self.stage_name}: {label} {max(0.0, float(diameter_cm)):.2f}cm",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (220, 220, 220),
            2,
            cv2.LINE_AA,
        )

    @staticmethod
    def _odd(value: int) -> int:
        return value if value % 2 == 1 else value + 1

    @staticmethod
    def _class_color(class_label: str):
        if class_label == "LARGE":
            return (40, 40, 220)
        if class_label == "MEDIUM":
            return (0, 220, 255)
        if class_label == "SMALL":
            return (40, 220, 40)
        return (180, 180, 180)
