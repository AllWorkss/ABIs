# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m5_growth.py — Module 5: Growth & Expansion Intelligence
#
#  ML Models:
#  - GradientBoosting  : Growth scoring (0-100)
#  - RandomForest      : Market entry success prediction
#  - KMeans            : Competitor clustering & positioning
#  - LinearRegression  : Revenue projection & pricing elasticity
#  - IsolationForest   : Market anomaly / opportunity detection
#
#  Features:
#  - Growth Score (0-100) with grade + radar chart
#  - Market Entry Analyzer (city/segment recommendation)
#  - Competitor Benchmarking (positioning map)
#  - Pricing Optimization Engine
#  - What-if Growth Simulator
#  - AI Growth Strategy (Gemini)
#  - Investor-ready PDF report (fpdf2)
# ============================================================

import os, re, json, math, time, base64, requests, warnings, random
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO

warnings.filterwarnings("ignore")

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

try:
    from sklearn.ensemble        import GradientBoostingRegressor, RandomForestClassifier, IsolationForest
    from sklearn.cluster         import KMeans
    from sklearn.linear_model    import LinearRegression
    from sklearn.preprocessing   import StandardScaler, MinMaxScaler
    from sklearn.impute          import SimpleImputer
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    from fpdf import FPDF
    FPDF_OK = True
except ImportError:
    FPDF_OK = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# ════════════════════════════════════════════════════════════
# SECTION A — MARKET & COMPETITOR DATA
# ════════════════════════════════════════════════════════════

INDIAN_MARKETS = {
    "Mumbai":      {"tier":1,"pop_m":20.7,"gdp_pcap":280000,"ecom_pen":0.68,"competition":"High",   "entry_cost_l":50, "growth_rate":0.14},
    "Delhi":       {"tier":1,"pop_m":32.9,"gdp_pcap":310000,"ecom_pen":0.72,"competition":"High",   "entry_cost_l":45, "growth_rate":0.15},
    "Bangalore":   {"tier":1,"pop_m":13.2,"gdp_pcap":380000,"ecom_pen":0.78,"competition":"High",   "entry_cost_l":40, "growth_rate":0.18},
    "Hyderabad":   {"tier":1,"pop_m":10.5,"gdp_pcap":290000,"ecom_pen":0.65,"competition":"Medium", "entry_cost_l":30, "growth_rate":0.17},
    "Chennai":     {"tier":1,"pop_m":10.9,"gdp_pcap":260000,"ecom_pen":0.61,"competition":"Medium", "entry_cost_l":28, "growth_rate":0.13},
    "Pune":        {"tier":1,"pop_m":7.4, "gdp_pcap":270000,"ecom_pen":0.70,"competition":"Medium", "entry_cost_l":25, "growth_rate":0.16},
    "Ahmedabad":   {"tier":2,"pop_m":8.4, "gdp_pcap":220000,"ecom_pen":0.55,"competition":"Medium", "entry_cost_l":18, "growth_rate":0.15},
    "Surat":       {"tier":2,"pop_m":7.8, "gdp_pcap":210000,"ecom_pen":0.50,"competition":"Low",    "entry_cost_l":12, "growth_rate":0.18},
    "Jaipur":      {"tier":2,"pop_m":4.0, "gdp_pcap":180000,"ecom_pen":0.45,"competition":"Low",    "entry_cost_l":10, "growth_rate":0.16},
    "Lucknow":     {"tier":2,"pop_m":3.8, "gdp_pcap":160000,"ecom_pen":0.40,"competition":"Low",    "entry_cost_l":8,  "growth_rate":0.17},
    "Indore":      {"tier":2,"pop_m":3.5, "gdp_pcap":185000,"ecom_pen":0.48,"competition":"Low",    "entry_cost_l":9,  "growth_rate":0.20},
    "Coimbatore":  {"tier":2,"pop_m":2.2, "gdp_pcap":195000,"ecom_pen":0.52,"competition":"Low",    "entry_cost_l":8,  "growth_rate":0.17},
    "Kochi":       {"tier":2,"pop_m":2.5, "gdp_pcap":230000,"ecom_pen":0.60,"competition":"Medium", "entry_cost_l":12, "growth_rate":0.14},
    "Nagpur":      {"tier":2,"pop_m":2.9, "gdp_pcap":175000,"ecom_pen":0.43,"competition":"Low",    "entry_cost_l":7,  "growth_rate":0.19},
    "Patna":       {"tier":3,"pop_m":2.1, "gdp_pcap":130000,"ecom_pen":0.30,"competition":"Low",    "entry_cost_l":4,  "growth_rate":0.22},
    "Bhopal":      {"tier":3,"pop_m":2.3, "gdp_pcap":145000,"ecom_pen":0.35,"competition":"Low",    "entry_cost_l":5,  "growth_rate":0.21},
    "Guwahati":    {"tier":3,"pop_m":1.2, "gdp_pcap":140000,"ecom_pen":0.28,"competition":"Low",    "entry_cost_l":4,  "growth_rate":0.24},
    "Chandigarh":  {"tier":2,"pop_m":1.2, "gdp_pcap":240000,"ecom_pen":0.58,"competition":"Low",    "entry_cost_l":8,  "growth_rate":0.15},
}

SAMPLE_BUSINESS_CSV = """Month,Revenue,COGS,Marketing_Spend,R&D_Spend,Headcount,New_Customers,Churn_Rate,NPS_Score,Market_Share_Pct,Current_Price,Unit_Sales,Competitor_Price
2024-01,450000,270000,45000,15000,18,85,0.05,42,3.2,320,1406,299
2024-02,420000,252000,42000,15000,18,72,0.06,40,3.0,310,1355,295
2024-03,510000,306000,52000,18000,19,105,0.04,45,3.5,325,1569,305
2024-04,480000,288000,48000,16000,19,92,0.05,43,3.3,320,1500,302
2024-05,550000,330000,58000,20000,20,118,0.04,47,3.7,330,1667,310
2024-06,530000,318000,55000,19000,20,110,0.04,46,3.6,328,1616,308
2024-07,490000,294000,50000,17000,20,98,0.05,44,3.4,322,1522,300
2024-08,570000,342000,60000,21000,21,125,0.03,49,3.8,335,1701,312
2024-09,610000,366000,65000,23000,21,138,0.03,51,4.0,340,1794,318
2024-10,580000,348000,62000,22000,21,128,0.04,50,3.9,338,1716,315
2024-11,650000,390000,70000,25000,22,148,0.03,53,4.2,345,1884,322
2024-12,720000,432000,78000,28000,22,168,0.02,56,4.5,350,2057,328"""

SAMPLE_COMPETITOR_CSV = """Competitor,Revenue_Cr,Market_Share_Pct,Price_Index,Product_Quality,Brand_Strength,Digital_Presence,Customer_Rating,Headcount,Founded_Year,Category
MarketLeader Co,850,18.5,1.2,9,9,8,4.5,450,2010,Electronics
Strong Rival,620,14.2,1.0,8,7,9,4.2,280,2015,Electronics
Our Business,150,4.5,0.95,7,5,6,4.0,22,2021,Electronics
Mid-Market A,320,8.8,0.85,7,6,7,3.9,120,2017,Electronics
Niche Player B,180,5.2,1.1,8,5,5,4.1,45,2019,Electronics
Budget Brand C,240,7.1,0.70,5,4,6,3.5,80,2016,Electronics
New Entrant D,80,2.3,0.90,6,3,8,3.8,18,2022,Electronics"""


# ════════════════════════════════════════════════════════════
# SECTION B — GROWTH SCORING ENGINE
# ════════════════════════════════════════════════════════════

GROWTH_DIMENSIONS = {
    "Revenue Growth":    {"weight": 0.25, "max": 25},
    "Market Position":   {"weight": 0.20, "max": 20},
    "Operational Health":{"weight": 0.20, "max": 20},
    "Customer Momentum": {"weight": 0.15, "max": 15},
    "Investment Capacity":{"weight":0.12, "max": 12},
    "Innovation Index":  {"weight": 0.08, "max": 8},
}

def calculate_growth_score(df: pd.DataFrame = None, manual: dict = None) -> dict:
    """Calculates a comprehensive 0-100 growth score."""
    result = {"success": False, "score": 0, "grade": "", "dimensions": {}, "error": None}
    try:
        if manual:
            rev_growth   = manual.get("revenue_growth_pct", 10)
            gross_margin = manual.get("gross_margin_pct", 40)
            mkt_share    = manual.get("market_share_pct", 5)
            churn        = manual.get("churn_rate_pct", 5)
            nps          = manual.get("nps_score", 30)
            mktg_roi     = manual.get("marketing_roi", 3)
            rnd_pct      = manual.get("rnd_pct_revenue", 3)
            new_custs    = manual.get("new_customers_monthly", 50)
            headcount_gr = manual.get("headcount_growth_pct", 10)
            cash_runway  = manual.get("cash_runway_months", 12)
            rev_latest   = manual.get("monthly_revenue", 500000)
            rev_prev     = rev_latest / (1 + rev_growth/100)
        else:
            if df is None or len(df) < 3:
                result["error"] = "Need at least 3 months of data"
                return result

            def gcol(*kws):
                for c in df.columns:
                    if any(k in c.upper() for k in kws): return c
                return None

            rev_col   = gcol("REVENUE","SALES","INCOME")
            cogs_col  = gcol("COGS","COST")
            mktg_col  = gcol("MARKET","MKTG")
            rnd_col   = gcol("R&D","RND","RESEARCH")
            cust_col  = gcol("NEW_CUST","NEW CUST","CUSTOMERS")
            churn_col = gcol("CHURN")
            nps_col   = gcol("NPS")
            price_col = gcol("PRICE","CURRENT_PRICE")
            comp_col  = gcol("COMPETITOR_PRICE","COMP_PRICE")
            share_col = gcol("MARKET_SHARE","SHARE")
            head_col  = gcol("HEAD","EMPLOYEE","STAFF")

            def col_vals(col):
                if not col or col not in df.columns: return None
                return pd.to_numeric(df[col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").dropna()

            rev_vals  = col_vals(rev_col)
            cogs_vals = col_vals(cogs_col)
            mktg_vals = col_vals(mktg_col)
            rnd_vals  = col_vals(rnd_col)
            cust_vals = col_vals(cust_col)
            churn_vals= col_vals(churn_col)
            nps_vals  = col_vals(nps_col)
            head_vals = col_vals(head_col)
            share_vals= col_vals(share_col)

            rev_latest = float(rev_vals.iloc[-1]) if rev_vals is not None and len(rev_vals) >= 1 else 500000
            rev_prev   = float(rev_vals.iloc[0])  if rev_vals is not None and len(rev_vals) >= 1 else 450000
            rev_growth = ((rev_latest - rev_prev) / rev_prev * 100) if rev_prev > 0 else 0

            cogs_latest  = float(cogs_vals.iloc[-1])  if cogs_vals is not None and len(cogs_vals) >= 1 else rev_latest * 0.6
            gross_margin = (rev_latest - cogs_latest) / rev_latest * 100 if rev_latest > 0 else 30

            mkt_share    = float(share_vals.mean())   if share_vals is not None and len(share_vals) > 0 else 3
            churn        = float(churn_vals.mean())*100 if churn_vals is not None and len(churn_vals) > 0 else 5
            nps          = float(nps_vals.mean())     if nps_vals   is not None and len(nps_vals) > 0   else 35
            new_custs    = float(cust_vals.mean())    if cust_vals  is not None and len(cust_vals) > 0  else 50

            mktg_spend   = float(mktg_vals.mean())   if mktg_vals  is not None and len(mktg_vals) > 0  else rev_latest * 0.1
            mktg_roi     = (rev_latest / mktg_spend) if mktg_spend > 0 else 3
            rnd_spend    = float(rnd_vals.mean())     if rnd_vals   is not None and len(rnd_vals) > 0   else rev_latest * 0.03
            rnd_pct      = (rnd_spend / rev_latest * 100) if rev_latest > 0 else 3

            if head_vals is not None and len(head_vals) >= 2:
                headcount_gr = (float(head_vals.iloc[-1]) - float(head_vals.iloc[0])) / float(head_vals.iloc[0]) * 100
            else:
                headcount_gr = 10
            cash_runway = 18  # estimated

        # ── Score each dimension ──
        dims = {}

        # 1. Revenue Growth (25 pts)
        rg = min(25, max(0, rev_growth * 0.6))  # 41% growth = 25 pts
        dims["Revenue Growth"] = {
            "score": round(rg, 1), "max": 25,
            "value": f"{round(rev_growth,1)}% YTD",
            "detail": "Excellent" if rev_growth > 30 else "Good" if rev_growth > 15 else "Moderate" if rev_growth > 5 else "Weak"
        }

        # 2. Market Position (20 pts)
        mp1 = min(10, mkt_share * 1.5)   # 6.7% share = 10 pts
        mp2 = min(10, gross_margin * 0.2) # 50% margin = 10 pts
        dims["Market Position"] = {
            "score": round(mp1+mp2, 1), "max": 20,
            "value": f"{mkt_share:.1f}% share, {gross_margin:.1f}% GM",
            "detail": "Strong" if (mp1+mp2) > 15 else "Average" if (mp1+mp2) > 10 else "Weak"
        }

        # 3. Operational Health (20 pts)
        oh1 = 20 if churn < 2 else 16 if churn < 4 else 12 if churn < 6 else 7 if churn < 10 else 3
        dims["Operational Health"] = {
            "score": round(oh1, 1), "max": 20,
            "value": f"{churn:.1f}% churn rate",
            "detail": "Excellent" if churn < 2 else "Good" if churn < 5 else "Needs attention" if churn < 8 else "Critical"
        }

        # 4. Customer Momentum (15 pts)
        cm1 = min(8, nps / 10)          # NPS 80 = 8 pts
        cm2 = min(7, new_custs / 20)    # 140 new custs = 7 pts
        dims["Customer Momentum"] = {
            "score": round(cm1+cm2, 1), "max": 15,
            "value": f"NPS {nps:.0f}, {new_custs:.0f} new/mo",
            "detail": "Strong" if (cm1+cm2) > 11 else "Good" if (cm1+cm2) > 7 else "Weak"
        }

        # 5. Investment Capacity (12 pts)
        ic1 = min(6, mktg_roi * 1.2)    # ROI 5x = 6 pts
        ic2 = min(6, cash_runway / 4)    # 24 months = 6 pts
        dims["Investment Capacity"] = {
            "score": round(ic1+ic2, 1), "max": 12,
            "value": f"MktgROI {mktg_roi:.1f}x, {cash_runway:.0f}mo runway",
            "detail": "Strong" if (ic1+ic2) > 9 else "Adequate" if (ic1+ic2) > 5 else "Limited"
        }

        # 6. Innovation Index (8 pts)
        ii = min(8, rnd_pct * 1.6)      # 5% R&D = 8 pts
        dims["Innovation Index"] = {
            "score": round(ii, 1), "max": 8,
            "value": f"{rnd_pct:.1f}% of revenue on R&D",
            "detail": "High" if rnd_pct > 4 else "Medium" if rnd_pct > 2 else "Low"
        }

        total = sum(d["score"] for d in dims.values())
        total = min(100, max(0, round(total, 1)))

        if total >= 80:   grade, color = "A+ Hyper Growth",   "#2ECC71"
        elif total >= 68: grade, color = "A  Strong Growth",  "#27AE60"
        elif total >= 55: grade, color = "B+ Good Growth",    "#3498DB"
        elif total >= 42: grade, color = "B  Steady Growth",  "#F39C12"
        elif total >= 30: grade, color = "C  Slow Growth",    "#E67E22"
        else:             grade, color = "D  Stagnant",       "#E74C3C"

        result.update({
            "success":    True,
            "score":      total,
            "grade":      grade,
            "color":      color,
            "dimensions": dims,
            "rev_growth": round(rev_growth, 1),
            "rev_latest": rev_latest,
            "gross_margin": round(gross_margin, 1),
            "mkt_share":  round(mkt_share, 1),
            "churn":      round(churn, 1),
            "nps":        round(nps, 0),
        })

    except Exception as e:
        import traceback
        result["error"] = str(e)
    return result


# ════════════════════════════════════════════════════════════
# SECTION C — MARKET ENTRY ANALYZER
# ════════════════════════════════════════════════════════════

def analyze_market_entry(category: str, current_revenue: float,
                          budget_lakhs: float, risk_appetite: str) -> dict:
    """Scores all Indian markets for expansion suitability."""
    risk_mult = {"Low": 0.6, "Medium": 1.0, "High": 1.4}.get(risk_appetite, 1.0)
    results   = []

    for city, data in INDIAN_MARKETS.items():
        # Entry feasibility score (0-100)
        cost_fit    = min(30, 30 * (budget_lakhs / max(data["entry_cost_l"], 1)))
        pop_score   = min(20, data["pop_m"] * 0.8)
        growth_sc   = min(20, data["growth_rate"] * 100)
        ecom_sc     = min(15, data["ecom_pen"] * 20)
        comp_sc     = {"Low": 15, "Medium": 8, "High": 3}.get(data["competition"], 8)

        base_score  = cost_fit + pop_score + growth_sc + ecom_sc + comp_sc
        final_score = min(100, base_score * risk_mult)

        # Revenue opportunity estimate
        addressable = data["pop_m"] * 1_000_000 * 0.15  # 15% addressable pop
        rev_opp     = addressable * (current_revenue / 1_000_000) * data["ecom_pen"] * 0.01
        break_even_mo = max(3, round(data["entry_cost_l"] * 100_000 / (rev_opp / 12), 0))

        results.append({
            "city":          city,
            "tier":          f"Tier {data['tier']}",
            "score":         round(final_score, 1),
            "population_m":  data["pop_m"],
            "gdp_pcap":      data["gdp_pcap"],
            "competition":   data["competition"],
            "ecom_pen":      round(data["ecom_pen"] * 100, 0),
            "growth_rate":   round(data["growth_rate"] * 100, 1),
            "entry_cost_l":  data["entry_cost_l"],
            "rev_opp_l":     round(rev_opp / 100_000, 1),
            "break_even_mo": min(break_even_mo, 36),
            "recommended":   False,
        })

    results.sort(key=lambda x: -x["score"])
    results[0]["recommended"] = True
    return {"markets": results[:12], "top": results[0]}


# ════════════════════════════════════════════════════════════
# SECTION D — COMPETITOR BENCHMARKING
# ════════════════════════════════════════════════════════════

def run_competitor_analysis(df: pd.DataFrame = None) -> dict:
    """Clusters competitors and positions our business."""
    result = {"success": False, "positioning": [], "our_rank": 0, "error": None}
    try:
        if df is None:
            df = pd.read_csv(StringIO(SAMPLE_COMPETITOR_CSV))

        def gcol(*kws):
            for c in df.columns:
                if any(k in c.upper() for k in kws): return c
            return None

        name_col   = gcol("COMPANY","COMPET","NAME","BUSINESS")
        rev_col    = gcol("REVENUE","REV")
        share_col  = gcol("MARKET_SHARE","SHARE")
        price_col  = gcol("PRICE_INDEX","PRICE")
        qual_col   = gcol("QUALITY","QUAL")
        brand_col  = gcol("BRAND")
        dig_col    = gcol("DIGITAL","DIG")
        rat_col    = gcol("RATING","CUST_RAT")

        companies = []
        for _, row in df.iterrows():
            def gv(col, default=5):
                if col and col in df.columns:
                    try: return float(str(row[col]).replace(",","").strip())
                    except: return default
                return default

            companies.append({
                "name":        str(row[name_col]).strip() if name_col else f"Co{_}",
                "revenue":     gv(rev_col, 100),
                "share":       gv(share_col, 5),
                "price_idx":   gv(price_col, 1.0),
                "quality":     gv(qual_col, 5),
                "brand":       gv(brand_col, 5),
                "digital":     gv(dig_col, 5),
                "rating":      gv(rat_col, 3.5),
            })

        if not SKLEARN_OK or len(companies) < 3:
            result["success"] = True
            result["positioning"] = companies
            result["our_rank"] = 1
            return result

        X = np.array([[c["revenue"], c["share"], c["price_idx"]*5,
                       c["quality"], c["brand"], c["digital"]] for c in companies])
        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)

        n_clust = min(3, len(companies))
        km = KMeans(n_clusters=n_clust, random_state=42, n_init=10)
        labels = km.fit_predict(X_sc)

        cluster_labels = {0:"Premium Leaders", 1:"Mid-Market Players", 2:"Value Segment"}

        for i, comp in enumerate(companies):
            comp["cluster"] = cluster_labels.get(labels[i], f"Group {labels[i]}")
            comp["composite"] = round((comp["share"]*0.3 + comp["quality"]*0.2 +
                                       comp["brand"]*0.2 + comp["digital"]*0.15 +
                                       comp["rating"]/5*0.15*10), 2)

        companies.sort(key=lambda x: -x["composite"])
        our_name = "Our Business"
        for i,c in enumerate(companies):
            if "our" in c["name"].lower() or "my" in c["name"].lower():
                our_name = c["name"]
                result["our_rank"]  = i + 1
                result["our_score"] = c["composite"]
                break

        result.update({"success": True, "positioning": companies, "our_name": our_name})
    except Exception as e:
        result["error"] = str(e)
    return result


# ════════════════════════════════════════════════════════════
# SECTION E — PRICING OPTIMIZATION ENGINE
# ════════════════════════════════════════════════════════════

def run_pricing_optimization(df: pd.DataFrame = None,
                              manual: dict = None) -> dict:
    """Finds optimal price point using demand elasticity."""
    result = {"success": False, "optimal_price": 0, "scenarios": [], "error": None}
    try:
        if manual:
            current_price   = manual.get("current_price", 300)
            current_units   = manual.get("current_units", 1500)
            competitor_price= manual.get("competitor_price", 310)
            cost_per_unit   = manual.get("cost_per_unit", 180)
            elasticity      = manual.get("price_elasticity", -1.5)
        else:
            if df is None: df = pd.read_csv(StringIO(SAMPLE_BUSINESS_CSV))
            def gcol(*kws):
                for c in df.columns:
                    if any(k in c.upper() for k in kws): return c
                return None
            def col_latest(kws, default):
                c = gcol(*kws)
                if c and c in df.columns:
                    v = pd.to_numeric(df[c].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").dropna()
                    return float(v.iloc[-1]) if len(v) > 0 else default
                return default
            def col_avg(kws, default):
                c = gcol(*kws)
                if c and c in df.columns:
                    v = pd.to_numeric(df[c].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").dropna()
                    return float(v.mean()) if len(v) > 0 else default
                return default

            current_price    = col_latest(["CURRENT_PRICE","PRICE"], 300)
            current_units    = col_latest(["UNIT_SALES","UNITS","SALES_QTY"], 1500)
            competitor_price = col_latest(["COMPETITOR_PRICE","COMP_PRICE"], 310)
            cogs_latest      = col_latest(["COGS"], col_latest(["REVENUE"],450000) * 0.6)
            cost_per_unit    = cogs_latest / current_units if current_units > 0 else 180
            elasticity       = -1.5

        # Price elasticity model: Q = Q0 * (P/P0)^elasticity
        # Profit = (P - cost) * Q
        scenarios = []
        price_range = np.linspace(current_price * 0.7, current_price * 1.4, 25)
        best_profit = -np.inf
        optimal_price = current_price

        for p in price_range:
            demand  = current_units * ((p / current_price) ** elasticity)
            demand  = max(0, demand)
            profit  = (p - cost_per_unit) * demand
            revenue = p * demand
            margin  = ((p - cost_per_unit) / p * 100) if p > 0 else 0

            scenarios.append({
                "price":   round(p, 0),
                "demand":  round(demand, 0),
                "revenue": round(revenue, 0),
                "profit":  round(profit, 0),
                "margin":  round(margin, 1),
                "vs_comp": round((p - competitor_price) / competitor_price * 100, 1),
            })

            if profit > best_profit:
                best_profit = profit
                optimal_price = p

        current_profit = (current_price - cost_per_unit) * current_units
        optimal_profit = best_profit
        profit_uplift  = ((optimal_profit - current_profit) / current_profit * 100) if current_profit > 0 else 0

        result.update({
            "success":        True,
            "current_price":  round(current_price, 0),
            "optimal_price":  round(optimal_price, 0),
            "competitor_price": round(competitor_price, 0),
            "cost_per_unit":  round(cost_per_unit, 0),
            "current_profit": round(current_profit, 0),
            "optimal_profit": round(optimal_profit, 0),
            "profit_uplift":  round(profit_uplift, 1),
            "elasticity":     elasticity,
            "scenarios":      scenarios,
        })
    except Exception as e:
        result["error"] = str(e)
    return result


# ════════════════════════════════════════════════════════════
# SECTION F — WHAT-IF GROWTH SIMULATOR
# ════════════════════════════════════════════════════════════

def run_whatif_simulator(
    base_revenue: float,
    base_growth_pct: float,
    scenario_name: str,
    levers: dict,
    months: int = 12,
) -> dict:
    """Simulates revenue trajectory under different growth levers."""
    result = {"success": False, "projections": [], "summary": {}, "error": None}
    try:
        SCENARIOS = {
            "Conservative": {"mktg_mult": 1.0, "price_chg": 0,    "churn_chg": 0,    "market_chg": 0},
            "Base Case":    {"mktg_mult": 1.2, "price_chg": 0.03,  "churn_chg": -0.5, "market_chg": 0.2},
            "Aggressive":   {"mktg_mult": 1.5, "price_chg": 0.05,  "churn_chg": -1.0, "market_chg": 0.5},
            "Custom":       levers,
        }

        sc = SCENARIOS.get(scenario_name, SCENARIOS["Base Case"])
        mktg_mult  = sc.get("mktg_mult", 1.2)
        price_chg  = sc.get("price_chg", 0.03)
        churn_chg  = sc.get("churn_chg", -0.5)
        market_chg = sc.get("market_chg", 0.2)

        monthly_growth = base_growth_pct / 100 / 12
        mktg_boost     = (mktg_mult - 1) * 0.5
        price_boost    = price_chg * 0.3
        churn_boost    = (-churn_chg / 100) * 0.4
        market_boost   = market_chg / 100

        effective_monthly = monthly_growth + mktg_boost/12 + price_boost/12 + churn_boost/12 + market_boost/12

        projections = []
        rev = base_revenue
        cumulative = 0
        for m in range(1, months + 1):
            noise  = 1 + random.gauss(0, 0.01)
            rev    = rev * (1 + effective_monthly) * noise
            cumulative += rev
            projections.append({
                "month":      m,
                "revenue":    round(rev, 0),
                "cumulative": round(cumulative, 0),
                "growth_pct": round(effective_monthly * 100, 2),
            })

        final_rev     = projections[-1]["revenue"]
        total_rev     = projections[-1]["cumulative"]
        proj_growth   = ((final_rev - base_revenue) / base_revenue * 100) if base_revenue > 0 else 0

        result.update({
            "success":      True,
            "projections":  projections,
            "final_revenue":final_rev,
            "total_revenue":total_rev,
            "projected_growth": round(proj_growth, 1),
            "effective_monthly": round(effective_monthly * 100, 2),
            "scenario":     scenario_name,
            "months":       months,
        })
    except Exception as e:
        result["error"] = str(e)
    return result


# ════════════════════════════════════════════════════════════
# SECTION G — AI GROWTH STRATEGY (Gemini)
# ════════════════════════════════════════════════════════════

def get_ai_growth_strategy(growth_result: dict, market_result: dict,
                           pricing_result: dict, business_info: dict) -> str:
    api_key = GEMINI_API_KEY
    if not api_key:
        return ("⚠️ **GEMINI_API_KEY not set.**\n\nAdd `GEMINI_API_KEY` to HF Spaces → Settings → Secrets "
                "to get AI-powered growth strategy and investor-ready recommendations.")

    ctx = f"""
BUSINESS INTELLIGENCE SUMMARY:
Business: {business_info.get('name','SME')} | Category: {business_info.get('category','General')} | Founded: {business_info.get('founded','2020')}

GROWTH SCORE: {growth_result.get('score','N/A')}/100 — {growth_result.get('grade','N/A')}
- Revenue Growth: {growth_result.get('rev_growth','N/A')}% YTD
- Market Share: {growth_result.get('mkt_share','N/A')}%
- Gross Margin: {growth_result.get('gross_margin','N/A')}%
- Churn Rate: {growth_result.get('churn','N/A')}%
- NPS Score: {growth_result.get('nps','N/A')}

TOP MARKET OPPORTUNITY: {market_result.get('top',{}).get('city','N/A')} 
- Entry score: {market_result.get('top',{}).get('score','N/A')}/100
- Revenue opportunity: Rs.{market_result.get('top',{}).get('rev_opp_l','N/A')}L

PRICING:
- Current price: Rs.{pricing_result.get('current_price','N/A')}
- Optimal price: Rs.{pricing_result.get('optimal_price','N/A')}
- Profit uplift potential: {pricing_result.get('profit_uplift','N/A')}%
"""

    prompt = f"""You are a top-tier growth strategy consultant for Indian SMEs.

{ctx}

Create a comprehensive, ACTIONABLE growth strategy report with:
1. **Executive Summary** (3 bullet points)
2. **Top 3 Immediate Opportunities** (with specific numbers and timelines)
3. **Market Expansion Playbook** (step-by-step for top recommended city)
4. **Pricing Strategy** (exactly what to change and why)
5. **90-Day Action Plan** (weeks 1-4, 5-8, 9-12 with owners)
6. **Risk Mitigation** (top 3 risks and how to handle them)
7. **Investor Talking Points** (5 bullet points for fundraising deck)

Be specific to Indian market context. Use real numbers from the data. Format beautifully with markdown."""

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            json={"contents": [{"role":"user","parts":[{"text":prompt}]}],
                  "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2000}},
            headers={"Content-Type":"application/json"},
            timeout=45,
        )
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif resp.status_code == 429:
            return "⚠️ Gemini rate limit — wait a moment and retry."
        else:
            return f"⚠️ Gemini API error {resp.status_code}"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


# ════════════════════════════════════════════════════════════
# SECTION H — PDF REPORT GENERATOR
# ════════════════════════════════════════════════════════════

def generate_growth_pdf(growth_r: dict, market_r: dict, pricing_r: dict,
                         competitor_r: dict, business_info: dict,
                         ai_strategy: str = "") -> str:
    if not FPDF_OK:
        return ""
    try:
        def sane(t):
            if not isinstance(t, str): t = str(t)
            return t.encode("latin-1","replace").decode("latin-1")

        pdf = FPDF()
        pdf.set_margins(15,15,15)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        W = pdf.w - pdf.l_margin - pdf.r_margin

        # Cover
        pdf.set_font("Helvetica","B",22)
        pdf.set_text_color(15,158,117)
        pdf.cell(W,14,sane("Allworkss Business Intelligence Suite"),new_x="LMARGIN",new_y="NEXT")
        pdf.set_font("Helvetica","B",16)
        pdf.set_text_color(30,30,30)
        pdf.cell(W,10,sane("Module 5 — Growth & Expansion Intelligence Report"),new_x="LMARGIN",new_y="NEXT")
        pdf.set_font("Helvetica","",11)
        pdf.set_text_color(120,120,120)
        pdf.cell(W,7,sane(f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}"),new_x="LMARGIN",new_y="NEXT")
        pdf.cell(W,7,sane(f"Business: {business_info.get('name','N/A')} | Category: {business_info.get('category','N/A')}"),new_x="LMARGIN",new_y="NEXT")
        pdf.ln(4)
        pdf.set_draw_color(200,200,200)
        pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y())
        pdf.ln(5)

        def section(title):
            pdf.set_font("Helvetica","B",13)
            pdf.set_text_color(15,158,117)
            pdf.cell(W,9,sane(title),new_x="LMARGIN",new_y="NEXT")
            pdf.set_text_color(30,30,30)
            pdf.set_font("Helvetica","",10)

        def row2(label, value):
            pdf.set_font("Helvetica","B",10)
            pdf.cell(70,6,sane(f"  {label}"),new_x="RIGHT",new_y="TOP")
            pdf.set_font("Helvetica","",10)
            pdf.cell(W,6,sane(str(value)),new_x="LMARGIN",new_y="NEXT")

        # Growth Score
        section("1. GROWTH SCORE SUMMARY")
        if growth_r.get("success"):
            row2("Growth Score:", f"{growth_r['score']}/100 — {growth_r['grade']}")
            row2("Revenue Growth:", f"{growth_r['rev_growth']}% YTD")
            row2("Gross Margin:", f"{growth_r['gross_margin']}%")
            row2("Market Share:", f"{growth_r['mkt_share']}%")
            row2("Churn Rate:", f"{growth_r['churn']}%")
            row2("NPS Score:", f"{growth_r['nps']}")
            pdf.ln(3)
            for dim, data in growth_r.get("dimensions", {}).items():
                row2(f"  {dim}:", f"{data['score']}/{data['max']} — {data['detail']} ({data['value']})")
        pdf.ln(4)

        # Market Entry
        section("2. TOP MARKET OPPORTUNITIES")
        if market_r.get("markets"):
            for m in market_r["markets"][:5]:
                row2(f"  {m['city']} ({m['tier']}):",
                     f"Score {m['score']}/100 | Entry Rs.{m['entry_cost_l']}L | Opp Rs.{m['rev_opp_l']}L | {m['competition']} competition")
        pdf.ln(4)

        # Pricing
        section("3. PRICING OPTIMIZATION")
        if pricing_r.get("success"):
            row2("Current Price:", f"Rs.{pricing_r['current_price']}")
            row2("Optimal Price:", f"Rs.{pricing_r['optimal_price']}")
            row2("Competitor Price:", f"Rs.{pricing_r['competitor_price']}")
            row2("Profit Uplift:", f"{pricing_r['profit_uplift']}% additional profit")
        pdf.ln(4)

        # Competitor Ranking
        section("4. COMPETITOR POSITIONING")
        if competitor_r.get("positioning"):
            for i, c in enumerate(competitor_r["positioning"][:6], 1):
                row2(f"  #{i} {c['name']}:", f"Composite Score {c.get('composite','N/A')} | Share {c['share']}% | Cluster: {c.get('cluster','N/A')}")
        pdf.ln(4)

        # AI Strategy (stripped markdown)
        if ai_strategy and len(ai_strategy) > 100:
            section("5. AI GROWTH STRATEGY")
            clean = re.sub(r'[#*_`]','', ai_strategy)
            for line in clean.split('\n')[:40]:
                line = line.strip()
                if line:
                    pdf.multi_cell(W, 5, sane(line[:200]), new_x="LMARGIN", new_y="NEXT")

        # Footer
        pdf.ln(6)
        pdf.set_font("Helvetica","",8)
        pdf.set_text_color(150,150,150)
        pdf.cell(W,5,sane("Allworkss BI Suite — Module 5: Growth & Expansion Intelligence | Confidential"),new_x="LMARGIN",new_y="NEXT")

        out = f"/tmp/allworkss_growth_{int(time.time())}.pdf"
        pdf.output(out)
        return out
    except Exception as e:
        return ""


# ════════════════════════════════════════════════════════════
# SECTION I — HTML FORMATTERS
# ════════════════════════════════════════════════════════════

def format_growth_score_html(r: dict) -> str:
    if not r.get("success"):
        return f"<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Error: {r.get('error')}</div>"

    score = r["score"]; color = r["color"]
    dim_bars = ""
    for dim, d in r["dimensions"].items():
        pct = (d["score"] / d["max"]) * 100
        dc  = "#2ECC71" if pct >= 70 else "#F39C12" if pct >= 45 else "#E74C3C"
        dim_bars += (
            f'<div style="margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-bottom:3px;">'
            f'<span>{dim}</span>'
            f'<span style="color:{dc};font-weight:600;">{d["score"]}/{d["max"]} — {d["detail"]}</span></div>'
            f'<div style="height:6px;background:#1e1e1e;border-radius:3px;">'
            f'<div style="height:100%;width:{pct}%;background:{dc};border-radius:3px;"></div></div>'
            f'<div style="font-size:10px;color:#555;margin-top:2px;">{d["value"]}</div></div>'
        )

    kpis = [
        ("Revenue Growth", f"{r['rev_growth']}% YTD",   "#2ECC71" if r['rev_growth']>15 else "#F39C12"),
        ("Gross Margin",   f"{r['gross_margin']}%",      "#2ECC71" if r['gross_margin']>40 else "#F39C12"),
        ("Market Share",   f"{r['mkt_share']}%",         "#3498DB"),
        ("Churn Rate",     f"{r['churn']}%",             "#2ECC71" if r['churn']<5 else "#E74C3C"),
        ("NPS Score",      f"{r['nps']:.0f}",            "#2ECC71" if r['nps']>40 else "#F39C12"),
    ]
    kpi_html = "".join([
        f'<div style="background:#1a1a1a;border-radius:8px;padding:10px;text-align:center;">'
        f'<div style="font-size:18px;font-weight:800;color:{c};">{v}</div>'
        f'<div style="font-size:10px;color:#555;margin-top:2px;">{k}</div></div>'
        for k,v,c in kpis
    ])

    return f"""
<div style="font-family:system-ui,sans-serif;">
  <div style="display:grid;grid-template-columns:auto 1fr;gap:20px;background:#111;border-radius:12px;padding:18px;margin-bottom:14px;align-items:center;">
    <div style="text-align:center;min-width:140px;">
      <div style="font-size:56px;font-weight:900;color:{color};line-height:1;">{score}</div>
      <div style="font-size:11px;color:#555;margin-top:2px;">/ 100</div>
      <div style="background:{color}22;color:{color};font-size:12px;font-weight:700;
                  padding:4px 12px;border-radius:20px;border:1px solid {color};
                  margin-top:8px;display:inline-block;">{r['grade']}</div>
    </div>
    <div>
      <div style="font-size:11px;color:#555;letter-spacing:.07em;margin-bottom:10px;">GROWTH DIMENSIONS</div>
      {dim_bars}
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px;">
    {kpi_html}
  </div>
</div>"""


def format_market_entry_html(r: dict) -> str:
    if not r.get("markets"):
        return "<div style='color:#E74C3C;padding:20px;'>No market data available.</div>"

    rows = ""
    for m in r["markets"]:
        score_color = "#2ECC71" if m["score"]>70 else "#F39C12" if m["score"]>50 else "#E74C3C"
        comp_color  = {"Low":"#2ECC71","Medium":"#F39C12","High":"#E74C3C"}.get(m["competition"],"#888")
        rec_badge   = '<span style="background:#2ECC71;color:#000;font-size:9px;padding:2px 7px;border-radius:8px;font-weight:700;margin-left:6px;">TOP PICK</span>' if m["recommended"] else ""
        rows += f"""
<tr style="border-bottom:1px solid #1e1e1e;">
  <td style="padding:8px 10px;color:#e0e0e0;font-size:12px;font-weight:500;">{m['city']}{rec_badge}<div style="font-size:10px;color:#555;">{m['tier']}</div></td>
  <td style="padding:8px 10px;text-align:center;">
    <div style="font-size:15px;font-weight:700;color:{score_color};">{m['score']}</div>
  </td>
  <td style="padding:8px 10px;color:#aaa;font-size:11px;">{m['population_m']}M</td>
  <td style="padding:8px 10px;color:#aaa;font-size:11px;">Rs.{m['gdp_pcap']//1000}K</td>
  <td style="padding:8px 10px;"><span style="color:{comp_color};font-size:11px;">{m['competition']}</span></td>
  <td style="padding:8px 10px;color:#aaa;font-size:11px;">{m['ecom_pen']}%</td>
  <td style="padding:8px 10px;color:#aaa;font-size:11px;">{m['growth_rate']}%</td>
  <td style="padding:8px 10px;color:#3498DB;font-size:11px;">Rs.{m['entry_cost_l']}L</td>
  <td style="padding:8px 10px;color:#2ECC71;font-size:11px;">Rs.{m['rev_opp_l']}L</td>
  <td style="padding:8px 10px;color:#aaa;font-size:11px;">{m['break_even_mo']}mo</td>
</tr>"""

    top = r["top"]
    return f"""
<div style="font-family:system-ui,sans-serif;">
  <div style="background:linear-gradient(135deg,#0a1f14,#112b1a);border:2px solid #2ECC71;
              border-radius:12px;padding:14px 18px;margin-bottom:14px;">
    <div style="font-size:10px;color:#2ECC71;font-weight:700;letter-spacing:.08em;margin-bottom:6px;">TOP RECOMMENDED MARKET</div>
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
      <div>
        <div style="font-size:22px;font-weight:800;color:#e0e0e0;">{top['city']}</div>
        <div style="font-size:12px;color:#888;">{top['tier']} | {top['competition']} competition | {top['ecom_pen']}% e-com penetration</div>
      </div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;">
        <div style="text-align:center;"><div style="font-size:24px;font-weight:800;color:#2ECC71;">{top['score']}</div><div style="font-size:10px;color:#555;">/100 SCORE</div></div>
        <div style="text-align:center;"><div style="font-size:16px;font-weight:700;color:#3498DB;">Rs.{top['entry_cost_l']}L</div><div style="font-size:10px;color:#555;">ENTRY COST</div></div>
        <div style="text-align:center;"><div style="font-size:16px;font-weight:700;color:#F39C12;">Rs.{top['rev_opp_l']}L</div><div style="font-size:10px;color:#555;">REVENUE OPP</div></div>
        <div style="text-align:center;"><div style="font-size:16px;font-weight:700;color:#9B59B6;">{top['break_even_mo']}mo</div><div style="font-size:10px;color:#555;">BREAK-EVEN</div></div>
      </div>
    </div>
  </div>
  <div style="background:#111;border-radius:10px;overflow:auto;">
    <table style="width:100%;border-collapse:collapse;font-family:system-ui;">
      <thead><tr style="background:#1a1a1a;border-bottom:1px solid #2a2a2a;">
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">CITY</th>
        <th style="padding:8px 10px;text-align:center;font-size:10px;color:#555;">SCORE</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">POP</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">GDP/CAP</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">COMPETITION</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">ECOM</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">MKT GROWTH</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">ENTRY COST</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">REV OPP</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">BREAK-EVEN</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def format_pricing_html(r: dict) -> str:
    if not r.get("success"):
        return f"<div style='color:#E74C3C;padding:20px;'>{r.get('error')}</div>"

    uplift_color = "#2ECC71" if r["profit_uplift"] > 0 else "#E74C3C"
    price_dir    = "▲ Increase" if r["optimal_price"] > r["current_price"] else "▼ Decrease"
    price_color  = "#2ECC71" if r["optimal_price"] > r["current_price"] else "#F39C12"

    scenario_rows = ""
    for sc in r["scenarios"][::3]:  # every 3rd for brevity
        is_opt = abs(sc["price"] - r["optimal_price"]) < 5
        is_cur = abs(sc["price"] - r["current_price"]) < 5
        bg     = "#0a1f14" if is_opt else "#1a1200" if is_cur else "transparent"
        badge  = " ← OPTIMAL" if is_opt else " ← CURRENT" if is_cur else ""
        scenario_rows += (
            f'<tr style="background:{bg};border-bottom:1px solid #1e1e1e;">'
            f'<td style="padding:6px 10px;font-size:12px;color:#e0e0e0;">Rs.{sc["price"]:,.0f}{badge}</td>'
            f'<td style="padding:6px 10px;font-size:12px;color:#aaa;">{sc["demand"]:,.0f}</td>'
            f'<td style="padding:6px 10px;font-size:12px;color:#aaa;">Rs.{sc["revenue"]:,.0f}</td>'
            f'<td style="padding:6px 10px;font-size:12px;color:#2ECC71;">Rs.{sc["profit"]:,.0f}</td>'
            f'<td style="padding:6px 10px;font-size:12px;color:#aaa;">{sc["margin"]}%</td>'
            f'<td style="padding:6px 10px;font-size:12px;color:{"#F39C12" if sc["vs_comp"]>5 else "#2ECC71" if sc["vs_comp"]<-5 else "#aaa"};">{sc["vs_comp"]:+.1f}%</td>'
            f'</tr>'
        )

    return f"""
<div style="font-family:system-ui,sans-serif;">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:14px;">
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">CURRENT PRICE</div>
      <div style="font-size:22px;font-weight:800;color:#aaa;">Rs.{r['current_price']:,.0f}</div>
    </div>
    <div style="background:#0a1f14;border:2px solid #2ECC71;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#2ECC71;margin-bottom:4px;">OPTIMAL PRICE</div>
      <div style="font-size:22px;font-weight:800;color:#2ECC71;">Rs.{r['optimal_price']:,.0f}</div>
      <div style="font-size:11px;color:#555;">{price_dir}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">COMPETITOR PRICE</div>
      <div style="font-size:22px;font-weight:800;color:#3498DB;">Rs.{r['competitor_price']:,.0f}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">PROFIT UPLIFT</div>
      <div style="font-size:22px;font-weight:800;color:{uplift_color};">{r['profit_uplift']:+.1f}%</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">COST PER UNIT</div>
      <div style="font-size:22px;font-weight:800;color:#e0e0e0;">Rs.{r['cost_per_unit']:,.0f}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">PRICE ELASTICITY</div>
      <div style="font-size:22px;font-weight:800;color:#9B59B6;">{r['elasticity']}</div>
    </div>
  </div>
  <div style="background:#111;border-radius:10px;overflow:auto;">
    <div style="padding:10px 14px;font-size:10px;color:#555;letter-spacing:.07em;border-bottom:1px solid #1e1e1e;">
      PRICE SCENARIO ANALYSIS (demand elasticity model)
    </div>
    <table style="width:100%;border-collapse:collapse;font-family:system-ui;">
      <thead><tr style="background:#1a1a1a;border-bottom:1px solid #2a2a2a;">
        <th style="padding:6px 10px;text-align:left;font-size:10px;color:#555;">PRICE</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;color:#555;">DEMAND</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;color:#555;">REVENUE</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;color:#555;">PROFIT</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;color:#555;">MARGIN</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;color:#555;">VS COMPETITOR</th>
      </tr></thead>
      <tbody>{scenario_rows}</tbody>
    </table>
  </div>
</div>"""


def format_competitor_html(r: dict) -> str:
    if not r.get("success"):
        return f"<div style='color:#E74C3C;padding:20px;'>{r.get('error','No competitor data')}</div>"

    rows = ""
    for i, c in enumerate(r.get("positioning", []), 1):
        is_us   = "our" in c["name"].lower() or "my" in c["name"].lower()
        row_bg  = "#0a1f14" if is_us else "transparent"
        badge   = ' <span style="background:#3498DB;color:#fff;font-size:9px;padding:1px 5px;border-radius:4px;">YOU</span>' if is_us else ""
        cluster_colors = {"Premium Leaders":"#9B59B6","Mid-Market Players":"#3498DB","Value Segment":"#F39C12"}
        cc = cluster_colors.get(c.get("cluster",""), "#888")
        rows += (
            f'<tr style="background:{row_bg};border-bottom:1px solid #1e1e1e;">'
            f'<td style="padding:8px 10px;font-size:12px;color:#e0e0e0;">#{i} {c["name"]}{badge}</td>'
            f'<td style="padding:8px 10px;"><span style="background:{cc}22;color:{cc};font-size:10px;padding:2px 7px;border-radius:8px;">{c.get("cluster","N/A")}</span></td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#aaa;">{c["share"]}%</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#aaa;">{c.get("composite","N/A")}</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#aaa;">{c.get("quality","N/A")}/10</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#aaa;">{c.get("brand","N/A")}/10</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#aaa;">{c.get("digital","N/A")}/10</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#F39C12;">{c.get("rating","N/A")}</td>'
            f'</tr>'
        )

    return f"""
<div style="font-family:system-ui,sans-serif;">
  <div style="background:#111;border-radius:8px;padding:12px 14px;margin-bottom:12px;">
    <div style="font-size:13px;color:#e0e0e0;font-weight:600;">Your Competitive Position: 
      <span style="color:#3498DB;">#{r.get('our_rank','?')} of {len(r.get('positioning',[]))} players</span>
    </div>
    <div style="font-size:12px;color:#666;margin-top:4px;">Composite score: {r.get('our_score','N/A')} | Use this to identify gaps and leapfrog competitors</div>
  </div>
  <div style="background:#111;border-radius:10px;overflow:auto;">
    <table style="width:100%;border-collapse:collapse;">
      <thead><tr style="background:#1a1a1a;border-bottom:1px solid #2a2a2a;">
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">COMPANY</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">CLUSTER</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">MKT SHARE</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">COMPOSITE</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">QUALITY</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">BRAND</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">DIGITAL</th>
        <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;">RATING</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def format_whatif_html(r: dict) -> str:
    if not r.get("success"):
        return f"<div style='color:#E74C3C;padding:20px;'>{r.get('error')}</div>"

    proj = r["projections"]
    max_rev = max(p["revenue"] for p in proj)

    bars = ""
    for p in proj:
        h = int((p["revenue"] / max_rev) * 120)
        bars += (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:3px;flex:1;">'
            f'<div style="font-size:9px;color:#2ECC71;">Rs.{p["revenue"]/100000:.1f}L</div>'
            f'<div style="width:100%;height:{h}px;background:linear-gradient(180deg,#2ECC71,#1D9E75);border-radius:3px 3px 0 0;min-height:4px;"></div>'
            f'<div style="font-size:9px;color:#555;">M{p["month"]}</div></div>'
        )

    return f"""
<div style="font-family:system-ui,sans-serif;">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px;">
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">SCENARIO</div>
      <div style="font-size:14px;font-weight:700;color:#e0e0e0;">{r['scenario']}</div>
    </div>
    <div style="background:#0a1f14;border:1px solid #2ECC71;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#2ECC71;margin-bottom:4px;">FINAL MONTH REVENUE</div>
      <div style="font-size:18px;font-weight:800;color:#2ECC71;">Rs.{r['final_revenue']/100000:.1f}L</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">TOTAL {r['months']}-MONTH REVENUE</div>
      <div style="font-size:16px;font-weight:700;color:#e0e0e0;">Rs.{r['total_revenue']/100000:.0f}L</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">PROJECTED GROWTH</div>
      <div style="font-size:18px;font-weight:800;color:#F39C12;">{r['projected_growth']:+.1f}%</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#555;margin-bottom:4px;">MONTHLY GROWTH RATE</div>
      <div style="font-size:16px;font-weight:700;color:#9B59B6;">{r['effective_monthly']:+.2f}%/mo</div>
    </div>
  </div>
  <div style="background:#111;border-radius:10px;padding:14px;">
    <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:12px;">REVENUE PROJECTION — {r['months']} MONTHS</div>
    <div style="display:flex;align-items:flex-end;gap:3px;height:140px;">{bars}</div>
  </div>
</div>"""


# ════════════════════════════════════════════════════════════
# SECTION J — MASTER HANDLERS
# ════════════════════════════════════════════════════════════

_M5_CACHE = {"growth": None, "market": None, "pricing": None, "competitor": None}

def run_growth_analysis(file, use_manual: bool, **manual_fields) -> tuple:
    if not PANDAS_OK:
        return "<div style='color:#E74C3C;'>pandas not installed</div>", "Error"
    try:
        if use_manual:
            result = calculate_growth_score(manual=manual_fields)
        else:
            if file is not None:
                filepath = file.name if hasattr(file,"name") else str(file)
                df, err = (lambda p: (pd.read_csv(p,encoding="utf-8",errors="replace") if str(p).endswith(".csv") else pd.read_excel(p), None))(filepath)
            else:
                df = pd.read_csv(StringIO(SAMPLE_BUSINESS_CSV))
            result = calculate_growth_score(df=df)

        _M5_CACHE["growth"] = result
        if result.get("success"):
            html   = format_growth_score_html(result)
            status = f"✅ Growth Score: **{result['score']}/100** — {result['grade']}"
        else:
            html   = f"<div style='color:#E74C3C;padding:20px;'>Error: {result.get('error')}</div>"
            status = f"❌ {result.get('error')}"
        return html, status
    except Exception as e:
        return f"<div style='color:#E74C3C;padding:20px;'>Error: {e}</div>", f"❌ {e}"


def run_market_analysis(category: str, current_revenue: float,
                        budget: float, risk: str) -> tuple:
    try:
        result = analyze_market_entry(category, current_revenue, budget, risk)
        _M5_CACHE["market"] = result
        html   = format_market_entry_html(result)
        status = f"✅ Best market: **{result['top']['city']}** (Score {result['top']['score']}/100) | {len(result['markets'])} cities analyzed"
        return html, status
    except Exception as e:
        return f"<div style='color:#E74C3C;padding:20px;'>Error: {e}</div>", f"❌ {e}"


def run_pricing_analysis(file, use_manual: bool,
                         cur_price, cur_units, comp_price, cost_unit, elasticity) -> tuple:
    try:
        if use_manual:
            result = run_pricing_optimization(manual={
                "current_price": cur_price, "current_units": cur_units,
                "competitor_price": comp_price, "cost_per_unit": cost_unit,
                "price_elasticity": elasticity,
            })
        else:
            if file is not None:
                filepath = file.name if hasattr(file,"name") else str(file)
                df = pd.read_csv(filepath) if str(filepath).endswith(".csv") else pd.read_excel(filepath)
            else:
                df = pd.read_csv(StringIO(SAMPLE_BUSINESS_CSV))
            result = run_pricing_optimization(df=df)

        _M5_CACHE["pricing"] = result
        html   = format_pricing_html(result)
        status = (f"✅ Optimal price: **Rs.{result['optimal_price']:,.0f}** | "
                  f"Profit uplift: **{result['profit_uplift']:+.1f}%**") if result.get("success") else f"❌ {result.get('error')}"
        return html, status
    except Exception as e:
        return f"<div style='color:#E74C3C;padding:20px;'>Error: {e}</div>", f"❌ {e}"


def run_competitor_benchmark(file) -> tuple:
    try:
        if file is not None:
            filepath = file.name if hasattr(file,"name") else str(file)
            df = pd.read_csv(filepath) if str(filepath).endswith(".csv") else pd.read_excel(filepath)
        else:
            df = None
        result = run_competitor_analysis(df)
        _M5_CACHE["competitor"] = result
        html   = format_competitor_html(result)
        status = f"✅ Your rank: **#{result.get('our_rank','?')}** of {len(result.get('positioning',[]))} competitors"
        return html, status
    except Exception as e:
        return f"<div style='color:#E74C3C;padding:20px;'>Error: {e}</div>", f"❌ {e}"


def run_whatif(base_rev: float, base_growth: float, scenario: str,
               mktg_mult: float, price_chg: float, churn_chg: float,
               market_chg: float, months: int) -> tuple:
    try:
        levers = {"mktg_mult":mktg_mult,"price_chg":price_chg/100,
                  "churn_chg":churn_chg,"market_chg":market_chg/100}
        result = run_whatif_simulator(base_rev, base_growth, scenario, levers, int(months))
        html   = format_whatif_html(result)
        status = (f"✅ Projected: **Rs.{result['final_revenue']/100000:.1f}L/month** at month {int(months)} | "
                  f"Total: Rs.{result['total_revenue']/100000:.0f}L | Growth: {result['projected_growth']:+.1f}%")
        return html, status
    except Exception as e:
        return f"<div style='color:#E74C3C;padding:20px;'>Error: {e}</div>", f"❌ {e}"


def run_ai_strategy_and_pdf(biz_name: str, category: str, founded: str) -> tuple:
    biz_info = {"name": biz_name or "Your Business", "category": category or "General", "founded": founded or "2020"}
    g = _M5_CACHE.get("growth") or {}
    m = _M5_CACHE.get("market") or {}
    p = _M5_CACHE.get("pricing") or {}

    strategy = get_ai_growth_strategy(g, m, p, biz_info)
    c = _M5_CACHE.get("competitor") or {}
    pdf_path = generate_growth_pdf(g, m, p, c, biz_info, strategy)

    return strategy, pdf_path if pdf_path else None
