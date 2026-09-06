import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from traffic_ai.pipeline import TrafficDecisionEngine
from traffic_ai.providers import MockEventProvider
from traffic_ai.storage import SQLiteStorage
from traffic_ai.controller import SignalController
from traffic_ai.schemas import IntersectionSnapshot

import asyncio
import os
import time
from contextlib import asynccontextmanager

import osmnx as ox
import networkx as nx

BASELINE_TRAFFIC = {
    "Silk Board":     {"location": "Silk Board", "density": 0.9, "timestamp": 0, "congestion_score": 9},
    "Hebbal":         {"location": "Hebbal", "density": 0.8, "timestamp": 0, "congestion_score": 8},
    "Whitefield":     {"location": "Whitefield", "density": 0.85, "timestamp": 0, "congestion_score": 8.5},
    "Marathahalli":   {"location": "Marathahalli", "density": 0.75, "timestamp": 0, "congestion_score": 7.5},
    "Electronic City":{"location": "Electronic City", "density": 0.7, "timestamp": 0, "congestion_score": 7},
    "Koramangala":    {"location": "Koramangala", "density": 0.65, "timestamp": 0, "congestion_score": 6.5},
    "Indiranagar":    {"location": "Indiranagar", "density": 0.6, "timestamp": 0, "congestion_score": 6},
    "MG Road":        {"location": "MG Road", "density": 0.55, "timestamp": 0, "congestion_score": 5.5},
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed baseline on startup — timestamp=0 means TTL never expires
    for location, data in BASELINE_TRAFFIC.items():
        active_hotspots[location] = data
        
    asyncio.create_task(fetch_predicthq_events())

    # NOTE: Starlette 1.x removed the legacy @app.on_event("startup") hook, so
    # background threads must be started from the lifespan context manager.
    threading.Thread(target=background_multi_vision_loop, daemon=True).start()
    threading.Thread(target=zone_state_producer_loop, daemon=True).start()
    print(f"ZoneState producer started (tick every {ZONE_TICK_SECS}s)...")
    yield

# MLOps: Initialize the FastAPI Application
app = FastAPI(
    title="NammaFlow AI API",
    description="Intelligent Traffic & Crowd Management Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Enable Cross-Origin Resource Sharing (CORS) for React Frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

try:
    if os.path.exists(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
except Exception as e:
    pass

@app.get("/")
def serve_dashboard():
    """Serves the stunning premium frontend dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/concourse")
def serve_concourse():
    """Serves the Concourse Global Mega-Event Capacity & Crowd Grid."""
    concourse_path = os.path.join(STATIC_DIR, "concourse.html")
    if not os.path.exists(concourse_path):
        concourse_path = "concourse.html"
    with open(concourse_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

from traffic_ai.events import CityEventTracker
from traffic_ai.rl_agent import DeepRLRewardEngine, GlobalTrafficState
from traffic_ai.pipeline import SnapshotProvider
from traffic_ai.multi_vision import MultiCameraIngestor
from traffic_ai.zone_state import ZoneStateEngine
import threading
import time

# Incorporate Phase 2 Directed Graph Engine
from traffic_ai.graph_engine import CityGraphPhysics

# Initialize core variables
logger = SQLiteStorage(db_path="traffic_data.sqlite")
event_tracker = CityEventTracker()
mock_provider = MockEventProvider(seed=42, event_tracker=event_tracker)
rl_engine = DeepRLRewardEngine()

# Concourse zone grid — the backend owns this state and is the real producer
# for decision_logs / active_alerts. The dashboard hydrates from it when reachable.
zone_engine = ZoneStateEngine(storage=logger)
ZONE_TICK_SECS = float(os.environ.get("ZONE_TICK_SECS", "3.0"))


def zone_state_producer_loop():
    """Background producer: advances the owned zone state and persists every
    tick's decisions + transition alerts to traffic_data.sqlite."""
    while True:
        try:
            zone_engine.tick()
        except Exception as e:
            print("ZoneState Producer Failure:", e)
        time.sleep(zone_engine.tick_interval)

city_graph = CityGraphPhysics()

# Asynchronous Vision Shared State using Phase 1.5 Physics
GLOBAL_MULTI_STATE = {}
multi_vision_adapter = MultiCameraIngestor()

def background_multi_vision_loop():
    """Continuously processes all junctions fusing vision and explicit graph propagation."""
    while True:
        try:
            # 1. Base Ingestion
            base_state = multi_vision_adapter.build_state()
            
            # 2. Inject Arrivals (Delayed Graph Simulation)
            arrivals = city_graph.process_arrivals()
            for junction, incoming in arrivals.items():
                if junction in base_state and incoming > 0:
                    base_state[junction]["vehicles"] += int(incoming)
            
            # 3. Recompute Math (Mandatory dependency calculation)
            for j, data in base_state.items():
                v = data["vehicles"]
                data["speed"] = multi_vision_adapter.estimate_speed(v)
                data["density"] = multi_vision_adapter.compute_density(v)
                data["flow"] = multi_vision_adapter.compute_flow(v, data["speed"])
                
            # 4. Save to Memory Matrix
            for junction_id, data in base_state.items():
                GLOBAL_MULTI_STATE[junction_id] = data
                
        except Exception as e:
            print("Multi-Vision Async Failure:", e)
        time.sleep(0.5)



class PhaseOneProvider(SnapshotProvider):
    """Zero-Latency bridge extracting deterministic YOLO physics from the background state."""
    def get_snapshot(self, intersection_id: str) -> IntersectionSnapshot:
        base_sim = mock_provider.get_snapshot(intersection_id)
        
        # Pull live YOLO data mapped to exact deterministic files
        # We map frontend 'mg_road' target to 'silk_board' logic to maintain compatibility
        vision_target = "silk_board" if intersection_id == "mg_road" else intersection_id
        
        if vision_target in GLOBAL_MULTI_STATE:
            live_data = GLOBAL_MULTI_STATE[vision_target]
            
            return IntersectionSnapshot(
                vehicle_count=live_data["vehicles"],
                crowd_density=live_data["density"],
                emergency_vehicle_present=base_sim.emergency_vehicle_present,
                event_risk_level=base_sim.event_risk_level,
                weather=base_sim.weather
            )
        # Fault Tolerance ensures presentation doesn't crash during deployment anomalies
        return base_sim

hybrid_provider = PhaseOneProvider()
engine = TrafficDecisionEngine(provider=hybrid_provider, logger=logger)
controller = SignalController()

class SnapshotPayload(BaseModel):
    vehicle_count: int
    crowd_density: float
    emergency_vehicle_present: bool = False

@app.get("/traffic_state")
def get_traffic():
    """PHASE 1.5 - UNIFIED STATE OUTPUT (SANITY CHECK)"""
    return GLOBAL_MULTI_STATE

@app.get("/predictions")
def get_predictions():
    """PHASE 3: PREDICTIVE LAYER exposing mathematical ETAs for the Visual Orchestrator."""
    preds = []
    current_time = time.time()
    for source, dest, v_count, impact in city_graph.peek_waves():
        eta = max(0, impact - current_time)
        preds.append({
            "target": dest,
            "eta_sec": round(eta, 1),
            "magnitude": round(v_count, 1)
        })
    preds.sort(key=lambda x: x["eta_sec"])
    return {"predictions": preds}

@app.get("/health")
def health_check():
    """MLOps standard health check endpoint."""
    return {"status": "healthy", "model_version": "v1-hybrid-cv"}

@app.post("/predict")
def predict_signal(payload: SnapshotPayload):
    snapshot = IntersectionSnapshot(
        vehicle_count=payload.vehicle_count,
        crowd_density=payload.crowd_density,
        emergency_vehicle_present=payload.emergency_vehicle_present
    )
    plan = controller.recommend(snapshot)
    return {
        "inference": {
            "green_seconds": plan.green_seconds,
            "red_seconds": plan.red_seconds,
            "reason": plan.reason
        }
    }

@app.get("/intersection/{intersection_id}/live")
def get_live_decision(intersection_id: str, weather: str = "clear"):
    # MLOps context injection
    mock_provider.weather_mode = weather
    
    decision = engine.run_once(intersection_id)
    
    # === GRAPH DISPATCH PROTOCOL (PHASE 2)
    vision_target = "silk_board" if intersection_id == "mg_road" else intersection_id
    if vision_target in GLOBAL_MULTI_STATE:
        data = GLOBAL_MULTI_STATE[vision_target]
        # Only dispatch if signal favors traffic clearing and density warrants flow
        # Bounding Outflow to Inflow Conservation
        if decision.plan.green_seconds >= 30 and data["density"] > 0.1:
            # 🚨 HARD CONSTRAINT (SAFETY INTERLOCK MATRIX)
            downstream_node = "madiwala" if vision_target == "silk_board" else "koramangala"
            if downstream_node in GLOBAL_MULTI_STATE and GLOBAL_MULTI_STATE[downstream_node]["density"] > 0.9:
                pass # RL Override: Block Dispatch to prevent terminal gridlock spiral
            else:
                throughput_released = int(max(1, min(data["vehicles"], data["flow"] * 0.05)))
                city_graph.dispatch_wave(
                    source=vision_target,
                    throughput=throughput_released,
                    current_speed_kmh=data["speed"]
                )
    
    # === GLOBAL REINFORCEMENT LEARNING BRIDGE (PHASE 3) ===
    try:
        densities = [
            GLOBAL_MULTI_STATE["silk_board"]["density"],
            GLOBAL_MULTI_STATE["madiwala"]["density"],
            GLOBAL_MULTI_STATE["koramangala"]["density"]
        ]
        flows = [
            GLOBAL_MULTI_STATE["silk_board"]["flow"],
            GLOBAL_MULTI_STATE["madiwala"]["flow"],
            GLOBAL_MULTI_STATE["koramangala"]["flow"]
        ]
    except KeyError:
        # Failsafe if graph buffers are still initializing
        densities, flows = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]

    rl_state = GlobalTrafficState(densities=densities, flows=flows)
    marl_reward = rl_engine.calculate_reward(rl_state)
    
    return {
        "intersection": intersection_id,
        "features": {
            "vehicles": decision.snapshot.vehicle_count,
            "crowd_density": decision.snapshot.crowd_density,
            "emergency": decision.snapshot.emergency_vehicle_present,
            "event_risk": decision.snapshot.event_risk_level
        },
        "decision": {
            "green": decision.plan.green_seconds,
            "red": decision.plan.red_seconds,
            "reason": decision.plan.reason,
            "weather": decision.snapshot.weather,
            "rl_reward_score": marl_reward
        }
    }

@app.get("/alerts")
def get_recent_alerts():
    """Retrieve recent alerts for MLOps dashboarding."""
    try:
        import sqlite3
        with sqlite3.connect("traffic_data.sqlite") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM active_alerts ORDER BY timestamp DESC LIMIT 10").fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database not ready or corrupted.")

# ==================== N8N INTEGRATION LAYER ====================
import time

# This persistent dictionary catches dynamic updates from your automated workflows
active_hotspots = {}

def get_active_density(node_id: str) -> float:
    """Returns stored density only if written < 300 seconds ago, else 0.0."""
    entry = active_hotspots.get(node_id)
    if not entry:
        return 0.0
    
    if entry.get("timestamp", -1) == 0:  # permanent baseline, never expires
        return entry.get("density", 0.0)
        
    timestamp = entry.get("timestamp", 0)
    if (time.time() - timestamp) < 300:
        score = entry.get("congestion_score", 0)
        return entry.get("density", min(1.0, float(score) / 10.0))
        
    return 0.0

from fastapi import Request
from typing import Optional

CURRENT_WEATHER = "clear"
CURRENT_EVENT = "none"
active_incidents = []
live_event_cards = []

class WeatherUpdate(BaseModel):
    condition: str

@app.post("/weather")
def update_weather(payload: WeatherUpdate):
    global CURRENT_WEATHER
    CURRENT_WEATHER = payload.condition.lower()
    return {"status": "ok", "weather": CURRENT_WEATHER}

class LiveEventUpdate(BaseModel):
    event_type: str

@app.post("/events/live")
def set_live_event(payload: LiveEventUpdate):
    global CURRENT_EVENT
    CURRENT_EVENT = payload.event_type.lower()
    return {"status": "ok", "active_event": CURRENT_EVENT}

class Incident(BaseModel):
    id: str
    lat: float
    lon: float
    description: str
    severity: str

@app.post("/incidents")
def receive_incidents(payload: list[Incident]):
    global active_incidents
    active_incidents = [i.model_dump() if hasattr(i, 'model_dump') else i.dict() for i in payload]
    return {"status": "ok", "count": len(active_incidents)}

@app.get("/incidents")
def get_incidents():
    return active_incidents

class TrafficEvent(BaseModel):
    location: str
    density: Optional[float] = None
    congestion_score: Optional[int] = None
    congestion_level: Optional[str] = None
    prediction: Optional[str] = None
    event: Optional[str] = None
    timestamp: Optional[float] = None

@app.post("/traffic")
def ingest_traffic(events: list[TrafficEvent]):
    updated = []
    for e in events:
        # Derive density from congestion_score if not provided
        density = e.density
        if density is None and e.congestion_score is not None:
            density = round(min(1.0, e.congestion_score / 10), 2)
        if density is None:
            density = 0.5  # hard fallback

        import time
        active_hotspots[e.location] = {
            "location": e.location,
            "density": density,
            "timestamp": e.timestamp or time.time(),
            "congestion_score": e.congestion_score or round(density * 10),
            "congestion_level": e.congestion_level or "unknown",
            "prediction": e.prediction or "",
            "event": e.event or "none"
        }
        updated.append(e.location)
    return {"updated": updated, "count": len(updated)}

@app.get("/traffic")
def get_n8n_data():
    current_state = {loc: get_active_density(loc) for loc in active_hotspots}
    
    # 1. Overlay base temporal physics (Rush Hour, IPL Events)
    modified_state = apply_time_factors(current_state)
    
    # 2. Overlay universal environmental drag (Rain)
    global CURRENT_WEATHER
    if CURRENT_WEATHER == "rain":
        for k in modified_state:
            modified_state[k] = min(1.0, modified_state[k] * 1.4)
            
    res = []
    for loc, raw_data in active_hotspots.items():
        data = dict(raw_data)
        data["density"] = modified_state.get(loc, data.get("density", 0.0))
        data["congestion_score"] = min(10, round(data["density"] * 10))
        res.append(data)
    return res

import urllib.request
import json
import datetime

PREDICTHQ_TOKEN = "RRuNOWcrmdoyLwl6C4ritN8XLvnlbz_CqBL65jVZ"

async def fetch_predicthq_events():
    global live_event_cards
    while True:
        try:
            url = 'https://api.predicthq.com/v1/events/?within=50km@12.9716,77.5946&limit=25&sort=-rank&state=active'
            req = urllib.request.Request(url, headers={
                'Authorization': f'Bearer {PREDICTHQ_TOKEN}', 
                'Accept': 'application/json'
            })
            data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
            
            cards = []
            for e in data.get('results', []):
                lon, lat = e['location']
                color = "#ea580c" if e['category'] in ["expos", "festivals", "community", "observances"] else "#e11d48"
                subcat = "EVENT"
                if "labels" in e and len(e["labels"]) > 0:
                    subcat = e["labels"][0].upper()
                
                raw_time = e.get('start', '')
                try:
                    dt = datetime.datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                    nicetime = dt.strftime("%a, %d %b %Y %I:%M %p")
                except:
                    nicetime = raw_time

                address = e.get('description', '')
                if not address:
                    address = 'Bengaluru, India'
                address = address[:85] + ("..." if len(address) > 85 else "")

                cards.append({
                    "lat": lat,
                    "lon": lon,
                    "title": e['title'],
                    "address": address,
                    "time": nicetime,
                    "rank": e.get('rank', 50),
                    "local_rank": e.get('local_rank', e.get('rank', 50)),
                    "category": e.get('category', 'UNKNOWN').upper(),
                    "subcategory": subcat,
                    "color": color
                })
            live_event_cards = cards
        except Exception as ex:
            print("PredictHQ Fetch Error:", ex)
            
        await asyncio.sleep(3600)

@app.get("/events/cards")
def get_event_cards():
    return live_event_cards

G_routing = None

def _load_routing_graph():
    global G_routing
    print("[ROUTING] Spooling mathematical routing geometry into memory...")
    try:
        import osmnx as ox
        ox.settings.timeout = 30
        G_routing = ox.graph_from_place("Bangalore, India", network_type="drive", simplify=True)
        print("[ROUTING] Routing Vector Grid online!")
    except Exception as e:
        G_routing = None
        print(f"[ROUTING] Routing graph notice: {e}")

threading.Thread(target=_load_routing_graph, daemon=True).start()

forecast_cache = {}
forecast_cache_time = 0
FORECAST_CACHE_TTL = 120  # seconds

def get_cached_forecast() -> dict:
    global forecast_cache, forecast_cache_time
    now = time.time()
    if forecast_cache and (now - forecast_cache_time) < FORECAST_CACHE_TTL:
        return forecast_cache
    forecast_cache = {
        "t_plus_15": predict_future_state(15),
        "t_plus_30": predict_future_state(30),
        "t_plus_60": predict_future_state(60),
    }
    forecast_cache_time = now
    return forecast_cache

def compute_confidence(path: list, forecast: dict) -> dict:
    windows = ["t_plus_15", "t_plus_30", "t_plus_60"]

    # Get average density across path nodes for each time window
    window_densities = []
    for w in windows:
        w_data = forecast.get(w, {})
        densities = [w_data.get(str(n), 0.0) for n in path]
        window_densities.append(sum(densities) / max(len(densities), 1))

    # Variance across windows — high variance = unpredictable = low confidence
    mean = sum(window_densities) / 3
    variance = sum((d - mean) ** 2 for d in window_densities) / 3

    # Base confidence inversely proportional to peak density and variance
    peak_density = max(window_densities)
    confidence = max(0.0, 1.0 - peak_density * 0.6 - variance * 2.0)

    # Trend — is congestion getting better or worse over time?
    if window_densities[2] > window_densities[0] + 0.15:
        trend = "worsening"
    elif window_densities[2] < window_densities[0] - 0.15:
        trend = "clearing"
    else:
        trend = "stable"

    return {
        "score": round(confidence * 100),
        "trend": trend,
        "peak_density": round(peak_density, 2),
        "variance": round(variance, 3),
        "label": "High" if confidence > 0.7 else "Medium" if confidence > 0.4 else "Low"
    }

@app.post("/route")
async def get_route(request: Request):
    data = await request.json()
    source = data["source"]
    dest = data["destination"]

    if not G_routing:
        return {"route": []}

    source_node = ox.distance.nearest_nodes(G_routing, source["lon"], source["lat"])
    target_node = ox.distance.nearest_nodes(G_routing, dest["lon"], dest["lat"])

    # Load forecast cache (non-blocking, returns instantly if cache is warm)
    forecast = get_cached_forecast()

    # Estimate rough trip duration from straight-line distance
    # to pick which forecast window to use for weighting
    import math
    def haversine_minutes(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        dist_km = R * 2 * math.asin(math.sqrt(a))
        return (dist_km / 25) * 60  # assume 25 km/h avg speed in Bengaluru

    est_minutes = haversine_minutes(
        source["lat"], source["lon"],
        dest["lat"], dest["lon"]
    )

    # Pick the right forecast window
    if est_minutes <= 15:
        future_densities = forecast["t_plus_15"]
    elif est_minutes <= 30:
        future_densities = forecast["t_plus_30"]
    else:
        future_densities = forecast["t_plus_60"]

    for u, v, k, d in G_routing.edges(keys=True, data=True):
        node_key = str(v)
        density = future_densities.get(node_key, 0.0)
        d["weight"] = (1 + density * 5) * d.get("travel_time", d.get("length", 1))

    try:
        path = nx.shortest_path(G_routing, source_node, target_node, weight="weight")
    except Exception:
        path = []

    coords = []
    for node in path:
        coords.append([G_routing.nodes[node]['x'], G_routing.nodes[node]['y']])

    forecast = get_cached_forecast()
    confidence = compute_confidence(path, forecast)

    return {
        "route": coords,
        "distance_km": round((est_minutes / 60) * 25, 2),
        "duration_min": round(est_minutes, 2),
        "forecast_window": f"t_plus_{15 if est_minutes <= 15 else 30 if est_minutes <= 30 else 60}",
        "est_arrival_density": round(sum(future_densities.get(str(n), 0) for n in path) / max(1, len(path)), 2),
        "warning": "High congestion expected on this route" if sum(future_densities.get(str(n), 0) for n in path) / max(1, len(path)) > 0.6 else None,
        "confidence": confidence["score"],
        "confidence_label": confidence["label"],
        "trend": confidence["trend"],
        "recommendation": (
            "Leave now — conditions worsen in 30 min" if confidence["trend"] == "worsening"
            else "Route is clearing — good time to travel" if confidence["trend"] == "clearing"
            else "Conditions stable for your journey"
        )
    }

import datetime
from copy import deepcopy
from typing import Optional, Dict
from pydantic import BaseModel

class SimulateRequest(BaseModel):
    rain: Optional[bool] = False
    event: Optional[Dict] = None
    hour: Optional[int] = None

def apply_time_factors(hotspots: dict, hour: int = None) -> dict:
    if hour is None:
        hour = datetime.datetime.now().hour
    res = deepcopy(hotspots)
    if (8 <= hour <= 10) or (17 <= hour <= 20):
        for k in res:
            res[k] = min(1.0, res[k] * 2.5)
            
    global CURRENT_EVENT
    if CURRENT_EVENT == "ipl":
        # IPL Match from 7 PM to 11 PM creates heavy pre/post congestion (6 PM to midnight)
        if 18 <= hour <= 23:
            for loc in ["MG Road", "Indiranagar", "Koramangala", "Silk Board"]:
                if loc in res:
                    # Massive spike simulating stadium crowds backing up central arteries
                    res[loc] = min(1.0, res[loc] * 2.5 + 0.4)
                    
    return res

@app.post("/simulate")
def simulate_traffic_scenario(payload: SimulateRequest):
    # Lock base structural densities utilizing the robust TTL validation hook
    base_densities = {loc: get_active_density(loc) for loc in active_hotspots}
    
    # [1] Simulate Base Office Loading Time Factors
    sim_densities = apply_time_factors(base_densities, payload.hour)
    
    # [2] Simulate Rain Hazard Structural Drag
    if payload.rain:
        for k in sim_densities:
            sim_densities[k] = min(1.0, sim_densities[k] * 1.4)
            
    # [3] Simulate Anomalous Event Spikes
    if payload.event and "location" in payload.event and "intensity" in payload.event:
        loc = payload.event["location"]
        intensity = payload.event["intensity"]
        sim_densities[loc] = min(1.0, sim_densities.get(loc, 0.0) + intensity)

    # [4] Vector Congestion Spillback Cascade Simulator
    spread_updates = {}
    location_coords = {
        "Silk Board": (77.6220, 12.9177),
        "Whitefield": (77.7499, 12.9698),
        "Hebbal": (77.5970, 13.0358),
        "Electronic City": (77.6770, 12.8399),
        "Koramangala": (77.6245, 12.9352),
        "Indiranagar": (77.6412, 12.9719),
        "MG Road": (77.6050, 12.9756),
        "Marathahalli": (77.6974, 12.9591)
    }

    if G_routing:
        for loc, density in sim_densities.items():
            if density > 0.7 and loc in location_coords:
                lx, ly = location_coords[loc]
                try:
                    source_node = ox.distance.nearest_nodes(G_routing, lx, ly)
                    # Directly bleed 30% of congestion over topological neighbors via graph edge limits
                    for neighbor in G_routing.neighbors(source_node):
                        spread_amount = 0.3 * density
                        spread_updates[str(neighbor)] = min(1.0, sim_densities.get(str(neighbor), 0.0) + spread_amount)
                except Exception:
                    pass

    # Seamlessly overlay cascading matrix updates
    for k, v in spread_updates.items():
        sim_densities[k] = min(1.0, sim_densities.get(k, 0.0) + v)

    return {"simulated_hotspots": sim_densities}

def predict_future_state(minutes_ahead: int) -> dict:
    current = {loc: get_active_density(loc) for loc in active_hotspots}
    
    future_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes_ahead)
    future_hour = future_time.hour
    
    predicted = apply_time_factors(current, future_hour)
    
    iterations = minutes_ahead // 5
    
    location_coords = {
        "Silk Board": (77.6220, 12.9177),
        "Whitefield": (77.7499, 12.9698),
        "Hebbal": (77.5970, 13.0358),
        "Electronic City": (77.6770, 12.8399),
        "Koramangala": (77.6245, 12.9352),
        "Indiranagar": (77.6412, 12.9719),
        "MG Road": (77.6050, 12.9756),
        "Marathahalli": (77.6974, 12.9591)
    }
    
    if G_routing:
        for _ in range(iterations):
            spread_updates = {}
            for loc, density in list(predicted.items()):
                if density > 0.5 and loc in location_coords:
                    lx, ly = location_coords[loc]
                    try:
                        source_node = ox.distance.nearest_nodes(G_routing, lx, ly)
                        for neighbor in G_routing.neighbors(source_node):
                            neighbor_key = str(neighbor)
                            current_neighbor = predicted.get(neighbor_key, 0.0)
                            spread_updates[neighbor_key] = min(1.0, current_neighbor + 0.15 * density)
                    except Exception:
                        pass
            for k, v in spread_updates.items():
                predicted[k] = min(1.0, predicted.get(k, 0.0) + v)
            
    for k in list(predicted.keys()):
        if predicted[k] < 0.4:
            predicted[k] = max(0.0, predicted[k] - (0.05 * (minutes_ahead / 15.0)))
            
    global CURRENT_WEATHER
    if CURRENT_WEATHER == "rain":
        for k in predicted:
            predicted[k] = min(1.0, predicted[k] * 1.4)
            
    return predicted


class PredictRequest(BaseModel):
    minutes_ahead: Optional[int] = 30
    rain: Optional[bool] = False

@app.post("/forecast")
def predict_traffic(payload: PredictRequest):
    results = {}
    for t in [15, 30, 60]:
        state = predict_future_state(t)
        if payload.rain:
            state = {k: min(1.0, v * 1.4) for k, v in state.items()}
        results[f"t_plus_{t}"] = state
    return {
        "current": {loc: get_active_density(loc) for loc in active_hotspots.keys()},
        "predictions": results,
        "generated_at": datetime.datetime.now().isoformat()
    }

@app.post("/chat")
async def chat_interaction(request: Request):
    payload = await request.json()
    query = payload.get("message", "").lower()
    
    total_hotspots = len(active_hotspots)
    critical_zones = [k for k, v in active_hotspots.items() if v.get("congestion_score", 0) >= 8]
    
    response = "🤖 Live API Telemetry Link:\n"
    if "status" in query or "traffic" in query:
        response += f"Tracking {total_hotspots} live intersections."
        if critical_zones:
            response += f"\n🚨 CRITICAL DANGER: Avoid {', '.join(critical_zones)}!"
        else:
            response += "\n✅ Network relatively stable."
    elif "rain" in query or "weather" in query:
        response += "🌧️ Rain algorithms predicting high choke points at Silk Board."
    else:
        found = False
        for node, data in active_hotspots.items():
            if node.lower() in query:
                score = data.get("congestion_score", 0)
                response += f"📍 {node} LIVE Telemetry:\nStatus: {'CRITICAL' if score >= 8 else 'HIGH' if score >= 6 else 'MEDIUM' if score >= 4 else 'CLEAR'} ({score}/10)\nSpeed Impact: -{score*7}%\n"
                found = True
        
        if not found:
            response += "I am locally hooked to the FastAPI state graph. Ask me about specific zones like 'Whitefield' or 'Silk Board', or general 'status'!"

    return {"response": response}

import sqlite3

@app.get("/traffic/history")
def get_traffic_history():
    db_path = "traffic_data.sqlite"
    if not os.path.exists(db_path):
        db_path = "src/traffic_data.sqlite"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    strftime('%H', timestamp) as hr,
                    AVG(vehicle_count) as avg_vehicles,
                    AVG(crowd_density) as avg_density
                FROM decision_logs 
                WHERE timestamp IS NOT NULL
                GROUP BY hr
                ORDER BY hr ASC
                LIMIT 24
            ''')
            rows = cursor.fetchall()
            chart_data = []
            for row in rows:
                if not row[0]: continue
                hr_num = int(row[0])
                avg_veh = int(row[1]) if row[1] else 50
                avg_den = float(row[2]) if row[2] else 0.5
                period = "AM" if hr_num < 12 else "PM"
                disp_hr = hr_num if hr_num <= 12 else hr_num - 12
                if disp_hr == 0: disp_hr = 12
                chart_data.append({
                    "hour": f"{disp_hr}{period}",
                    "vehicles": avg_veh,
                    "speed": int(60 - (avg_den * 45))
                })
            return chart_data if chart_data else [{"hour": "12PM", "speed": 28, "vehicles": 45}]
    except Exception as e:
        return [{"hour": "12PM", "speed": 28, "vehicles": 45}]

@app.get("/optimization/suggest")
def get_optimization():
    return [
        {
            "id": 1,
            "title": "Increase Signal Green TTL at Silk Board",
            "description": "Traffic volume exceeds normal capacity by 45%.",
            "impact": "High", "action": "Extend by 25s", "status": "pending"
        },
        {
            "id": 2,
            "title": "Reroute Heavy Vehicles away from Hebbal",
            "description": "Flyover structural density is critically high.",
            "impact": "Critical", "action": "Divert Route", "status": "active"
        }
    ]

@app.get("/events/filtered")
def get_events_filtered():
    return {
        "live": [
            {
                "title": "GIDS 2026: Global Developer Summit",
                "lat": 12.9774, "lon": 77.7145,
                "category": "conferences", "rank": 90, "impact": 0.85,
                "status": "live"
            },
            {
                "title": "MAP Talk: Terracotta Making Art",
                "lat": 12.9723, "lon": 77.5951,
                "category": "arts", "rank": 55, "impact": 0.45,
                "status": "live"
            }
        ],
        "upcoming": [
            {
                "title": "BIC Talk: Sound Judgment in Uncertainty",
                "lat": 12.9649, "lon": 77.6321,
                "category": "community", "rank": 40, "impact": 0.3,
                "status": "upcoming", "starts_in_mins": 75
            },
            {
                "title": "Resonance: Veena & Bansuri Concert",
                "lat": 12.9649, "lon": 77.6321,
                "category": "concerts", "rank": 50, "impact": 0.4,
                "status": "upcoming", "starts_in_mins": 120
            }
        ],
        "total": 4
    }

class ChatReqPayload(BaseModel):
    message: str

@app.post("/assistant/chat")
def assistant_chat_bridge(req: ChatReqPayload):
    total = len(active_hotspots)
    return {
        "reply": f"NammaFlow AI Copilot: Monitoring {total} active junction nodes. Traffic is heaviest around Silk Board & MG Road. Recommendation: Maintain adaptive signal phase extension."
    }

from fastapi.staticfiles import StaticFiles
import os
from fastapi.middleware.cors import CORSMiddleware

# Enable CORS for NextJS proxy if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # NammaFlow AI Project Root
try:
    # Hosts the Physics WebGL maps dynamically at localhost:8000/engine/traffic_map_gl.html
    app.mount("/engine", StaticFiles(directory=static_path, html=True), name="static")
    
    # Expose the core structural workspace dynamically for Native Next.js payload parsing
    app.mount("/static", StaticFiles(directory="."), name="static2")
except Exception as e:
    print("Static map mount failed:", e)

# ==================== CONCOURSE ZONE-STATE API ====================
# The dashboard hydrates from /zone_state when it can reach this backend;
# the producer thread owns the state and writes traffic_data.sqlite.

class ZoneAction(BaseModel):
    action: str
    city: Optional[str] = None
    kind: Optional[str] = None
    zone: Optional[str] = None
    delta: Optional[int] = 0
    running: Optional[bool] = None
    speed: Optional[int] = None

@app.get("/zone_state")
def get_zone_state(city: Optional[str] = None):
    """Full owned zone-grid state (cities, zones, schedule, phase, toggles)."""
    return zone_engine.snapshot(city)

@app.post("/zone_state/action")
def zone_state_action(payload: ZoneAction):
    """Organizer / visitor controls that re-drive the owned physics.

    Actions: select_city, reset, skip, shift_schedule (delay|extend|endearly),
    toggle_overflow, shock (letout|metro|checkin), toggle_rain,
    toggle_emergency, adjust_shuttle, shift_shuttles, hotel_redirect,
    signal_extension, set_running, set_speed.
    """
    result = zone_engine.apply_action(payload.action, {
        "city": payload.city,
        "kind": payload.kind,
        "zone": payload.zone,
        "delta": payload.delta,
        "running": payload.running,
        "speed": payload.speed,
    })
    if result is None:
        raise HTTPException(status_code=400, detail=f"Unknown zone action '{payload.action}'")
    return result

@app.get("/zone_state/history")
def get_zone_history(limit: int = 20, city: Optional[str] = None):
    """Recent producer decision rows (zone snapshots + decisions)."""
    return zone_engine.storage.fetch_zone_decisions(limit=min(limit, 200), city=city)

@app.get("/zone_state/alerts")
def get_zone_alerts(limit: int = 20, city: Optional[str] = None):
    """Recent producer alert rows (venue capacity, last-mile, schedule shifts)."""
    return zone_engine.storage.fetch_zone_alerts(limit=min(limit, 200), city=city)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("traffic_ai.api:app", host="0.0.0.0", port=8000, reload=True)
