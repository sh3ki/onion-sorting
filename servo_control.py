import threading
import time
from typing import Dict

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
except Exception:
    board = None
    busio = None
    PCA9685 = None


class ServoController:
    def __init__(
        self,
        enabled: bool,
        driver: str,
        servo1_pin: int,
        servo2_pin: int,
        servo1_channel: int,
        servo2_channel: int,
        rest_angle: float,
        push_angle: float,
        back_angle: float,
        servo1_rest_angle: float,
        servo1_push_angle: float,
        servo1_back_angle: float,
        servo1_reverse: bool,
        servo1_trim_deg: float,
        servo2_rest_angle: float,
        servo2_push_angle: float,
        servo2_back_angle: float,
        servo2_reverse: bool,
        servo2_trim_deg: float,
        hold_sec: float,
        cooldown_sec: float,
        pca9685_address: int,
        pca9685_frequency: int,
        servo_min_pulse_us: int,
        servo_max_pulse_us: int,
    ):
        self.driver = str(driver or "gpio").strip().lower()
        if self.driver not in ("gpio", "pca9685"):
            self.driver = "gpio"

        if self.driver == "pca9685":
            self.enabled = bool(enabled) and PCA9685 is not None and board is not None and busio is not None
        else:
            self.enabled = bool(enabled) and GPIO is not None

        self.rest_angle = float(rest_angle)
        self.push_angle = float(push_angle)
        self.back_angle = float(back_angle)

        self._rest_angles = {
            "servo1": float(servo1_rest_angle),
            "servo2": float(servo2_rest_angle),
        }
        self._push_angles = {
            "servo1": float(servo1_push_angle),
            "servo2": float(servo2_push_angle),
        }
        self._back_angles = {
            "servo1": float(servo1_back_angle),
            "servo2": float(servo2_back_angle),
        }
        self._reverse = {
            "servo1": bool(servo1_reverse),
            "servo2": bool(servo2_reverse),
        }
        self._trim_deg = {
            "servo1": float(servo1_trim_deg),
            "servo2": float(servo2_trim_deg),
        }

        self.hold_sec = float(hold_sec)
        self.cooldown_sec = float(cooldown_sec)
        self.pca9685_address = int(pca9685_address)
        self.pca9685_frequency = int(pca9685_frequency)
        self.servo_min_pulse_us = int(servo_min_pulse_us)
        self.servo_max_pulse_us = int(servo_max_pulse_us)

        self._pins = {"servo1": int(servo1_pin), "servo2": int(servo2_pin)}
        self._channels_idx = {"servo1": int(servo1_channel), "servo2": int(servo2_channel)}
        self._pwms = {}
        self._pca_channels = {}
        self._pca = None
        self._lock = threading.Lock()
        self._last_action_ts = {"servo1": 0.0, "servo2": 0.0}
        self._states = {"servo1": "IDLE", "servo2": "IDLE"}

        if self.enabled:
            if self.driver == "pca9685":
                try:
                    i2c = busio.I2C(board.SCL, board.SDA)
                    self._pca = PCA9685(i2c, address=self.pca9685_address)
                    self._pca.frequency = self.pca9685_frequency

                    for key, channel in self._channels_idx.items():
                        self._pca_channels[key] = self._pca.channels[channel]
                        self._write_angle(key, self._rest_angles[key])
                        self._states[key] = "READY"

                    print(
                        f"[servo] PCA9685 enabled addr=0x{self.pca9685_address:02X} "
                        f"freq={self.pca9685_frequency}Hz channels={self._channels_idx}"
                    )
                except Exception as exc:
                    self.enabled = False
                    print(f"[servo] PCA9685 init failed: {exc}. Running in mock mode.")
                    self._states["servo1"] = "MOCK_READY"
                    self._states["servo2"] = "MOCK_READY"
            else:
                try:
                    GPIO.setwarnings(False)
                    GPIO.setmode(GPIO.BCM)
                    for key, pin in self._pins.items():
                        GPIO.setup(pin, GPIO.OUT)
                        pwm = GPIO.PWM(pin, 50)
                        pwm.start(0)
                        self._pwms[key] = pwm
                        self._write_angle(key, self._rest_angles[key])
                        self._states[key] = "READY"
                except Exception as exc:
                    self.enabled = False
                    print(f"[servo] GPIO init failed: {exc}. Running in mock mode.")
                    self._states["servo1"] = "MOCK_READY"
                    self._states["servo2"] = "MOCK_READY"
        else:
            if self.driver == "pca9685":
                if PCA9685 is None or board is None or busio is None:
                    print("[servo] PCA9685 libraries not available. Running in mock mode.")
                else:
                    print("[servo] PCA9685 disabled by config. Running in mock mode.")
            else:
                if GPIO is None:
                    print("[servo] RPi.GPIO not available. Running in mock mode.")
                else:
                    print("[servo] Hardware disabled by config. Running in mock mode.")

    def push(self, servo_key: str) -> bool:
        if servo_key not in self._pins:
            return False

        now = time.monotonic()

        with self._lock:
            if now - self._last_action_ts[servo_key] < self.cooldown_sec:
                return False

            self._states[servo_key] = "SWING_FWD"
            if self.enabled:
                self._write_angle(servo_key, self._push_angles[servo_key])
            else:
                print(f"[servo-mock] {servo_key} -> forward")

        time.sleep(self.hold_sec)

        with self._lock:
            self._states[servo_key] = "SWING_BACK"
            if self.enabled:
                self._write_angle(servo_key, self._back_angles[servo_key])
            else:
                print(f"[servo-mock] {servo_key} -> back")

        time.sleep(self.hold_sec)

        with self._lock:
            self._states[servo_key] = "REST"
            if self.enabled:
                self._write_angle(servo_key, self._rest_angles[servo_key])
            else:
                print(f"[servo-mock] {servo_key} -> rest")

            self._last_action_ts[servo_key] = time.monotonic()
            self._states[servo_key] = "READY" if self.enabled else "MOCK_READY"

        return True

    def manual_cycle(self, servo_key: str, forward_angle: float, back_angle: float, phase_pause_sec: float) -> bool:
        if servo_key not in self._pins:
            return False

        pause_sec = max(0.0, float(phase_pause_sec))

        with self._lock:
            self._states[servo_key] = "MANUAL_FWD"
            if self.enabled:
                self._write_angle(servo_key, float(forward_angle))
            else:
                print(f"[servo-mock] {servo_key} -> manual forward")

        time.sleep(pause_sec)

        with self._lock:
            self._states[servo_key] = "MANUAL_BACK"
            if self.enabled:
                self._write_angle(servo_key, float(back_angle))
            else:
                print(f"[servo-mock] {servo_key} -> manual back")

            self._last_action_ts[servo_key] = time.monotonic()
            self._states[servo_key] = "READY" if self.enabled else "MOCK_READY"

        return True

    def get_states(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._states)

    def cleanup(self) -> None:
        with self._lock:
            if self.enabled:
                if self.driver == "pca9685":
                    for channel in self._pca_channels.values():
                        try:
                            channel.duty_cycle = 0
                        except Exception:
                            pass
                    self._pca_channels.clear()
                    if self._pca is not None:
                        try:
                            self._pca.deinit()
                        except Exception:
                            pass
                        self._pca = None
                else:
                    for pwm in self._pwms.values():
                        try:
                            pwm.stop()
                        except Exception:
                            pass
                    self._pwms.clear()
                    try:
                        GPIO.cleanup()
                    except Exception:
                        pass
            self._states["servo1"] = "STOPPED"
            self._states["servo2"] = "STOPPED"

    def _write_angle(self, servo_key: str, angle: float) -> None:
        angle = self._map_servo_angle(servo_key, angle)

        if self.driver == "pca9685":
            channel = self._pca_channels.get(servo_key)
            if channel is None:
                return

            duty = self._angle_to_pca_duty(angle)
            channel.duty_cycle = duty
            return

        pwm = self._pwms.get(servo_key)
        if pwm is None:
            return

        duty = self._angle_to_duty(angle)
        pwm.ChangeDutyCycle(duty)

    @staticmethod
    def _angle_to_duty(angle: float) -> float:
        return 2.5 + (max(0.0, min(180.0, angle)) / 180.0) * 10.0

    def _angle_to_pca_duty(self, angle: float) -> int:
        angle = max(0.0, min(180.0, float(angle)))
        pulse_us = self.servo_min_pulse_us + ((angle / 180.0) * (self.servo_max_pulse_us - self.servo_min_pulse_us))
        period_us = 1_000_000.0 / float(self.pca9685_frequency)
        duty = int((pulse_us / period_us) * 65535.0)
        return max(0, min(65535, duty))

    def _map_servo_angle(self, servo_key: str, angle: float) -> float:
        mapped = float(angle)
        if self._reverse.get(servo_key, False):
            mapped = 180.0 - mapped
        mapped += self._trim_deg.get(servo_key, 0.0)
        return max(0.0, min(180.0, mapped))
