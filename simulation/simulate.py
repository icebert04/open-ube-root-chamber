# -*- coding: utf-8 -*-
"""
open-root-chamber — simulation/simulate.py

Live terminal simulation of the chamber.
Mirrors the interactive widget: real-time sensor readings,
relay states, vessel tray, batch summary, and serial log.

Zero external dependencies — uses only Python stdlib.
Works on Python 3.6+ on any OS.

Run:
    python simulate.py
    python simulate.py --days 30 --speed 5 --ambient-humidity 72 --ambient-temp 25
    python simulate.py --days 30 --speed 999 --batch
"""

import curses
import random
import time
import argparse
import sys
from dataclasses import dataclass
from enum import Enum
from collections import deque


# ─── Config (mirrors firmware constants) ──────────────────────────────────────

HUMIDITY_TARGET         = 87.5
TEMPERATURE_TARGET      = 29.0
DEADBAND                = 1.5
VESSEL_COUNT            = 40
TICKS_PER_DAY           = 120   # 1 tick = ~12 simulated minutes
HIGH_VIGOR_CM           = 3.0
GROWING_CM              = 0.5
CONT_HUMIDITY_THRESHOLD = 93.0  # % above this, mold risk x5


# ─── Color pair IDs ───────────────────────────────────────────────────────────
# Defined once here, initialized in setup_colors()

C_NORMAL   = 0
C_GREEN    = 1
C_YELLOW   = 2
C_RED      = 3
C_CYAN     = 4
C_BLUE     = 5
C_DIM      = 6
C_HEADER   = 7


# ─── Models ───────────────────────────────────────────────────────────────────

class Vigor(Enum):
    HIGH    = "HIGH"
    GROWING = "GROW"
    DUD     = "DUD "


@dataclass
class Vessel:
    id: int
    root_cm: float = 0.0
    vigor: Vigor = Vigor.DUD
    contaminated: bool = False
    dormant: bool = False

    def update_vigor(self):
        if self.contaminated:
            self.vigor = Vigor.DUD
        elif self.root_cm >= HIGH_VIGOR_CM:
            self.vigor = Vigor.HIGH
        elif self.root_cm >= GROWING_CM:
            self.vigor = Vigor.GROWING
        else:
            self.vigor = Vigor.DUD


# ─── Deadband Controller (mirrors pid_controller.h) ───────────────────────────

class DeadbandController:
    def __init__(self, setpoint, deadband=DEADBAND):
        self.setpoint = setpoint
        self.deadband = deadband

    def should_actuate(self, current):
        return (self.setpoint - current) > self.deadband


# ─── Chamber ──────────────────────────────────────────────────────────────────

class Chamber:
    def __init__(self, ambient_hum, ambient_temp, cont_risk, seed=42):
        random.seed(seed)
        self.ambient_hum  = ambient_hum
        self.ambient_temp = ambient_temp
        self.cont_risk    = cont_risk

        self.humidity    = ambient_hum
        self.temperature = ambient_temp
        self.mister_on   = False
        self.heat_on     = False
        self.mist_cycles = 0
        self.tick        = 0

        self.hum_ctrl  = DeadbandController(HUMIDITY_TARGET)
        self.temp_ctrl = DeadbandController(TEMPERATURE_TARGET)

        self.vessels = [
            Vessel(id=i+1, dormant=random.random() < 0.2, root_cm=random.uniform(0, 0.2))
            for i in range(VESSEL_COUNT)
        ]
        self.log = deque(maxlen=10)           # rolling display log (last 10 only)
        self.contamination_log = []           # NEVER truncated — every event kept

    def step(self):
        self.tick += 1

        # Sensor physics — exponential lag toward ambient + actuator boost + noise
        self.humidity += (
            (self.ambient_hum  - self.humidity)    * 0.05
            + (2.5 if self.mister_on else 0)
            + random.gauss(0, 0.4)
        )
        self.temperature += (
            (self.ambient_temp - self.temperature) * 0.05
            + (0.8 if self.heat_on else 0)
            + random.gauss(0, 0.15)
        )
        self.humidity    = max(40.0, min(100.0, self.humidity))
        self.temperature = max(15.0, min(40.0,  self.temperature))

        # Controller — mirrors pid_controller.h deadband logic
        prev_mister = self.mister_on
        self.mister_on = self.hum_ctrl.should_actuate(self.humidity)
        self.heat_on   = self.temp_ctrl.should_actuate(self.temperature)

        if self.mister_on and not prev_mister:
            self.mist_cycles += 1
            self._log("ok",  "[MIST] ON  hum={:.1f}% target={}%".format(self.humidity, HUMIDITY_TARGET))
        elif not self.mister_on and prev_mister:
            self._log("ok",  "[MIST] OFF hum={:.1f}%".format(self.humidity))

        if self.tick % 8 == 0:
            self._log("info", "[LOG]  hum={:.1f}% temp={:.1f}C mister={} heat={}".format(
                self.humidity, self.temperature,
                "ON" if self.mister_on else "OFF",
                "ON" if self.heat_on   else "OFF",
            ))

        
        # Plant growth
        hum_ok  = 85 <= self.humidity    <= 93
        temp_ok = 27.5 <= self.temperature <= 31
        good      = hum_ok and temp_ok
        good_rate = random.uniform(0.04, 0.18) / TICKS_PER_DAY
        bad_rate  = random.uniform(0.00, 0.02) / TICKS_PER_DAY

        for v in self.vessels:
            if v.contaminated:
                continue
            if v.dormant:
                if good and random.random() < 0.008:
                    v.dormant = False
                    self._log("ok", "[VISION] Vessel #{:03d} broke dormancy".format(v.id))
                continue
            v.root_cm += good_rate if good else bad_rate
            v.update_vigor()

            # Contamination risk — humidity spike multiplies mold probability.
            # This models what root_vigor.py detects visually via the Pi camera:
            # the CAUSE (humidity overshoot) modeled here → the SYMPTOM (mold)
            # detected there.
            spike = self.humidity > CONT_HUMIDITY_THRESHOLD
            effective_risk = self.cont_risk * 5 if spike else self.cont_risk
            if random.random() < effective_risk:
                v.contaminated = True
                v.update_vigor()
                reason = "HUMIDITY SPIKE ({:.1f}%)".format(self.humidity) if spike else "RANDOM"
                msg = "[VISION] ! Contamination Vessel #{:03d} -- {} -- quarantine!".format(v.id, reason)
                self._log("err", msg)
                # Also write to contamination_log which is NEVER truncated
                self._log_contamination(v.id, reason)
        

    def _log(self, level, msg):
        self.log.append((level, "Day {:05.2f} | {}".format(self.tick / TICKS_PER_DAY, msg)))

    def _log_contamination(self, vessel_id, reason):
        """Permanent record — never truncated unlike self.log."""
        self.contamination_log.append(
            "Day {:05.2f} | Vessel #{:03d} | {}".format(
                self.tick / TICKS_PER_DAY, vessel_id, reason)
        )

    def dump_log_to_file(self):
        import os
        version = 1
        filename = "sim_log_v{}.txt".format(version)
        while os.path.exists(filename):
            version += 1
            filename = "sim_log_v{}.txt".format(version)
        with open(filename, "w") as f:
            f.write("open-ube-root-chamber Simulation Log\n")
            f.write("=" * 40 + "\n")
            f.write("Days run: {:.2f}\n".format(self.day))
            f.write("=" * 40 + "\n\n")

            # --- Contamination audit trail (complete, never truncated) ---
            f.write("=== Contamination Events ({} total) ===\n".format(
                len(self.contamination_log)))
            if self.contamination_log:
                for entry in self.contamination_log:
                    f.write("  [CONTAMINATION] {}\n".format(entry))
            else:
                f.write("  None\n")
            f.write("\n")

            # --- Rolling serial log (last 10 entries) ---
            f.write("=== Serial Log (last 10 entries) ===\n")
            for level, msg in self.log:
                f.write("[{}] {}\n".format(level.upper(), msg))
            f.write("\n")

            # --- Final stats ---
            f.write("=== Final Stats ===\n")
            f.write("  High vigor   : {}\n".format(self.high_count))
            f.write("  Growing      : {}\n".format(self.grow_count))
            f.write("  Duds         : {}\n".format(self.dud_count))
            f.write("  Contaminated : {}\n".format(self.cont_count))
            f.write("  Mist cycles  : {}\n".format(self.mist_cycles))
            f.write("  Est. revenue : ${:.2f}\n".format(self.revenue))
        print("\n[LOG] Simulation log saved to {}".format(filename))

    @property
    def day(self):        return self.tick / TICKS_PER_DAY
    @property
    def high_count(self): return sum(1 for v in self.vessels if v.vigor == Vigor.HIGH    and not v.contaminated)
    @property
    def grow_count(self): return sum(1 for v in self.vessels if v.vigor == Vigor.GROWING and not v.contaminated)
    @property
    def dud_count(self):  return sum(1 for v in self.vessels if v.vigor == Vigor.DUD     and not v.contaminated)
    @property
    def cont_count(self): return sum(1 for v in self.vessels if v.contaminated)
    @property
    def revenue(self):    return self.high_count * 0.50 + self.grow_count * 0.15


# ─── Curses helpers ───────────────────────────────────────────────────────────

def setup_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_GREEN,  curses.COLOR_GREEN,  -1)
    curses.init_pair(C_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_RED,    curses.COLOR_RED,    -1)
    curses.init_pair(C_CYAN,   curses.COLOR_CYAN,   -1)
    curses.init_pair(C_BLUE,   curses.COLOR_BLUE,   -1)
    curses.init_pair(C_DIM,    curses.COLOR_WHITE,  -1)
    curses.init_pair(C_HEADER, curses.COLOR_BLACK,  curses.COLOR_CYAN)


def safe_addstr(win, y, x, text, attr=0):
    """Write text without crashing on terminal edge overflow."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    if x >= w:
        return
    text = text[:w - x]
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_box(win, y, x, h, w, title=""):
    """Draw a rounded box with optional title."""
    attr = curses.color_pair(C_DIM)
    safe_addstr(win, y,     x,     "+" + "-" * (w - 2) + "+", attr)
    safe_addstr(win, y + h - 1, x, "+" + "-" * (w - 2) + "+", attr)
    for row in range(y + 1, y + h - 1):
        safe_addstr(win, row, x,         "|", attr)
        safe_addstr(win, row, x + w - 1, "|", attr)
    if title:
        label = " {} ".format(title)
        safe_addstr(win, y, x + 2, label, attr)


def bar_str(value, lo, hi, width=20):
    """Render a simple ASCII bar for a value within a range."""
    pct   = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    filled = int(pct * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


# ─── Render ───────────────────────────────────────────────────────────────────

def render(stdscr, chamber, total_days):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # ── Header bar ────────────────────────────────────────────────────────────
    pct    = min(chamber.day / total_days, 1.0)
    bar_w  = max(10, w - 45)
    filled = int(pct * bar_w)
    prog   = "#" * filled + "-" * (bar_w - filled)
    header = " open-ube-root-chamber  Day {:5.1f}/{:<3d}  [{}] {:3.0f}% ".format(
        chamber.day, total_days, prog, pct * 100
    )
    safe_addstr(stdscr, 0, 0, header.ljust(w), curses.color_pair(C_HEADER) | curses.A_BOLD)

    row = 2

    # ── Sensors ───────────────────────────────────────────────────────────────
    draw_box(stdscr, row, 0, 5, w, "sensors")

    hum_color  = C_GREEN if 85 <= chamber.humidity    <= 93  else C_RED
    temp_color = C_GREEN if 27.5 <= chamber.temperature <= 31 else C_YELLOW

    hum_bar  = bar_str(chamber.humidity,    40, 100)
    temp_bar = bar_str(chamber.temperature, 15,  40)

    safe_addstr(stdscr, row+1, 2,  "HUMIDITY",    curses.color_pair(C_DIM))
    safe_addstr(stdscr, row+2, 2,  "{:.1f}%  {}".format(chamber.humidity, hum_bar),
                curses.color_pair(hum_color) | curses.A_BOLD)

    col2 = w // 4
    safe_addstr(stdscr, row+1, col2, "TEMPERATURE", curses.color_pair(C_DIM))
    safe_addstr(stdscr, row+2, col2, "{:.1f}C  {}".format(chamber.temperature, temp_bar),
                curses.color_pair(temp_color) | curses.A_BOLD)

    col3 = w // 2
    safe_addstr(stdscr, row+1, col3, "MIST CYCLES", curses.color_pair(C_DIM))
    safe_addstr(stdscr, row+2, col3, str(chamber.mist_cycles), curses.A_BOLD)

    col4 = (w * 3) // 4
    safe_addstr(stdscr, row+1, col4, "EST. pH", curses.color_pair(C_DIM))
    safe_addstr(stdscr, row+2, col4, "{:.1f}".format(random.uniform(5.8, 6.2)), curses.A_BOLD)

    row += 6

    # ── Relay states + Vessel tray (side by side) ─────────────────────────────
    mid = w // 3

    # Relay box
    draw_box(stdscr, row, 0, 7, mid, "relay states")
    relays = [
        ("Ultrasonic mister", chamber.mister_on,        "ON",    "OFF"),
        ("Heat mat",          chamber.heat_on,           "ON",    "OFF"),
        ("Contamination",     chamber.cont_count > 0,   "ALERT", "CLEAR"),
    ]
    for i, (label, state, on_txt, off_txt) in enumerate(relays):
        safe_addstr(stdscr, row + 1 + i*2, 2, label)
        if state:
            badge_color = C_RED if on_txt == "ALERT" else C_GREEN
            safe_addstr(stdscr, row + 1 + i*2, mid - 10,
                        "[{}]".format(on_txt), curses.color_pair(badge_color) | curses.A_BOLD)
        else:
            safe_addstr(stdscr, row + 1 + i*2, mid - 10,
                        "[{}]".format(off_txt), curses.color_pair(C_DIM))

    # Vessel tray box
    draw_box(stdscr, row, mid, 7, w - mid, "vessel tray -- 40 setts")
    ICONS = {Vigor.HIGH: "H", Vigor.GROWING: "G", Vigor.DUD: "."}
    VCOLORS = {Vigor.HIGH: C_GREEN, Vigor.GROWING: C_YELLOW, Vigor.DUD: C_RED}

    tray_row = row + 1
    tray_col = mid + 2
    for i, v in enumerate(chamber.vessels):
        col_offset = (i % 20) * 2
        r_offset   = i // 20
        if v.contaminated:
            safe_addstr(stdscr, tray_row + r_offset, tray_col + col_offset,
                        "X", curses.color_pair(C_RED) | curses.A_BOLD)
        elif v.dormant:
            safe_addstr(stdscr, tray_row + r_offset, tray_col + col_offset,
                        "z", curses.color_pair(C_DIM))
        else:
            safe_addstr(stdscr, tray_row + r_offset, tray_col + col_offset,
                        ICONS[v.vigor], curses.color_pair(VCOLORS[v.vigor]) | curses.A_BOLD)

    legend_row = tray_row + 3
    safe_addstr(stdscr, legend_row, mid + 2,
                "H=high vigor  G=growing  .=dud  X=contaminated  z=dormant",
                curses.color_pair(C_DIM))

    row += 8

    # ── Batch summary ─────────────────────────────────────────────────────────
    draw_box(stdscr, row, 0, 4, w, "batch summary")
    col_w = w // 4
    labels  = ["High vigor", "Growing", "Duds", "Est. revenue"]
    values  = [str(chamber.high_count), str(chamber.grow_count),
               str(chamber.dud_count),  "${:.2f}".format(chamber.revenue)]
    vcolors = [C_GREEN, C_YELLOW, C_RED, C_BLUE]

    for i, (lbl, val, vc) in enumerate(zip(labels, values, vcolors)):
        safe_addstr(stdscr, row + 1, i * col_w + 2, lbl,  curses.color_pair(C_DIM))
        safe_addstr(stdscr, row + 2, i * col_w + 2, val,  curses.color_pair(vc) | curses.A_BOLD)

    row += 5

    # ── Serial log ────────────────────────────────────────────────────────────
    log_h = max(4, h - row - 1)
    draw_box(stdscr, row, 0, log_h, w, "serial monitor -- ESP32 log")

    LOG_COLORS = {"ok": C_GREEN, "info": C_DIM, "warn": C_YELLOW, "err": C_RED}
    log_entries = list(chamber.log)
    visible = log_entries[-(log_h - 2):]
    for i, (level, msg) in enumerate(visible):
        safe_addstr(stdscr, row + 1 + i, 2,
                    msg[:w - 4], curses.color_pair(LOG_COLORS.get(level, C_NORMAL)))

    stdscr.refresh()


# ─── Batch mode (no curses, for GitHub Actions) ───────────────────────────────

def run_batch(chamber, total_days):
    total_ticks = total_days * TICKS_PER_DAY
    print("\nopen-ube-root-chamber simulation [batch mode]")
    print("Days: {}  Vessels: {}  Ambient: {:.0f}% / {:.0f}C".format(
        total_days, VESSEL_COUNT, chamber.ambient_hum, chamber.ambient_temp))
    print("-" * 50)

    for t in range(total_ticks):
        chamber.step()
        if t % TICKS_PER_DAY == 0:
            day = t // TICKS_PER_DAY + 1
            print("Day {:02d} | Hum:{:.1f}% Temp:{:.1f}C | High:{} Grow:{} Cont:{} | Mist cycles:{}".format(
                day, chamber.humidity, chamber.temperature,
                chamber.high_count, chamber.grow_count,
                chamber.cont_count, chamber.mist_cycles,
            ))


# ─── Curses entrypoint ────────────────────────────────────────────────────────

def run_live(stdscr, chamber, total_days, tick_delay):
    curses.curs_set(0)
    stdscr.nodelay(True)
    setup_colors()

    total_ticks = total_days * TICKS_PER_DAY

    try:
        for _ in range(total_ticks):
            chamber.step()
            render(stdscr, chamber, total_days)
            time.sleep(tick_delay)

            # q or Ctrl+C to quit early
            key = stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break
    except KeyboardInterrupt:
        pass

    # Final report printed after curses exits
    curses.curs_set(1)

def dump_log_to_file(self):
        import os
        version = 1
        filename = f"sim_log_v{version}.txt"
        while os.path.exists(filename):
            version += 1
            filename = f"sim_log_v{version}.txt"
        
        with open(filename, "w") as f:
            f.write(f"Simulation Log - Version {version}\n")
            f.write("="*30 + "\n")
            for level, msg in self.log:
                f.write(f"[{level.upper()}] {msg}\n")
            f.write(f"\nFinal Stats: High={self.high_count} Grow={self.grow_count} Duds={self.dud_count} Revenue=${self.revenue:.2f}")
        print(f"\n[!] Log saved to {filename}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="open-ube-root-chamber terminal simulation")
    parser.add_argument("--days",               type=int,   default=30,    help="Simulation duration in days")
    parser.add_argument("--speed",              type=float, default=5.0,   help="Ticks per second (higher = faster)")
    parser.add_argument("--ambient-humidity",   type=float, default=75.0,  help="Room humidity %%")
    parser.add_argument("--ambient-temp",       type=float, default=26.0,  help="Room temperature C")
    parser.add_argument("--contamination-risk", type=float, default=0.0003,help="Contamination prob per tick")
    parser.add_argument("--seed",               type=int,   default=42,    help="Random seed")
    parser.add_argument("--batch",              action="store_true",        help="Non-interactive mode for CI")
    args = parser.parse_args()

    chamber = Chamber(
        ambient_hum  = args.ambient_humidity,
        ambient_temp = args.ambient_temp,
        cont_risk    = args.contamination_risk,
        seed         = args.seed,
    )

    if args.batch:
        run_batch(chamber, args.days)
    else:
        print("Starting simulation... press Q to quit early.")
        time.sleep(0.5)
        curses.wrapper(run_live, chamber, args.days, 1.0 / args.speed)

    # Final report — always prints after both batch and live modes
    print("\n=== Final Batch Report ===")
    print("  High vigor   : {} vessels -- ready to sell @ $0.50".format(chamber.high_count))
    print("  Growing      : {} vessels -- monitor another week".format(chamber.grow_count))
    print("  Duds         : {} vessels".format(chamber.dud_count))
    print("  Contaminated : {} vessels -- quarantined".format(chamber.cont_count))
    print("  Mist cycles  : {}".format(chamber.mist_cycles))
    print("  Est. revenue : ${:.2f}".format(chamber.revenue))

    # Print contamination audit to console so you see it immediately
    print("\n=== Contamination Audit ({} events) ===".format(len(chamber.contamination_log)))
    if chamber.contamination_log:
        for entry in chamber.contamination_log:
            print("  [CONTAMINATION] {}".format(entry))
    else:
        print("  None")

    chamber.dump_log_to_file()


if __name__ == "__main__":
    main()