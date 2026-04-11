import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

import config


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

    def _fit_best_circle(self, contour: np.ndarray) -> Tuple[Tuple[float, float], float]:
        center_enclosing, radius_enclosing = cv2.minEnclosingCircle(contour)
        return center_enclosing, radius_enclosing

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

        # Use improved circle fitting for more accurate diameter
        (cx, cy), radius = self._fit_best_circle(contour)
        
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

    def render_cached(self, frame: np.ndarray, result: DetectionResult) -> np.ndarray:
        display = frame.copy()
        h, w = display.shape[:2]
        x0, y0, rw, rh = self._resolve_roi(w, h)

        cv2.rectangle(display, (x0, y0), (x0 + rw, y0 + rh), (120, 120, 120), 1)
        self._draw_trigger_line(display, x0, y0, rw, rh)

        if result is not None and result.center is not None and float(result.radius_px) > 1.0:
            color = self._class_color(result.class_label)
            cv2.circle(display, result.center, int(result.radius_px), color, 2)
            cv2.circle(display, result.center, 3, color, -1)

        label = result.class_label if result is not None else "NO_OBJECT"
        diameter_cm = result.diameter_cm if result is not None else 0.0
        self._draw_stage_label(display, label, diameter_cm)
        return display

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
        """
        Lightweight onion segmentation.
        Uses HSV red/purple mask plus glare-connected pixels.
        """
        k = self._odd(self.blur_kernel_size)
        blurred = cv2.GaussianBlur(roi_frame, (k, k), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]

        h1_min = int(getattr(config, "ONION_HUE1_MIN", 0))
        h1_max = int(getattr(config, "ONION_HUE1_MAX", 18))
        h2_min = int(getattr(config, "ONION_HUE2_MIN", 125))
        h2_max = int(getattr(config, "ONION_HUE2_MAX", 179))
        sat_min = int(getattr(config, "ONION_SAT_MIN", 32))
        val_min = int(getattr(config, "ONION_MIN_VALUE", 30))

        mask_h1 = cv2.inRange(hsv, (h1_min, sat_min, val_min), (h1_max, 255, 255))
        mask_h2 = cv2.inRange(hsv, (h2_min, sat_min, val_min), (h2_max, 255, 255))
        mask_color = cv2.bitwise_or(mask_h1, mask_h2)

        glare_min = int(getattr(config, "ONION_GLARE_VALUE_MIN", 235))
        mask_glare = cv2.inRange(val, glare_min, 255)
        connect_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        connected_color = cv2.dilate(mask_color, connect_kernel, iterations=1)
        mask_glare_connected = cv2.bitwise_and(mask_glare, connected_color)

        mask = cv2.bitwise_or(mask_color, mask_glare_connected)

        mk = self._odd(self.morph_kernel_size)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (mk, mk))

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        return mask

    def _pick_best_contour(self, mask: np.ndarray):
        """
        Pick the largest valid onion contour.
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = mask.shape[:2]
        max_area_ratio = float(getattr(config, "ONION_MAX_CONTOUR_AREA_RATIO", 0.35))
        max_aspect_ratio = float(getattr(config, "ONION_MAX_ASPECT_RATIO", 2.20))
        min_solidity = float(getattr(config, "ONION_MIN_SOLIDITY", 0.75))
        min_fill_ratio = float(getattr(config, "ONION_MIN_FILL_RATIO", 0.35))
        max_area = float(h * w) * max_area_ratio
        candidates = []

        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_contour_area:
                continue
            if area > max_area:
                continue

            peri = cv2.arcLength(c, True)
            if peri <= 0:
                continue

            circularity = (4.0 * math.pi * area) / (peri * peri)
            if circularity < 0.35:
                continue

            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            if hull_area <= 0:
                continue
            solidity = float(area / hull_area)
            if solidity < min_solidity:
                continue

            rect = cv2.minAreaRect(c)
            major = max(rect[1][0], rect[1][1])
            minor = min(rect[1][0], rect[1][1])
            if minor <= 0:
                continue
            aspect_ratio = float(major / minor)
            if aspect_ratio > max_aspect_ratio:
                continue

            (cx, cy), radius = cv2.minEnclosingCircle(c)
            if radius < 2.0:
                continue

            circle_area = math.pi * radius * radius
            fill_ratio = area / circle_area if circle_area > 0 else 0
            if fill_ratio < min_fill_ratio:
                continue

            score = area + (circularity * 200.0) + (solidity * 200.0) + (80.0 / max(1.0, aspect_ratio))
            candidates.append((score, c))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]


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
