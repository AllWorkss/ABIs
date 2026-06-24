# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m2_logistics_router.py — Smart 3PL Logistics Router
#
#  Features:
#  1. Address input + geocoding (Nominatim/OpenStreetMap)
#  2. Real road distance via OSRM (free routing engine)
#  3. Real-time freight rate simulation (dynamic pricing)
#  4. Peak/off-peak price prediction
#  5. AI Parcel Scanning via Google Gemini Vision
#  6. Interactive Leaflet map with route polyline
#  7. All 6 providers ranked, cheapest highlighted
# ============================================================

import re, math, json, time, os, random, base64, requests
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

# ── Gemini API Key — set via HF Spaces Secret or env var ──
# Go to HF Spaces → Settings → Variables & Secrets → Add GEMINI_API_KEY
# NEVER hardcode a real key in production
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


# ════════════════════════════════════════════════════════════
# SECTION A — PROVIDER RATE CARDS
# Based on publicly available rate structures (2024-25)
# Real APIs require provider business accounts
# ════════════════════════════════════════════════════════════

TPL_PROVIDERS = {
    "Porter": {
        "color": "#FF6B35", "type": "Last-mile / Intracity",
        "modes": {
            "Bike":         {"base": 49,  "per_km": 8,   "max_kg": 20,   "max_km": 50},
            "Tata Ace":     {"base": 249, "per_km": 22,  "max_kg": 750,  "max_km": 200},
            "Pickup Truck": {"base": 699, "per_km": 35,  "max_kg": 2000, "max_km": 300},
        },
        "gst": 18, "rating": 4.3, "cod": True, "tracking": True,
        "coverage": "Tier-1 & 2 cities",
        "delivery_hrs": {"Bike": 2, "Tata Ace": 4, "Pickup Truck": 6},
        "peak_hours": [(8,11),(18,21)], "peak_mult": 1.35, "offpeak_mult": 0.85,
        "best_for": "Same-day intracity, B2B last-mile",
    },
    "Dunzo": {
        "color": "#00B4D8", "type": "Hyperlocal Quick Commerce",
        "modes": {
            "Bike":  {"base": 39, "per_km": 12, "max_kg": 20, "max_km": 15},
            "Cycle": {"base": 25, "per_km": 8,  "max_kg": 5,  "max_km": 8},
        },
        "gst": 18, "rating": 4.0, "cod": False, "tracking": True,
        "coverage": "10 metro cities",
        "delivery_hrs": {"Bike": 1, "Cycle": 1},
        "peak_hours": [(12,14),(19,22)], "peak_mult": 1.5, "offpeak_mult": 0.75,
        "best_for": "Hyperlocal <15km, groceries, documents",
    },
    "Borzo": {
        "color": "#7B2D8B", "type": "On-demand B2B Courier",
        "modes": {
            "Bike": {"base": 55,  "per_km": 10, "max_kg": 30,  "max_km": 80},
            "Car":  {"base": 120, "per_km": 18, "max_kg": 100, "max_km": 150},
            "Van":  {"base": 250, "per_km": 28, "max_kg": 500, "max_km": 200},
        },
        "gst": 18, "rating": 4.1, "cod": True, "tracking": True,
        "coverage": "25+ cities India",
        "delivery_hrs": {"Bike": 3, "Car": 4, "Van": 5},
        "peak_hours": [(9,12),(17,20)], "peak_mult": 1.25, "offpeak_mult": 0.90,
        "best_for": "B2B courier, multi-stop, parcels",
    },
    "Delhivery": {
        "color": "#E63946", "type": "Pan-India Surface & Air",
        "modes": {
            "Surface": {"base": 45,  "per_km": 5,  "max_kg": 5000, "max_km": 5000},
            "Express": {"base": 80,  "per_km": 9,  "max_kg": 500,  "max_km": 5000},
            "Air":     {"base": 150, "per_km": 25, "max_kg": 500,  "max_km": 5000},
        },
        "gst": 18, "rating": 4.2, "cod": True, "tracking": True,
        "coverage": "Pan India 18,000+ pincodes",
        "delivery_hrs": {"Surface": 72, "Express": 48, "Air": 24},
        "peak_hours": [(10,12)], "peak_mult": 1.08, "offpeak_mult": 0.95,
        "best_for": "Pan-India, e-commerce, heavy freight",
    },
    "Shiprocket": {
        "color": "#F4A261", "type": "Multi-carrier Aggregator",
        "modes": {
            "Economy":  {"base": 35, "per_km": 4,  "max_kg": 300, "max_km": 5000},
            "Standard": {"base": 55, "per_km": 7,  "max_kg": 500, "max_km": 5000},
            "Express":  {"base": 90, "per_km": 12, "max_kg": 300, "max_km": 5000},
        },
        "gst": 18, "rating": 4.0, "cod": True, "tracking": True,
        "coverage": "Pan India + International",
        "delivery_hrs": {"Economy": 96, "Standard": 72, "Express": 48},
        "peak_hours": [(9,11),(14,16)], "peak_mult": 1.12, "offpeak_mult": 0.88,
        "best_for": "Small business e-commerce, COD, aggregated rates",
    },
    "BlueDart": {
        "color": "#1D3557", "type": "Premium Express Courier",
        "modes": {
            "Priority":    {"base": 150, "per_km": 18, "max_kg": 100, "max_km": 5000},
            "Dart Apex":   {"base": 200, "per_km": 22, "max_kg": 200, "max_km": 5000},
            "Air Express": {"base": 350, "per_km": 45, "max_kg": 500, "max_km": 5000},
        },
        "gst": 18, "rating": 4.5, "cod": True, "tracking": True,
        "coverage": "Pan India + 220 countries",
        "delivery_hrs": {"Priority": 24, "Dart Apex": 36, "Air Express": 12},
        "peak_hours": [(9,10)], "peak_mult": 1.05, "offpeak_mult": 0.98,
        "best_for": "High-value, time-critical, premium parcels",
    },
}

CITY_COORDS = {
    "mumbai":(19.076,72.877),"delhi":(28.613,77.209),"bangalore":(12.971,77.594),
    "bengaluru":(12.971,77.594),"chennai":(13.082,80.270),"kolkata":(22.572,88.363),
    "hyderabad":(17.385,78.486),"pune":(18.520,73.856),"ahmedabad":(23.022,72.571),
    "surat":(21.170,72.831),"jaipur":(26.912,75.787),"lucknow":(26.846,80.946),
    "nagpur":(21.145,79.088),"nashik":(19.997,73.789),"indore":(22.719,75.857),
    "bhopal":(23.259,77.412),"chandigarh":(30.733,76.779),"coimbatore":(11.016,76.955),
    "kochi":(9.931,76.267),"visakhapatnam":(17.686,83.218),"new delhi":(28.613,77.209),
    "navi mumbai":(19.033,73.029),"thane":(19.218,72.978),"gurgaon":(28.459,77.026),
    "gurugram":(28.459,77.026),"noida":(28.535,77.391),"agra":(27.176,78.008),
    "vadodara":(22.307,73.181),"patna":(25.594,85.137),"guwahati":(26.144,91.736),
    "faridabad":(28.408,77.317),"andheri":(19.119,72.846),"bandra":(19.054,72.819),
    "powai":(19.116,72.905),"worli":(19.011,72.817),"dadar":(19.018,72.841),
    "hinjewadi":(18.591,73.738),"kharadi":(18.553,73.944),"hadapsar":(18.502,73.926),
    "whitefield":(12.969,77.750),"electronic city":(12.839,77.676),
    "salt lake":(22.579,88.418),"rajarhat":(22.618,88.468),
    "gachibowli":(17.440,78.348),"hitech city":(17.449,78.381),
}


# ════════════════════════════════════════════════════════════
# SECTION B — GEOCODING & REAL ROAD DISTANCE
# ════════════════════════════════════════════════════════════

def geocode_address(address: str) -> dict:
    """Geocodes address. Tries local dict first, then Nominatim API."""
    result = {"lat": None, "lon": None, "display": address, "found": False, "city": ""}

    addr_lower = address.lower().strip()

    # Local lookup — fastest
    for city, coords in CITY_COORDS.items():
        if city in addr_lower:
            result.update({"lat": coords[0], "lon": coords[1],
                           "display": address.title(), "found": True, "city": city.title()})
            return result

    # Nominatim API
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address + ", India", "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "AllworkssBI/2.0"},
            timeout=8,
        )
        if resp.status_code == 200 and resp.json():
            d = resp.json()[0]
            addr_comp = d.get("address", {})
            city_name = addr_comp.get("city") or addr_comp.get("town") or addr_comp.get("state", "")
            result.update({
                "lat": float(d["lat"]), "lon": float(d["lon"]),
                "display": d.get("display_name", address),
                "found": True, "city": city_name,
            })
    except Exception:
        pass

    return result


def get_road_distance_osrm(lat1, lon1, lat2, lon2) -> dict:
    """
    Gets real road distance and duration using OSRM (free routing API).
    Falls back to Haversine estimate if API fails.
    """
    result = {"distance_km": None, "duration_min": None, "source": "estimate"}

    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        resp = requests.get(url, params={"overview": "false"}, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                result.update({
                    "distance_km": round(route["distance"] / 1000, 1),
                    "duration_min": round(route["duration"] / 60, 0),
                    "source": "osrm_real",
                })
                return result
    except Exception:
        pass

    # Haversine fallback with road factor
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    straight_km = R * 2 * math.asin(math.sqrt(a))

    factor = 1.5 if straight_km < 10 else 1.35 if straight_km < 50 else 1.25 if straight_km < 200 else 1.20
    road_km = round(straight_km * factor, 1)
    result.update({
        "distance_km": road_km,
        "duration_min": round(road_km / 40 * 60, 0),
        "source": "haversine_estimate",
    })
    return result


def get_route_polyline_osrm(lat1, lon1, lat2, lon2) -> list:
    """Gets actual road route coordinates from OSRM for map display."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        resp = requests.get(url, params={"overview": "full", "geometries": "geojson"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                coords = data["routes"][0]["geometry"]["coordinates"]
                # OSRM returns [lon, lat] — Leaflet needs [lat, lon]
                return [[c[1], c[0]] for c in coords]
    except Exception:
        pass
    # Fallback: straight line
    return [[lat1, lon1], [lat2, lon2]]


# ════════════════════════════════════════════════════════════
# SECTION C — DYNAMIC RATE CALCULATOR
# Real-time pricing with peak/off-peak prediction
# ════════════════════════════════════════════════════════════

def is_peak(peak_hours: list, hour: int) -> bool:
    return any(s <= hour < e for s, e in peak_hours)


def calc_provider_rates(name: str, distance_km: float, weight_kg: float) -> list:
    """
    Calculates rates for all eligible modes of a provider.
    Includes peak/off-peak multipliers, GST, weight surcharge.
    Returns sorted list of mode options.
    """
    card = TPL_PROVIDERS[name]
    now_hour = datetime.now().hour
    peak = is_peak(card["peak_hours"], now_hour)
    mult = card["peak_mult"] if peak else card["offpeak_mult"]

    options = []
    for mode, specs in card["modes"].items():
        if weight_kg > specs["max_kg"]: continue
        if distance_km > specs["max_km"]: continue

        base_fare = specs["base"] + specs["per_km"] * distance_km

        # Weight surcharge: +Rs.3/kg above 5kg
        wt_surcharge = max(0, (weight_kg - 5)) * 3.0

        # Time-based dynamic pricing
        cost_before_gst = (base_fare + wt_surcharge) * mult

        # Add micro-randomness to simulate dynamic pricing (±2%)
        random.seed(int(time.time() / 300))  # changes every 5 min
        noise = random.uniform(0.98, 1.02)
        cost_before_gst *= noise

        gst_amt = cost_before_gst * (card["gst"] / 100)
        total   = round(cost_before_gst + gst_amt, 0)

        # Off-peak price prediction
        offpeak_base = (base_fare + wt_surcharge) * card["offpeak_mult"]
        offpeak_gst  = offpeak_base * (card["gst"] / 100)
        offpeak_total = round(offpeak_base + offpeak_gst, 0)

        # Peak price (for showing savings opportunity)
        peak_base  = (base_fare + wt_surcharge) * card["peak_mult"]
        peak_total = round(peak_base * (1 + card["gst"]/100), 0)

        savings_if_wait = round(total - offpeak_total, 0) if peak else 0

        # Find next off-peak window
        next_offpeak = ""
        if peak:
            current_h = now_hour
            for h in range(current_h + 1, current_h + 12):
                h_mod = h % 24
                if not is_peak(card["peak_hours"], h_mod):
                    next_offpeak = f"{h_mod:02d}:00"
                    break

        options.append({
            "mode":         mode,
            "total":        int(total),
            "base_fare":    round(base_fare, 0),
            "gst":          round(gst_amt, 0),
            "is_peak":      peak,
            "offpeak_price":int(offpeak_total),
            "peak_price":   int(peak_total),
            "savings_wait": int(savings_if_wait),
            "next_offpeak": next_offpeak,
            "delivery_hrs": card["delivery_hrs"].get(mode, 24),
            "max_kg":       specs["max_kg"],
            "max_km":       specs["max_km"],
        })

    return sorted(options, key=lambda x: x["total"])


def scan_all_providers(distance_km: float, weight_kg: float) -> list:
    """Scans all 6 providers, returns ranked results."""
    results = []

    for name, card in TPL_PROVIDERS.items():
        modes = calc_provider_rates(name, distance_km, weight_kg)

        if not modes:
            # Check why — weight or distance limit
            all_modes = card["modes"]
            max_kg_any = max(s["max_kg"] for s in all_modes.values())
            max_km_any = max(s["max_km"] for s in all_modes.values())
            reason = (
                f"Exceeds max weight ({max_kg_any}kg)" if weight_kg > max_kg_any
                else f"Exceeds max distance ({max_km_any}km)" if distance_km > max_km_any
                else "Not available for this route"
            )
            results.append({
                "provider": name, "color": card["color"],
                "available": False, "reason": reason,
                "best_total": 999999,
            })
            continue

        best = modes[0]
        results.append({
            "provider":   name,
            "color":      card["color"],
            "type":       card["type"],
            "available":  True,
            "best_mode":  best["mode"],
            "best_total": best["total"],
            "best_gst":   best["gst"],
            "is_peak":    best["is_peak"],
            "savings":    best["savings_wait"],
            "next_offpeak": best["next_offpeak"],
            "offpeak_price": best["offpeak_price"],
            "delivery_hrs": best["delivery_hrs"],
            "rating":     card["rating"],
            "cod":        card["cod"],
            "tracking":   card["tracking"],
            "coverage":   card["coverage"],
            "best_for":   card["best_for"],
            "all_modes":  modes,
        })

    results.sort(key=lambda x: (not x["available"], x["best_total"]))
    return results


# ════════════════════════════════════════════════════════════
# SECTION D — GEMINI PARCEL SCANNER
# ════════════════════════════════════════════════════════════

def scan_parcel_gemini(image_path: str) -> dict:
    """
    Uses Google Gemini 1.5 Flash to estimate parcel dimensions/weight
    from an uploaded photo.
    """
    result = {
        "success": False, "weight_kg": None,
        "length_cm": None, "width_cm": None, "height_cm": None,
        "parcel_type": None, "description": None,
        "confidence": None, "error": None,
    }

    api_key = GEMINI_API_KEY
    if not api_key:
        result["error"] = "GEMINI_API_KEY not set. Add it in HF Spaces Secrets."
        return result

    if not image_path:
        result["error"] = "No image provided."
        return result

    try:
        path = Path(image_path)
        ext  = path.suffix.lower()
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        mime_map = {".jpg":"image/jpeg",".jpeg":"image/jpeg",
                    ".png":"image/png",".webp":"image/webp",".gif":"image/gif"}
        mime = mime_map.get(ext, "image/jpeg")

        prompt = (
            "You are a logistics AI assistant. Analyze this parcel/package image carefully. "
            "Estimate the shipping weight, dimensions, and parcel type. "
            "Consider typical item sizes relative to any visible reference objects. "
            "Respond ONLY in this exact JSON (no markdown, no extra text):\n"
            '{"weight_kg":0.5,"length_cm":30,"width_cm":20,"height_cm":15,'
            '"parcel_type":"box","description":"Small cardboard box",'
            '"confidence":"medium","fragile":false}'
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": img_b64}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200},
        }

        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            raw  = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            raw  = re.sub(r"```json|```", "", raw).strip()
            parsed = json.loads(raw)
            result.update({
                "success":     True,
                "weight_kg":   float(parsed.get("weight_kg", 1.0)),
                "length_cm":   float(parsed.get("length_cm", 30)),
                "width_cm":    float(parsed.get("width_cm", 20)),
                "height_cm":   float(parsed.get("height_cm", 15)),
                "parcel_type": parsed.get("parcel_type", "box"),
                "description": parsed.get("description", ""),
                "confidence":  parsed.get("confidence", "medium"),
                "fragile":     parsed.get("fragile", False),
            })
        elif resp.status_code == 400:
            result["error"] = "Invalid API key or request. Check GEMINI_API_KEY."
        elif resp.status_code == 429:
            result["error"] = "Gemini rate limit hit. Try again in a moment."
        else:
            result["error"] = f"Gemini API error {resp.status_code}: {resp.text[:200]}"

    except json.JSONDecodeError:
        result["error"] = "AI returned unexpected format. Try again."
    except FileNotFoundError:
        result["error"] = "Image file not found."
    except Exception as e:
        result["error"] = str(e)

    return result


# ════════════════════════════════════════════════════════════
# SECTION E — INTERACTIVE MAP (Leaflet + OSRM route)
# ════════════════════════════════════════════════════════════

def generate_map_html(
    p_lat, p_lon, p_name,
    d_lat, d_lon, d_name,
    distance_km, duration_min, route_coords, source
) -> str:
    """Generates Leaflet map HTML with real road route polyline."""

    center_lat = (p_lat + d_lat) / 2
    center_lon = (p_lon + d_lon) / 2
    zoom = 13 if distance_km < 10 else 11 if distance_km < 50 else 9 if distance_km < 200 else 7 if distance_km < 500 else 6

    # Build JS array of route coordinates
    coords_js = json.dumps(route_coords)

    dist_source = "Real road distance (OSRM)" if source == "osrm_real" else "Estimated road distance"
    duration_str = f"{int(duration_min // 60)}h {int(duration_min % 60)}m" if duration_min >= 60 else f"{int(duration_min)}m"

    return f"""
<div style="border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;margin-bottom:16px;font-family:system-ui,sans-serif;">
  <div style="background:#1a1a1a;padding:10px 16px;display:flex;justify-content:space-between;
              align-items:center;flex-wrap:wrap;gap:8px;">
    <span style="font-size:13px;font-weight:600;color:#e0e0e0;">Route Map</span>
    <div style="display:flex;gap:16px;flex-wrap:wrap;">
      <span style="font-size:12px;color:#2ECC71;font-weight:600;">{distance_km} km</span>
      <span style="font-size:12px;color:#888;">{duration_str} drive</span>
      <span style="font-size:11px;color:#555;">{dist_source}</span>
    </div>
  </div>
  <div id="aw-routemap" style="height:360px;width:100%;background:#0d0d0d;"></div>
  <div style="background:#111;padding:8px 16px;display:flex;gap:16px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:#888;">
      <div style="width:10px;height:10px;border-radius:50%;background:#2ECC71;"></div>
      {p_name}
    </div>
    <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:#888;">
      <div style="width:10px;height:10px;border-radius:50%;background:#E74C3C;"></div>
      {d_name}
    </div>
  </div>
</div>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function() {{
  var routeCoords = {coords_js};

  function buildMap() {{
    if (typeof L === 'undefined') {{ setTimeout(buildMap, 400); return; }}
    var el = document.getElementById('aw-routemap');
    if (!el) {{ setTimeout(buildMap, 400); return; }}
    if (el._leaflet_id) {{
      try {{ window._awMap && window._awMap.invalidateSize(); }} catch(e) {{}}
      return;
    }}

    var map = L.map('aw-routemap', {{zoomControl:true, preferCanvas:true}})
                .setView([{center_lat}, {center_lon}], {zoom});
    window._awMap = map;

    // OpenStreetMap tiles - universally supported
    L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
      crossOrigin: true,
    }}).addTo(map);

    // Draw route polyline
    var routeLine = L.polyline(routeCoords, {{
      color: '#1D9E75', weight: 4, opacity: 0.9,
      dashArray: routeCoords.length <= 2 ? '8 5' : null,
    }}).addTo(map);

    // Pickup marker
    var pickupIcon = L.divIcon({{
      html: '<div style="background:#2ECC71;width:14px;height:14px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.8);"></div>',
      iconSize:[14,14], iconAnchor:[7,7], className:'',
    }});
    L.marker([{p_lat},{p_lon}], {{icon:pickupIcon}})
      .addTo(map)
      .bindPopup('<b style="color:#2ECC71;">PICK-UP</b><br>{p_name}')
      .openPopup();

    // Dropoff marker
    var dropIcon = L.divIcon({{
      html: '<div style="background:#E74C3C;width:14px;height:14px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.8);"></div>',
      iconSize:[14,14], iconAnchor:[7,7], className:'',
    }});
    L.marker([{d_lat},{d_lon}], {{icon:dropIcon}})
      .addTo(map)
      .bindPopup('<b style="color:#E74C3C;">DROP-OFF</b><br>{d_name}');

    // Fit map to route
    map.fitBounds(routeLine.getBounds(), {{padding:[30,30]}});
  }}

  setTimeout(buildMap, 1200);
}})();
</script>
"""


# ════════════════════════════════════════════════════════════
# SECTION F — RATE COMPARISON HTML
# ════════════════════════════════════════════════════════════

def format_rates_html(results, pickup, dropoff, distance_km, weight_kg, duration_min) -> str:
    """Builds the full rate comparison card HTML."""
    now_str    = datetime.now().strftime("%I:%M %p, %d %b %Y")
    available  = [r for r in results if r["available"]]
    unavailable= [r for r in results if not r["available"]]
    duration_str = f"{int(duration_min//60)}h {int(duration_min%60)}m" if duration_min >= 60 else f"{int(duration_min)}m"

    html = f"""
<div style="font-family:system-ui,sans-serif;">

<!-- Route Summary -->
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px;">
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;">
    <div style="font-size:9px;color:#555;letter-spacing:0.07em;margin-bottom:6px;">PICK-UP</div>
    <div style="font-size:12px;color:#2ECC71;font-weight:500;">{pickup}</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;">
    <div style="font-size:9px;color:#555;letter-spacing:0.07em;margin-bottom:6px;">DROP-OFF</div>
    <div style="font-size:12px;color:#E74C3C;font-weight:500;">{dropoff}</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:24px;font-weight:800;color:#2ECC71;">{distance_km}</div>
    <div style="font-size:10px;color:#555;">km road</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:18px;font-weight:700;color:#e0e0e0;">{duration_str}</div>
    <div style="font-size:10px;color:#555;">drive time</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:14px;font-weight:600;color:#e0e0e0;">{weight_kg} kg</div>
    <div style="font-size:10px;color:#555;">shipment</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;">
    <div style="font-size:9px;color:#555;letter-spacing:0.07em;margin-bottom:4px;">SCANNED</div>
    <div style="font-size:11px;color:#888;">{now_str}</div>
  </div>
</div>
"""

    if not available:
        return html + "<div style='color:#E74C3C;padding:20px;text-align:center;'>No providers available for this route and weight.</div></div>"

    cheapest = available[0]

    # Cheapest highlight banner
    savings_info = ""
    if cheapest.get("savings", 0) > 0:
        savings_info = f'<div style="font-size:11px;color:#F39C12;margin-top:4px;">Currently PEAK — wait until {cheapest["next_offpeak"]} to save Rs.{cheapest["savings"]:,.0f}</div>'
    elif cheapest.get("savings", 0) == 0 and not cheapest.get("is_peak"):
        savings_info = '<div style="font-size:11px;color:#2ECC71;margin-top:4px;">Off-peak discount applied</div>'

    html += f"""
<div style="background:linear-gradient(135deg,#0a1f14,#112b1a);border:2px solid #2ECC71;
            border-radius:12px;padding:16px;margin-bottom:14px;">
  <div style="font-size:9px;color:#2ECC71;font-weight:700;letter-spacing:0.1em;margin-bottom:10px;">
    CHEAPEST OPTION — AUTOMATICALLY IDENTIFIED
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
    <div>
      <div style="font-size:20px;font-weight:700;color:{cheapest['color']};">{cheapest['provider']}</div>
      <div style="font-size:12px;color:#888;margin-top:2px;">{cheapest['type']} &mdash; {cheapest['best_mode']}</div>
      <div style="font-size:11px;color:#555;margin-top:3px;">{cheapest['best_for']}</div>
      {savings_info}
    </div>
    <div style="text-align:right;">
      <div style="font-size:34px;font-weight:800;color:#2ECC71;">Rs.{cheapest['best_total']:,}</div>
      <div style="font-size:11px;color:#555;">incl. 18% GST</div>
      <div style="font-size:12px;color:#888;margin-top:4px;">{cheapest['delivery_hrs']}h delivery</div>
    </div>
  </div>
</div>

<div style="font-size:10px;color:#444;letter-spacing:0.07em;margin-bottom:10px;">
  ALL {len(available)} PROVIDERS — RANKED BY PRICE (INCL. GST, REAL-TIME RATES)
</div>
"""

    # All providers
    for i, r in enumerate(available):
        is_best = i == 0
        border  = "2px solid #2ECC71" if is_best else "1px solid #1e1e1e"
        bg      = "#0d1a12" if is_best else "#141414"
        rank_badge = f'<span style="background:#2ECC71;color:#000;font-size:9px;padding:2px 6px;border-radius:8px;font-weight:700;margin-left:6px;">#1 CHEAPEST</span>' if is_best else f'<span style="font-size:11px;color:#444;margin-left:4px;">#{i+1}</span>'

        # Peak/off-peak indicator
        timing_html = ""
        if r.get("is_peak"):
            timing_html = f'<span style="background:#3a2000;color:#F39C12;font-size:10px;padding:2px 7px;border-radius:8px;margin-left:4px;">PEAK HOUR</span>'
            if r.get("savings", 0) > 0:
                timing_html += f'<div style="font-size:11px;color:#F39C12;margin-top:5px;">Save Rs.{r["savings"]:,} after {r["next_offpeak"]}</div>'
        else:
            timing_html = '<span style="background:#0d2a1a;color:#2ECC71;font-size:10px;padding:2px 7px;border-radius:8px;margin-left:4px;">OFF-PEAK</span>'

        # Mode options
        modes_html = ""
        if r.get("all_modes"):
            modes_html = '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;">'
            for m in r["all_modes"]:
                mc = "#2ECC71" if m == r["all_modes"][0] else "#444"
                mb = "#0d2a1a" if m == r["all_modes"][0] else "#1a1a1a"
                modes_html += f'<div style="background:{mb};border:1px solid {mc};border-radius:6px;padding:4px 9px;font-size:11px;"><span style="color:{mc};font-weight:500;">{m["mode"]}</span><span style="color:#666;margin-left:5px;">Rs.{m["total"]:,}</span><span style="color:#444;margin-left:5px;">{m["delivery_hrs"]}h</span></div>'
            modes_html += '</div>'

        html += f"""
<div style="background:{bg};border:{border};border-radius:8px;padding:12px 14px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">
    <div style="flex:1;min-width:160px;">
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:4px;">
        <span style="font-size:15px;font-weight:600;color:{r['color']};">{r['provider']}</span>
        {rank_badge}{timing_html}
      </div>
      <div style="font-size:11px;color:#666;">{r['type']}</div>
      <div style="font-size:11px;color:#444;margin-top:2px;">{r['best_for']}</div>
      {modes_html}
    </div>
    <div style="text-align:right;flex-shrink:0;">
      <div style="font-size:24px;font-weight:700;color:#e0e0e0;">Rs.{r['best_total']:,}</div>
      <div style="font-size:10px;color:#444;">GST Rs.{r['best_gst']:,}</div>
      <div style="display:flex;gap:12px;justify-content:flex-end;margin-top:8px;flex-wrap:wrap;">
        <div style="text-align:center;">
          <div style="font-size:13px;color:#e0e0e0;">{r['delivery_hrs']}h</div>
          <div style="font-size:9px;color:#444;">DELIVERY</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:12px;color:#aaa;">{"⭐"*int(r['rating'])}{r['rating']}</div>
          <div style="font-size:9px;color:#444;">RATING</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:12px;color:{'#2ECC71' if r['cod'] else '#444'};">{"COD" if r["cod"] else "No COD"}</div>
          <div style="font-size:9px;color:#444;">PAYMENT</div>
        </div>
      </div>
    </div>
  </div>
</div>"""

    if unavailable:
        html += '<div style="font-size:10px;color:#333;letter-spacing:0.07em;margin:12px 0 6px;">NOT AVAILABLE</div>'
        for r in unavailable:
            html += f'<div style="background:#111;border:1px solid #1a1a1a;border-radius:6px;padding:8px 12px;margin-bottom:5px;display:flex;justify-content:space-between;font-size:11px;"><span style="color:{r["color"]};">{r["provider"]}</span><span style="color:#333;">{r["reason"]}</span></div>'

    html += "</div>"
    return html


# ════════════════════════════════════════════════════════════
# SECTION G — PARCEL SCAN HTML
# ════════════════════════════════════════════════════════════

def format_parcel_scan_html(scan: dict) -> str:
    if not scan:
        return ""

    if not scan["success"]:
        return f"""
<div style="background:#1a0d0d;border:1px solid #E74C3C;border-radius:8px;padding:12px;
            margin-bottom:14px;font-family:system-ui,sans-serif;">
  <div style="font-size:11px;color:#E74C3C;font-weight:600;margin-bottom:4px;">Parcel Scan Error</div>
  <div style="font-size:12px;color:#888;">{scan['error']}</div>
  <div style="font-size:11px;color:#555;margin-top:6px;">Tip: Add GEMINI_API_KEY in HF Spaces Settings → Secrets</div>
</div>"""

    conf_color = "#2ECC71" if scan["confidence"]=="high" else "#F39C12" if scan["confidence"]=="medium" else "#E74C3C"
    fragile_badge = '<span style="background:#3a0a0a;color:#E74C3C;font-size:10px;padding:2px 7px;border-radius:6px;margin-left:8px;">FRAGILE</span>' if scan.get("fragile") else ""

    return f"""
<div style="background:#0d1a0d;border:1px solid #2ECC71;border-radius:10px;padding:14px;
            margin-bottom:14px;font-family:system-ui,sans-serif;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <div style="font-size:11px;color:#2ECC71;font-weight:700;letter-spacing:0.08em;">
      GEMINI AI PARCEL SCAN
    </div>
    <div>
      <span style="background:#0d2a1a;color:{conf_color};font-size:10px;padding:2px 8px;border-radius:6px;">{scan['confidence'].upper()} CONFIDENCE</span>
      {fragile_badge}
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px;margin-bottom:10px;">
    <div style="background:#111;border-radius:6px;padding:10px;text-align:center;">
      <div style="font-size:22px;font-weight:800;color:#2ECC71;">{scan['weight_kg']}</div>
      <div style="font-size:10px;color:#555;">kg weight</div>
    </div>
    <div style="background:#111;border-radius:6px;padding:10px;text-align:center;">
      <div style="font-size:14px;font-weight:600;color:#e0e0e0;">{scan['length_cm']}cm</div>
      <div style="font-size:10px;color:#555;">length</div>
    </div>
    <div style="background:#111;border-radius:6px;padding:10px;text-align:center;">
      <div style="font-size:14px;font-weight:600;color:#e0e0e0;">{scan['width_cm']}cm</div>
      <div style="font-size:10px;color:#555;">width</div>
    </div>
    <div style="background:#111;border-radius:6px;padding:10px;text-align:center;">
      <div style="font-size:14px;font-weight:600;color:#e0e0e0;">{scan['height_cm']}cm</div>
      <div style="font-size:10px;color:#555;">height</div>
    </div>
    <div style="background:#111;border-radius:6px;padding:10px;text-align:center;">
      <div style="font-size:14px;font-weight:600;color:#e0e0e0;">{scan['parcel_type'].title()}</div>
      <div style="font-size:10px;color:#555;">type</div>
    </div>
  </div>
  <div style="font-size:12px;color:#777;">AI: {scan['description']}</div>
  <div style="font-size:11px;color:#444;margin-top:5px;">Weight pre-filled from scan. Override manually if needed.</div>
</div>"""


# ════════════════════════════════════════════════════════════
# SECTION H — MASTER HANDLER (Gradio entry point)
# ════════════════════════════════════════════════════════════

def run_logistics_router(
    pickup_addr: str,
    dropoff_addr: str,
    weight_kg: float,
    parcel_image,
) -> tuple:
    """
    Returns (parcel_html, map_html, rates_html, weight_out)
    """
    # ── Step 1: Parcel image scan ──
    scan_result = None
    parcel_html = ""
    if parcel_image is not None:
        filepath = parcel_image.name if hasattr(parcel_image, "name") else str(parcel_image)
        scan_result = scan_parcel_gemini(filepath)
        parcel_html = format_parcel_scan_html(scan_result)
        if scan_result and scan_result["success"]:
            weight_kg = scan_result["weight_kg"]  # override with AI estimate

    # ── Step 2: Validate ──
    if not pickup_addr or not pickup_addr.strip():
        return parcel_html, "", "<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Please enter a pick-up address.</div>", weight_kg

    if not dropoff_addr or not dropoff_addr.strip():
        return parcel_html, "", "<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Please enter a drop-off address.</div>", weight_kg

    if not weight_kg or weight_kg <= 0:
        weight_kg = 1.0

    # ── Step 3: Geocode ──
    pickup  = geocode_address(pickup_addr)
    dropoff = geocode_address(dropoff_addr)

    if not pickup["found"]:
        return parcel_html, "", f"<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Could not locate: <b>{pickup_addr}</b>. Try adding city name (e.g. Andheri Mumbai).</div>", weight_kg

    if not dropoff["found"]:
        return parcel_html, "", f"<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Could not locate: <b>{dropoff_addr}</b>. Try adding city name (e.g. Hinjewadi Pune).</div>", weight_kg

    # ── Step 4: Real road distance ──
    road = get_road_distance_osrm(pickup["lat"], pickup["lon"], dropoff["lat"], dropoff["lon"])
    distance_km  = road["distance_km"]
    duration_min = road["duration_min"] or (distance_km / 40 * 60)

    # ── Step 5: Route polyline ──
    route_coords = get_route_polyline_osrm(pickup["lat"], pickup["lon"], dropoff["lat"], dropoff["lon"])

    # ── Step 6: Map ──
    map_html = generate_map_html(
        pickup["lat"], pickup["lon"], pickup_addr.title(),
        dropoff["lat"], dropoff["lon"], dropoff_addr.title(),
        distance_km, duration_min, route_coords, road["source"],
    )

    # ── Step 7: Scan providers & compare ──
    results   = scan_all_providers(distance_km, weight_kg)
    rates_html = format_rates_html(
        results, pickup_addr.title(), dropoff_addr.title(),
        distance_km, weight_kg, duration_min,
    )

    return parcel_html, map_html, rates_html, weight_kg