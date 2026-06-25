# firmware-esp32

Environment control firmware for the open-root-chamber. Runs on an ESP32-WROOM-32 and manages the ultrasonic mister and heat mat to hold the chamber at the precise conditions ube mini-setts need to sprout.

---

## What This Does

- Reads temperature and humidity every 2 seconds from a DHT22 sensor
- Fires the ultrasonic mister relay when humidity drops below 86% (87.5% target − 1.5% deadband)
- Fires the heat mat relay when temperature drops below 27.5°C (29°C target − 1.5°C deadband)
- Logs all sensor readings and relay state changes to Serial

The `PIDController` class in `pid_controller.h` is shared by both actuators — same class, different setpoints. If you change the deadband or targets here, update `simulation/simulate.py` to match so the simulation stays accurate.

---

## Hardware Required

| Component            | Spec               | Approx Cost |
| -------------------- | ------------------ | ----------- |
| ESP32 dev board      | ESP32-WROOM-32     | $5–8        |
| DHT22 sensor         | AM2302             | $3–5        |
| 2-channel relay      | 5V, optocoupled    | $2–4        |
| Ultrasonic mister    | 5V, 113kHz disc    | $4–6        |
| Heat mat             | 10W seedling mat   | $8–12       |

Full BOM and wiring in [`hardware-configs/chamber_specs.md`](../hardware-configs/chamber_specs.md).

---

## Pin Map

| GPIO | Connected To       |
| ---- | ------------------ |
| 4    | DHT22 data         |
| 16   | Relay CH1 (mister) |
| 17   | Relay CH2 (heat mat)|
| 2    | Onboard LED (heartbeat) |

---

## Flashing the ESP32

**1. Install Arduino IDE**
Download from [arduino.cc/en/software](https://www.arduino.cc/en/software)

**2. Add ESP32 board support**
Arduino IDE → Preferences → Additional Board Manager URLs:
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```
Then: Tools → Board → Boards Manager → search `esp32` → Install

**3. Install libraries via Library Manager**
Tools → Manage Libraries → search and install:
- `DHT sensor library` by Adafruit
- `Adafruit Unified Sensor`

**4. Flash**
- Open `firmware-esp32/main.ino`
- Select board: `ESP32 Dev Module`
- Select the correct COM port
- Click Upload

---

## Reading the Serial Monitor

Open Tools → Serial Monitor, set baud rate to `115200`. You will see:

```
[open-root-chamber] Firmware started.
[LOG] Humidity: 76.3% | Temperature: 25.1°C | Mister: ON | Heat Mat: ON
[MIST] Relay ON — humidity 76.3% (target 87.5%)
[LOG] Humidity: 83.1% | Temperature: 27.8°C | Mister: ON | Heat Mat: OFF
[MIST] Relay OFF — humidity 88.2%
```

---

## Running the Simulation Before Flashing

Before wiring anything up, validate your setpoints and deadband values using the terminal simulation. It runs the exact same controller logic as this firmware.

```bash
# From the repo root
pip install rich
python simulation/simulate.py
```

**Useful flags:**

```bash
# Simulate a poorly controlled room (low humidity, cold ambient)
python simulation/simulate.py --ambient-humidity 65 --ambient-temp 23

# Simulate high contamination risk
python simulation/simulate.py --contamination-risk 0.002

# Run fast without the live UI (same as GitHub Actions)
python simulation/simulate.py --days 30 --speed 999 --batch
```

If the simulation shows the mister cycling too aggressively or the heat mat never turning off, adjust `HUMIDITY_TARGET`, `TEMPERATURE_TARGET`, or `DEADBAND` in `simulate.py` first — then mirror those values in `pid_controller.h` before flashing.

---

## Calibration

If your ambient room humidity is very far from the 87.5% target (e.g. Manila dry season can drop to 55%), the mister will run continuously and may oversaturate the chamber. In that case, reduce `DEADBAND` to `1.0` in `pid_controller.h` for tighter control.

Monitor via Serial for the first 24 hours after flashing to confirm the relay is cycling, not stuck ON or OFF.
