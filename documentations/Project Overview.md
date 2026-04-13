# PROJECT TITLE

Raspberry Pi-Based Onion Sorting System (Dual Camera, Dual Servo, HDMI + Browser Monitoring)

---

# 1. Project Overview

This project builds a low-cost, real-time onion sorting prototype using:
- 1 Raspberry Pi 4 Model B
- 1 Raspberry Pi Camera Module (CSI)
- 1 USB webcam
- 2 servo motors for two sorting gates
- 1 HDMI touchscreen for local monitoring
- 1 browser dashboard for remote monitoring

The system uses two camera views and two physical sorting stages:

Stage 1 (Large Gate):
- Camera 1 inspects onions at Gate 1.
- If onion is Large, Servo 1 pushes it to the Large funnel.
- If not Large, onion continues forward.

Stage 2 (Medium Gate):
- Camera 2 inspects onions that passed Gate 1.
- If onion is Medium, Servo 2 pushes it to the Medium funnel.
- If not Medium, onion continues to the Small output.

Final classes:
- Small: diameter < 3.0 cm
- Medium: 3.0 cm to 5.0 cm
- Large: diameter > 5.0 cm

Both camera feeds are displayed side-by-side on the HDMI touchscreen and streamed side-by-side in a web dashboard.

---

# 2. General Objective

Design and implement a dual-camera, dual-servo onion sorting system on Raspberry Pi that performs real-time size-based classification and physical diversion while providing live local and browser monitoring.

---

# 3. Specific Objectives

- Capture Camera 1 (CSI) and Camera 2 (USB) simultaneously.
- Detect and measure onion diameter in centimeters in each stage.
- Trigger Servo 1 only for Large onions at Gate 1.
- Trigger Servo 2 only for Medium onions at Gate 2.
- Leave Small onions unactuated.
- Display both annotated feeds side-by-side on HDMI touchscreen.
- Stream both annotated feeds side-by-side in browser using Flask.
- Maintain stable FPS suitable for sorting.

---

# 4. System Architecture

Camera 1 (CSI) -> Stage 1 Vision -> Large Decision -> Servo 1 (Large Gate)
Camera 2 (USB) -> Stage 2 Vision -> Medium Decision -> Servo 2 (Medium Gate)

Stage outputs + system status -> Combined Side-by-Side Frame

Combined frame -> HDMI touchscreen display
Combined frame -> Flask MJPEG browser stream

---

# 5. Hardware Components

- Raspberry Pi 4 Model B
- Raspberry Pi Camera Module v2/v3 (CSI)
- USB webcam (UVC compatible)
- 7-inch HDMI touchscreen
- 2x servo motors (Gate 1 and Gate 2)
- External 5V supply for servo power
- Conveyor and 3 funnel outputs (Large, Medium, Small)
- Mounting brackets and wiring accessories
- Uniform lighting
- New Philippine 5 peso coin (25 mm or 2.5 cm) for calibration

---

# 6. Software Components

- Raspberry Pi OS (Bookworm)
- Python 3
- OpenCV
- NumPy
- Flask
- RPi.GPIO or pigpio/PCA9685 stack

---

# 7. Core Workflow

1. Acquire frames from both cameras.
2. Run Stage 1 detection on Camera 1 view.
3. Classify Large versus Not Large.
4. If Large, schedule Servo 1 actuation based on travel delay.
5. Run Stage 2 detection on Camera 2 view.
6. Classify Medium versus Not Medium.
7. If Medium, schedule Servo 2 actuation based on travel delay.
8. Build one combined side-by-side annotated frame.
9. Show combined frame on HDMI and stream same frame to browser.

---

# 8. Calibration Method

Reference object: new Philippine 5 peso coin (25 mm or 2.5 cm).

For each camera independently:
- Detect coin diameter in pixels.
- Compute pixels-per-cm.

Formula:

PixelsPerCm = CoinDiameterPixels / 2.5

Diameter conversion:

DiameterCm = OnionDiameterPixels / PixelsPerCm

Each camera must have its own calibration value because lens, angle, and mounting differ.

---

# 9. Sorting Logic

Stage 1 (Camera 1 + Servo 1):
- If diameter > 5.0 cm -> Large -> trigger Servo 1
- Else -> pass to next stage

Stage 2 (Camera 2 + Servo 2):
- If 3.0 <= diameter <= 5.0 cm -> Medium -> trigger Servo 2
- Else -> Small -> no push

---

# 10. Display and Browser Monitoring

The system creates one combined frame:
- Left panel: Camera 1 annotated feed
- Right panel: Camera 2 annotated feed
- Overlay: FPS, counters, servo states

Outputs:
- HDMI touchscreen: local real-time monitoring
- Browser dashboard: remote MJPEG stream

---

# 11. Expected Performance (Raspberry Pi 4)

At 640x480 per camera, optimized processing:
- HDMI side-by-side display: about 15 to 22 FPS combined
- Per-camera processing: about 15 to 25 FPS
- Browser MJPEG stream: about 8 to 15 FPS per client
- Local display latency: about 60 to 140 ms
- Browser latency: about 180 to 500 ms

Performance depends on:
- Lighting quality
- Contour complexity
- Stream JPEG quality
- Number of browser clients

---

# 12. Design Considerations

- Use fixed camera mounts and avoid vibration.
- Keep lighting uniform for both stages.
- Avoid onion overlap in detection zones.
- Power servos from external 5V supply with common ground to Pi.
- Use non-blocking servo actuation so vision threads maintain FPS.

---

# 13. Scope and Limitations

- Intended for prototype and academic use.
- Sensitive to lighting and camera movement.
- Overlapping onions reduce reliability.
- Throughput is limited compared to industrial systems.

---

# 14. Conclusion

This project demonstrates that a Raspberry Pi 4 can run a practical two-stage onion sorting system using one CSI camera, one USB webcam, and two servo gates, while providing real-time local and browser-based monitoring through a combined side-by-side display pipeline.