# 🌱 open-root-chamber

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
open-root-chamber/
├── firmware-esp32/         # ESP32 environment control (C++ / Arduino)
├── edge-vision/            # Root vigor detection (Python / OpenCV)
├── hardware-configs/       # BOM, wiring, nutrient solution recipe
├── simulation/             # Terminal simulation of the full system
└── docs/                   # Wiring diagrams, calibration guides
```

Each folder has its own README with setup instructions specific to that module.

---

## Quick Start

### 1. Run the simulation first (no hardware needed)

```bash
pip install rich
python simulation/simulate.py
```

Watch a 30-day sprouting cycle play out in your terminal — sensors, relay states, vessel tray, and serial log all live. Good way to understand the system before touching hardware.

### 2. Flash the ESP32

See [`firmware-esp32/README.md`](firmware-esp32/README.md) for full wiring and flashing instructions.

### 3. Run edge vision on a Raspberry Pi

```bash
cd edge-vision
pip install -r requirements.txt
python root_vigor.py
```

---

## Contributing

See `CONTRIBUTING.md` for the Live Jam schedule and how to claim a vessel assignment. Engineers can own a specific vessel in the Manila lab — watch your code optimizations reduce mortality on your actual batch via the live camera feed.

---

## License

MIT — build it, fork it, grow ube with it.
