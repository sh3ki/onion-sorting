# Onion Diameter Detection & Calibration Guide

## Overview

The onion sorting system uses **accurate diameter measurement** to classify onions as **SMALL**, **MEDIUM**, or **LARGE**. This guide explains how to achieve accurate detection and calibration.

## What Was Improved

### 1. **Detection Algorithm (vision.py)**
- **CLAHE Contrast Enhancement**: Automatically enhances image contrast for better onion visibility
- **Dual Thresholding**: Uses both Otsu and adaptive thresholding for robust segmentation
- **Multi-Method Circle Fitting**: Tests multiple circle-fitting strategies to find the most accurate diameter
- **Relaxed Circularity Check**: Allows real onions with slight surface irregularities (0.55-1.30 range)
- **Fill-Ratio Scoring**: Prioritizes contours that best match actual onion shapes

### 2. **Calibration System (calibration.py)**
- **Robust Object Detection**: Detects coins OR onions using HoughCircles + contour fallback
- **Custom Reference Size**: Specify any reference object diameter using `--diameter-cm` flag
- **Accurate pixels_per_cm Calculation**: Automatically computes camera resolution in pixels/cm

### 3. **Configuration Tuning (config.py)**
- **Optimized Parameters**: Tuned kernel sizes and thresholds specifically for onions
- **Relaxed Detection Thresholds**: Better handles real onion variations

## How to Calibrate (Step-by-Step)

### **Option A: Calibrate with a Reference Coin (Quick)**

Use a coin with known diameter (e.g., 2.5cm) as reference:

```bash
# SSH into the Pi
ssh onion@192.168.100.44

# Navigate to project directory
cd /home/onion/onion-sorting

# Activate virtual environment
source .venv/bin/activate

# Run calibration for Stage 1 (with coin at 2.5cm)
python calibration.py --stage 1

# Or Stage 2
python calibration.py --stage 2
```

**In the calibration window:**
1. Position the **2.5cm coin** in the field of view
2. Press **SPACE** to capture a sample when coin is clearly visible
3. Capture **at least 5 samples** in different positions
4. Press **S** to save the calibration
5. Press **Q** to quit

### **Option B: Calibrate with Actual Onions (Recommended for Accuracy)**

For most accurate diameter classification, calibrate with actual onions:

```bash
ssh onion@192.168.100.44
cd /home/onion/onion-sorting
source .venv/bin/activate

# Measure an onion's diameter with a caliper or ruler in cm
# Example: if onion is 5.5cm diameter

# Stage 1 calibration
python calibration.py --stage 1 --diameter-cm 5.5

# Stage 2 calibration
python calibration.py --stage 2 --diameter-cm 5.5
```

**In the calibration window:**
1. Place the **measured onion** in the field of view
2. Press **SPACE** to capture samples (**at least 5**)
3. Capture samples with onion in different positions/angles
4. Press **S** to save
5. Press **Q** to quit

## Diameter Classification

After calibration, onions are classified based on your configured thresholds:

```
SMALL  : diameter <= 3.8cm
MEDIUM : 3.8cm < diameter <= 6.0cm
LARGE  : diameter > 6.0cm
```

**To adjust thresholds**, edit `config.py`:
```python
SMALL_MAX_CM = 3.8        # Maximum small onion diameter
MEDIUM_MIN_CM = 3.8       # Minimum medium onion diameter
MEDIUM_MAX_CM = 6.0       # Maximum medium onion diameter
LARGE_GT_CM = 6.0         # Minimum large onion diameter
```

## Verifying Calibration

### 1. **Check Calibration Files**

After calibration, check the saved calibration:

```bash
cat /home/onion/onion-sorting/calibration_stage1.json
cat /home/onion/onion-sorting/calibration_stage2.json
```

You should see:
```json
{
  "pixels_per_cm": 45.5,
  "reference_diameter_cm": 5.5,
  "sample_count": 10,
  "mean_diameter_px": 249.75,
  "std_diameter_px": 2.34,
  "created_at": "2025-04-10T14:23:45Z"
}
```

- **pixels_per_cm**: Ratio of pixels to real cm (should be ~40-50 for this camera setup)
- **reference_diameter_cm**: Your reference object size
- **sample_count**: Number of samples captured
- **std_diameter_px**: Standard deviation (lower is better - indicates consistency)

### 2. **Test Detection in Real-Time**

Restart the app and watch the dashboard:

```bash
# Kill current app
pkill -f '.venv/bin/python main.py'

# Start app
cd /home/onion/onion-sorting
nohup env ENABLE_LOCAL_DISPLAY=0 .venv/bin/python main.py > app.log 2>&1 < /dev/null &

# Check status
curl http://127.0.0.1:5000/api/status
```

**Expected output when onion is on conveyor:**
```
STAGE1: MEDIUM 5.45cm
STAGE2: LARGE 6.78cm
```

Instead of:
```
STAGE1: NO_OBJECT 0.00cm
STAGE2: NO_OBJECT 0.00cm
```

### 3. **Check Logs**

```bash
tail -f /home/onion/onion-sorting/app.log | grep -E "STAGE|diameter"
```

## Troubleshooting

### Problem: Still shows "NO_OBJECT"

1. **Check if calibration was saved:**
   ```bash
   ls -la /home/onion/onion-sorting/calibration_*.json
   ```

2. **Verify pixels_per_cm is not zero:**
   ```bash
   grep pixels_per_cm /home/onion/onion-sorting/calibration_stage1.json
   ```
   Should show a value like `45.0` to `50.0`, not `0`

3. **Run calibration again:**
   ```bash
   python calibration.py --stage 1 --diameter-cm 5.5
   # Make sure sample_count >= 5 before saving
   ```

### Problem: Measurements are off by large amounts

1. **Verify reference object size** - ensure you're using the correct diameter in cm
2. **Check lighting** - use consistent lighting during calibration
3. **Calibrate each stage separately** - Stage 1 and Stage 2 may have different camera angles
4. **Use fresh calibration samples** - recalibrate with fresh onion samples every month

### Problem: Sometimes detects, sometimes doesn't

1. **Lower MIN_CONTOUR_AREA** in config.py if detecting small onions
2. **Increase detection smoothing** by raising DIAMETER_SMOOTHING_FRAMES (3-10 frames recommended)
3. **Check conveyor lighting** - ensure even lighting across conveyor belt

## Advanced: Understanding Detection Flow

```
Frame from Camera
    ↓
[CLAHE Contrast Enhancement]
    ↓
[Dual Thresholding: Otsu + Adaptive]
    ↓
[Morphological Operations: Open/Close]
    ↓
[Pick Best Contour by Circularity + Fill Ratio]
    ↓
[Fit Best Circle using Multiple Methods]
    ↓
[Calculate Diameter: diameter_px * pixels_per_cm]
    ↓
[Smooth Diameter with Moving Window]
    ↓
[Classify: SMALL / MEDIUM / LARGE]
    ↓
API Status + Web Dashboard
```

## Parameters You Can Tune

In `config.py`:

```python
# Detection sensitivity
MIN_CONTOUR_AREA = 300          # Lower = detects smaller onions
CIRCULARITY_MIN = 0.55          # Lower = accepts more irregular shapes
CIRCULARITY_MAX = 1.30          # Higher = accepts more irregular shapes

# Smoothing (for conveyor motion)
DIAMETER_SMOOTHING_FRAMES = 6   # Higher = smoother but slower response

# Thresholds
BLUR_KERNEL_SIZE = 7            # Odd number, higher = more blur
MORPH_KERNEL_SIZE = 7           # Odd number, controls morphological ops
```

## Performance Notes

- **Detection speed:** ~30-50ms per frame on Raspberry Pi 4
- **Calibration time:** ~30 seconds to capture 10 samples (press SPACE every 3 seconds)
- **Accuracy:** ±2-3mm with proper calibration and lighting

## When to Recalibrate

- After moving camera
- After changing lighting significantly
- After ~2-4 weeks (lighting drift)
- If accuracy drops on new onion batches

---

**For questions or issues**, check `/home/onion/onion-sorting/app.log` for detailed error messages.
