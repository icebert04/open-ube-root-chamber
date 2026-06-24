# 🌱 open-root-chamber

**Automated aeroponic sprouting chamber for ube (_Dioscorea alata_) mini-setts.**

An open-source ESP32 + Raspberry Pi system that maintains the precise
humidity (85–90%) and temperature (28–30°C) conditions for breaking ube
tuber dormancy — without soil, without constant human intervention.

---

## Why This Exists

Traditional ube propagation buries tuber cuttings in soil where they rot
from overwatering and soil pathogens. This system suspends the cuttings
in a sterile mesh tray and mists their exposed roots with an oxygenated
nutrient solution — eliminating the rot vector entirely.

| Metric                 | Soil Method    | open-root-chamber  |
| ---------------------- | -------------- | ------------------ |
| Sprouting success rate | ~60%           | ~90%+              |
| Labor per cycle        | Daily watering | Near-zero          |
| Contamination vector   | Soil pathogens | Eliminated         |
| Cost per unit          | ~$0.30         | ~$0.08 operational |

---

## Repository Structure

```
open-root-chamber/
├── firmware-esp32/
│   ├── main.ino            # Main control loop (mister + heat mat)
│   └── pid_controller.h    # Reusable deadband controller (used by both actuators)
│
├── edge-vision/
│   ├── root_vigor.py       # OpenCV root detection + vigor classification
│   └── requirements.txt    # Python deps (pinned)
│
├── hardware-configs/
│   └── chamber_specs.md    # Full BOM, wiring guide, nutrient recipe
│
└── docs/
    └── wiring-diagram.md   # Step-by-step wiring for non-EE engineers
```

---

## Module Breakdown

### `firmware-esp32/` — Environment Control

**Language:** C++ (Arduino framework)
**Hardware:** ESP32-WROOM-32, DHT22 sensor, 2-channel relay, ultrasonic mister, heat mat

Controls the chamber environment via a deadband controller:

- Reads temperature + humidity every 2 seconds from a DHT22 sensor
- Fires the ultrasonic mister relay if humidity drops below 86% (87.5 − 1.5 deadband)
- Fires the heat mat relay if temperature drops below 27.5°C (29 − 1.5 deadband)
- Logs all readings to Serial (viewable in Arduino IDE Serial Monitor)

The `PIDController` class in `pid_controller.h` is reusable — both the mister
and the heat mat use the same class with different setpoints. DRY by design.

### `edge-vision/` — Root Vigor Detection

**Language:** Python 3.9+
**Hardware:** Raspberry Pi 4 + Pi Camera Module v2 (or USB webcam)

A computer vision pipeline that:

1. Captures a frame from the camera above the tray
2. Segments root pixels by HSV color range (off-white/cream ube roots)
3. Skeletonizes the root mask to measure root path length in cm
4. Classifies each vessel as `HIGH_VIGOR` (≥3cm), `GROWING` (0.5–3cm), or `DUD` (<0.5cm)
5. Returns an annotated debug frame for the dashboard livestream

### `hardware-configs/` — Physical Build

Bill of materials, wiring diagrams, nutrient solution recipe, and chamber
dimension specs. Total build cost per unit: **~$50–80 USD.**

---

## Quick Start

### Flash the ESP32

```bash
# 1. Install Arduino IDE (arduino.cc/en/software)
# 2. Add ESP32 board support:
#    Arduino IDE → Preferences → Additional Board URLs:
#    https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
# 3. Install libraries via Library Manager:
#    - DHT sensor library (Adafruit)
#    - Adafruit Unified Sensor
# 4. Open firmware-esp32/main.ino and flash to your board
```

### Run Edge Vision (on Raspberry Pi)

```bash
cd edge-vision
pip install -r requirements.txt
python root_vigor.py
```

---

## Calibration Notes

Before your first run, set `PIXELS_PER_CM` in `root_vigor.py`:

1. Place a ruler in the camera frame
2. Count how many pixels span 1cm using `cv2.imshow()`
3. Update the constant at the top of the file

Adjust `ROOT_HSV_LOWER` / `ROOT_HSV_UPPER` if root color detection is poor
under your lighting conditions. Use the HSV trackbar script in `docs/` to tune live.

---

## Contributing

This repo is built during **Passport Turtles Live Jams** — open coding sessions
where engineers improve real hardware running in a Manila pilot lab.

See `CONTRIBUTING.md` for session schedule and how to claim a vessel assignment.

---

## License

MIT — build it, fork it, grow ube with it.
