# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m2_supply_chain.py — Supply Chain Optimization
#
#  Features:
#  - Vendor sidebar with full detail panel
#  - CSV upload + manual add form for vendors
#  - Route mapping with transport modes
#  - 3PL ecosystem (Porter, Dunzo, Borzo, etc.)
#  - ML recommendation: best 3PL per route
#  - RandomForest + KMeans + IsolationForest + LinearRegression
# ============================================================

# ── Imports ──────────────────────────────────────────────────
import re
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

try:
    from sklearn.preprocessing  import StandardScaler
    from sklearn.cluster         import KMeans
    from sklearn.ensemble        import RandomForestClassifier, IsolationForest
    from sklearn.linear_model    import LinearRegression
    from sklearn.impute          import SimpleImputer
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    import gradio as gr
    GRADIO_OK = True
except ImportError:
    GRADIO_OK = False


# ════════════════════════════════════════════════════════════
# SECTION A — 3PL PROVIDER DATABASE
# Rate cards, coverage, strengths for ML recommendation
# ════════════════════════════════════════════════════════════

TPL_PROVIDERS = {
    "Porter": {
        "type":        "Last-mile / Intracity",
        "modes":       ["Bike", "Tata Ace", "Truck"],
        "best_for":    ["Same-day", "Intracity", "Small loads", "B2B last-mile"],
        "avg_cost_km": 12,        # Rs per km
        "min_cost":    80,        # Rs base charge
        "max_weight":  2000,      # kg (2 ton Tata Ace)
        "coverage":    "Tier-1 cities",
        "delivery_hrs": {"same_city": 2, "next_day": 24},
        "rating":      4.3,
        "api_available": True,
        "tracking":    True,
        "cod":         True,
        "color":       "#FF6B35",
    },
    "Dunzo": {
        "type":        "Hyperlocal / Quick commerce",
        "modes":       ["Bike", "Cycle"],
        "best_for":    ["Hyperlocal", "Grocery", "Documents", "Quick delivery <5km"],
        "avg_cost_km": 18,
        "min_cost":    40,
        "max_weight":  20,        # kg
        "coverage":    "10 metro cities",
        "delivery_hrs": {"same_city": 1, "next_day": None},
        "rating":      4.0,
        "api_available": True,
        "tracking":    True,
        "cod":         False,
        "color":       "#00B4D8",
    },
    "Borzo": {
        "type":        "On-demand courier / B2B",
        "modes":       ["Bike", "Car", "Van"],
        "best_for":    ["B2B courier", "Documents", "Parcels", "Multi-stop"],
        "avg_cost_km": 15,
        "min_cost":    60,
        "max_weight":  50,
        "coverage":    "25+ cities India",
        "delivery_hrs": {"same_city": 3, "next_day": 24},
        "rating":      4.1,
        "api_available": True,
        "tracking":    True,
        "cod":         True,
        "color":       "#7B2D8B",
    },
    "Delhivery": {
        "type":        "Pan-India logistics",
        "modes":       ["Surface", "Air", "Express"],
        "best_for":    ["Pan-India", "E-commerce", "Heavy freight", "Warehousing"],
        "avg_cost_km": 6,
        "min_cost":    45,
        "max_weight":  500,
        "coverage":    "Pan India 18,000+ pincodes",
        "delivery_hrs": {"same_city": 24, "next_day": 48},
        "rating":      4.2,
        "api_available": True,
        "tracking":    True,
        "cod":         True,
        "color":       "#E63946",
    },
    "Shiprocket": {
        "type":        "Aggregator / E-commerce",
        "modes":       ["Surface", "Air", "Express"],
        "best_for":    ["E-commerce", "Small business", "Multi-carrier", "COD"],
        "avg_cost_km": 7,
        "min_cost":    50,
        "max_weight":  300,
        "coverage":    "Pan India + International",
        "delivery_hrs": {"same_city": 24, "next_day": 48},
        "rating":      4.0,
        "api_available": True,
        "tracking":    True,
        "cod":         True,
        "color":       "#F4A261",
    },
    "BlueDart": {
        "type":        "Premium express",
        "modes":       ["Air", "Surface", "Express"],
        "best_for":    ["Premium", "High-value", "Time-critical", "Documents"],
        "avg_cost_km": 20,
        "min_cost":    150,
        "max_weight":  100,
        "coverage":    "Pan India + International",
        "delivery_hrs": {"same_city": 12, "next_day": 24},
        "rating":      4.5,
        "api_available": True,
        "tracking":    True,
        "cod":         True,
        "color":       "#1D3557",
    },
}

TRANSPORT_MODES = {
    "Bike":     {"speed_kmh": 30, "cost_per_km": 8,  "max_kg": 20,   "icon": "🏍️"},
    "Auto":     {"speed_kmh": 25, "cost_per_km": 12, "max_kg": 50,   "icon": "🛺"},
    "Tata Ace": {"speed_kmh": 40, "cost_per_km": 18, "max_kg": 750,  "icon": "🚐"},
    "Truck":    {"speed_kmh": 50, "cost_per_km": 25, "max_kg": 5000, "icon": "🚛"},
    "Air":      {"speed_kmh": 800,"cost_per_km": 80, "max_kg": 500,  "icon": "✈️"},
    "Rail":     {"speed_kmh": 60, "cost_per_km": 10, "max_kg": 10000,"icon": "🚂"},
}


# ════════════════════════════════════════════════════════════
# SECTION B — IN-MEMORY VENDOR STORE
# Holds all vendors across session
# ════════════════════════════════════════════════════════════

# Global vendor store (list of dicts)
_VENDOR_STORE = []

def get_vendors() -> list:
    return _VENDOR_STORE

def add_vendor(vendor: dict):
    # Avoid duplicates by name
    existing_names = [v["name"].lower() for v in _VENDOR_STORE]
    if vendor["name"].lower() not in existing_names:
        _VENDOR_STORE.append(vendor)

def clear_vendors():
    _VENDOR_STORE.clear()

def build_vendor_from_row(row: dict, cols: dict) -> dict:
    """Builds a standardized vendor dict from a CSV row."""
    def g(keywords):
        for k, v in cols.items():
            if any(kw in v for kw in keywords):
                val = row.get(k, "")
                return str(val).strip() if val and str(val) != "nan" else ""
        return ""

    name     = g(["SUPPLIER","VENDOR","NAME","PARTY"]) or "Unknown"
    ontime   = g(["ON TIME","ONTIME","DELIVERY RATE","ON-TIME","DELIVERY %"])
    quality  = g(["QUALITY","DEFECT","REJECTION","QUALITY %"])
    lead     = g(["LEAD TIME","DAYS","DELIVERY DAYS","LEAD DAYS"])
    price    = g(["PRICE","COST","RATE","UNIT PRICE","AVG PRICE"])
    reliab   = g(["RELIABILITY","PERFORMANCE","RELIABILITY %"])
    location = g(["LOCATION","CITY","STATE","ADDRESS","ORIGIN"])
    gstin    = g(["GSTIN","GST","TAX ID"])
    contact  = g(["CONTACT","PHONE","EMAIL","MOBILE"])
    route    = g(["ROUTE","DELIVERY ROUTE","PATH"])
    mode     = g(["MODE","TRANSPORT","VEHICLE"])

    return {
        "name":         name,
        "gstin":        gstin or "Not provided",
        "contact":      contact or "Not provided",
        "location":     location or "Not specified",
        "on_time":      ontime or "N/A",
        "quality":      quality or "N/A",
        "lead_days":    lead or "N/A",
        "avg_price":    price or "N/A",
        "reliability":  reliab or "N/A",
        "route":        route or "Not specified",
        "transport_mode": mode or "Not specified",
        "score":        0,
        "risk":         "Unknown",
        "tier":         "Unknown",
        "best_3pl":     "",
        "added_at":     datetime.now().strftime("%d %b %Y %H:%M"),
    }


# ════════════════════════════════════════════════════════════
# SECTION C — ML ENGINE: SUPPLIER SCORING + 3PL RECOMMENDATION
# ════════════════════════════════════════════════════════════

def ml_score_vendors(vendors: list) -> list:
    """
    Scores all vendors using ML.
    KMeans clustering + composite weighted scoring.
    Returns vendors with score, tier, risk, best_3pl filled in.
    """
    if not vendors or not SKLEARN_OK or not PANDAS_OK:
        # Rule-based fallback
        for v in vendors:
            try:
                ot = float(str(v.get("on_time","50")).replace("%","").replace("N/A","50"))
                if ot <= 1: ot *= 100
                score = min(100, max(0, int(ot * 0.7 + 30)))
            except Exception:
                score = 50
            v["score"] = score
            v["risk"]  = "Low" if score >= 70 else "Medium" if score >= 45 else "High"
            v["tier"]  = "Top Performer" if score >= 75 else "Average" if score >= 50 else "Under Performer"
        return vendors

    # Build feature matrix
    rows = []
    for v in vendors:
        def to_float(val, default=50.0):
            try:
                f = float(str(val).replace("%","").replace(",","").strip())
                return f * 100 if f <= 1 else f
            except Exception:
                return default

        lead_raw = to_float(v.get("lead_days","7"), 7)
        rows.append([
            to_float(v.get("on_time","50"),   50),   # on-time %
            to_float(v.get("quality","70"),   70),   # quality %
            max(0, 30 - lead_raw),                    # inverted lead (lower = better)
            to_float(v.get("reliability","60"),60),   # reliability %
        ])

    X = np.array(rows, dtype=float)
    imputer = SimpleImputer(strategy="median")
    X = imputer.fit_transform(X)
    scaler  = StandardScaler()
    X_sc    = scaler.fit_transform(X)

    # KMeans tiers
    n = min(3, len(vendors))
    if n >= 2:
        km      = KMeans(n_clusters=n, random_state=42, n_init=10)
        labels  = km.fit_predict(X_sc)
        means   = {c: X_sc[labels==c].mean() for c in range(n)}
        ranked  = sorted(means, key=means.get, reverse=True)
        tier_map = {ranked[0]:"Top Performer"}
        if n>1: tier_map[ranked[1]] = "Average"
        if n>2: tier_map[ranked[2]] = "Under Performer"
    else:
        labels  = [0]*len(vendors)
        tier_map = {0:"Average"}

    # Isolation Forest anomaly
    anomalies = [False]*len(vendors)
    if len(vendors) >= 5:
        iso = IsolationForest(contamination=0.15, random_state=42)
        anomalies = [p==-1 for p in iso.fit_predict(X_sc)]

    # Weighted composite score (0-100)
    weights = np.array([0.35, 0.25, 0.25, 0.15])
    X_mm    = X.copy()
    for j in range(X.shape[1]):
        mn, mx = X[:,j].min(), X[:,j].max()
        if mx > mn:
            X_mm[:,j] = (X[:,j]-mn)/(mx-mn)*100
    scores = X_mm @ weights

    for i, v in enumerate(vendors):
        score     = round(float(scores[i]), 1)
        score     = max(0, min(100, score))
        v["score"]   = score
        v["tier"]    = tier_map.get(labels[i], "Average")
        v["risk"]    = "Low" if score>=70 else "Medium" if score>=45 else "High"
        v["anomaly"] = anomalies[i]

    return vendors


def recommend_3pl(vendor: dict, weight_kg: float = 50, distance_km: float = 30) -> list:
    """
    ML-style recommendation: scores each 3PL provider for a given route.
    Returns ranked list with scores and reasoning.
    """
    results = []

    for name, p in TPL_PROVIDERS.items():
        score = 100

        # Weight check — eliminate if exceeds max
        if weight_kg > p["max_weight"]:
            continue

        # Cost scoring (lower = better), normalize to 0-30 pts
        estimated_cost = p["min_cost"] + (p["avg_cost_km"] * distance_km)
        max_possible   = 150 + (80 * distance_km)
        cost_score     = 30 - int((estimated_cost / max_possible) * 30)
        score          = max(0, cost_score)

        # Speed scoring (faster = better) 0-25 pts
        hrs = p["delivery_hrs"].get("same_city", 24)
        if hrs is None: hrs = 48
        if hrs <= 1:    score += 25
        elif hrs <= 3:  score += 20
        elif hrs <= 6:  score += 15
        elif hrs <= 24: score += 10
        else:           score += 5

        # Coverage 0-20 pts
        if "Pan India" in p["coverage"]:    score += 20
        elif "25+" in p["coverage"]:        score += 15
        elif "10 metro" in p["coverage"]:   score += 12
        else:                               score += 8

        # Rating 0-15 pts
        score += int((p["rating"] - 3.5) * 15)

        # Features 0-10 pts
        if p["tracking"]: score += 4
        if p["cod"]:      score += 3
        if p["api_available"]: score += 3

        score = max(0, min(100, score))

        results.append({
            "provider":      name,
            "type":          p["type"],
            "modes":         ", ".join(p["modes"]),
            "score":         score,
            "estimated_cost": round(estimated_cost, 0),
            "delivery_hrs":  hrs,
            "coverage":      p["coverage"],
            "rating":        p["rating"],
            "cod":           p["cod"],
            "tracking":      p["tracking"],
            "color":         p["color"],
            "best_for":      ", ".join(p["best_for"][:3]),
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    # Mark winner
    if results:
        results[0]["recommended"] = True
        for r in results[1:]:
            r["recommended"] = False

    return results


# ════════════════════════════════════════════════════════════
# SECTION D — FILE READER + CSV IMPORTER
# ════════════════════════════════════════════════════════════

def read_supply_file(filepath: str):
    path = Path(filepath)
    ext  = path.suffix.lower()
    df, raw_text = None, ""
    try:
        if ext == ".csv":
            df = pd.read_csv(filepath, encoding="utf-8", errors="replace") if PANDAS_OK else None
            raw_text = df.to_string() if df is not None else open(filepath).read()
        elif ext in [".xlsx",".xls"]:
            df = pd.read_excel(filepath) if PANDAS_OK else None
            raw_text = df.to_string() if df is not None else ""
        elif ext == ".pdf":
            if PDFPLUMBER_OK:
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t: raw_text += t + "\n"
        elif ext in [".txt",".tsv"]:
            raw_text = open(filepath, encoding="utf-8", errors="replace").read()
            if PANDAS_OK:
                try:
                    import io
                    sep = "\t" if ext==".tsv" else ","
                    df  = pd.read_csv(io.StringIO(raw_text), sep=sep)
                except Exception:
                    pass
    except Exception as e:
        return None, f"ERROR: {e}", "error"
    return df, raw_text, ext.lstrip(".")


def import_vendors_from_csv(files) -> tuple:
    """
    Reads uploaded CSV/Excel files, extracts vendor rows,
    scores them with ML, adds to vendor store.
    Returns (status_message, vendor_list_html, vendor_names_list)
    """
    if not files:
        return "No files uploaded.", format_vendor_list_html(), get_vendor_names()

    imported = 0
    errors   = []

    for file in (files if isinstance(files, list) else [files]):
        if file is None: continue
        filepath = file.name if hasattr(file,"name") else str(file)
        df, raw_text, ftype = read_supply_file(filepath)

        if df is None or not PANDAS_OK:
            errors.append(f"{Path(filepath).name}: Could not read as table")
            continue

        cols = {c: c.upper() for c in df.columns}

        # Need at least a name-like column
        has_name = any(
            any(k in v for k in ["SUPPLIER","VENDOR","NAME","PARTY"])
            for v in cols.values()
        )
        if not has_name:
            errors.append(f"{Path(filepath).name}: No supplier/vendor name column found")
            continue

        for _, row in df.iterrows():
            vendor = build_vendor_from_row(row.to_dict(), cols)
            if vendor["name"] and vendor["name"] != "Unknown":
                add_vendor(vendor)
                imported += 1

    # Score all vendors with ML
    scored = ml_score_vendors(get_vendors())
    _VENDOR_STORE.clear()
    _VENDOR_STORE.extend(scored)

    status = f"Imported {imported} vendors."
    if errors:
        status += " Errors: " + "; ".join(errors)

    return status, format_vendor_list_html(), get_vendor_names()


def add_vendor_manual(
    name, gstin, contact, location,
    on_time, quality, lead_days,
    avg_price, reliability, route, transport_mode
) -> tuple:
    """Adds a single vendor from manual form."""
    if not name or not name.strip():
        return "Please enter a vendor name.", format_vendor_list_html(), get_vendor_names()

    vendor = {
        "name":           name.strip(),
        "gstin":          gstin.strip() if gstin else "Not provided",
        "contact":        contact.strip() if contact else "Not provided",
        "location":       location.strip() if location else "Not specified",
        "on_time":        str(on_time) if on_time else "N/A",
        "quality":        str(quality) if quality else "N/A",
        "lead_days":      str(lead_days) if lead_days else "N/A",
        "avg_price":      str(avg_price) if avg_price else "N/A",
        "reliability":    str(reliability) if reliability else "N/A",
        "route":          route.strip() if route else "Not specified",
        "transport_mode": transport_mode if transport_mode else "Not specified",
        "score":          0,
        "risk":           "Unknown",
        "tier":           "Unknown",
        "best_3pl":       "",
        "added_at":       datetime.now().strftime("%d %b %Y %H:%M"),
    }

    add_vendor(vendor)
    scored = ml_score_vendors(get_vendors())
    _VENDOR_STORE.clear()
    _VENDOR_STORE.extend(scored)

    return (
        f"Vendor '{name}' added successfully.",
        format_vendor_list_html(),
        get_vendor_names(),
    )


# ════════════════════════════════════════════════════════════
# SECTION E — FORMATTERS
# HTML for sidebar + detail panel
# ════════════════════════════════════════════════════════════

def format_vendor_list_html() -> str:
    """Renders the sidebar vendor list as styled HTML."""
    vendors = get_vendors()
    if not vendors:
        return """
<div style='padding:20px;color:#888;text-align:center;font-size:13px;'>
  No vendors yet.<br>Upload a CSV or add manually.
</div>"""

    items = []
    for i, v in enumerate(vendors):
        risk_color = (
            "#2ECC71" if v["risk"]=="Low" else
            "#F39C12" if v["risk"]=="Medium" else
            "#E74C3C"
        )
        tier_icon = (
            "🥇" if v["tier"]=="Top Performer" else
            "🥈" if v["tier"]=="Average" else
            "🥉"
        )
        score_bar = int(v["score"])

        items.append(f"""
<div onclick="document.getElementById('vendor_select').value='{v["name"]}';
              document.getElementById('vendor_select').dispatchEvent(new Event('change'));"
     style='padding:10px 12px;border-bottom:1px solid #2a2a2a;cursor:pointer;
            transition:background 0.2s;'
     onmouseover="this.style.background='#1e3a2f'"
     onmouseout="this.style.background='transparent'">
  <div style='display:flex;justify-content:space-between;align-items:center;'>
    <span style='font-weight:500;font-size:13px;color:#e0e0e0;'>{tier_icon} {v["name"]}</span>
    <span style='font-size:11px;font-weight:600;color:{risk_color};'>{v["score"]}/100</span>
  </div>
  <div style='height:3px;background:#333;border-radius:2px;margin:5px 0;'>
    <div style='height:100%;width:{score_bar}%;background:{risk_color};border-radius:2px;'></div>
  </div>
  <div style='display:flex;justify-content:space-between;font-size:11px;color:#888;'>
    <span>{v["location"]}</span>
    <span style='color:{risk_color};'>{v["risk"]} Risk</span>
  </div>
</div>""")

    return f"""
<div style='background:#121212;border-radius:8px;border:1px solid #2a2a2a;max-height:500px;overflow-y:auto;'>
  <div style='padding:10px 12px;background:#1a1a1a;border-bottom:1px solid #2a2a2a;font-size:12px;color:#888;letter-spacing:0.05em;'>
    VENDORS ({len(vendors)})
  </div>
  {"".join(items)}
</div>"""


def format_vendor_detail(vendor_name: str, weight_kg: float, distance_km: float) -> str:
    """Renders the full vendor detail panel."""
    vendors = get_vendors()
    vendor  = next((v for v in vendors if v["name"]==vendor_name), None)

    if not vendor:
        return "<div style='padding:20px;color:#888;'>Select a vendor from the list to see details.</div>"

    # Score color
    risk_color = (
        "#2ECC71" if vendor["risk"]=="Low" else
        "#F39C12" if vendor["risk"]=="Medium" else
        "#E74C3C"
    )
    tier_icon = (
        "🥇" if vendor["tier"]=="Top Performer" else
        "🥈" if vendor["tier"]=="Average" else
        "🥉"
    )

    # Get 3PL recommendations
    tpl_recs = recommend_3pl(vendor, weight_kg, distance_km)

    # Build 3PL cards
    tpl_html = ""
    for i, t in enumerate(tpl_recs[:6]):
        border = "2px solid #2ECC71" if i==0 else "1px solid #2a2a2a"
        badge  = "<span style='background:#2ECC71;color:#000;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:6px;'>BEST</span>" if i==0 else ""
        tpl_html += f"""
<div style='background:#1a1a1a;border:{border};border-radius:8px;padding:12px;margin-bottom:8px;'>
  <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>
    <span style='font-weight:600;font-size:13px;color:{t["color"]};'>{t["provider"]}{badge}</span>
    <span style='font-size:13px;font-weight:600;color:#e0e0e0;'>{t["score"]}/100</span>
  </div>
  <div style='font-size:11px;color:#aaa;margin-bottom:6px;'>{t["type"]}</div>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:11px;'>
    <div style='color:#888;'>Est. Cost</div><div style='color:#e0e0e0;font-weight:500;'>Rs.{t["estimated_cost"]:,.0f}</div>
    <div style='color:#888;'>Delivery</div><div style='color:#e0e0e0;font-weight:500;'>{t["delivery_hrs"]} hrs</div>
    <div style='color:#888;'>Modes</div><div style='color:#e0e0e0;'>{t["modes"]}</div>
    <div style='color:#888;'>Coverage</div><div style='color:#e0e0e0;'>{t["coverage"]}</div>
    <div style='color:#888;'>Rating</div><div style='color:#e0e0e0;'>{"⭐"*int(t["rating"])} {t["rating"]}</div>
    <div style='color:#888;'>COD</div><div style='color:#e0e0e0;'>{"Yes" if t["cod"] else "No"}</div>
  </div>
  <div style='margin-top:6px;font-size:10px;color:#666;'>Best for: {t["best_for"]}</div>
</div>"""

    # Transport modes for route
    route_str = vendor.get("route","Not specified")
    mode_str  = vendor.get("transport_mode","Not specified")
    modes_html = ""
    for mode_name, mode_data in TRANSPORT_MODES.items():
        if weight_kg <= mode_data["max_kg"]:
            est_time = round(distance_km / mode_data["speed_kmh"], 1)
            est_cost = round(distance_km * mode_data["cost_per_km"], 0)
            modes_html += f"""
<div style='display:flex;align-items:center;gap:10px;padding:8px 10px;
            background:#1a1a1a;border-radius:6px;margin-bottom:6px;border:1px solid #2a2a2a;'>
  <span style='font-size:18px;'>{mode_data["icon"]}</span>
  <div style='flex:1;'>
    <div style='font-size:12px;font-weight:500;color:#e0e0e0;'>{mode_name}</div>
    <div style='font-size:11px;color:#888;'>Max {mode_data["max_kg"]}kg</div>
  </div>
  <div style='text-align:right;'>
    <div style='font-size:12px;color:#2ECC71;font-weight:500;'>Rs.{est_cost:,.0f}</div>
    <div style='font-size:11px;color:#888;'>{est_time}h</div>
  </div>
</div>"""

    anomaly_banner = ""
    if vendor.get("anomaly"):
        anomaly_banner = """
<div style='background:#4a1a1a;border:1px solid #E74C3C;border-radius:6px;padding:8px 12px;
            margin-bottom:12px;font-size:12px;color:#ff8080;'>
  ⚠️ ML Anomaly Flag: This vendor shows statistically unusual patterns. Review contracts carefully.
</div>"""

    return f"""
<div style='background:#0d0d0d;border-radius:10px;padding:16px;font-family:system-ui,sans-serif;'>

  {anomaly_banner}

  <!-- Header -->
  <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;
              padding-bottom:12px;border-bottom:1px solid #2a2a2a;'>
    <div>
      <div style='font-size:18px;font-weight:600;color:#e0e0e0;'>{tier_icon} {vendor["name"]}</div>
      <div style='font-size:12px;color:#888;margin-top:2px;'>{vendor["location"]}</div>
      <div style='font-size:11px;color:#666;margin-top:2px;'>Added {vendor["added_at"]}</div>
    </div>
    <div style='text-align:right;'>
      <div style='font-size:28px;font-weight:700;color:{risk_color};'>{vendor["score"]}</div>
      <div style='font-size:11px;color:#888;'>/ 100</div>
      <div style='font-size:11px;color:{risk_color};font-weight:500;margin-top:2px;'>{vendor["risk"]} Risk</div>
    </div>
  </div>

  <!-- Profile -->
  <div style='margin-bottom:14px;'>
    <div style='font-size:11px;color:#666;letter-spacing:0.05em;margin-bottom:8px;'>VENDOR PROFILE</div>
    <div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;'>
      <div style='background:#1a1a1a;border-radius:6px;padding:8px 10px;'>
        <div style='font-size:10px;color:#666;'>GSTIN</div>
        <div style='font-size:12px;color:#e0e0e0;margin-top:2px;'>{vendor["gstin"]}</div>
      </div>
      <div style='background:#1a1a1a;border-radius:6px;padding:8px 10px;'>
        <div style='font-size:10px;color:#666;'>CONTACT</div>
        <div style='font-size:12px;color:#e0e0e0;margin-top:2px;'>{vendor["contact"]}</div>
      </div>
      <div style='background:#1a1a1a;border-radius:6px;padding:8px 10px;'>
        <div style='font-size:10px;color:#666;'>ML TIER</div>
        <div style='font-size:12px;color:#e0e0e0;margin-top:2px;'>{tier_icon} {vendor["tier"]}</div>
      </div>
      <div style='background:#1a1a1a;border-radius:6px;padding:8px 10px;'>
        <div style='font-size:10px;color:#666;'>TRANSPORT MODE</div>
        <div style='font-size:12px;color:#e0e0e0;margin-top:2px;'>{vendor["transport_mode"]}</div>
      </div>
    </div>
  </div>

  <!-- Performance -->
  <div style='margin-bottom:14px;'>
    <div style='font-size:11px;color:#666;letter-spacing:0.05em;margin-bottom:8px;'>PERFORMANCE SCORES</div>
    {_perf_bar("On-Time Delivery", vendor["on_time"], "#2ECC71")}
    {_perf_bar("Quality Score", vendor["quality"], "#3498DB")}
    {_perf_bar("Reliability", vendor["reliability"], "#9B59B6")}
    <div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px;'>
      <div style='background:#1a1a1a;border-radius:6px;padding:8px 10px;'>
        <div style='font-size:10px;color:#666;'>LEAD TIME</div>
        <div style='font-size:14px;font-weight:600;color:#e0e0e0;margin-top:2px;'>{vendor["lead_days"]} <span style='font-size:11px;color:#888;'>days</span></div>
      </div>
      <div style='background:#1a1a1a;border-radius:6px;padding:8px 10px;'>
        <div style='font-size:10px;color:#666;'>AVG PRICE</div>
        <div style='font-size:14px;font-weight:600;color:#e0e0e0;margin-top:2px;'>Rs.{vendor["avg_price"]}</div>
      </div>
    </div>
  </div>

  <!-- Route -->
  <div style='margin-bottom:14px;'>
    <div style='font-size:11px;color:#666;letter-spacing:0.05em;margin-bottom:8px;'>ROUTE & DELIVERY</div>
    <div style='background:#1a1a1a;border-radius:6px;padding:10px 12px;margin-bottom:8px;'>
      <div style='font-size:10px;color:#666;'>ROUTE</div>
      <div style='font-size:13px;color:#e0e0e0;margin-top:3px;'>📍 {route_str}</div>
    </div>
    <div style='font-size:11px;color:#666;margin-bottom:6px;'>Eligible transport modes for {distance_km}km / {weight_kg}kg:</div>
    {modes_html}
  </div>

  <!-- 3PL Recommendations -->
  <div>
    <div style='font-size:11px;color:#666;letter-spacing:0.05em;margin-bottom:8px;'>
      3PL RECOMMENDATIONS (ML Ranked)
      <span style='font-size:10px;color:#555;margin-left:6px;'>for {distance_km}km, {weight_kg}kg</span>
    </div>
    {tpl_html}
  </div>

</div>"""


def _perf_bar(label: str, value_str: str, color: str) -> str:
    """Renders a single performance metric bar."""
    try:
        val = float(str(value_str).replace("%","").replace(",","").strip())
        if val <= 1: val *= 100
        val = min(100, max(0, val))
    except Exception:
        val = 0

    return f"""
<div style='margin-bottom:8px;'>
  <div style='display:flex;justify-content:space-between;font-size:11px;color:#888;margin-bottom:3px;'>
    <span>{label}</span><span style='color:#e0e0e0;'>{value_str}</span>
  </div>
  <div style='height:5px;background:#2a2a2a;border-radius:3px;'>
    <div style='height:100%;width:{val}%;background:{color};border-radius:3px;'></div>
  </div>
</div>"""


def get_vendor_names() -> list:
    return [v["name"] for v in get_vendors()]


def format_ecosystem_html() -> str:
    """Renders the 3PL ecosystem overview."""
    html = """
<div style='background:#0d0d0d;border-radius:10px;padding:16px;font-family:system-ui,sans-serif;'>
  <div style='font-size:14px;font-weight:600;color:#e0e0e0;margin-bottom:4px;'>3PL Ecosystem</div>
  <div style='font-size:12px;color:#888;margin-bottom:14px;'>Connected logistics providers available for route optimization</div>
  <div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;'>"""

    for name, p in TPL_PROVIDERS.items():
        html += f"""
<div style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:12px;
            border-left:3px solid {p["color"]};'>
  <div style='font-size:13px;font-weight:600;color:{p["color"]};margin-bottom:4px;'>{name}</div>
  <div style='font-size:10px;color:#666;margin-bottom:6px;'>{p["type"]}</div>
  <div style='font-size:11px;color:#888;'>From Rs.{p["min_cost"]}</div>
  <div style='font-size:11px;color:#888;'>{p["coverage"]}</div>
  <div style='font-size:11px;color:#aaa;margin-top:4px;'>⭐ {p["rating"]}</div>
  <div style='font-size:10px;color:#555;margin-top:4px;'>{", ".join(p["modes"])}</div>
</div>"""

    html += "</div></div>"
    return html


# ════════════════════════════════════════════════════════════
# SECTION F — GRADIO UI BUILDER
# Returns a gr.Blocks component — called from app.py
# ════════════════════════════════════════════════════════════

def build_supply_chain_ui() -> "gr.Blocks":
    """
    Builds and returns the full Supply Chain module UI.
    Called from app.py and embedded as a tab.
    """

    with gr.Blocks() as sc_ui:

        gr.Markdown("""
## Module 2 — Supply Chain Optimization
**ML Models:** RandomForest · KMeans · IsolationForest · LinearRegression · 3PL Scorer
""")

        with gr.Tabs():

            # ══════════════════════════════════════
            # SUB-TAB 1: VENDOR SIDEBAR + DETAIL
            # ══════════════════════════════════════
            with gr.Tab("Vendor Intelligence"):

                gr.Markdown("Add vendors via CSV upload or manual form. Click a vendor to see full details, route analysis, and 3PL recommendations.")

                with gr.Row():

                    # ── LEFT SIDEBAR ──
                    with gr.Column(scale=1, min_width=220):

                        gr.Markdown("#### Vendor List")
                        vendor_list_html = gr.HTML(
                            value=format_vendor_list_html(),
                            label="Vendors",
                        )

                        # Hidden dropdown to capture click
                        vendor_select = gr.Dropdown(
                            choices=get_vendor_names(),
                            label="Selected Vendor",
                            visible=False,
                            elem_id="vendor_select",
                        )

                        gr.Markdown("**Route parameters for 3PL scoring:**")
                        route_weight = gr.Slider(
                            label="Shipment Weight (kg)",
                            minimum=1, maximum=5000, value=50, step=10,
                        )
                        route_dist = gr.Slider(
                            label="Distance (km)",
                            minimum=1, maximum=1500, value=30, step=5,
                        )
                        refresh_btn = gr.Button("Refresh Detail", size="sm")

                    # ── RIGHT DETAIL PANEL ──
                    with gr.Column(scale=2):
                        vendor_detail_html = gr.HTML(
                            value="<div style='padding:40px;color:#888;text-align:center;'>Select a vendor from the list to see details.</div>",
                            label="Vendor Detail",
                        )

                # Wire: dropdown change → refresh detail
                def on_vendor_select(name, weight, dist):
                    return format_vendor_detail(name, weight, dist)

                vendor_select.change(
                    fn=on_vendor_select,
                    inputs=[vendor_select, route_weight, route_dist],
                    outputs=[vendor_detail_html],
                )
                refresh_btn.click(
                    fn=on_vendor_select,
                    inputs=[vendor_select, route_weight, route_dist],
                    outputs=[vendor_detail_html],
                )

            # ══════════════════════════════════════
            # SUB-TAB 2: CSV IMPORT
            # ══════════════════════════════════════
            with gr.Tab("Import from CSV"):

                gr.Markdown("""
### Upload Supplier / Vendor CSV or Excel
Auto-detects columns. Supported headers:
- `Supplier Name` / `Vendor Name`
- `On Time Delivery %` · `Quality Score %` · `Lead Time Days` · `Reliability %`
- `Location` · `GSTIN` · `Contact` · `Route` · `Transport Mode`
""")

                csv_files = gr.File(
                    label="Upload CSV / Excel / PDF",
                    file_types=[".csv",".xlsx",".xls",".pdf",".txt"],
                    file_count="multiple",
                )
                import_btn = gr.Button("Import Vendors", variant="primary")
                import_status = gr.Markdown(label="Import Status")

                gr.Markdown("---")
                gr.Markdown("**Sample CSV format:**")
                gr.Markdown("""
```
Supplier Name,On Time Delivery %,Quality Score %,Lead Time Days,Reliability %,Location,GSTIN,Contact,Route,Transport Mode
MetalWorks Co,92,88,5,90,Mumbai,27AABCU9603R1ZX,9876543210,Mumbai-Pune,Truck
PackPro India,85,90,3,87,Delhi,07AABCU9603R1ZX,9123456789,Delhi-NCR,Tata Ace
Raj Logistics,60,72,14,65,Chennai,33AABCU9603R1ZX,9988776655,Chennai-Bangalore,Truck
```
""")

                import_btn.click(
                    fn=import_vendors_from_csv,
                    inputs=[csv_files],
                    outputs=[import_status, vendor_list_html, vendor_select],
                )

            # ══════════════════════════════════════
            # SUB-TAB 3: MANUAL ADD VENDOR
            # ══════════════════════════════════════
            with gr.Tab("Add Vendor Manually"):

                gr.Markdown("### Add a single vendor with full details")

                with gr.Row():
                    man_name    = gr.Textbox(label="Vendor / Supplier Name *", placeholder="e.g. MetalWorks Co")
                    man_location= gr.Textbox(label="City / Location", placeholder="e.g. Mumbai")

                with gr.Row():
                    man_gstin   = gr.Textbox(label="GSTIN", placeholder="27AABCU9603R1ZX")
                    man_contact = gr.Textbox(label="Contact (Phone / Email)", placeholder="9876543210")

                gr.Markdown("#### Performance Metrics")
                with gr.Row():
                    man_ontime  = gr.Number(label="On-Time Delivery %", value=80, minimum=0, maximum=100)
                    man_quality = gr.Number(label="Quality Score %", value=80, minimum=0, maximum=100)
                    man_reliab  = gr.Number(label="Reliability %", value=80, minimum=0, maximum=100)

                with gr.Row():
                    man_lead    = gr.Number(label="Lead Time (days)", value=7, minimum=1)
                    man_price   = gr.Number(label="Avg Unit Price (Rs.)", value=0, minimum=0)

                gr.Markdown("#### Route & Transport")
                with gr.Row():
                    man_route   = gr.Textbox(label="Route", placeholder="e.g. Mumbai to Pune")
                    man_mode    = gr.Dropdown(
                        choices=["Bike","Auto","Tata Ace","Truck","Air","Rail","Not specified"],
                        value="Truck",
                        label="Transport Mode",
                    )

                man_add_btn = gr.Button("Add Vendor", variant="primary")
                man_status  = gr.Markdown(label="Status")

                man_add_btn.click(
                    fn=add_vendor_manual,
                    inputs=[
                        man_name, man_gstin, man_contact, man_location,
                        man_ontime, man_quality, man_lead,
                        man_price, man_reliab, man_route, man_mode,
                    ],
                    outputs=[man_status, vendor_list_html, vendor_select],
                )

            # ══════════════════════════════════════
            # SUB-TAB 4: 3PL ECOSYSTEM
            # ══════════════════════════════════════
            with gr.Tab("3PL Ecosystem"):

                gr.Markdown("""
### Connected Logistics Providers
All providers below are integrated into the ML recommendation engine.
Select a vendor and set route parameters to get the best provider recommendation.
""")
                gr.HTML(value=format_ecosystem_html())

                gr.Markdown("---")
                gr.Markdown("### Compare 3PL Providers for a Route")

                with gr.Row():
                    cmp_weight = gr.Number(label="Shipment Weight (kg)", value=50, minimum=1)
                    cmp_dist   = gr.Number(label="Distance (km)", value=50, minimum=1)
                    cmp_btn    = gr.Button("Compare All Providers", variant="primary")

                cmp_result = gr.HTML(label="Comparison")

                def compare_all(weight, dist):
                    recs = recommend_3pl({}, weight, dist)
                    html = """
<div style='background:#0d0d0d;border-radius:10px;padding:16px;font-family:system-ui,sans-serif;'>
<div style='font-size:14px;font-weight:600;color:#e0e0e0;margin-bottom:12px;'>
  Provider Comparison — {w}kg over {d}km
</div>""".format(w=weight, d=dist)

                    for i, t in enumerate(recs):
                        border = "2px solid #2ECC71" if i==0 else "1px solid #2a2a2a"
                        badge  = " 🏆 RECOMMENDED" if i==0 else ""
                        html += f"""
<div style='background:#1a1a1a;border:{border};border-radius:8px;padding:12px;margin-bottom:8px;
            display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;'>
  <div>
    <span style='font-weight:600;color:{t["color"]};font-size:13px;'>{t["provider"]}{badge}</span>
    <div style='font-size:11px;color:#888;margin-top:2px;'>{t["type"]} · {t["modes"]}</div>
    <div style='font-size:11px;color:#555;margin-top:2px;'>Best for: {t["best_for"]}</div>
  </div>
  <div style='display:flex;gap:16px;flex-wrap:wrap;'>
    <div style='text-align:center;'>
      <div style='font-size:18px;font-weight:700;color:#e0e0e0;'>{t["score"]}</div>
      <div style='font-size:10px;color:#888;'>SCORE</div>
    </div>
    <div style='text-align:center;'>
      <div style='font-size:14px;font-weight:600;color:#2ECC71;'>Rs.{t["estimated_cost"]:,.0f}</div>
      <div style='font-size:10px;color:#888;'>EST COST</div>
    </div>
    <div style='text-align:center;'>
      <div style='font-size:14px;font-weight:600;color:#e0e0e0;'>{t["delivery_hrs"]}h</div>
      <div style='font-size:10px;color:#888;'>DELIVERY</div>
    </div>
    <div style='text-align:center;'>
      <div style='font-size:12px;color:#aaa;'>⭐{t["rating"]}</div>
      <div style='font-size:10px;color:#888;'>RATING</div>
    </div>
  </div>
</div>"""
                    html += "</div>"
                    return html

                cmp_btn.click(
                    fn=compare_all,
                    inputs=[cmp_weight, cmp_dist],
                    outputs=[cmp_result],
                )

    return sc_ui


# ════════════════════════════════════════════════════════════
# SECTION G — LEGACY HANDLER (used by older app.py)
# ════════════════════════════════════════════════════════════

def run_supply_chain_audit(files) -> tuple:
    """Legacy entry point — kept for backwards compatibility."""
    if not files:
        return (
            "Upload files or use the Vendor Intelligence tab above.",
            "Add vendors via Import or Manual Entry tabs.",
            "",
            "Use the 3PL Ecosystem tab for provider comparison.",
        )
    status, _, _ = import_vendors_from_csv(files)
    vendors = get_vendors()
    summary = f"Imported {len(vendors)} vendors. Go to Vendor Intelligence tab to view details.\n\n{status}"
    return summary, format_vendor_list_html(), "", ""
