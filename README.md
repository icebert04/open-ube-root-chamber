# 🌱 open-ube-root-chamber

**Automated aeroponic sprouting chamber for ube (_Dioscorea alata_) mini-setts.**

Built during **Passport Turtles Live Jams** — open coding sessions where engineers worldwide improve real hardware running in a Manila pilot lab. If you're here, you're either a member, curious, or you grow ube. All three are welcome.

---

## The Problem We're Solving

Traditional ube propagation buries tuber cuttings in soil. They rot. Overwatering, soil pathogens, and inconsistent humidity wipe out 30–50% of a batch before anything sprouts. The labor cost of daily manual checking makes small-scale production uneconomical.

This system suspends ube mini-setts in a sterile mesh tray and mists their exposed roots with an oxygenated nutrient solution on a precise automated cycle — eliminating the rot vector entirely and reducing human handling to near-zero.

| Metric                 | Soil Method    | open-root-chamber  |
| ---------------------- | -------------- | ------------------ |
| Sprouting success rate | ~60%           | ~90%+              |
| Labor per cycle        | Daily watering | Near-zero          |
| Contamination vector   | Soil pathogens | Eliminated         |
| Cost per unit          | ~$0.30         | ~$0.08 operational |
| Hardware cost          | —              | ~$50–80 per unit   |

---

## How It Works

An ESP32 microcontroller reads a DHT22 humidity and temperature sensor every 2 seconds. A deadband controller fires relay-driven ultrasonic misters and heat mats to hold the chamber at exactly 85–90% humidity and 28–30°C — the precise window ube setts need to break dormancy without rotting. A Raspberry Pi camera above the tray runs a computer vision pipeline that measures root length per vessel and flags contamination before it spreads.

---

## Repository Structure

```
open-ube-root-chamber/
├── firmware-esp32/         # ESP32 environment control (C++ / Arduino)
│   ├── main.ino            # Main control loop (mister + heat mat)
│   └── pid_controller.h    # Reusable deadband controller
├── edge-vision/            # Root vigor detection (Python / OpenCV)
│   ├── root_vigor.py
│   └── requirements.txt
├── hardware-configs/       # BOM, wiring, nutrient solution recipe
│   └── chamber_specs.md
├── simulation/             # Terminal simulation of the full system
│   └── simulate.py
└── docs/                   # Wiring diagrams, calibration guides
```

---

## Quick Start

### Step 1 — Run the simulation first (no hardware needed)

Before touching any hardware, validate the system in your terminal:

```bash
pip install rich
python simulation/simulate.py
```

Watch a 30-day sprouting cycle play out live — sensors, relay states, vessel tray, and serial log all updating in real time. Use this to understand the system and tune setpoints before flashing.

Useful flags:

```bash
# Simulate a dry room (Manila dry season)
python simulation/simulate.py --ambient-humidity 65 --ambient-temp 23

# Simulate high contamination risk
python simulation/simulate.py --contamination-risk 0.002

# Fast batch run with no live UI (same as GitHub Actions)
python simulation/simulate.py --days 30 --speed 999 --batch
```

If the simulation shows the mister cycling too aggressively or the heat mat never turning off, adjust `HUMIDITY_TARGET`, `TEMPERATURE_TARGET`, or `DEADBAND` at the top of `simulate.py` — then mirror those values in `firmware-esp32/pid_controller.h` before flashing. The simulation and firmware must stay in sync.

---

### Step 2 — Wire the hardware

| Component         | Spec             | Approx Cost |
| ----------------- | ---------------- | ----------- |
| ESP32 dev board   | ESP32-WROOM-32   | $5–8        |
| DHT22 sensor      | AM2302           | $3–5        |
| 2-channel relay   | 5V, optocoupled  | $2–4        |
| Ultrasonic mister | 5V, 113kHz disc  | $4–6        |
| Heat mat          | 10W seedling mat | $8–12       |

**Pin map:**

| GPIO | Connected To            |
| ---- | ----------------------- |
| 4    | DHT22 data              |
| 16   | Relay CH1 → mister      |
| 17   | Relay CH2 → heat mat    |
| 2    | Onboard LED (heartbeat) |

Full wiring diagram and nutrient solution recipe in [`hardware-configs/chamber_specs.md`](hardware-configs/chamber_specs.md).

---

### Step 3 — Flash the ESP32

**Install Arduino IDE** from [arduino.cc/en/software](https://www.arduino.cc/en/software)

**Add ESP32 board support** — Arduino IDE → Preferences → Additional Board Manager URLs:

```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

Then: Tools → Board → Boards Manager → search `esp32` → Install

**Install libraries** via Tools → Manage Libraries:

- `DHT sensor library` by Adafruit
- `Adafruit Unified Sensor`

**Flash:**

- Open `firmware-esp32/main.ino`
- Select board: `ESP32 Dev Module`
- Select your COM port
- Click Upload

---

### Step 4 — Read the Serial Monitor

Open Tools → Serial Monitor, baud rate `115200`. You will see:

```
[open-root-chamber] Firmware started.
[LOG] Humidity: 76.3% | Temperature: 25.1°C | Mister: ON | Heat Mat: ON
[MIST] Relay ON — humidity 76.3% (target 87.5%)
[MIST] Relay OFF — humidity 88.2%
```

---

### Step 5 — Run edge vision on a Raspberry Pi

```bash
cd edge-vision
pip install -r requirements.txt
python root_vigor.py
```

Place a ruler in the camera frame first and set `PIXELS_PER_CM` in `root_vigor.py` to calibrate. Adjust `ROOT_HSV_LOWER` / `ROOT_HSV_UPPER` if root detection is poor under your lighting.

---

## Calibration Notes

If your ambient room humidity is far from the 87.5% target (Manila dry season can drop to 55%), the mister may run continuously and oversaturate the chamber. Reduce `DEADBAND` to `1.0` in `pid_controller.h` for tighter control. Monitor via Serial for the first 24 hours after flashing to confirm the relay is cycling, not stuck ON or OFF.

---

## Contributing

See `CONTRIBUTING.md` for the Live Jam schedule and how to claim a vessel assignment. Engineers can own a specific vessel in the Manila lab — watch your code optimizations reduce mortality on your actual batch via the live camera feed.

---

## License

MIT — build it, fork it, grow ube with it.
