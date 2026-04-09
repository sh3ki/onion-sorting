import threading
import time
from typing import Dict

import cv2
from flask import Flask, Response, jsonify, render_template

import config


class SharedState:
    def __init__(self, stream_max_fps: int = 12, jpeg_quality: int = 70):
        self._lock = threading.Lock()
        self._jpeg_frames = {
            "combined": None,
            "stage1": None,
            "stage2": None,
        }
        self._status: Dict[str, object] = {}
        self._calibration_requests = []
        self._calibration_cancel_requests = []
        self._manual_servo_requests = []
        self._stop_requested = False
        self.stream_max_fps = max(1, int(stream_max_fps))
        self.jpeg_quality = int(max(30, min(95, jpeg_quality)))

    def set_frame(self, frame, stream: str = "combined") -> None:
        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if not ok:
            return
        stream_key = str(stream)
        if stream_key not in self._jpeg_frames:
            stream_key = "combined"
        with self._lock:
            self._jpeg_frames[stream_key] = encoded.tobytes()

    def set_status(self, status: Dict[str, object]) -> None:
        with self._lock:
            self._status = dict(status)

    def get_status(self) -> Dict[str, object]:
        with self._lock:
            return dict(self._status)

    def request_calibration(self, stage: int) -> None:
        target = int(config.CALIBRATION_TARGET_SAMPLES)
        stage_num = 1 if int(stage) == 1 else 2
        with self._lock:
            self._calibration_requests.append({"stage": stage_num, "target": target, "ts": time.monotonic()})

    def consume_calibration_request(self):
        with self._lock:
            if not self._calibration_requests:
                return None
            req = self._calibration_requests.pop(0)
            return req

    def request_calibration_cancel(self, stage: int) -> None:
        stage_num = 1 if int(stage) == 1 else 2
        with self._lock:
            self._calibration_cancel_requests.append({"stage": stage_num, "ts": time.monotonic()})

    def consume_calibration_cancel_request(self):
        with self._lock:
            if not self._calibration_cancel_requests:
                return None
            req = self._calibration_cancel_requests.pop(0)
            return req

    def request_manual_servo(self, servo_key: str):
        key = str(servo_key).strip().lower()
        if key not in ("servo1", "servo2"):
            return False, "Invalid servo key"

        with self._lock:
            self._manual_servo_requests.append({"servo": key, "ts": time.monotonic()})

        return True, f"{key} cycle accepted"

    def consume_manual_servo_request(self):
        with self._lock:
            if not self._manual_servo_requests:
                return None
            req = self._manual_servo_requests.pop(0)
            return req

    def request_stop(self) -> None:
        with self._lock:
            self._stop_requested = True

    def consume_stop_request(self) -> bool:
        with self._lock:
            stop = bool(self._stop_requested)
            self._stop_requested = False
            return stop

    def frame_generator(self, stream: str = "combined"):
        frame_interval = 1.0 / float(self.stream_max_fps)
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        stream_key = str(stream)
        if stream_key not in self._jpeg_frames:
            stream_key = "combined"

        while True:
            with self._lock:
                payload = self._jpeg_frames.get(stream_key)

            if payload is None:
                time.sleep(0.03)
                continue

            yield boundary + payload + b"\r\n"
            time.sleep(frame_interval)


def create_app(shared_state: SharedState, app_name: str = "Onion Sorting Dashboard") -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.route("/")
    def index():
        return render_template("index.html", app_name=app_name)

    @app.route("/servo")
    def servo_page():
        return render_template("servo.html", app_name=app_name)

    @app.route("/video_feed")
    def video_feed():
        return Response(
            shared_state.frame_generator("combined"),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/video_feed_stage1")
    def video_feed_stage1():
        return Response(
            shared_state.frame_generator("stage1"),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/video_feed_stage2")
    def video_feed_stage2():
        return Response(
            shared_state.frame_generator("stage2"),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/api/status")
    def api_status():
        return jsonify(shared_state.get_status())

    @app.route("/api/calibrate_stage1", methods=["POST"])
    def api_calibrate_stage1():
        shared_state.request_calibration(stage=1)
        target = int(config.CALIBRATION_TARGET_SAMPLES)
        return jsonify({"ok": True, "message": f"Stage 1 calibration started ({target} fixed samples)"})

    @app.route("/api/calibrate_stage2", methods=["POST"])
    def api_calibrate_stage2():
        shared_state.request_calibration(stage=2)
        target = int(config.CALIBRATION_TARGET_SAMPLES)
        return jsonify({"ok": True, "message": f"Stage 2 calibration started ({target} fixed samples)"})

    @app.route("/api/calibrate_stage1_cancel", methods=["POST"])
    def api_calibrate_stage1_cancel():
        shared_state.request_calibration_cancel(stage=1)
        return jsonify({"ok": True, "message": "Stage 1 calibration cancel requested"})

    @app.route("/api/calibrate_stage2_cancel", methods=["POST"])
    def api_calibrate_stage2_cancel():
        shared_state.request_calibration_cancel(stage=2)
        return jsonify({"ok": True, "message": "Stage 2 calibration cancel requested"})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        shared_state.request_stop()
        return jsonify({"ok": True, "message": "Stop requested"})

    @app.route("/api/servo/<servo_key>", methods=["POST"])
    def api_servo_cycle(servo_key: str):
        ok, message = shared_state.request_manual_servo(servo_key)
        code = 200 if ok else 400
        return jsonify({"ok": ok, "message": message, "servo": str(servo_key)}), code

    @app.route("/health")
    def health():
        return {"ok": True}

    return app
