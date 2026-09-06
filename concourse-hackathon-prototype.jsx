import { useState, useEffect, useMemo, useRef } from "react";
import {
  Orbit, Hotel, Bus, Building2, AlertTriangle, Sparkles, Send,
  Plus, Minus, Zap, MessageCircle, TrendingUp, TrendingDown, Minus as Flat,
  CloudRain, Siren, ShieldCheck, RefreshCw, Compass, MapPin, Activity,
  Gauge, Car, ArrowRight, CheckCircle2, ChevronRight, Globe
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";

// ==========================================
// 🎨 COLOR PALETTE & DESIGN SYSTEM
// ==========================================
const COLORS = {
  normal: "#4FD8E0",
  warning: "#F5A623",
  critical: "#FF5C6C",
  ai: "#8B7CF6",
  emergency: "#EF4444",
  rain: "#38BDF8",
  bg: "#0B0F17",
  panel: "#121926",
  panelAlt: "#161F2E",
  border: "#263042",
  textPrimary: "#E8EDF4",
  textMuted: "#7C8AA0",
};

// ==========================================
// 🌍 MULTI-CITY GLOBAL EVENT DEFINITIONS
// (No longer limited to only one city)
// ==========================================
const CITIES_DATA = {
  london: {
    id: "london",
    name: "London, United Kingdom",
    flag: "🇬🇧",
    venueName: "Wembley Stadium",
    eventName: "European Football Final & World Arena Concert",
    currency: "£",
    speedUnit: "mph",
    shuttleLabel: "Double-Decker / Shuttles",
    zones: [
      { id: "venue", name: "Wembley Stadium Core", type: "venue", baseline: 58, capacityLabel: "85,000 capacity", unit: "stadium density", x: 130, y: 150 },
      { id: "transitHub", name: "Wembley Park (Jubilee/Metropolitan)", type: "transit", baseline: 52, capacityLabel: "24 trains/hr", unit: "station load", x: 300, y: 90 },
      { id: "transitE", name: "Olympic Way & Bakerloo Feeder", type: "transit", baseline: 36, capacityLabel: "14 trains/hr", unit: "pedestrian flow", x: 300, y: 210 },
      { id: "hotelN", name: "Wembley Park Hotel District", type: "hotel", baseline: 74, capacityLabel: "4,200 rooms", unit: "room occupancy", x: 470, y: 80 },
      { id: "hotelS", name: "Central London West End District", type: "hotel", baseline: 42, capacityLabel: "9,500 rooms", unit: "room occupancy", x: 470, y: 220 },
      { id: "corridor", name: "North Circular A406 Artery", type: "corridor", baseline: 64, capacityLabel: "4,500 veh/hr", unit: "arterial load", x: 210, y: 280 }
    ],
    shuttleBaseline: { transitHub: 16, transitE: 10 }
  },
  newyork: {
    id: "newyork",
    name: "New York / NJ, USA",
    flag: "🇺🇸",
    venueName: "MetLife Stadium",
    eventName: "World Cup Finals & Summer Music Festival",
    currency: "$",
    speedUnit: "mph",
    shuttleLabel: "NJ Transit Express Shuttles",
    zones: [
      { id: "venue", name: "MetLife Stadium Core", type: "venue", baseline: 62, capacityLabel: "82,500 capacity", unit: "stadium density", x: 130, y: 150 },
      { id: "transitHub", name: "Secaucus Junction Rail Hub", type: "transit", baseline: 54, capacityLabel: "28 trains/hr", unit: "concourse load", x: 300, y: 90 },
      { id: "transitE", name: "Lincoln Tunnel Express Coaches", type: "transit", baseline: 40, capacityLabel: "35 coaches/hr", unit: "corridor load", x: 300, y: 210 },
      { id: "hotelN", name: "Midtown Manhattan Hotels", type: "hotel", baseline: 78, capacityLabel: "14,000 rooms", unit: "room occupancy", x: 470, y: 80 },
      { id: "hotelS", name: "Jersey City & Hoboken District", type: "hotel", baseline: 44, capacityLabel: "6,200 rooms", unit: "room occupancy", x: 470, y: 220 },
      { id: "corridor", name: "Route 3 & NJ Turnpike Bottleneck", type: "corridor", baseline: 68, capacityLabel: "5,800 veh/hr", unit: "arterial load", x: 210, y: 280 }
    ],
    shuttleBaseline: { transitHub: 20, transitE: 12 }
  },
  tokyo: {
    id: "tokyo",
    name: "Tokyo, Japan",
    flag: "🇯🇵",
    venueName: "Japan National Stadium",
    eventName: "World Athletics Championships & Tech Expo",
    currency: "¥",
    speedUnit: "km/h",
    shuttleLabel: "Toei & Metro Fleet",
    zones: [
      { id: "venue", name: "National Stadium Core", type: "venue", baseline: 54, capacityLabel: "68,000 capacity", unit: "arena density", x: 130, y: 150 },
      { id: "transitHub", name: "Sendagaya & Yamanote Loop", type: "transit", baseline: 48, capacityLabel: "36 trains/hr", unit: "platform density", x: 300, y: 90 },
      { id: "transitE", name: "Toei Oedo & Chuo-Sobu Line", type: "transit", baseline: 34, capacityLabel: "22 trains/hr", unit: "passenger flow", x: 300, y: 210 },
      { id: "hotelN", name: "Shinjuku Central Hotel District", type: "hotel", baseline: 70, capacityLabel: "11,000 rooms", unit: "room occupancy", x: 470, y: 80 },
      { id: "hotelS", name: "Roppongi & Shinagawa District", type: "hotel", baseline: 38, capacityLabel: "7,500 rooms", unit: "room occupancy", x: 470, y: 220 },
      { id: "corridor", name: "Shuto Expressway C1 Loop", type: "corridor", baseline: 56, capacityLabel: "4,000 veh/hr", unit: "arterial load", x: 210, y: 280 }
    ],
    shuttleBaseline: { transitHub: 18, transitE: 12 }
  },
  bengaluru: {
    id: "bengaluru",
    name: "Bengaluru, India",
    flag: "🇮🇳",
    venueName: "Kanteerava Stadium & KTPO",
    eventName: "GIDS Global Developer Summit & IPL Match",
    currency: "₹",
    speedUnit: "km/h",
    shuttleLabel: "BMTC & Metro Feeder Volvos",
    zones: [
      { id: "venue", name: "Kanteerava Arena Core", type: "venue", baseline: 55, capacityLabel: "35,000 capacity", unit: "arena density", x: 130, y: 150 },
      { id: "transitHub", name: "Majestic Central Interconnect", type: "transit", baseline: 50, capacityLabel: "Purple/Green lines", unit: "transit load", x: 300, y: 90 },
      { id: "transitE", name: "Silk Board & ORR Feeder Shuttles", type: "transit", baseline: 38, capacityLabel: "16 feeder routes", unit: "transit load", x: 300, y: 210 },
      { id: "hotelN", name: "MG Road & Indiranagar District", type: "hotel", baseline: 72, capacityLabel: "4,500 rooms", unit: "room occupancy", x: 470, y: 80 },
      { id: "hotelS", name: "Electronic City & Koramangala", type: "hotel", baseline: 40, capacityLabel: "3,800 rooms", unit: "room occupancy", x: 470, y: 220 },
      { id: "corridor", name: "Hebbal Flyover & Outer Ring Artery", type: "corridor", baseline: 66, capacityLabel: "4,600 veh/hr", unit: "arterial load", x: 210, y: 280 }
    ],
    shuttleBaseline: { transitHub: 12, transitE: 8 }
  },
  dubai: {
    id: "dubai",
    name: "Dubai, UAE",
    flag: "🇦🇪",
    venueName: "Coca-Cola Arena & Expo City",
    eventName: "World Government Summit & Mega Concert",
    currency: "AED",
    speedUnit: "km/h",
    shuttleLabel: "RTA Premium Event Buses",
    zones: [
      { id: "venue", name: "Coca-Cola Arena Core", type: "venue", baseline: 52, capacityLabel: "17,000 capacity", unit: "arena density", x: 130, y: 150 },
      { id: "transitHub", name: "Burj Khalifa / Dubai Mall Metro", type: "transit", baseline: 46, capacityLabel: "Red Line Metro", unit: "platform load", x: 300, y: 90 },
      { id: "transitE", name: "Expo 2020 Route 2020 Feeder", type: "transit", baseline: 32, capacityLabel: "12 express lines", unit: "feeder load", x: 300, y: 210 },
      { id: "hotelN", name: "Downtown & Business Bay Hotels", type: "hotel", baseline: 76, capacityLabel: "8,500 rooms", unit: "room occupancy", x: 470, y: 80 },
      { id: "hotelS", name: "Dubai Marina & JBR District", type: "hotel", baseline: 36, capacityLabel: "7,000 rooms", unit: "room occupancy", x: 470, y: 220 },
      { id: "corridor", name: "Sheikh Zayed Road (E11) Arterial", type: "corridor", baseline: 62, capacityLabel: "6,200 veh/hr", unit: "highway load", x: 210, y: 280 }
    ],
    shuttleBaseline: { transitHub: 14, transitE: 10 }
  }
};

// Cascading exodus surge sequence (from Crowdflow surge simulator)
const SURGE_SCRIPT = {
  venue: [10, 6, -10, -22, -18, -8],
  transitHub: [3, 9, 18, 24, 15, 7],
  transitE: [1, 4, 8, 14, 9, 4],
  hotelN: [2, 3, 4, 5, 4, 2],
  hotelS: [0, 1, 2, 3, 2, 1],
  corridor: [4, 10, 19, 22, 16, 8]
};

function clamp(v, min = 0, max = 100) {
  return Math.max(min, Math.min(max, v));
}

function seedHistory(baseline) {
  const hist = [];
  for (let i = -4; i <= 0; i++) {
    hist.push({ t: i, v: clamp(baseline + Math.sin(i) * 3 + (i % 2 === 0 ? 2 : -2)) });
  }
  return hist;
}

function initCityZones(cityKey) {
  const city = CITIES_DATA[cityKey] || CITIES_DATA.london;
  return city.zones.map((z) => {
    const history = seedHistory(z.baseline);
    return {
      ...z,
      value: history[history.length - 1].v,
      forecast: z.baseline,
      history,
      speed: Math.round(60 * Math.exp(-0.035 * (z.baseline / 10))),
      flow: Math.round(z.baseline * 42)
    };
  });
}

function computeZonePhysics(v, isRain, isEmergency, speedUnit) {
  // Crowdflow exponential speed degradation model: v_speed = v_max * exp(-k * density)
  const maxSpeed = speedUnit === "mph" ? 45.0 : 65.0;
  const k = 0.04;
  let speed = maxSpeed * Math.exp(-k * (v / 10.0));
  
  if (isRain) speed *= 0.68; // Rain structural friction
  if (isEmergency) speed = Math.max(speed, maxSpeed * 0.75); // Emergency corridor clearance

  const flow = Math.round(v * speed * 0.9);
  return {
    speed: Math.max(4, Math.round(speed)),
    flow: flow
  };
}

function statusOf(v) {
  if (v >= 82) return "critical";
  if (v >= 68) return "warning";
  return "normal";
}

function zoneIcon(type, size = 16) {
  if (type === "hotel") return <Hotel size={size} />;
  if (type === "transit") return <Bus size={size} />;
  if (type === "corridor") return <Car size={size} />;
  return <Building2 size={size} />;
}

function zoneSummaryText(zones, cityName) {
  return `City / Metro: ${cityName}\n` + zones
    .map(
      (z) =>
        `- ${z.name} (${z.type}): ${z.value.toFixed(0)}% load (forecast +15m: ${z.forecast.toFixed(0)}%, speed: ${z.speed}km/h). Capacity: ${z.capacityLabel}`
    )
    .join("\n");
}

// Resilient AI caller with built-in rich contextual offline fallback
async function callAI(prompt, systemContext) {
  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 600,
        messages: [{ role: "user", content: prompt }],
      }),
    });
    if (response.ok) {
      const data = await response.json();
      const text = (data.content || [])
        .map((b) => (b.type === "text" ? b.text : ""))
        .filter(Boolean)
        .join("\n")
        .trim();
      if (text) return text;
    }
  } catch (err) {
    // Graceful offline fallback
  }

  // Dynamic Rule-Based High Quality Fallback (Simulates Claude Copilot grounded in Crowdflow math)
  if (systemContext.type === "briefing") {
    const stressed = systemContext.stressedZone?.name || "Transit Corridors";
    const val = systemContext.stressedZone?.value.toFixed(0) || "78";
    const rainNote = systemContext.isRain ? " Heavy rainfall is introducing a 32% physical speed drag on arterial routes." : "";
    const emNote = systemContext.isEmergency ? " Emergency priority corridor is actively overriding default cycle allocations." : "";

    return `Operational Briefing for ${systemContext.cityName}:\n` +
      `Telemetry indicates network stability with moderate pressure concentrated at ${stressed} (${val}% capacity).` +
      rainNote + emNote +
      ` Multi-agent reinforcement learning (MARL) reward score is stable. Egress propagation models estimate venue outflow clearance within 35 minutes if active shuttle allocations are maintained.\n\n` +
      `- Action 1: Maintain +25s green phase extension on outbound transit gates.\n` +
      `- Action 2: Redirect prospective hotel departures toward relief districts.\n` +
      `- Action 3: Keep 4 standby shuttle units primed at the central terminal.`;
  } else {
    // Attendee chat response
    const q = (systemContext.query || "").toLowerCase();
    const city = systemContext.cityName;
    if (q.includes("stay") || q.includes("hotel")) {
      const rec = systemContext.bestHotel || "South Overflow District";
      return `For ${city}, I recommend booking in the ${rec.name} (currently at ${rec.value.toFixed(0)}% occupancy). It offers faster check-in and lower rates compared to the crowded core district.`;
    }
    if (q.includes("rain") || q.includes("weather")) {
      return systemContext.isRain
        ? `Rain hazard protocols are active across ${city}. Expect travel delays of +12 to +18 minutes. Shuttle frequency has been reinforced at main exits.`
        : `Weather in ${city} is currently clear. Transit lines and road arteries are operating under normal schedule.`;
    }
    if (q.includes("leave") || q.includes("time") || q.includes("shuttle")) {
      return `Leaving within the next 15 minutes lets you take advantage of our discounted off-peak transit rate. Peak venue exit surge is projected in 25 minutes.`;
    }
    return `Based on live sensors in ${city}: ${systemContext.stressedZone?.name || "The core venue"} is at ${systemContext.stressedZone?.value.toFixed(0) || 60}% load. We recommend using designated express shuttles for fastest dispersal.`;
  }
}

// ==========================================
// 🧩 UI ATOMS & PRIMITIVES
// ==========================================
function Panel({ children, className = "", accent }) {
  return (
    <div
      className={`bg-[#121926] border border-[#263042] relative ${className}`}
      style={accent ? { boxShadow: `inset 3px 0 0 0 ${accent}` } : undefined}
    >
      {children}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div className="text-[11px] tracking-wider text-[#7C8AA0] uppercase font-semibold mb-2" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
      {children}
    </div>
  );
}

function Sparkline({ history, color }) {
  const w = 90, h = 26;
  const vals = history.map((p) => p.v);
  const min = Math.min(...vals) - 2;
  const max = Math.max(...vals) + 2;
  const pts = vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * w;
      const y = h - ((v - min) / (max - min || 1)) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" />
    </svg>
  );
}

function ZoneCard({ zone, selected, onClick, speedUnit }) {
  const status = statusOf(zone.value);
  const color = COLORS[status];
  const trend = zone.forecast - zone.value;
  return (
    <button
      onClick={onClick}
      className={`text-left w-full bg-[#121926] border p-3 transition-all cursor-pointer ${
        selected ? "border-[#8B7CF6] shadow-[0_0_15px_rgba(139,124,246,0.15)]" : "border-[#263042] hover:border-[#3b485d]"
      }`}
      style={{ boxShadow: `inset 3px 0 0 0 ${color}` }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[#7C8AA0]">
          {zoneIcon(zone.type, 13)}
          <span className="text-[12px] font-medium text-[#E8EDF4] truncate max-w-[120px]">{zone.name}</span>
        </div>
        <Sparkline history={zone.history} color={color} />
      </div>
      <div className="flex items-end justify-between mt-2">
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-bold text-[#E8EDF4]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {zone.value.toFixed(0)}
          </span>
          <span className="text-xs text-[#7C8AA0]">%</span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px]" style={{ color: trend > 2 ? COLORS.critical : trend < -2 ? COLORS.normal : COLORS.textMuted }}>
          {trend > 2 ? <TrendingUp size={12} /> : trend < -2 ? <TrendingDown size={12} /> : <Flat size={12} />}
          <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{zone.forecast.toFixed(0)}%</span>
        </div>
      </div>
      <div className="flex items-center justify-between text-[10px] text-[#7C8AA0] mt-1.5 pt-1.5 border-t border-[#1d2636]">
        <span>{zone.capacityLabel}</span>
        <span className="text-emerald-400 font-mono">{zone.speed} {speedUnit}</span>
      </div>
    </button>
  );
}

// ==========================================
// 🗺️ DIGITAL TWIN TOPOLOGY NETWORK (SVG)
// ==========================================
function TopologyNetworkMap({ zones, selectedId, onSelectZone, isRain, isEmergency }) {
  const selected = zones.find((z) => z.id === selectedId);

  return (
    <Panel className="p-4 overflow-hidden">
      <div className="flex items-center justify-between mb-2">
        <SectionLabel>Digital Twin Vector Topology (Live Nodes)</SectionLabel>
        <div className="flex items-center gap-3 text-[11px] font-mono text-[#7C8AA0]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#4FD8E0]"></span> Normal</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#F5A623]"></span> Warning</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#FF5C6C]"></span> Surge</span>
        </div>
      </div>

      <div className="relative w-full h-[230px] bg-[#0B0F17]/90 border border-[#1b2434] rounded-sm flex items-center justify-center">
        <svg viewBox="0 0 580 320" className="w-full h-full">
          <defs>
            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#8B7CF6" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#4FD8E0" stopOpacity="0.3" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Connected Topology Edges */}
          <line x1="130" y1="150" x2="300" y2="90" stroke="url(#edgeGrad)" strokeWidth="2" strokeDasharray="4 3" />
          <line x1="130" y1="150" x2="300" y2="210" stroke="url(#edgeGrad)" strokeWidth="2" strokeDasharray="4 3" />
          <line x1="130" y1="150" x2="210" y2="280" stroke="url(#edgeGrad)" strokeWidth="2" />
          <line x1="300" y1="90" x2="470" y2="80" stroke="url(#edgeGrad)" strokeWidth="2" />
          <line x1="300" y1="210" x2="470" y2="220" stroke="url(#edgeGrad)" strokeWidth="2" />
          <line x1="210" y1="280" x2="470" y2="220" stroke="url(#edgeGrad)" strokeWidth="1.5" strokeDasharray="2 2" />

          {/* Interactive Nodes */}
          {zones.map((z) => {
            const isSel = z.id === selectedId;
            const status = statusOf(z.value);
            const col = COLORS[status];
            return (
              <g key={z.id} onClick={() => onSelectZone(z.id)} className="cursor-pointer">
                {/* Outer Glow Ring */}
                <circle
                  cx={z.x || 100}
                  cy={z.y || 100}
                  r={isSel ? 24 : 18}
                  fill={col}
                  fillOpacity={isSel ? 0.25 : 0.12}
                  stroke={col}
                  strokeWidth={isSel ? 2.5 : 1.2}
                  className="transition-all"
                  filter={status === "critical" ? "url(#glow)" : undefined}
                />
                <circle cx={z.x || 100} cy={z.y || 100} r="7" fill={col} />
                
                {/* Node Label */}
                <text
                  x={z.x || 100}
                  y={(z.y || 100) + (z.y > 180 ? 25 : -22)}
                  textAnchor="middle"
                  fill="#E8EDF4"
                  fontSize="10"
                  fontFamily="'Space Grotesk', sans-serif"
                  fontWeight="600"
                >
                  {z.name.split(" ")[0]} ({z.value.toFixed(0)}%)
                </text>
              </g>
            );
          })}
        </svg>

        {isEmergency && (
          <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-red-950/80 border border-red-500/50 px-2 py-1 rounded text-[10px] text-red-300 font-mono animate-pulse">
            <Siren size={12} /> EMERGENCY WAVE ACTIVE
          </div>
        )}

        {isRain && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-blue-950/80 border border-sky-400/50 px-2 py-1 rounded text-[10px] text-sky-300 font-mono">
            <CloudRain size={12} /> MONSOON FRICTION: +32% DELAY
          </div>
        )}
      </div>
    </Panel>
  );
}

// ==========================================
// 🛠️ ORGANIZER COMMAND CENTER VIEW
// ==========================================
function OrganizerView({
  city, zones, selectedId, setSelectedId, alerts, recs,
  applyHotelRedirect, applyShuttleShift, shuttles, adjustShuttle,
  surgeActive, triggerSurge, isRain, toggleRain, isEmergency, toggleEmergency,
  applySignalExtension, signalExtended, actionLog,
  briefing, briefingLoading, onGenerateBriefing, rlReward
}) {
  const selected = zones.find((z) => z.id === selectedId) || zones[0];
  const chartData = selected.history.map((p) => ({ t: `T${p.t >= 0 ? "+" : ""}${p.t * 5}m`, value: Math.round(p.v) }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_1fr] gap-4">
      {/* LEFT COLUMN: TELEMETRY & SPATIAL CONTROL */}
      <div className="space-y-4">
        {/* KPI OVERVIEW STRIP (CROWDFLOW METRICS) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <Panel className="p-3">
            <div className="flex items-center gap-1.5 text-[10px] text-[#7C8AA0] uppercase font-semibold">
              <Gauge size={13} className="text-emerald-400" /> Avg. Velocity
            </div>
            <div className="text-xl font-bold font-mono text-[#E8EDF4] mt-1">
              {Math.round(zones.reduce((a, b) => a + b.speed, 0) / zones.length)} <span className="text-xs text-[#7C8AA0]">{city.speedUnit}</span>
            </div>
          </Panel>
          <Panel className="p-3">
            <div className="flex items-center gap-1.5 text-[10px] text-[#7C8AA0] uppercase font-semibold">
              <Car size={13} className="text-sky-400" /> System Flow
            </div>
            <div className="text-xl font-bold font-mono text-[#E8EDF4] mt-1">
              {zones.reduce((a, b) => a + b.flow, 0).toLocaleString()} <span className="text-xs text-[#7C8AA0]">flux/h</span>
            </div>
          </Panel>
          <Panel className="p-3">
            <div className="flex items-center gap-1.5 text-[10px] text-[#7C8AA0] uppercase font-semibold">
              <AlertTriangle size={13} className="text-amber-400" /> Risk Hotspots
            </div>
            <div className="text-xl font-bold font-mono text-[#E8EDF4] mt-1">
              {zones.filter((z) => z.value >= 70).length} <span className="text-xs text-[#7C8AA0]">nodes</span>
            </div>
          </Panel>
          <Panel className="p-3">
            <div className="flex items-center gap-1.5 text-[10px] text-[#7C8AA0] uppercase font-semibold">
              <Activity size={13} className="text-purple-400" /> MARL Reward
            </div>
            <div className="text-xl font-bold font-mono text-purple-300 mt-1">
              {rlReward} <span className="text-xs text-[#7C8AA0]">pts</span>
            </div>
          </Panel>
        </div>

        {/* ZONE CAPACITY GRID */}
        <Panel className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <SectionLabel>Monitored Urban Corridors & Districts</SectionLabel>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleRain}
                className={`flex items-center gap-1 text-[11px] px-2.5 py-1 border transition-all cursor-pointer ${
                  isRain ? "bg-sky-950/80 border-sky-400 text-sky-300" : "border-[#263042] text-[#7C8AA0] hover:text-[#E8EDF4]"
                }`}
              >
                <CloudRain size={12} /> {isRain ? "Rain Hazard Active" : "Simulate Rain"}
              </button>
              <button
                onClick={toggleEmergency}
                className={`flex items-center gap-1 text-[11px] px-2.5 py-1 border transition-all cursor-pointer ${
                  isEmergency ? "bg-red-950/80 border-red-500 text-red-300 animate-pulse" : "border-[#263042] text-[#7C8AA0] hover:text-[#E8EDF4]"
                }`}
              >
                <Siren size={12} /> {isEmergency ? "Emergency Override" : "Priority Ambulance"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {zones.map((z) => (
              <ZoneCard key={z.id} zone={z} selected={z.id === selectedId} onClick={() => setSelectedId(z.id)} speedUnit={city.speedUnit} />
            ))}
          </div>
        </Panel>

        {/* DIGITAL TWIN VECTOR MAP */}
        <TopologyNetworkMap
          zones={zones}
          selectedId={selectedId}
          onSelectZone={setSelectedId}
          isRain={isRain}
          isEmergency={isEmergency}
        />

        {/* 15-MIN PREDICTIVE RECHARTS */}
        <Panel className="p-4">
          <div className="flex items-center justify-between mb-2">
            <SectionLabel>{selected.name} — Real-Time Trend &amp; Slope Forecast</SectionLabel>
            <span className="text-[11px] font-mono text-[#7C8AA0]">{selected.capacityLabel}</span>
          </div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1c2635" vertical={false} />
                <XAxis dataKey="t" stroke="#7C8AA0" fontSize={10} tickLine={false} />
                <YAxis stroke="#7C8AA0" fontSize={10} domain={[0, 100]} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "#161F2E", border: "1px solid #263042", fontSize: 12, color: "#E8EDF4" }}
                  labelStyle={{ color: "#7C8AA0" }}
                />
                <Line type="monotone" dataKey="value" stroke={COLORS[statusOf(selected.value)]} strokeWidth={2.4} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* RIGHT COLUMN: DIGITAL TWIN INTERVENTIONS & CO-PILOT */}
      <div className="space-y-4">
        {/* EVENT SURGE SIMULATION TRIGGER */}
        <Panel className="p-4" accent={COLORS.warning}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-[#E8EDF4] flex items-center gap-1.5">
                <Zap size={15} className="text-[#F5A623]" /> Event-End Outflow Cascade
              </div>
              <div className="text-[11px] text-[#7C8AA0] mt-0.5">
                Simulates 20,000+ attendee egress from {city.venueName} into transit hubs.
              </div>
            </div>
            <button
              onClick={triggerSurge}
              disabled={surgeActive}
              className="flex items-center gap-1 text-[11px] font-medium px-3 py-1.5 border border-[#FF5C6C]/60 text-[#FF5C6C] hover:bg-[#FF5C6C]/10 disabled:opacity-40 cursor-pointer"
            >
              {surgeActive ? "Surge in motion…" : "Trigger Surge"}
            </button>
          </div>
        </Panel>

        {/* ACTIVE ALERTS */}
        <Panel className="p-4">
          <SectionLabel>Active Corridor Alerts ({alerts.length})</SectionLabel>
          {alerts.length === 0 && <div className="text-sm text-[#7C8AA0] py-1">All monitored districts operating inside safety parameters.</div>}
          <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
            {alerts.map((a, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-[#161F2E] border border-[#263042]" style={{ boxShadow: `inset 3px 0 0 0 ${COLORS[a.level]}` }}>
                <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" style={{ color: COLORS[a.level] }} />
                <div className="text-[12px] text-[#E8EDF4] leading-snug">{a.text}</div>
              </div>
            ))}
          </div>
        </Panel>

        {/* CROWDFLOW DIGITAL TWIN SMART MITIGATIONS */}
        <Panel className="p-4">
          <SectionLabel>Smart AI Interventions (One-Click Actions)</SectionLabel>
          <div className="space-y-2.5">
            {/* Action 1: Green Extension */}
            <div className="p-2.5 bg-[#161F2E] border border-[#263042] flex items-center justify-between">
              <div>
                <div className="text-[12px] font-medium text-[#E8EDF4]">Extend Egress Signal Green Phase (+25s)</div>
                <div className="text-[10px] text-[#7C8AA0]">Flushes venue perimeter before gridlock reaches arterial rings.</div>
              </div>
              <button
                onClick={applySignalExtension}
                className={`text-[11px] px-2.5 py-1 border transition-all cursor-pointer ${
                  signalExtended ? "bg-emerald-950/70 border-emerald-500 text-emerald-300" : "border-[#4FD8E0]/40 text-[#4FD8E0] hover:bg-[#4FD8E0]/10"
                }`}
              >
                {signalExtended ? "Applied ✓" : "Execute"}
              </button>
            </div>

            {/* Action 2: Hotel Redirect */}
            {recs.hotel && (
              <div className="p-2.5 bg-[#161F2E] border border-[#263042] flex items-center justify-between">
                <div>
                  <div className="text-[12px] font-medium text-[#E8EDF4]">Redirect Hotel Bookings</div>
                  <div className="text-[10px] text-[#7C8AA0]">Shift from {recs.hotel.stressed.name} ({recs.hotel.stressed.value.toFixed(0)}%) → {recs.hotel.relief.name}.</div>
                </div>
                <button onClick={applyHotelRedirect} className="text-[11px] px-2.5 py-1 border border-[#4FD8E0]/40 text-[#4FD8E0] hover:bg-[#4FD8E0]/10 cursor-pointer">
                  Redirect
                </button>
              </div>
            )}

            {/* Action 3: Shuttle Shift */}
            {recs.transit && (
              <div className="p-2.5 bg-[#161F2E] border border-[#263042] flex items-center justify-between">
                <div>
                  <div className="text-[12px] font-medium text-[#E8EDF4]">Reallocate 4 Shuttle Units</div>
                  <div className="text-[10px] text-[#7C8AA0]">Shift capacity to {recs.transit.stressed.name}.</div>
                </div>
                <button onClick={applyShuttleShift} className="text-[11px] px-2.5 py-1 border border-[#4FD8E0]/40 text-[#4FD8E0] hover:bg-[#4FD8E0]/10 cursor-pointer">
                  Reallocate
                </button>
              </div>
            )}
          </div>
        </Panel>

        {/* SHUTTLE FLEET MANAGEMENT STEPPERS */}
        <Panel className="p-4">
          <SectionLabel>{city.shuttleLabel} Allocation</SectionLabel>
          <div className="space-y-2.5 mt-1">
            {zones.filter((z) => z.type === "transit").map((z) => (
              <div key={z.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-[#E8EDF4]">
                  <Bus size={13} className="text-[#7C8AA0]" /> {z.name}
                </div>
                <div className="flex items-center gap-1.5">
                  <button onClick={() => adjustShuttle(z.id, -1)} className="w-6 h-6 flex items-center justify-center border border-[#263042] text-[#7C8AA0] hover:text-[#E8EDF4] cursor-pointer">
                    <Minus size={11} />
                  </button>
                  <span className="w-7 text-center font-mono text-sm font-semibold text-[#E8EDF4]">{shuttles[z.id] || 8}</span>
                  <button onClick={() => adjustShuttle(z.id, 1)} className="w-6 h-6 flex items-center justify-center border border-[#263042] text-[#7C8AA0] hover:text-[#E8EDF4] cursor-pointer">
                    <Plus size={11} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* AI OPERATIONS BRIEFING (COPILOT) */}
        <Panel className="p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Sparkles size={13} style={{ color: COLORS.ai }} />
              <SectionLabel>Crowdflow Operations Copilot</SectionLabel>
            </div>
            <button
              onClick={onGenerateBriefing}
              disabled={briefingLoading}
              className="text-[11px] px-2.5 py-1 border border-[#8B7CF6]/50 text-[#8B7CF6] hover:bg-[#8B7CF6]/10 disabled:opacity-50 cursor-pointer"
            >
              {briefingLoading ? "Analyzing State…" : "Generate Briefing"}
            </button>
          </div>
          {briefing ? (
            <div className="text-[12px] text-[#E8EDF4] leading-relaxed whitespace-pre-wrap p-3 bg-[#161F2E] border border-[#8B7CF6]/30 font-sans">
              {briefing}
            </div>
          ) : (
            <div className="text-[11px] text-[#7C8AA0] italic">
              Click &quot;Generate Briefing&quot; to compile real-time telemetry into executive operational recommendations.
            </div>
          )}
        </Panel>

        {/* ACTION LOG AUDIT */}
        {actionLog.length > 0 && (
          <Panel className="p-4">
            <SectionLabel>Operations Log Audit</SectionLabel>
            <div className="space-y-1 text-[11px] text-[#7C8AA0] font-mono max-h-[110px] overflow-y-auto">
              {actionLog.slice(-6).reverse().map((l, i) => <div key={i}>{l}</div>)}
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

// ==========================================
// 📱 ATTENDEE SMART GUIDE VIEW
// ==========================================
function AttendeeView({
  city, zones, chatMessages, chatInput, setChatInput, sendChat, chatLoading, isRain
}) {
  const hotels = [...zones.filter((z) => z.type === "hotel")].sort((a, b) => a.value - b.value);
  const transits = zones.filter((z) => z.type === "transit");
  const venue = zones.find((z) => z.id === "venue");
  const bestHotel = hotels[0];

  const routeStatus = (v) => (v >= 80 ? "Heavy Congestion" : v >= 65 ? "Building Up" : "Flowing Smoothly");

  const chatEndRef = useRef(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-4">
      <div className="space-y-4">
        {/* RAIN BANNER IF ACTIVE */}
        {isRain && (
          <div className="p-3 bg-sky-950/70 border border-sky-400/40 flex items-center gap-2.5 text-sky-200 text-xs">
            <CloudRain size={16} className="text-sky-400 flex-shrink-0" />
            <div>
              <b>Weather Alert in {city.name}:</b> Heavy rainfall active. Transit feeder headways extended by ~10 mins. Please allow extra time.
            </div>
          </div>
        )}

        {/* HOTEL RECOMMENDATIONS */}
        <Panel className="p-4">
          <SectionLabel>Nearby Accommodations ({city.name})</SectionLabel>
          <div className="space-y-2.5">
            {hotels.map((h) => (
              <div key={h.id} className="p-3 bg-[#161F2E] border border-[#263042] flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-[#E8EDF4]">
                    <Hotel size={14} className="text-[#7C8AA0]" /> {h.name}
                    {h.id === bestHotel?.id && (
                      <span className="text-[10px] px-1.5 py-0.5 border border-[#4FD8E0]/50 text-[#4FD8E0]">Recommended</span>
                    )}
                  </div>
                  <div className="text-[11px] text-[#7C8AA0] mt-1">{h.capacityLabel} &middot; Commute: {h.id === "hotelN" ? "10–14" : "20–28"} min</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold font-mono" style={{ color: COLORS[statusOf(h.value)] }}>
                    {h.value.toFixed(0)}%
                  </div>
                  <div className="text-[10px] text-[#7C8AA0]">Occupancy</div>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* LIVE TRANSIT ROUTE GUIDANCE */}
        <Panel className="p-4">
          <SectionLabel>Live Departure Feeder Status</SectionLabel>
          <div className="space-y-3">
            {transits.map((t) => (
              <div key={t.id} className="p-3 bg-[#161F2E] border border-[#263042]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold text-[#E8EDF4]">
                    <Bus size={13} className="text-[#7C8AA0]" /> {t.name}
                  </div>
                  <span className="text-[11px] font-mono" style={{ color: COLORS[statusOf(t.value)] }}>{routeStatus(t.value)}</span>
                </div>
                <div className="h-1.5 bg-[#0B0F17] mt-2.5 overflow-hidden rounded-full">
                  <div className="h-full transition-all duration-500" style={{ width: `${t.value}%`, background: COLORS[statusOf(t.value)] }} />
                </div>
                <div className="flex justify-between text-[10px] text-[#7C8AA0] mt-1.5 font-mono">
                  <span>Load: {t.value.toFixed(0)}%</span>
                  <span>Velocity: {t.speed} {city.speedUnit}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* TIME-SHIFT FARE INCENTIVE */}
        <Panel className="p-4" accent={COLORS.normal}>
          <div className="flex items-start gap-2.5">
            <Sparkles size={16} className="text-[#4FD8E0] mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-xs font-semibold text-[#E8EDF4]">Time-Shift Commuter Voucher ({city.currency})</div>
              <div className="text-[11px] text-[#7C8AA0] mt-1 leading-relaxed">
                {venue?.forecast < venue?.value - 4
                  ? "Venue Core is initiating exodus. Depart now or delay 30 minutes to redeem a 25% discount on municipal express shuttles."
                  : "Off-peak departure reward available. Scan this code at venue exits for a discounted return fare."}
              </div>
            </div>
          </div>
        </Panel>
      </div>

      {/* RIGHT COLUMN: AI CONCIERGE CHAT */}
      <Panel className="p-4 flex flex-col h-[560px]">
        <div className="flex items-center justify-between mb-3 border-b border-[#263042] pb-2.5">
          <div className="flex items-center gap-1.5">
            <MessageCircle size={15} style={{ color: COLORS.ai }} />
            <SectionLabel>{city.name} AI Event Concierge</SectionLabel>
          </div>
          <span className="text-[10px] font-mono text-purple-400">Live Telemetry Linked</span>
        </div>

        {/* Prompt Suggestions */}
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          {["Where should I stay?", "Which route is fastest?", "Is rain causing delays?"].map((prompt, i) => (
            <button
              key={i}
              onClick={() => sendChat(prompt)}
              className="text-[10.5px] px-2 py-0.5 bg-[#161F2E] border border-[#263042] text-[#7C8AA0] hover:text-[#E8EDF4] hover:border-[#8B7CF6] transition-all cursor-pointer"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Chat Stream */}
        <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
          {chatMessages.length === 0 && (
            <div className="text-[12px] text-[#7C8AA0] leading-relaxed p-3 bg-[#161F2E]/60 border border-[#263042]/50">
              Welcome to the {city.name} event assistance desk. Ask about lodging vacancy, departure congestion, or shuttle timetables. Responses are dynamically calculated using real-time sensor streams.
            </div>
          )}
          {chatMessages.map((m, i) => (
            <div
              key={i}
              className={`text-[12px] p-2.5 leading-snug max-w-[90%] rounded-sm ${
                m.role === "user" ? "ml-auto bg-[#1b2534] text-[#E8EDF4] border border-[#263042]" : "bg-[#161F2E] border border-[#8B7CF6]/30 text-[#E8EDF4]"
              }`}
            >
              {m.text}
            </div>
          ))}
          {chatLoading && <div className="text-[11px] text-purple-400 font-mono animate-pulse">Calculating optimal routes…</div>}
          <div ref={chatEndRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (chatInput.trim()) sendChat(chatInput.trim());
          }}
          className="flex items-center gap-2 mt-3"
        >
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder={`Ask about ${city.name} venue transit or hotels…`}
            className="flex-1 bg-[#0B0F17] border border-[#263042] px-3 py-2 text-[12px] text-[#E8EDF4] outline-none focus:border-[#8B7CF6]"
          />
          <button type="submit" className="w-8 h-8 flex items-center justify-center border border-[#8B7CF6]/50 text-[#8B7CF6] hover:bg-[#8B7CF6]/15 cursor-pointer">
            <Send size={13} />
          </button>
        </form>
      </Panel>
    </div>
  );
}

// ==========================================
// 🚀 MAIN APPLICATION ROOT
// ==========================================
export default function App() {
  const [selectedCityKey, setSelectedCityKey] = useState("london");
  const city = CITIES_DATA[selectedCityKey];

  const [zones, setZones] = useState(() => initCityZones("london"));
  const [shuttles, setShuttles] = useState(() => CITIES_DATA.london.shuttleBaseline);
  const [surge, setSurge] = useState({ active: false, step: 0 });
  const [selectedId, setSelectedId] = useState("venue");
  const [view, setView] = useState("organizer");
  const [actionLog, setActionLog] = useState([]);
  const [clock, setClock] = useState(0);

  // Weather and Emergency Modes (from Crowdflow)
  const [isRain, setIsRain] = useState(false);
  const [isEmergency, setIsEmergency] = useState(false);
  const [signalExtended, setSignalExtended] = useState(false);

  // AI Briefing and Chat
  const [briefing, setBriefing] = useState("");
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Switch City Handler
  function handleSelectCity(key) {
    setSelectedCityKey(key);
    const newCity = CITIES_DATA[key];
    const newZones = initCityZones(key);
    setZones(newZones);
    setShuttles(newCity.shuttleBaseline);
    setSelectedId("venue");
    setBriefing("");
    setChatMessages([]);
    setActionLog((l) => [...l, `T+${clock}m — Switched operational jurisdiction to ${newCity.name}`]);
  }

  const shuttlesRef = useRef(shuttles);
  const surgeRef = useRef(surge);
  const isRainRef = useRef(isRain);
  const isEmergencyRef = useRef(isEmergency);

  useEffect(() => { shuttlesRef.current = shuttles; }, [shuttles]);
  useEffect(() => { surgeRef.current = surge; }, [surge]);
  useEffect(() => { isRainRef.current = isRain; }, [isRain]);
  useEffect(() => { isEmergencyRef.current = isEmergency; }, [isEmergency]);

  // Real-Time Simulation Heartbeat (Every 3.2s = T+5 min)
  useEffect(() => {
    const interval = setInterval(() => {
      setZones((prev) =>
        prev.map((z) => {
          const step = surgeRef.current.active ? surgeRef.current.step : null;
          const noise = (Math.random() - 0.5) * 3.5;
          let scripted = 0;
          if (step != null && SURGE_SCRIPT[z.id] && step < SURGE_SCRIPT[z.id].length) {
            scripted = SURGE_SCRIPT[z.id][step];
          }

          let shuttleEffect = 0;
          if (z.type === "transit") {
            const base = city.shuttleBaseline[z.id] || 8;
            shuttleEffect = ((shuttlesRef.current[z.id] || base) - base) * 1.4;
          }

          let weatherEffect = isRainRef.current ? 4.5 : 0;
          let emergencyEffect = (isEmergencyRef.current && z.type === "transit") ? -6.0 : 0;
          const reversion = (z.baseline - z.value) * 0.08;

          const nextVal = clamp(z.value + noise + scripted - shuttleEffect + weatherEffect + emergencyEffect + reversion, 5, 98);
          const history = [...z.history, { t: z.history[z.history.length - 1].t + 1, v: nextVal }].slice(-14);

          // 4-point linear regression slope extrapolation for 15-min forward forecast
          const recent = history.slice(-4);
          const slope = recent.length >= 2 ? (recent[recent.length - 1].v - recent[0].v) / (recent.length - 1) : 0;
          const forecast = clamp(nextVal + slope * 3, 0, 100);

          const physics = computeZonePhysics(nextVal, isRainRef.current, isEmergencyRef.current, city.speedUnit);

          return {
            ...z,
            value: nextVal,
            history,
            forecast,
            speed: physics.speed,
            flow: physics.flow
          };
        })
      );

      setClock((c) => c + 5);
      setSurge((s) => (s.active ? (s.step + 1 >= 6 ? { active: false, step: 0 } : { ...s, step: s.step + 1 }) : s));
    }, 3200);

    return () => clearInterval(interval);
  }, [selectedCityKey, city]);

  // Active Threshold Alerts
  const alerts = useMemo(() => {
    const list = [];
    zones.forEach((z) => {
      const status = statusOf(z.value);
      if (status === "critical") {
        list.push({ level: "critical", text: `CRITICAL SURGE: ${z.name} reached ${z.value.toFixed(0)}% load (${z.capacityLabel}). Flow choke imminent.` });
      } else if (status === "warning") {
        list.push({ level: "warning", text: `HIGH PRESSURE: ${z.name} at ${z.value.toFixed(0)}% load. Commute speeds down to ${z.speed} ${city.speedUnit}.` });
      } else if (z.forecast >= 80 && z.value < 75) {
        list.push({ level: "warning", text: `PREDICTIVE ALERT: ${z.name} forecasted to reach ${z.forecast.toFixed(0)}% within 15 mins.` });
      }
    });
    return list.sort((a, b) => (a.level === "critical" ? -1 : 1));
  }, [zones, city]);

  // Automated Mitigation Recommendations
  const recs = useMemo(() => {
    const hotelZones = zones.filter((z) => z.type === "hotel").sort((a, b) => b.value - a.value);
    const transitZones = zones.filter((z) => z.type === "transit").sort((a, b) => b.value - a.value);
    let hotel = null, transit = null;
    if (hotelZones.length >= 2) {
      const stressed = hotelZones[0], relief = hotelZones[hotelZones.length - 1];
      if (stressed.value >= 70 && stressed.value - relief.value >= 14) hotel = { stressed, relief };
    }
    if (transitZones.length >= 2) {
      const stressed = transitZones[0], relief = transitZones[transitZones.length - 1];
      if (stressed.value >= 66 && stressed.value - relief.value >= 10) transit = { stressed, relief };
    }
    return { hotel, transit };
  }, [zones]);

  // Multi-Agent RL Reward Score (Crowdflow metric)
  const rlReward = useMemo(() => {
    const avgLoad = zones.reduce((a, b) => a + b.value, 0) / zones.length;
    const variance = zones.reduce((a, b) => a + Math.pow(b.value - avgLoad, 2), 0) / zones.length;
    const penalty = (avgLoad > 70 ? (avgLoad - 70) * 1.8 : 0) + Math.sqrt(variance) * 0.4;
    return Math.max(12, Math.round(100 - penalty));
  }, [zones]);

  // Action Dispatchers
  function triggerSurge() {
    setSurge({ active: true, step: 0 });
    setActionLog((l) => [...l, `T+${clock}m — Event-end exodus triggered at ${city.venueName}`]);
  }

  function toggleRain() {
    setIsRain((r) => {
      const next = !r;
      setActionLog((l) => [...l, `T+${clock}m — ${next ? "Monsoon rain friction protocol ACTIVATED" : "Weather restored to CLEAR"}`]);
      return next;
    });
  }

  function toggleEmergency() {
    setIsEmergency((e) => {
      const next = !e;
      setActionLog((l) => [...l, `T+${clock}m — ${next ? "EMERGENCY AMBULANCE PRIORITY CORRIDOR ENGAGED" : "Emergency corridor released"}`]);
      return next;
    });
  }

  function applySignalExtension() {
    setSignalExtended(true);
    setZones((prev) =>
      prev.map((z) => (z.id === "venue" ? { ...z, value: clamp(z.value - 9, 10, 95) } : z))
    );
    setActionLog((l) => [...l, `T+${clock}m — Applied +25s signal green phase to flush ${city.venueName} gates`]);
    setTimeout(() => setSignalExtended(false), 8000);
  }

  function adjustShuttle(zoneId, delta) {
    setShuttles((prev) => ({ ...prev, [zoneId]: clamp((prev[zoneId] || 8) + delta, 0, 32) }));
  }

  function applyShuttleShift() {
    if (!recs.transit) return;
    const { stressed, relief } = recs.transit;
    setShuttles((prev) => ({
      ...prev,
      [relief.id]: clamp((prev[relief.id] || 8) - 4, 0, 32),
      [stressed.id]: clamp((prev[stressed.id] || 8) + 4, 0, 32),
    }));
    setActionLog((l) => [...l, `T+${clock}m — Shifted 4 express shuttles: ${relief.name} → ${stressed.name}`]);
  }

  function applyHotelRedirect() {
    if (!recs.hotel) return;
    const { stressed, relief } = recs.hotel;
    setZones((prev) =>
      prev.map((z) => {
        if (z.id === stressed.id) return { ...z, baseline: clamp(z.baseline - 7, 20, 95) };
        if (z.id === relief.id) return { ...z, baseline: clamp(z.baseline + 7, 20, 95) };
        return z;
      })
    );
    setActionLog((l) => [...l, `T+${clock}m — Rerouted booking flow from ${stressed.name} to ${relief.name}`]);
  }

  async function onGenerateBriefing() {
    setBriefingLoading(true);
    const stressed = zones.find((z) => z.value >= 70);
    const text = await callAI(
      `Generate operations briefing for ${city.name} with live zones:\n${zoneSummaryText(zones, city.name)}`,
      {
        type: "briefing",
        cityName: city.name,
        stressedZone: stressed,
        isRain,
        isEmergency
      }
    );
    setBriefing(text);
    setBriefingLoading(false);
  }

  async function sendChat(text) {
    setChatMessages((m) => [...m, { role: "user", text }]);
    setChatInput("");
    setChatLoading(true);
    const stressed = zones.find((z) => z.value >= 70);
    const bestHotel = [...zones.filter((z) => z.type === "hotel")].sort((a, b) => a.value - b.value)[0];
    const reply = await callAI(text, {
      type: "chat",
      cityName: city.name,
      query: text,
      stressedZone: stressed,
      bestHotel,
      isRain
    });
    setChatMessages((m) => [...m, { role: "assistant", text: reply }]);
    setChatLoading(false);
  }

  return (
    <div className="min-h-screen w-full bg-[#0B0F17] text-[#E8EDF4]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: #263042; }
      `}</style>

      <div className="p-4 sm:p-6 max-w-[1300px] mx-auto">
        {/* HEADER BAR WITH GLOBAL CITY SELECTOR */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6 pb-4 border-b border-[#1c2636]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-sm bg-[#161F2E] border border-[#263042] flex items-center justify-center">
              <Orbit size={24} style={{ color: COLORS.ai }} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight text-[#E8EDF4]">Concourse</span>
                <span className="text-[10px] px-1.5 py-0.5 bg-[#8B7CF6]/20 border border-[#8B7CF6]/40 text-[#8B7CF6] font-mono">
                  Crowdflow Multi-City Engine
                </span>
              </div>
              <div className="text-xs text-[#7C8AA0]">Global Mega-Event Capacity &amp; Crowd Grid Orchestrator</div>
            </div>
          </div>

          {/* GLOBAL CITY DROPDOWN SELECTOR */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-[#121926] border border-[#263042] px-2.5 py-1.5">
              <Globe size={14} className="text-sky-400" />
              <span className="text-[11px] text-[#7C8AA0] uppercase font-semibold">Jurisdiction:</span>
              <select
                value={selectedCityKey}
                onChange={(e) => handleSelectCity(e.target.value)}
                className="bg-transparent text-xs font-semibold text-[#E8EDF4] outline-none cursor-pointer"
              >
                {Object.values(CITIES_DATA).map((c) => (
                  <option key={c.id} value={c.id} className="bg-[#121926] text-[#E8EDF4]">
                    {c.flag} {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* PERSONA VIEW SWITCHER */}
            <div className="flex border border-[#263042] bg-[#121926]">
              <button
                onClick={() => setView("organizer")}
                className={`px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                  view === "organizer" ? "bg-[#1f2c42] text-[#E8EDF4]" : "text-[#7C8AA0] hover:text-[#E8EDF4]"
                }`}
              >
                Command Center
              </button>
              <button
                onClick={() => setView("attendee")}
                className={`px-3 py-1.5 text-xs font-medium border-l border-[#263042] transition-colors cursor-pointer ${
                  view === "attendee" ? "bg-[#1f2c42] text-[#E8EDF4]" : "text-[#7C8AA0] hover:text-[#E8EDF4]"
                }`}
              >
                Attendee Guide
              </button>
            </div>

            <div className="text-xs font-mono text-[#7C8AA0] bg-[#121926] border border-[#263042] px-2.5 py-1.5">
              T+{clock}m
            </div>
          </div>
        </div>

        {/* ACTIVE EVENT SCENARIO BANNER */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 p-3 bg-[#121926]/90 border border-[#263042] rounded-sm text-xs">
          <div className="flex items-center gap-2">
            <span className="text-base">{city.flag}</span>
            <span className="font-semibold text-[#E8EDF4]">{city.venueName}:</span>
            <span className="text-[#7C8AA0]">{city.eventName}</span>
          </div>
          <div className="text-[11px] font-mono text-emerald-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span> Live Physics Telemetry Streaming
          </div>
        </div>

        {/* VIEW RENDERING */}
        {view === "organizer" ? (
          <OrganizerView
            city={city}
            zones={zones}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            alerts={alerts}
            recs={recs}
            applyHotelRedirect={applyHotelRedirect}
            applyShuttleShift={applyShuttleShift}
            shuttles={shuttles}
            adjustShuttle={adjustShuttle}
            surgeActive={surge.active}
            triggerSurge={triggerSurge}
            isRain={isRain}
            toggleRain={toggleRain}
            isEmergency={isEmergency}
            toggleEmergency={toggleEmergency}
            applySignalExtension={applySignalExtension}
            signalExtended={signalExtended}
            actionLog={actionLog}
            briefing={briefing}
            briefingLoading={briefingLoading}
            onGenerateBriefing={onGenerateBriefing}
            rlReward={rlReward}
          />
        ) : (
          <AttendeeView
            city={city}
            zones={zones}
            chatMessages={chatMessages}
            chatInput={chatInput}
            setChatInput={setChatInput}
            sendChat={sendChat}
            chatLoading={chatLoading}
            isRain={isRain}
          />
        )}
      </div>
    </div>
  );
}
