"""ZoneStateEngine — the backend's single source of truth for the Concourse
city grid, and a *real producer* for traffic_data.sqlite.

The frontend dashboard is a renderer: when it can reach this engine it stops
running its own simulation and hydrates from ``/zone_state``. This module owns:

  * per-city zone state (venue / transit hubs / hotels / corridor), mirrored
    from the dashboard's own data model so the two can never drift apart,
  * the event-schedule phase physics (doors -> main -> intermission -> exit),
  * the venue AT-CAPACITY state machine and last-mile queue logic,
  * organizer actions (delay / extend / end early / overflow / shuttles ...),
  * persistence: every tick writes decision_logs rows (one per zone plus a
    system balance row) and transition alerts to active_alerts.

Everything is rule-based and local — there is no external AI service.
"""

from __future__ import annotations

import math
import random
import threading
from typing import Any, Dict, List, Optional


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def fmt_min(m: int) -> str:
    return f"{int(m // 60):02d}:{int(m % 60):02d}"


# --------------------------------------------------------------------------- #
#  Data — mirrors the dashboard's CITIES_DATA exactly                          #
# --------------------------------------------------------------------------- #

def make_schedule(doors: int = 1080, door_len: int = 50, main_len: int = 90,
                  inter_len: int = 30, exit_len: int = 70) -> List[dict]:
    d, m, i = doors, doors + door_len, doors + door_len + main_len
    e = i + inter_len
    return [
        {"id": "doors", "label": "Doors Open", "start": d, "end": m, "color": "#38BDF8"},
        {"id": "main", "label": "Main Event", "start": m, "end": i, "color": "#A78BFA"},
        {"id": "intermission", "label": "Intermission", "start": i, "end": e, "color": "#F5A623"},
        {"id": "exit", "label": "Exit", "start": e, "end": e + exit_len, "color": "#FF5C6C"},
    ]


PHASE_FORCES: Dict[str, Dict[str, float]] = {
    "pre": {"venue": 0.5, "transitHub": 0.4, "transitE": 0.2, "corridor": 0.3},
    "doors": {"venue": 2.9, "transitHub": 1.1, "transitE": 0.6, "corridor": 0.7, "hotelN": 0.3},
    "main": {"venue": 1.2, "hotelN": 0.6, "hotelS": 0.4, "corridor": 0.5, "transitHub": 0.3},
    "intermission": {"venue": -0.8, "transitHub": 1.4, "transitE": 1.0, "hotelN": 0.6, "corridor": 0.4},
    "exit": {"venue": -3.2, "transitHub": 2.9, "transitE": 1.6, "hotelS": 0.9, "corridor": 1.8, "hotelN": 0.5},
    "ended": {"venue": -2.5, "transitHub": 1.0, "transitE": 0.8, "corridor": 0.6},
}

SURGE_SCRIPT: Dict[str, List[float]] = {
    "venue": [10, 6, -10, -22, -18, -8],
    "transitHub": [3, 9, 18, 24, 15, 7],
    "transitE": [1, 4, 8, 14, 9, 4],
    "hotelN": [2, 3, 4, 5, 4, 2],
    "hotelS": [0, 1, 2, 3, 2, 1],
    "corridor": [4, 10, 19, 22, 16, 8],
}


def _zones(*defs: dict) -> List[dict]:
    return list(defs)


# (id, name, type, baseline, capacity label, unit, x, y)
ZONE_SPECS = {
    "navimumbai": _zones(
        {"id": "venue", "name": "Pillai Campus Ground (Alegria Stage)", "type": "venue", "baseline": 60, "capacityLabel": "15,000 capacity ground", "unit": "ground density", "x": 130, "y": 150},
        {"id": "transitHub", "name": "Panvel Junction Railway Hub", "type": "transit", "baseline": 52, "capacityLabel": "Harbour & Central lines", "unit": "station load", "x": 300, "y": 90},
        {"id": "transitE", "name": "New Panvel ST Bus Depot Feeder", "type": "transit", "baseline": 38, "capacityLabel": "18 feeder routes", "unit": "bus load", "x": 300, "y": 210},
        {"id": "hotelN", "name": "Kamothe & Kharghar Hotels", "type": "hotel", "baseline": 70, "capacityLabel": "3,200 rooms", "unit": "room occupancy", "x": 470, "y": 80},
        {"id": "hotelS", "name": "Nerul, Vashi & CBD Belapur", "type": "hotel", "baseline": 42, "capacityLabel": "5,100 rooms", "unit": "room occupancy", "x": 470, "y": 220},
        {"id": "corridor", "name": "Sion–Panvel Highway & Palm Beach Artery", "type": "corridor", "baseline": 64, "capacityLabel": "5,000 veh/hr", "unit": "arterial load", "x": 210, "y": 280},
    ),
    "london": _zones(
        {"id": "venue", "name": "Wembley Stadium Core", "type": "venue", "baseline": 58, "capacityLabel": "85,000 capacity", "unit": "stadium density", "x": 130, "y": 150},
        {"id": "transitHub", "name": "Wembley Park (Jubilee/Metro)", "type": "transit", "baseline": 52, "capacityLabel": "24 trains/hr", "unit": "station load", "x": 300, "y": 90},
        {"id": "transitE", "name": "Olympic Way & Bakerloo Feeder", "type": "transit", "baseline": 36, "capacityLabel": "14 trains/hr", "unit": "pedestrian flow", "x": 300, "y": 210},
        {"id": "hotelN", "name": "Wembley Park Hotel District", "type": "hotel", "baseline": 74, "capacityLabel": "4,200 rooms", "unit": "room occupancy", "x": 470, "y": 80},
        {"id": "hotelS", "name": "Central London West End District", "type": "hotel", "baseline": 42, "capacityLabel": "9,500 rooms", "unit": "room occupancy", "x": 470, "y": 220},
        {"id": "corridor", "name": "North Circular A406 Artery", "type": "corridor", "baseline": 64, "capacityLabel": "4,500 veh/hr", "unit": "arterial load", "x": 210, "y": 280},
    ),
    "newyork": _zones(
        {"id": "venue", "name": "MetLife Stadium Core", "type": "venue", "baseline": 62, "capacityLabel": "82,500 capacity", "unit": "stadium density", "x": 130, "y": 150},
        {"id": "transitHub", "name": "Secaucus Junction Rail Hub", "type": "transit", "baseline": 54, "capacityLabel": "28 trains/hr", "unit": "concourse load", "x": 300, "y": 90},
        {"id": "transitE", "name": "Lincoln Tunnel Express Corridor", "type": "transit", "baseline": 40, "capacityLabel": "35 coaches/hr", "unit": "corridor load", "x": 300, "y": 210},
        {"id": "hotelN", "name": "Midtown Manhattan Hotels", "type": "hotel", "baseline": 78, "capacityLabel": "14,000 rooms", "unit": "room occupancy", "x": 470, "y": 80},
        {"id": "hotelS", "name": "Jersey City & Hoboken District", "type": "hotel", "baseline": 44, "capacityLabel": "6,200 rooms", "unit": "room occupancy", "x": 470, "y": 220},
        {"id": "corridor", "name": "Route 3 & NJ Turnpike Bottleneck", "type": "corridor", "baseline": 68, "capacityLabel": "5,800 veh/hr", "unit": "arterial load", "x": 210, "y": 280},
    ),
    "tokyo": _zones(
        {"id": "venue", "name": "Japan National Stadium Core", "type": "venue", "baseline": 54, "capacityLabel": "68,000 capacity", "unit": "arena density", "x": 130, "y": 150},
        {"id": "transitHub", "name": "Sendagaya & Yamanote Loop", "type": "transit", "baseline": 48, "capacityLabel": "36 trains/hr", "unit": "platform density", "x": 300, "y": 90},
        {"id": "transitE", "name": "Toei Oedo & Chuo-Sobu Line", "type": "transit", "baseline": 34, "capacityLabel": "22 trains/hr", "unit": "passenger flow", "x": 300, "y": 210},
        {"id": "hotelN", "name": "Shinjuku Central Hotel District", "type": "hotel", "baseline": 70, "capacityLabel": "11,000 rooms", "unit": "room occupancy", "x": 470, "y": 80},
        {"id": "hotelS", "name": "Roppongi & Shinagawa District", "type": "hotel", "baseline": 38, "capacityLabel": "7,500 rooms", "unit": "room occupancy", "x": 470, "y": 220},
        {"id": "corridor", "name": "Shuto Expressway C1 Loop", "type": "corridor", "baseline": 56, "capacityLabel": "4,000 veh/hr", "unit": "arterial load", "x": 210, "y": 280},
    ),
    "bengaluru": _zones(
        {"id": "venue", "name": "Kanteerava Arena Core", "type": "venue", "baseline": 55, "capacityLabel": "35,000 capacity", "unit": "arena density", "x": 130, "y": 150},
        {"id": "transitHub", "name": "Majestic Central Interconnect", "type": "transit", "baseline": 50, "capacityLabel": "Purple/Green lines", "unit": "transit load", "x": 300, "y": 90},
        {"id": "transitE", "name": "Silk Board & ORR Feeder Shuttles", "type": "transit", "baseline": 38, "capacityLabel": "16 feeder routes", "unit": "transit load", "x": 300, "y": 210},
        {"id": "hotelN", "name": "MG Road & Indiranagar District", "type": "hotel", "baseline": 72, "capacityLabel": "4,500 rooms", "unit": "room occupancy", "x": 470, "y": 80},
        {"id": "hotelS", "name": "Electronic City & Koramangala", "type": "hotel", "baseline": 40, "capacityLabel": "3,800 rooms", "unit": "room occupancy", "x": 470, "y": 220},
        {"id": "corridor", "name": "Hebbal Flyover & Outer Ring Artery", "type": "corridor", "baseline": 66, "capacityLabel": "4,600 veh/hr", "unit": "arterial load", "x": 210, "y": 280},
    ),
    "dubai": _zones(
        {"id": "venue", "name": "Coca-Cola Arena Core", "type": "venue", "baseline": 52, "capacityLabel": "17,000 capacity", "unit": "arena density", "x": 130, "y": 150},
        {"id": "transitHub", "name": "Burj Khalifa / Dubai Mall Metro", "type": "transit", "baseline": 46, "capacityLabel": "Red Line Metro", "unit": "platform load", "x": 300, "y": 90},
        {"id": "transitE", "name": "Expo 2020 Route 2020 Feeder", "type": "transit", "baseline": 32, "capacityLabel": "12 express lines", "unit": "feeder load", "x": 300, "y": 210},
        {"id": "hotelN", "name": "Downtown & Business Bay Hotels", "type": "hotel", "baseline": 76, "capacityLabel": "8,500 rooms", "unit": "room occupancy", "x": 470, "y": 80},
        {"id": "hotelS", "name": "Dubai Marina & JBR District", "type": "hotel", "baseline": 36, "capacityLabel": "7,000 rooms", "unit": "room occupancy", "x": 470, "y": 220},
        {"id": "corridor", "name": "Sheikh Zayed Road (E11) Arterial", "type": "corridor", "baseline": 62, "capacityLabel": "6,200 veh/hr", "unit": "highway load", "x": 210, "y": 280},
    ),
}

CITIES = {
    "navimumbai": {
        "id": "navimumbai", "name": "Navi Mumbai, India", "flag": "🇮🇳",
        "venueName": "Pillai College of Engineering Campus",
        "eventName": "Alegria Festival — Main Concert (50,000+ footfall)",
        "schedule": make_schedule(doors=1080, door_len=50, main_len=90, inter_len=30, exit_len=70),
        "speedUnit": "km/h", "shuttleBaseline": {"transitHub": 16, "transitE": 10},
    },
    "london": {
        "id": "london", "name": "London, United Kingdom", "flag": "🇬🇧",
        "venueName": "Wembley Stadium",
        "eventName": "UEFA European Final & World Arena Concert",
        "schedule": make_schedule(doors=1050, door_len=60, main_len=100, inter_len=30, exit_len=80),
        "speedUnit": "mph", "shuttleBaseline": {"transitHub": 16, "transitE": 10},
    },
    "newyork": {
        "id": "newyork", "name": "New York / NJ, USA", "flag": "🇺🇸",
        "venueName": "MetLife Stadium",
        "eventName": "World Cup Finals & Summer Music Festival",
        "schedule": make_schedule(doors=1080, door_len=60, main_len=100, inter_len=30, exit_len=70),
        "speedUnit": "mph", "shuttleBaseline": {"transitHub": 20, "transitE": 12},
    },
    "tokyo": {
        "id": "tokyo", "name": "Tokyo, Japan", "flag": "🇯🇵",
        "venueName": "Japan National Stadium",
        "eventName": "World Athletics Championships & Tech Expo",
        "schedule": make_schedule(doors=1030, door_len=60, main_len=120, inter_len=30, exit_len=60),
        "speedUnit": "km/h", "shuttleBaseline": {"transitHub": 18, "transitE": 12},
    },
    "bengaluru": {
        "id": "bengaluru", "name": "Bengaluru, India", "flag": "🇮🇳",
        "venueName": "Kanteerava Stadium & KTPO",
        "eventName": "GIDS Global Developer Summit & IPL Match",
        "schedule": make_schedule(doors=1070, door_len=50, main_len=100, inter_len=30, exit_len=60),
        "speedUnit": "km/h", "shuttleBaseline": {"transitHub": 12, "transitE": 8},
    },
    "dubai": {
        "id": "dubai", "name": "Dubai, UAE", "flag": "🇦🇪",
        "venueName": "Coca-Cola Arena & Expo City",
        "eventName": "World Government Summit & Mega Concert",
        "schedule": make_schedule(doors=1080, door_len=60, main_len=75, inter_len=30, exit_len=50),
        "speedUnit": "km/h", "shuttleBaseline": {"transitHub": 14, "transitE": 10},
    },
}

SHOCK_BUMPS = {
    "letout": {"venue": 20, "transitHub": 12, "transitE": 8, "hotelN": 7, "corridor": 14},
    "metro": {"transitHub": 16, "transitE": 9, "corridor": 10, "venue": -4},
    "checkin": {"hotelN": 15, "hotelS": 12, "transitHub": 6},
}


def status_of(v: float) -> str:
    if v >= 82:
        return "critical"
    if v >= 68:
        return "warning"
    return "normal"


def venue_state(z: dict) -> dict:
    v = z["value"]
    if v >= 96:
        return {"state": "atCapacity", "wait": clamp(round((v - 90) * 2.2), 5, 90), "label": "AT CAPACITY"}
    if v >= 82:
        return {"state": "critical", "wait": clamp(round((v - 80) * 1.4), 5, 30), "label": "NEAR CAPACITY"}
    if v >= 68:
        return {"state": "warning", "wait": 0, "label": "FILLING UP"}
    return {"state": "open", "wait": 0, "label": "OPEN"}


def phase_at(schedule: List[dict], clock: int) -> str:
    if not schedule:
        return "ended"
    if clock < schedule[0]["start"]:
        return "pre"
    if clock >= schedule[-1]["end"]:
        return "ended"
    for p in schedule:
        if p["start"] <= clock < p["end"]:
            return p["id"]
    return schedule[-1]["id"]


def seed_history(baseline: float) -> List[dict]:
    hist = []
    for i in range(-5, 1):
        hist.append({"t": i, "v": clamp(baseline + math.sin(i) * 3 + (2 if i % 2 == 0 else -2))})
    return hist


# --------------------------------------------------------------------------- #
#  Engine                                                                      #
# --------------------------------------------------------------------------- #

class ZoneStateEngine:
    """Owns the zone grid for all cities and acts as the SQLite producer.

    Thread-safe: the background producer thread and the FastAPI request
    handlers share one engine guarded by a lock.
    """

    def __init__(self, storage=None, default_city: str = "navimumbai",
                 tick_interval: float = 3.0):
        self.storage = storage
        self._lock = threading.RLock()
        self.tick_interval = tick_interval
        self.default_city = default_city
        self.paused = False
        self.ticks = 0

        self.city_id = default_city
        self.clock = 0
        self.surge_active = False
        self.surge_step = 0
        self.overflow_active = False
        self.rain = False
        self.emergency = False
        self.signal_extended = False
        self.shuttles: Dict[str, float] = {}
        self.schedule: List[dict] = []
        self.zones: List[dict] = []
        self.last_phase: str = "pre"
        self._prev_status: Dict[str, str] = {}
        self._prev_value: Dict[str, float] = {}
        self._seen_events = set()

        self._seed_city(default_city)

    # ----- lifecycle -------------------------------------------------- #

    def _seed_city(self, city_key: str) -> None:
        city = CITIES.get(city_key, CITIES[self.default_city])
        self.city_id = city["id"]
        self.schedule = [dict(p) for p in city["schedule"]]
        self.shuttles = dict(city["shuttleBaseline"])
        self.zones = []
        for spec in ZONE_SPECS[city["id"]]:
            hist = seed_history(spec["baseline"])
            z = dict(spec)
            z["value"] = hist[-1]["v"]
            z["forecast"] = spec["baseline"]
            z["history"] = hist
            z["speed"] = self._speed_for(city["speedUnit"], spec["baseline"], 0)
            z["flow"] = round(spec["baseline"] * 42)
            self.zones.append(z)
        self._prev_status = {z["id"]: "normal" for z in self.zones}
        self._prev_value = {z["id"]: z["value"] for z in self.zones}

    def reset(self) -> None:
        """Mirror of the dashboard's ↺ Reset: re-seed current city."""
        with self._lock:
            self._seed_city(self.city_id)
            self.clock = 0
            self.surge_active = False
            self.surge_step = 0
            self.overflow_active = False
            self.signal_extended = False
            self.last_phase = "pre"
            self._seen_events = set()
            self._emit_event(None, "SESSION", "info",
                             f"↺ Simulation reset — {self.city_name()} telemetry re-seeded to baseline.")

    def select_city(self, city_key: str) -> None:
        with self._lock:
            if city_key not in CITIES:
                city_key = self.default_city
            old = self.city_name()
            self._seed_city(city_key)
            self.overflow_active = False
            self.surge_active = False
            self.surge_step = 0
            self.last_phase = phase_at(self.schedule, 960 + self.clock)
            self._emit_event(None, "CITY_SWITCH", "info",
                             f"📍 Jurisdiction repositioned from {old} to {self.city_name()} ({CITIES[self.city_id]['venueName']}).")

    def city_name(self) -> str:
        return CITIES[self.city_id]["name"]

    # ----- helpers ---------------------------------------------------- #

    def _speed_for(self, speed_unit: str, load: float, rain: float) -> int:
        max_speed = 45.0 if speed_unit == "mph" else 65.0
        speed = max_speed * math.exp(-0.04 * (load / 10.0))
        if rain:
            speed *= 0.68
        return max(4, round(speed))

    def _advance_zone(self, z: dict, phase_id: str, scripted_step: Optional[int]) -> dict:
        noise = (random.random() - 0.5) * 3.5
        scripted = 0.0
        if scripted_step is not None and z["id"] in SURGE_SCRIPT:
            steps = SURGE_SCRIPT[z["id"]]
            if scripted_step < len(steps):
                scripted = steps[scripted_step]

        phase_force = PHASE_FORCES.get(phase_id, {}).get(z["id"], 0.0)
        overflow_effect = -4.5 if (self.overflow_active and z["id"] == "venue") else \
            (1.2 if (self.overflow_active and z["id"] in ("corridor", "transitHub")) else 0.0)

        shuttle_effect = 0.0
        if z["type"] == "transit":
            base = CITIES[self.city_id]["shuttleBaseline"].get(z["id"], 8)
            shuttle_effect = ((self.shuttles.get(z["id"]) or base) - base) * 1.4

        weather_effect = 4.5 if self.rain else 0.0
        emergency_effect = -6.0 if (self.emergency and z["type"] == "transit") else 0.0
        reversion = (z["baseline"] - z["value"]) * 0.08

        next_val = clamp(z["value"] + noise + scripted - shuttle_effect + weather_effect
                         + emergency_effect + phase_force + overflow_effect + reversion, 5, 98)
        history = [*z["history"], {"t": z["history"][-1]["t"] + 1, "v": next_val}][-14:]

        recent = history[-4:]
        slope = (recent[-1]["v"] - recent[0]["v"]) / (len(recent) - 1) if len(recent) >= 2 else 0.0
        forecast = clamp(next_val + slope * 3, 0, 100)

        speed = self._speed_for(CITIES[self.city_id]["speedUnit"], next_val, self.rain)
        if self.emergency:
            max_speed = 45.0 if CITIES[self.city_id]["speedUnit"] == "mph" else 65.0
            speed = max(speed, round(max_speed * 0.75))

        return {**z, "value": next_val, "history": history, "forecast": forecast,
                "speed": speed, "flow": round(next_val * speed * 0.9)}

    def _emit_event(self, zone_id: Optional[str], etype: str, level: str, message: str,
                    one_shot: bool = False) -> None:
        """Queue a row for active_alerts (persisted by the caller)."""
        key = f"{zone_id or 'system'}:{etype}"
        if one_shot and key in self._seen_events:
            return
        if one_shot:
            self._seen_events.add(key)
        if not hasattr(self, "_pending_alerts"):
            self._pending_alerts = []
        z = next((x for x in self.zones if x["id"] == zone_id), None)
        self._pending_alerts.append({
            "zone_id": zone_id,
            "city_id": self.city_id,
            "resource_type": z["type"] if z else None,
            "level": level,
            "type": etype,
            "message": message,
            "sim_time_min": 960 + self.clock,
        })

    # ----- alert + decision generation -------------------------------- #

    def _compute_alerts(self) -> List[dict]:
        alerts: List[dict] = []
        for z in self.zones:
            status = status_of(z["value"])
            prev = self._prev_status.get(z["id"], "normal")

            if status != prev:
                self._prev_status[z["id"]] = status
                if status == "critical":
                    if z["type"] == "venue":
                        vs = venue_state(z)
                        if vs["state"] == "atCapacity":
                            alerts.append(self._alert_row(
                                z, "VENUE_AT_CAPACITY", "critical",
                                f"🚧 {z['name']} is AT CAPACITY — entry paused (~{vs['wait']} min wait). Activate overflow control or hold the queue."))
                        else:
                            alerts.append(self._alert_row(
                                z, "VENUE_NEAR_CAPACITY", "critical",
                                f"{z['name']} is near capacity ({z['value']:.0f}% full) — admission should be throttled now."))
                    else:
                        alerts.append(self._alert_row(
                            z, "ZONE_CRITICAL", "critical",
                            f"{z['name']} is {z['value']:.0f}% full — very crowded right now."))
                elif status == "warning":
                    alerts.append(self._alert_row(
                        z, "ZONE_WARNING", "warning",
                        f"{z['name']} is getting busy ({z['value']:.0f}% full). Traffic there has slowed to {z['speed']} {CITIES[self.city_id]['speedUnit']}."))
                elif prev in ("critical", "warning"):
                    alerts.append(self._alert_row(
                        z, "ZONE_RECOVERED", "info",
                        f"{z['name']} has eased back to normal ({z['value']:.0f}% full)."))

            # Venue AT-CAPACITY crossing (distinct machine, re-fires each crossing)
            if z["type"] == "venue" and z["value"] >= 96 and self._prev_value.get(z["id"], 0) < 96:
                vs = venue_state(z)
                alerts.append(self._alert_row(
                    z, "VENUE_AT_CAPACITY", "critical",
                    f"🚧 {z['name']} crossed AT CAPACITY — entry paused (~{vs['wait']} min wait). Overflow / hold-queue recommended."))

            # Last-mile failure mode: station → gate shuttle queue full
            if z["type"] == "transit" and z["value"] >= 85 and self._prev_value.get(z["id"], 0) < 85:
                alerts.append(self._alert_row(
                    z, "LAST_MILE_QUEUE_FULL", "warning",
                    f"🚏 Last-mile shuttle queue full at {z['name']} — boarding delays ~{round((z['value'] - 80) * 1.4)} min for the final leg to the venue."))

            self._prev_value[z["id"]] = z["value"]
        return alerts

    def _alert_row(self, z: dict, etype: str, level: str, message: str) -> dict:
        return {"zone_id": z["id"], "city_id": self.city_id, "resource_type": z["type"],
                "level": level, "type": etype, "message": message, "sim_time_min": 960 + self.clock}

    def _decide(self, z: dict) -> dict:
        """Per-zone decision derived from the state machine (honest, rule-based)."""
        if z["type"] == "venue":
            vs = venue_state(z)
            if vs["state"] == "atCapacity":
                return {"action": "hold_queue", "reason": f"AT CAPACITY ({z['value']:.0f}%) — hold entry queue / activate overflow"}
            if vs["state"] == "critical":
                return {"action": "throttle", "reason": f"NEAR CAPACITY ({z['value']:.0f}%) — throttle admission now"}
        if z["type"] == "transit" and z["value"] >= 85:
            return {"action": "divert", "reason": f"LAST-MILE queue full ({z['value']:.0f}%) — divert to alternate entrance / hold boarding"}
        if z["value"] >= 82:
            return {"action": "relief", "reason": f"CRITICAL load ({z['value']:.0f}%) — route relief capacity in"}
        if z["value"] >= 68:
            return {"action": "reroute", "reason": f"WARNING load ({z['value']:.0f}%) — pre-emptive reroute of inflow"}
        return {"action": "monitor", "reason": f"STEADY ({z['value']:.0f}%) — standard monitoring"}

    def _balance_score(self) -> float:
        """Rule-based system balance: penalizes zone variance and distance from
        the comfortable operating point (55%), plus active-alert load."""
        loads = [z["value"] for z in self.zones]
        if not loads:
            return 100.0
        mean = sum(loads) / len(loads)
        variance = sum((v - mean) ** 2 for v in loads) / len(loads)
        active_alerts = sum(1 for z in self.zones if status_of(z["value"]) in ("warning", "critical"))
        score = 100.0 - variance * 2.5 - abs(mean - 55.0) * 0.5 - active_alerts * 2.0
        return round(clamp(score, 0, 100), 1)

    def _persist(self) -> None:
        """Write this tick's decisions + transition alerts to SQLite."""
        if self.storage is None:
            self._pending_alerts = []
            return
        rows = []
        for z in self.zones:
            d = self._decide(z)
            rows.append({
                "zone_id": z["id"], "city_id": self.city_id,
                "resource_type": z["type"], "load_value": z["value"],
                "sim_time_min": 960 + self.clock, "action": d["action"], "reason": d["reason"],
            })
        mean = round(sum(z["value"] for z in self.zones) / max(1, len(self.zones)), 1)
        rows.append({
            "zone_id": "__system__", "city_id": self.city_id, "resource_type": "system",
            "load_value": mean, "sim_time_min": 960 + self.clock, "action": "balance",
            "reason": f"system balance score={self._balance_score()}; mean_load={mean}; "
                      f"alerts_active={sum(1 for z in self.zones if status_of(z['value']) in ('warning', 'critical'))}",
        })
        try:
            self.storage.save_zone_decisions(rows)
            alerts = getattr(self, "_pending_alerts", [])
            if alerts:
                self.storage.save_zone_alerts(alerts)
        except Exception as exc:  # producer must never take the app down
            print("ZoneState persist failure:", exc)
        self._pending_alerts = []

    # ----- public API -------------------------------------------------- #

    def tick(self) -> dict:
        """One physics step (+5 sim minutes). Returns the full snapshot."""
        with self._lock:
            if self.paused:
                return self.snapshot()
            self.clock += 5
            ph = phase_at(self.schedule, 960 + self.clock)

            # Schedule-milestone alerts (cascading effect of schedule shifts)
            if ph != self.last_phase:
                if ph == "doors":
                    self._emit_event(None, "PHASE_DOORS", "info",
                                     f"🚪 Doors open at {CITIES[self.city_id]['venueName']} — arrival pressure building on transit and gates.")
                elif ph == "exit":
                    self._emit_event(None, "PHASE_EXIT", "warning",
                                     f"🚪 {CITIES[self.city_id]['venueName']} exit phase has started — egress pressure is building on transit and the corridor.")
                elif ph == "ended":
                    self._emit_event(None, "PHASE_ENDED", "info",
                                     f"🏁 {CITIES[self.city_id]['venueName']} event window has closed — crowd pressure is dispersing.")
                self.last_phase = ph

            scripted = self.surge_step if self.surge_active else None
            self.zones = [self._advance_zone(z, ph, scripted) for z in self.zones]
            if self.surge_active:
                self.surge_step += 1
                if self.surge_step >= 6:
                    self.surge_active = False
                    self.surge_step = 0

            self._pending_alerts = []
            self._pending_alerts.extend(self._compute_alerts())
            self._persist()
            self.ticks += 1
            return self.snapshot()

    def apply_action(self, action: str, payload: Optional[dict] = None) -> Optional[dict]:
        """Organizer / attendee-facing control. Returns the snapshot, or None
        for an unknown action."""
        payload = payload or {}
        with self._lock:
            if action == "select_city":
                self.select_city(payload.get("city") or self.default_city)
            elif action == "reset":
                self.reset()
            elif action == "skip":
                self.clock += 30
                ph = phase_at(self.schedule, 960 + self.clock)
                self.zones = [self._advance_zone(z, ph, None) for z in self.zones]
                self._pending_alerts = []
                self._pending_alerts.extend(self._compute_alerts())
                self._persist()
                self.ticks += 1
            elif action == "shift_schedule":
                self._shift_schedule(payload.get("kind", "delay"))
            elif action == "toggle_overflow":
                self.overflow_active = not self.overflow_active
                self._emit_event(None, "OVERFLOW_" + ("ACTIVE" if self.overflow_active else "RELEASED"),
                                 "warning" if self.overflow_active else "info",
                                 ("🛡️ Overflow control active — arrivals held in queue, venue pressure easing."
                                  if self.overflow_active else "🛡️ Overflow control released — normal admission resumed."))
                self._flush_alerts()
            elif action == "shock":
                self._shock(payload.get("kind", "letout"))
            elif action == "toggle_rain":
                self.rain = not self.rain
                self._emit_event(None, "WEATHER_" + ("RAIN" if self.rain else "CLEAR"), "info",
                                 ("🌧️ Heavy rain — traffic is moving about 30% slower."
                                  if self.rain else "☀️ Weather is clear — everything moving normally."))
                self._flush_alerts()
            elif action == "toggle_emergency":
                self.emergency = not self.emergency
                self._emit_event(None, "EMERGENCY_" + ("ENGAGED" if self.emergency else "RELEASED"), "info",
                                 ("🚑 Priority ambulance corridor engaged — traffic lights cleared for it."
                                  if self.emergency else "🚑 Ambulance corridor released."))
                self._flush_alerts()
            elif action == "adjust_shuttle":
                zid = payload.get("zone")
                if zid:
                    base = CITIES[self.city_id]["shuttleBaseline"].get(zid, 8)
                    self.shuttles[zid] = clamp((self.shuttles.get(zid) or base) + int(payload.get("delta", 0)), 0, 32)
            elif action == "shift_shuttles":
                self._shift_shuttles()
            elif action == "hotel_redirect":
                self._hotel_redirect()
            elif action == "signal_extension":
                self.signal_extended = True
                for z in self.zones:
                    if z["id"] == "venue":
                        z["value"] = clamp(z["value"] - 9, 10, 95)
                self._emit_event(None, "SIGNAL_EXTENDED", "info",
                                 "🚦 Exit lights kept green longer — the crowd is leaving faster.")
                self._flush_alerts()
            elif action == "set_running":
                self.paused = not bool(payload.get("running", True))
            elif action == "set_speed":
                mult = int(payload.get("speed", 1)) or 1
                self.tick_interval = round(3.2 / mult, 2)
            else:
                return None
            return self.snapshot()

    def _shift_schedule(self, kind: str) -> None:
        if kind == "delay":
            for p in self.schedule:
                p["start"] += 30
                p["end"] += 30
            self._emit_event(None, "SCHEDULE_DELAY", "warning",
                             f"⏰ {CITIES[self.city_id]['venueName']} doors delayed 30 min — arrival pressure shifts later. Forecasts recomputed.")
        elif kind == "extend":
            main = next((p for p in self.schedule if p["id"] == "main"), None)
            if main:
                main["end"] += 45
            exit_p = next((p for p in self.schedule if p["id"] == "exit"), None)
            if exit_p and main and exit_p["end"] < main["end"] + 60:
                exit_p["end"] = main["end"] + 60
            self._emit_event(None, "SCHEDULE_EXTEND", "warning",
                             "⏰ Main event extended 45 min — the exit surge is pushed later and softened.")
        elif kind == "endearly":
            self.surge_active = True
            self.surge_step = 0
            now = 960 + self.clock
            for p in self.schedule:
                if p["start"] > now:
                    p["start"] = now
                if p["end"] > now:
                    p["end"] = now
            self._emit_event(None, "SCHEDULE_END_EARLY", "warning",
                             f"🏁 {CITIES[self.city_id]['venueName']} ended early — the full egress surge is happening NOW.")
        self._flush_alerts()

    def _shock(self, kind: str) -> None:
        bumps = SHOCK_BUMPS.get(kind, SHOCK_BUMPS["letout"])
        for z in self.zones:
            if z["id"] in bumps:
                z["value"] = clamp(z["value"] + bumps[z["id"]], 5, 98)
        msgs = {
            "letout": "🎤 The concert just ended — 25,000 people are heading for transit and hotels.",
            "metro": "🚇 Metro disruption — trains are running at half capacity and the station is filling up.",
            "checkin": "🏨 Big check-in rush — hotel districts are filling up fast.",
        }
        self._emit_event(None, "SURGE_" + kind.upper(), "warning", msgs.get(kind, ""))
        self._flush_alerts()

    def _shift_shuttles(self) -> None:
        stressed, relief = self._transit_gap()
        if not stressed or not relief:
            return
        base_st = CITIES[self.city_id]["shuttleBaseline"].get(stressed["id"], 8)
        base_re = CITIES[self.city_id]["shuttleBaseline"].get(relief["id"], 8)
        self.shuttles[stressed["id"]] = clamp((self.shuttles.get(stressed["id"]) or base_st) + 4, 0, 32)
        self.shuttles[relief["id"]] = clamp((self.shuttles.get(relief["id"]) or base_re) - 4, 0, 32)
        self._emit_event(None, "SHUTTLE_SHIFT", "info",
                         f"🚌 Sent 4 extra shuttles to {stressed['name']} (relief from {relief['name']}).")
        self._flush_alerts()

    def _hotel_redirect(self) -> None:
        hotels = [z for z in self.zones if z["type"] == "hotel"]
        if len(hotels) < 2:
            return
        stressed = max(hotels, key=lambda z: z["value"])
        relief = min(hotels, key=lambda z: z["value"])
        for z in self.zones:
            if z["id"] == stressed["id"]:
                z["baseline"] = clamp(z["baseline"] - 7, 20, 95)
            elif z["id"] == relief["id"]:
                z["baseline"] = clamp(z["baseline"] + 7, 20, 95)
        self._emit_event(None, "HOTEL_REDIRECT", "info",
                         f"🏨 New guests are being directed to {relief['name']} instead of {stressed['name']}.")
        self._flush_alerts()

    def _transit_gap(self) -> tuple:
        transits = [z for z in self.zones if z["type"] == "transit"]
        if len(transits) < 2:
            return None, None
        return max(transits, key=lambda z: z["value"]), min(transits, key=lambda z: z["value"])

    def _flush_alerts(self) -> None:
        """Persist any queued event alerts immediately (actions don't wait for the next tick)."""
        if self.storage is not None and getattr(self, "_pending_alerts", []):
            try:
                self.storage.save_zone_alerts(self._pending_alerts)
            except Exception as exc:
                print("ZoneState alert persist failure:", exc)
        self._pending_alerts = []

    # ----- snapshot ---------------------------------------------------- #

    def snapshot(self, city: Optional[str] = None) -> dict:
        """Full state payload — the frontend hydrates from this shape."""
        with self._lock:
            if city and city in CITIES and city != self.city_id:
                # Read-only view of another city (defaults to current city state otherwise)
                saved = (self.city_id, self.zones, self.schedule, self.shuttles, self.clock,
                         self.overflow_active, self.rain, self.emergency)
                self._seed_city(city)
                out = self._snapshot_locked()
                (self.city_id, self.zones, self.schedule, self.shuttles, self.clock,
                 self.overflow_active, self.rain, self.emergency) = saved
                return out
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict:
        city = CITIES[self.city_id]
        ph = phase_at(self.schedule, 960 + self.clock)
        phase_label = {"pre": "Pre-Event", "ended": "Event Over"}.get(ph)
        if phase_label is None:
            phase_label = next((p["label"] for p in self.schedule if p["id"] == ph), ph)
        return {
            "cityId": self.city_id,
            "cityName": city["name"],
            "flag": city["flag"],
            "venueName": city["venueName"],
            "eventName": city["eventName"],
            "speedUnit": city["speedUnit"],
            "clock": self.clock,
            "simTime": fmt_min(960 + self.clock),
            "phase": ph,
            "phaseLabel": phase_label,
            "overflowActive": self.overflow_active,
            "rain": self.rain,
            "emergency": self.emergency,
            "signalExtended": self.signal_extended,
            "shuttles": dict(self.shuttles),
            "schedule": [dict(p) for p in self.schedule],
            "zones": [
                {
                    "id": z["id"], "name": z["name"], "type": z["type"],
                    "baseline": z["baseline"], "capacityLabel": z.get("capacityLabel"),
                    "unit": z.get("unit"), "x": z["x"], "y": z["y"],
                    "value": round(z["value"], 1), "forecast": round(z["forecast"], 1),
                    "speed": z["speed"], "flow": z["flow"],
                    "history": [dict(h) for h in z["history"]],
                }
                for z in self.zones
            ],
            "balanceScore": self._balance_score(),
            "producer": {
                "ticking": not self.paused,
                "paused": self.paused,
                "ticks": self.ticks,
                "tickEverySec": self.tick_interval,
            },
            "db": self.storage.counts() if self.storage is not None else {"decisions": 0, "alerts": 0},
        }


# Module-level convenience for importers
def default_engine(storage=None) -> ZoneStateEngine:
    return ZoneStateEngine(storage=storage)