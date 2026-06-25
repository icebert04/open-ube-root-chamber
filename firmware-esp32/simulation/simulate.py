# -*- coding: utf-8 -*-
"""
open-root-chamber — simulation/simulate.py

Live terminal simulation of the chamber.
Mirrors the interactive widget: real-time sensor readings,
relay states, vessel tray, batch summary, and serial log.

Run:
    python simulate.py
    python simulate.py --days 30 --speed 5 --ambient-humidity 72 --ambient-temp 25

Dependencies:
    pip install rich
"""

import random
import time
import argparse
from dataclasses import dataclass
from enum import Enum
from collections import deque

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich import box


# ─── Config (mirrors firmware constants) ──────────────────────────────────────

HUMIDITY_TARGET    = 87.5
TEMPERATURE_TARGET = 29.0
DEADBAND           = 1.5
VESSEL_COUNT       = 40
TICKS_PER_DAY      = 120   # 1 tick = ~12 simulated minutes
HIGH_VIGOR_CM      = 3.0
GROWING_CM         = 0.5


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
    def __init__(self, setpoint: float, deadband: float = DEADBAND):
        self.setpoint = setpoint
        self.deadband = deadband

    def should_actuate(self, current: float) -> bool:
        return (self.setpoint - current) > self.deadband


# ─── Chamber State ────────────────────────────────────────────────────────────

class Chamber:
    def __init__(self, ambient_hum: float, ambient_temp: float, cont_risk: float, seed: int = 42):
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
            Vessel(id=i+1, dormant=random.random()<0.2, root_cm=random.uniform(0, 0.2))
            for i in range(VESSEL_COUNT)
        ]
        self.log: deque[tuple[str,str]] = deque(maxlen=12)  # (level, message)

    def step(self):
        self.tick += 1

        # ── Sensor physics ────────────────────────────────────────────────────
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

        # ── Controller ────────────────────────────────────────────────────────
        prev_mister = self.mister_on
        self.mister_on = self.hum_ctrl.should_actuate(self.humidity)
        self.heat_on   = self.temp_ctrl.should_actuate(self.temperature)

        if self.mister_on and not prev_mister:
            self.mist_cycles += 1
            self._log("ok", f"[MIST] ON  hum={self.humidity:.1f}% target={HUMIDITY_TARGET}%")
        elif not self.mister_on and prev_mister:
            self._log("ok", f"[MIST] OFF hum={self.humidity:.1f}%")

        if self.tick % 8 == 0:
            self._log("info", f"[LOG]  hum={self.humidity:.1f}% temp={self.temperature:.1f}°C mister={'ON' if self.mister_on else 'OFF'} heat={'ON' if self.heat_on else 'OFF'}")

        # ── Plant growth ──────────────────────────────────────────────────────
        hum_ok  = 85 <= self.humidity    <= 93
        temp_ok = 27.5 <= self.temperature <= 31
        good = hum_ok and temp_ok
        good_rate = random.uniform(0.04, 0.18) / TICKS_PER_DAY
        bad_rate  = random.uniform(0.00, 0.02) / TICKS_PER_DAY

        for v in self.vessels:
            if v.contaminated:
                continue
            if v.dormant:
                if good and random.random() < 0.008:
                    v.dormant = False
                    self._log("ok", f"[VISION] Vessel #{v.id:03d} broke dormancy")
                continue
            v.root_cm += good_rate if good else bad_rate
            v.update_vigor()
            if random.random() < self.cont_risk:
                v.contaminated = True
                v.update_vigor()
                self._log("err", f"[VISION] ⚠ Contamination Vessel #{v.id:03d} — quarantine!")

    def _log(self, level: str, msg: str):
        day = self.tick / TICKS_PER_DAY
        self.log.append((level, f"Day {day:05.2f} | {msg}"))

    @property
    def day(self): return self.tick / TICKS_PER_DAY
    @property
    def high_count(self): return sum(1 for v in self.vessels if v.vigor==Vigor.HIGH and not v.contaminated)
    @property
    def grow_count(self): return sum(1 for v in self.vessels if v.vigor==Vigor.GROWING and not v.contaminated)
    @property
    def dud_count(self):  return sum(1 for v in self.vessels if v.vigor==Vigor.DUD and not v.contaminated)
    @property
    def cont_count(self): return sum(1 for v in self.vessels if v.contaminated)
    @property
    def revenue(self):    return self.high_count * 0.50 + self.grow_count * 0.15


# ─── Rendering ────────────────────────────────────────────────────────────────

def render(chamber: Chamber, total_days: int) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header",  size=3),
        Layout(name="sensors", size=5),
        Layout(name="middle",  size=14),
        Layout(name="summary", size=5),
        Layout(name="log",     size=16),
    )
    layout["middle"].split_row(
        Layout(name="actuators", ratio=1),
        Layout(name="vessels",   ratio=2),
    )

    # ── Header ────────────────────────────────────────────────────────────────
    pct = min(chamber.day / total_days, 1.0)
    bar_w = 50
    filled = int(pct * bar_w)
    bar = "█" * filled + "░" * (bar_w - filled)
    layout["header"].update(Panel(
        Text(f"open-root-chamber  |  Day {chamber.day:.1f} / {total_days}   [{bar}] {pct*100:.0f}%", style="bold"),
        box=box.SIMPLE
    ))

    # ── Sensors ───────────────────────────────────────────────────────────────
    hum_ok  = 85 <= chamber.humidity    <= 93
    temp_ok = 27.5 <= chamber.temperature <= 31
    hum_color  = "green" if hum_ok  else "red"
    temp_color = "green" if temp_ok else "yellow"

    sensor_table = Table(box=box.SIMPLE, expand=True, show_header=False)
    sensor_table.add_column(ratio=1)
    sensor_table.add_column(ratio=1)
    sensor_table.add_column(ratio=1)
    sensor_table.add_column(ratio=1)
    sensor_table.add_row(
        Text("HUMIDITY",    style="dim"),
        Text("TEMPERATURE", style="dim"),
        Text("MIST CYCLES", style="dim"),
        Text("EST. pH",     style="dim"),
    )
    sensor_table.add_row(
        Text(f"{chamber.humidity:.1f}%",    style=f"bold {hum_color}"),
        Text(f"{chamber.temperature:.1f}°C", style=f"bold {temp_color}"),
        Text(str(chamber.mist_cycles),       style="bold"),
        Text(f"{random.uniform(5.8, 6.2):.1f}", style="bold"),
    )
    layout["sensors"].update(Panel(sensor_table, title="[dim]sensors[/dim]", box=box.ROUNDED))

    # ── Actuators ─────────────────────────────────────────────────────────────
    act = Table(box=box.SIMPLE, expand=True, show_header=False)
    act.add_column()
    act.add_column()

    def relay_badge(on: bool, label_on="ON", label_off="OFF"):
        if on:
            return Text(f" {label_on} ", style="bold green on dark_green")
        return Text(f" {label_off} ", style="dim")

    act.add_row("Ultrasonic mister", relay_badge(chamber.mister_on))
    act.add_row("Heat mat",          relay_badge(chamber.heat_on))
    act.add_row("Contamination",     relay_badge(chamber.cont_count > 0, "ALERT", "CLEAR") if chamber.cont_count > 0
                                     else Text(" CLEAR ", style="dim"))
    layout["actuators"].update(Panel(act, title="[dim]relay states[/dim]", box=box.ROUNDED))

    # ── Vessel Tray ───────────────────────────────────────────────────────────
    COLOR = {Vigor.HIGH: "green", Vigor.GROWING: "yellow", Vigor.DUD: "red"}
    ICON  = {Vigor.HIGH: "■", Vigor.GROWING: "◆", Vigor.DUD: "·"}

    rows_text = Text()
    for i, v in enumerate(chamber.vessels):
        if v.contaminated:
            rows_text.append(" ✕ ", style="bold red")
        elif v.dormant:
            rows_text.append(" z ", style="dim")
        else:
            c = COLOR[v.vigor]
            rows_text.append(f" {ICON[v.vigor]} ", style=c)
        if (i + 1) % 8 == 0:
            rows_text.append("\n")

    legend = Text("\n■ high vigor  ◆ growing  · dud  ✕ contaminated  z dormant", style="dim")
    rows_text.append_text(legend)
    layout["vessels"].update(Panel(rows_text, title="[dim]vessel tray — 40 setts[/dim]", box=box.ROUNDED))

    # ── Summary ───────────────────────────────────────────────────────────────
    sum_table = Table(box=box.SIMPLE, expand=True, show_header=False)
    sum_table.add_column(ratio=1)
    sum_table.add_column(ratio=1)
    sum_table.add_column(ratio=1)
    sum_table.add_column(ratio=1)
    sum_table.add_row("High vigor", "Growing", "Duds", "Est. revenue")
    sum_table.add_row(
        Text(str(chamber.high_count), style="bold green"),
        Text(str(chamber.grow_count), style="bold yellow"),
        Text(str(chamber.dud_count),  style="bold red"),
        Text(f"${chamber.revenue:.2f}", style="bold blue"),
    )
    layout["summary"].update(Panel(sum_table, title="[dim]batch summary[/dim]", box=box.ROUNDED))

    # ── Serial Log ────────────────────────────────────────────────────────────
    log_colors = {"ok": "green", "info": "dim", "warn": "yellow", "err": "red"}
    log_text = Text()
    for level, msg in chamber.log:
        log_text.append(msg + "\n", style=log_colors.get(level, "white"))
    layout["log"].update(Panel(log_text, title="[dim]serial monitor — ESP32 log[/dim]", box=box.ROUNDED))

    return layout


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="open-root-chamber terminal simulation")
    parser.add_argument("--days",             type=int,   default=30,   help="Simulation duration in days")
    parser.add_argument("--speed",            type=float, default=5.0,  help="Ticks per second (higher = faster)")
    parser.add_argument("--ambient-humidity", type=float, default=75.0, help="Starting room humidity %%")
    parser.add_argument("--ambient-temp",     type=float, default=26.0, help="Starting room temperature °C")
    parser.add_argument("--contamination-risk", type=float, default=0.0003, help="Contamination probability per tick")
    parser.add_argument("--seed",             type=int,   default=42,   help="Random seed for reproducibility")
    args = parser.parse_args()

    chamber = Chamber(
        ambient_hum  = args.ambient_humidity,
        ambient_temp = args.ambient_temp,
        cont_risk    = args.contamination_risk,
        seed         = args.seed,
    )

    total_ticks = args.days * TICKS_PER_DAY
    tick_delay  = 1.0 / args.speed

    console = Console()
    console.print(f"\n[bold]open-root-chamber[/bold] simulation starting — {args.days} days at {args.speed}× speed")
    console.print(f"[dim]Ctrl+C to stop early\n[/dim]")

    with Live(render(chamber, args.days), console=console, refresh_per_second=10, screen=True) as live:
        try:
            for _ in range(total_ticks):
                chamber.step()
                live.update(render(chamber, args.days))
                time.sleep(tick_delay)
        except KeyboardInterrupt:
            pass

    # Final summary after Live exits
    console.print(f"\n[bold]═══ Final Batch Report ═══[/bold]")
    console.print(f"  High vigor   : [green]{chamber.high_count}[/green] vessels — ready to sell @ $0.50 each")
    console.print(f"  Growing      : [yellow]{chamber.grow_count}[/yellow] vessels — monitor another week")
    console.print(f"  Duds         : [red]{chamber.dud_count}[/red] vessels")
    console.print(f"  Contaminated : [red]{chamber.cont_count}[/red] vessels — quarantined")
    console.print(f"  Mist cycles  : {chamber.mist_cycles}")
    console.print(f"  Est. revenue : [bold blue]${chamber.revenue:.2f}[/bold blue]")


if __name__ == "__main__":
    main()
