# open-root-chamber — hardware-configs/chamber_specs.md

## Bill of Materials (BOM)

| Component         | Spec             | Approx Cost (USD) | Notes                               |
| ----------------- | ---------------- | ----------------- | ----------------------------------- |
| ESP32 dev board   | ESP32-WROOM-32   | $5–8              | Any 38-pin variant works            |
| DHT22 sensor      | AM2302           | $3–5              | Better accuracy than DHT11          |
| Ultrasonic mister | 5V, 113kHz disc  | $4–6              | 1–3 discs depending on chamber size |
| 5V relay module   | 2-channel        | $2–4              | One channel per actuator            |
| Heat mat          | 10W seedling mat | $8–12             | Sized to tray footprint             |
| Mesh tray         | 40×60cm HDPE     | $3–5              | Food-safe, autoclavable             |
| Reservoir tank    | 10L food-grade   | $6–10             | Holds nutrient/anti-fungal solution |
| 12V DC pump       | 3–5 L/min        | $6–10             | Circulates solution to misters      |
| Silicone tubing   | 8mm ID           | $5–8/m            | Chemical-resistant                  |
| Power supply      | 12V 3A + 5V USB  | $8–12             | Powers pump + ESP32 separately      |
| **Total**         |                  | **~$50–80**       | Per unit                            |

---

## Chamber Dimensions (Recommended Pilot)

- Tray size: 40cm × 60cm (fits ~30–40 ube setts)
- Enclosure height: 30cm (allows 20cm sprout clearance + camera mount)
- Camera mount height: 25cm above tray surface
- Camera field of view should cover full tray at this height

---

## Wiring Overview

```
DHT22 DATA  ──► GPIO4  (ESP32)
MISTER RELAY ─► GPIO16 (ESP32)
HEAT RELAY  ──► GPIO17 (ESP32)
STATUS LED  ──► GPIO2  (ESP32, onboard)

Relay CH1 IN ─► GPIO16
Relay CH1 COM ► 12V+
Relay CH1 NO ──► Mister pump +

Relay CH2 IN ─► GPIO17
Relay CH2 COM ► 12V+
Relay CH2 NO ──► Heat mat +
```

See `docs/wiring-diagram.md` for full illustrated wiring guide.

---

## Anti-Fungal Solution Recipe (Per 10L Batch)

| Ingredient             | Amount | Purpose                  |
| ---------------------- | ------ | ------------------------ |
| Distilled water        | 9.8L   | Base                     |
| Calcium nitrate        | 5g     | Primary N source for ube |
| Potassium phosphate    | 2g     | Root development         |
| Magnesium sulfate      | 1g     | Chlorophyll precursor    |
| Hydrogen peroxide (3%) | 20ml   | Anti-fungal, oxygenation |

> ⚠️ Replace solution every 7 days. H₂O₂ degrades and loses anti-fungal efficacy.
> pH target: 5.8–6.2. Check with a digital pH meter before filling reservoir.
