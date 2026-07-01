# open-ube-root-chamber — simulation/config.py
#
# SINGLE SOURCE OF TRUTH for all chamber constants.
# Every number that exists in both the firmware and the simulation
# is defined here ONCE. Nothing is hardcoded anywhere else.
#
# How it flows:
#   config.py  ──► imported by simulate.py      (Python)
#   config.py  ──► read by generate_config_h.py  (Python)
#              └──► writes firmware-esp32/config.h (C++ header)
#              └──► included by main.ino          (Arduino)
#
# To change a setpoint: edit this file only. Then run:
#   python simulation/generate_config_h.py
# That regenerates config.h so firmware matches instantly.

# ─── Controller setpoints (match pid_controller.h) ───────────────────────────
HUMIDITY_TARGET    = 87.5   # % midpoint of 85–90% safe band
TEMPERATURE_TARGET = 29.0   # °C midpoint of 28–30°C safe band
DEADBAND           = 1.5    # how far from target before relay fires

# ─── Safe operating bands (used by simulation growth model) ──────────────────
HUMIDITY_SAFE_LOW  = 85.0   # % below this: growth slows
HUMIDITY_SAFE_HIGH = 93.0   # % above this: mold risk multiplier kicks in
TEMP_SAFE_LOW      = 27.5   # °C below this: growth slows
TEMP_SAFE_HIGH     = 31.0   # °C above this: heat stress

# ─── Root vigor thresholds (match root_vigor.py) ─────────────────────────────
HIGH_VIGOR_CM = 3.0   # root >= this → HIGH_VIGOR → sell immediately
GROWING_CM    = 0.5   # root >= this → GROWING    → monitor

# ─── Contamination model ─────────────────────────────────────────────────────
# These model what root_vigor.py detects visually via the Pi camera.
# The simulation models the CAUSE; root_vigor.py detects the SYMPTOM.
CONT_RISK_BASE          = 0.0003  # base probability per tick per vessel
CONT_HUMIDITY_THRESHOLD = 93.0    # % above this, mold risk multiplies
CONT_HUMIDITY_MULTIPLIER = 9      # at max overshoot, risk = base * (1 + this)
CONT_HUMIDITY_TICKS_MAX  = 10     # ticks at ceiling before max multiplier kicks in

# ─── Simulation timing ───────────────────────────────────────────────────────
VESSEL_COUNT  = 40   # setts in the tray
TICKS_PER_DAY = 120  # 1 tick = ~12 simulated minutes

# ─── Firmware timing (informational — documented here for traceability) ───────
# These are used in main.ino, not in the Python simulation,
# but documented here so engineers know where they come from.
# SENSOR_INTERVAL_MS = 2000   # DHT22 read every 2 seconds
# SERIAL_LOG_MS      = 5000   # Serial.println every 5 seconds