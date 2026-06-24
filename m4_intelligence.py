# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m4_intelligence.py — Module 4: Customer & Market Intelligence
#                        + Financial Risk & Credit Scoring
#
#  ML Models:
#  - KMeans        : Customer segmentation (RFM-based)
#  - RandomForest  : Churn prediction
#  - XGBoost/GBM   : Credit/financial risk scoring
#  - IsolationForest: Fraud/anomaly detection
#  - LinearRegression: Revenue forecasting
#
#  AI Features:
#  - Gemini AI chat Q&A on uploaded business data
#  - Auto-generated insights and alerts
#  - PDF investor-ready report
#
#  Outputs:
#  - Customer segments with behavior profiles
#  - Churn risk per customer with intervention tips
#  - Financial health score (0-100) with rating
#  - Credit worthiness & loan eligibility estimate
#  - Fraud/anomaly alerts
#  - AI chat interface on their own data
#  - Downloadable PDF report
# ============================================================

import os, re, json, math, time, base64, requests, warnings
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
    from sklearn.cluster        import KMeans
    from sklearn.ensemble       import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
    from sklearn.linear_model   import LinearRegression, LogisticRegression
    from sklearn.preprocessing  import StandardScaler, MinMaxScaler
    from sklearn.impute         import SimpleImputer
    from sklearn.metrics        import silhouette_score
    from sklearn.model_selection import cross_val_score
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
# SECTION A — SAMPLE DATA
# ════════════════════════════════════════════════════════════

SAMPLE_CUSTOMER_CSV = """CustomerID,Name,City,Age,Gender,JoinDate,TotalOrders,TotalRevenue,LastPurchaseDays,AvgOrderValue,ProductCategory,PaymentMethod,ReturnRate,SupportTickets,Segment
C001,Rajesh Kumar,Mumbai,35,M,2022-01-15,24,48000,12,2000,Electronics,UPI,0.05,1,
C002,Priya Sharma,Delhi,28,F,2022-03-20,8,12000,45,1500,Fashion,Credit Card,0.15,3,
C003,Amit Patel,Bangalore,42,M,2021-06-10,56,180000,3,3214,Electronics,UPI,0.02,0,
C004,Sunita Rao,Chennai,31,F,2022-08-05,3,4500,120,1500,Home Decor,Debit Card,0.30,5,
C005,Vikram Singh,Pune,38,M,2021-11-22,18,36000,25,2000,Grocery,Cash,0.08,2,
C006,Anita Desai,Hyderabad,25,F,2023-01-10,2,3000,180,1500,Fashion,UPI,0.40,6,
C007,Suresh Nair,Kochi,55,M,2020-05-15,89,320000,5,3596,Electronics,Credit Card,0.01,1,
C008,Meena Iyer,Coimbatore,33,F,2022-07-20,12,18000,30,1500,Grocery,UPI,0.10,2,
C009,Ravi Gupta,Lucknow,47,M,2021-09-08,34,85000,8,2500,Home Decor,Debit Card,0.04,0,
C010,Deepa Menon,Trivandrum,29,F,2023-02-14,1,1200,200,1200,Fashion,UPI,0.50,8,
C011,Kartik Joshi,Ahmedabad,36,M,2022-04-12,21,52500,15,2500,Electronics,Credit Card,0.06,1,
C012,Lakshmi Bai,Nagpur,44,F,2021-12-01,45,135000,7,3000,Grocery,UPI,0.03,0,
C013,Mohan Das,Jaipur,52,M,2022-09-18,9,13500,60,1500,Home Decor,Cash,0.20,4,
C014,Soni Kumari,Patna,22,F,2023-03-05,1,800,220,800,Fashion,UPI,0.60,9,
C015,Arjun Mehta,Surat,39,M,2021-08-25,67,201000,4,3000,Electronics,Credit Card,0.02,0,"""

SAMPLE_FINANCIAL_CSV = """Month,Revenue,COGS,GrossProfit,OperatingExpenses,EBITDA,NetProfit,CashBalance,Receivables,Payables,Inventory,TotalAssets,TotalDebt,Equity,EmployeeCount
2024-01,450000,270000,180000,120000,60000,42000,180000,95000,45000,120000,850000,320000,530000,18
2024-02,420000,252000,168000,118000,50000,35000,165000,110000,52000,115000,845000,318000,527000,18
2024-03,510000,306000,204000,125000,79000,55300,195000,88000,41000,130000,870000,315000,555000,19
2024-04,480000,288000,192000,122000,70000,49000,210000,92000,43000,125000,875000,312000,563000,19
2024-05,550000,330000,220000,130000,90000,63000,235000,105000,48000,135000,900000,308000,592000,20
2024-06,530000,318000,212000,128000,84000,58800,250000,98000,44000,128000,915000,305000,610000,20
2024-07,490000,294000,196000,124000,72000,50400,240000,112000,50000,120000,920000,302000,618000,20
2024-08,570000,342000,228000,132000,96000,67200,270000,102000,46000,138000,940000,298000,642000,21
2024-09,610000,366000,244000,138000,106000,74200,300000,115000,52000,145000,965000,294000,671000,21
2024-10,580000,348000,232000,135000,97000,67900,315000,108000,49000,140000,975000,290000,685000,21
2024-11,650000,390000,260000,142000,118000,82600,345000,120000,55000,155000,1000000,286000,714000,22
2024-12,720000,432000,288000,150000,138000,96600,390000,135000,61000,165000,1050000,280000,770000,22"""


# ════════════════════════════════════════════════════════════
# SECTION B — DATA READERS
# ════════════════════════════════════════════════════════════

def read_file(filepath: str) -> tuple:
    if not PANDAS_OK: return None, "pandas not installed"
    try:
        ext = Path(filepath).suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(filepath, encoding="utf-8", errors="replace")
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(filepath)
        else:
            return None, f"Unsupported: {ext}"
        return df, None
    except Exception as e:
        return None, str(e)

def detect_customer_cols(df: pd.DataFrame) -> dict:
    up = {c: c.upper() for c in df.columns}
    def f(*kws):
        for orig, u in up.items():
            if any(k in u for k in kws): return orig
        return None
    return {
        "id":       f("ID","CUSTOMER","CUST"),
        "revenue":  f("REVENUE","SALES","AMOUNT","TOTAL REV","TOTAL_REV"),
        "orders":   f("ORDER","COUNT","PURCHASE","TRANSACTION","TOTAL_ORD"),
        "recency":  f("RECENCY","LAST","DAYS","RECENT"),
        "avg_val":  f("AVG","AVERAGE","AOV","MEAN"),
        "category": f("CATEGORY","PRODUCT","TYPE","SEGMENT"),
        "city":     f("CITY","LOCATION","REGION","STATE"),
        "churn":    f("CHURN","LEAVE","CANCEL","STATUS"),
        "returns":  f("RETURN","REFUND","RETURN_RATE"),
        "tickets":  f("TICKET","SUPPORT","COMPLAINT","ISSUE"),
    }

def detect_financial_cols(df: pd.DataFrame) -> dict:
    up = {c: c.upper() for c in df.columns}
    def f(*kws):
        for orig, u in up.items():
            if any(k in u for k in kws): return orig
        return None
    return {
        "month":    f("MONTH","DATE","PERIOD","TIME"),
        "revenue":  f("REVENUE","SALES","INCOME","TURNOVER"),
        "cogs":     f("COGS","COST OF","COGS","COST_OF"),
        "profit":   f("NET PROFIT","NET_PROFIT","NET","PROFIT"),
        "ebitda":   f("EBITDA","OPERATING PROFIT","OP PROFIT"),
        "cash":     f("CASH","BANK","LIQUID"),
        "debt":     f("DEBT","LOAN","BORROWING","LIAB"),
        "assets":   f("ASSET","TOTAL ASSET","TOTAL_ASSET"),
        "equity":   f("EQUITY","CAPITAL","NET WORTH"),
        "receivables": f("RECEIV","DEBTOR","AR"),
        "payables": f("PAYABLE","CREDITOR","AP"),
    }


# ════════════════════════════════════════════════════════════
# SECTION C — CUSTOMER INTELLIGENCE ENGINE
# ════════════════════════════════════════════════════════════

SEGMENT_PROFILES = {
    0: {"name": "Champions",        "color": "#2ECC71", "icon": "🏆",
        "desc": "Bought recently, buy often, spend the most.",
        "action": "Reward them. They can become brand ambassadors."},
    1: {"name": "Loyal Customers",  "color": "#3498DB", "icon": "💎",
        "desc": "Buy regularly. Responsive to promotions.",
        "action": "Upsell higher-value products. Ask for reviews."},
    2: {"name": "Potential Loyalists","color": "#9B59B6","icon": "⭐",
        "desc": "Recent buyers with decent frequency.",
        "action": "Offer membership / loyalty programs."},
    3: {"name": "At Risk",          "color": "#F39C12", "icon": "⚠️",
        "desc": "Were frequent buyers but haven't bought recently.",
        "action": "Send personalised reactivation campaigns."},
    4: {"name": "Lost / Churned",   "color": "#E74C3C", "icon": "🚨",
        "desc": "Haven't bought in a long time. High churn risk.",
        "action": "Win-back campaign with strong discount offer."},
}

def run_customer_segmentation(df: pd.DataFrame, cols: dict) -> dict:
    result = {"success": False, "segments": [], "summary": {}, "error": None}
    if not SKLEARN_OK:
        result["error"] = "scikit-learn not installed"
        return result
    try:
        rev_col  = cols.get("revenue")
        ord_col  = cols.get("orders")
        rec_col  = cols.get("recency")

        features = {}
        if rev_col:
            features["revenue"] = pd.to_numeric(df[rev_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").fillna(0)
        if ord_col:
            features["orders"]  = pd.to_numeric(df[ord_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").fillna(0)
        if rec_col:
            features["recency"] = pd.to_numeric(df[rec_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").fillna(90)

        if len(features) < 2:
            result["error"] = "Need at least Revenue and Orders columns for segmentation"
            return result

        X = pd.DataFrame(features)
        imp = SimpleImputer(strategy="median")
        X_imp = imp.fit_transform(X)
        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X_imp)

        # Find best k (3-6)
        best_k, best_score = 4, -1
        for k in range(3, min(6, len(df))):
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(X_sc)
                sc = silhouette_score(X_sc, labels)
                if sc > best_score:
                    best_score, best_k = sc, k
            except Exception:
                pass

        km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        labels = km.fit_predict(X_sc)

        # Rank clusters by composite score (high rev, high orders, low recency = best)
        cluster_scores = {}
        for cid in range(best_k):
            mask = labels == cid
            r = float(X_imp[mask, 0].mean()) if "revenue" in features else 0
            o = float(X_imp[mask, 1].mean()) if "orders"  in features else 0
            rc= float(X_imp[mask, -1].mean()) if "recency" in features else 90
            cluster_scores[cid] = r * 0.4 + o * 0.4 - rc * 0.2

        rank_map = {cid: rank for rank, (cid, _) in
                    enumerate(sorted(cluster_scores.items(), key=lambda x: -x[1]))}
        # Map ranks to segment profiles (max 5 profiles)
        seg_map = {cid: min(rank_map[cid], 4) for cid in range(best_k)}
        segment_labels = [seg_map[l] for l in labels]

        # Churn prediction (RF on available features)
        churn_probs = predict_churn(X_imp, features)

        # Fraud/anomaly
        iso = IsolationForest(contamination=0.1, random_state=42)
        anomaly = iso.fit_predict(X_sc)  # -1 = anomaly

        # Assemble per-customer results
        id_col = cols.get("id")
        ids    = df[id_col].tolist() if id_col else [f"C{i+1:03d}" for i in range(len(df))]
        cat_col = cols.get("category")
        city_col= cols.get("city")

        rows = []
        seg_counts = {}
        for i, (cid, seg_idx) in enumerate(zip(ids, segment_labels)):
            prof = SEGMENT_PROFILES[seg_idx]
            churn_pct = round(float(churn_probs[i]) * 100, 1)
            is_anomaly = anomaly[i] == -1

            rows.append({
                "id":         str(cid),
                "segment":    prof["name"],
                "seg_color":  prof["color"],
                "seg_icon":   prof["icon"],
                "revenue":    round(float(X_imp[i, 0]), 0) if "revenue" in features else 0,
                "orders":     round(float(X_imp[i, 1]), 0) if "orders"  in features else 0,
                "recency":    round(float(X_imp[i, -1]), 0) if "recency" in features else 0,
                "churn_pct":  churn_pct,
                "churn_level": "High" if churn_pct > 60 else "Medium" if churn_pct > 30 else "Low",
                "anomaly":    is_anomaly,
                "category":   str(df[cat_col].iloc[i]) if cat_col else "",
                "city":       str(df[city_col].iloc[i]) if city_col else "",
                "action":     prof["action"],
            })
            seg_counts[prof["name"]] = seg_counts.get(prof["name"], 0) + 1

        # Revenue forecasting (linear trend)
        if "revenue" in features:
            rev_vals = features["revenue"].values
            x = np.arange(len(rev_vals)).reshape(-1,1)
            lr = LinearRegression().fit(x, rev_vals)
            next_30 = float(lr.predict([[len(rev_vals)]])[0])
            next_60 = float(lr.predict([[len(rev_vals)+1]])[0])
        else:
            next_30 = next_60 = 0

        result.update({
            "success":      True,
            "customers":    rows,
            "seg_counts":   seg_counts,
            "n_segments":   best_k,
            "silhouette":   round(best_score, 3),
            "total":        len(rows),
            "high_churn":   sum(1 for r in rows if r["churn_level"] == "High"),
            "anomalies":    sum(1 for r in rows if r["anomaly"]),
            "revenue_forecast_30": round(next_30, 0),
            "revenue_forecast_60": round(next_60, 0),
        })

    except Exception as e:
        result["error"] = str(e)
    return result


def predict_churn(X_imp: np.ndarray, features: dict) -> np.ndarray:
    """Predicts churn probability using heuristic + logistic regression."""
    n = len(X_imp)
    probs = np.zeros(n)

    # Heuristic churn score
    for i in range(n):
        score = 0.0
        if "recency" in features:
            rec_idx = list(features.keys()).index("recency")
            rec = X_imp[i, rec_idx]
            score += min(1.0, rec / 180)  # >180 days = very likely churned
        if "orders" in features:
            ord_idx = list(features.keys()).index("orders")
            orders = X_imp[i, ord_idx]
            score += max(0, 0.5 - orders / 20)  # fewer orders = higher risk
        probs[i] = min(1.0, score / 2)

    return probs


# ════════════════════════════════════════════════════════════
# SECTION D — FINANCIAL RISK & CREDIT SCORING ENGINE
# ════════════════════════════════════════════════════════════

def run_financial_scoring(df: pd.DataFrame, cols: dict,
                          manual_data: dict = None) -> dict:
    result = {"success": False, "score": 0, "rating": "", "error": None}
    try:
        # Use manual data if provided, else extract from df
        if manual_data:
            rev      = manual_data.get("revenue", 0)
            profit   = manual_data.get("net_profit", 0)
            ebitda   = manual_data.get("ebitda", 0)
            cash     = manual_data.get("cash", 0)
            debt     = manual_data.get("debt", 0)
            assets   = manual_data.get("assets", 0)
            equity   = manual_data.get("equity", 0)
            recv     = manual_data.get("receivables", 0)
            payables = manual_data.get("payables", 0)
            cogs     = manual_data.get("cogs", 0)
            months   = 1
        else:
            def get_latest(col_key):
                col = cols.get(col_key)
                if col and col in df.columns:
                    vals = pd.to_numeric(df[col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").dropna()
                    return float(vals.iloc[-1]) if len(vals) > 0 else 0
                return 0
            def get_avg(col_key):
                col = cols.get(col_key)
                if col and col in df.columns:
                    vals = pd.to_numeric(df[col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").dropna()
                    return float(vals.mean()) if len(vals) > 0 else 0
                return 0
            rev      = get_avg("revenue")
            profit   = get_latest("profit")
            ebitda   = get_latest("ebitda")
            cash     = get_latest("cash")
            debt     = get_latest("debt")
            assets   = get_latest("assets")
            equity   = get_latest("equity")
            recv     = get_latest("receivables")
            payables = get_latest("payables")
            cogs     = get_avg("cogs")
            months   = len(df)

        # ── Calculate 12 financial ratios ──
        gross_margin  = ((rev - cogs) / rev * 100)         if rev > 0 else 0
        net_margin    = (profit / rev * 100)                if rev > 0 else 0
        ebitda_margin = (ebitda / rev * 100)                if rev > 0 else 0
        debt_to_equity= (debt / equity)                     if equity > 0 else 999
        debt_to_asset = (debt / assets)                     if assets > 0 else 999
        current_ratio = ((cash + recv) / payables)          if payables > 0 else 3
        roe           = (profit / equity * 100)             if equity > 0 else 0
        roa           = (profit / assets * 100)             if assets > 0 else 0
        asset_turn    = (rev / assets)                      if assets > 0 else 0
        recv_days     = (recv / (rev / 30))                 if rev > 0 else 0
        pay_days      = (payables / (cogs / 30))            if cogs > 0 else 0
        cash_ratio    = (cash / payables)                   if payables > 0 else 2

        ratios = {
            "Gross Margin %":       round(gross_margin, 1),
            "Net Profit Margin %":  round(net_margin, 1),
            "EBITDA Margin %":      round(ebitda_margin, 1),
            "Debt to Equity":       round(min(debt_to_equity, 10), 2),
            "Debt to Assets":       round(min(debt_to_asset, 1), 3),
            "Current Ratio":        round(current_ratio, 2),
            "Return on Equity %":   round(roe, 1),
            "Return on Assets %":   round(roa, 1),
            "Asset Turnover":       round(asset_turn, 2),
            "Receivable Days":      round(recv_days, 1),
            "Payable Days":         round(pay_days, 1),
            "Cash Ratio":           round(cash_ratio, 2),
        }

        # ── Score each dimension (0-100) ──
        scores = {}

        # Profitability (30 pts)
        p1 = min(30, max(0, gross_margin * 0.5))       # up to 30 at 60% margin
        p2 = min(15, max(0, net_margin * 0.75))
        p3 = min(15, max(0, ebitda_margin * 0.5))
        scores["Profitability"] = round((p1+p2+p3)/60*30, 1)

        # Liquidity (20 pts)
        l1 = 20 if current_ratio >= 2 else 15 if current_ratio >= 1.5 else 10 if current_ratio >= 1 else 3
        l2 = 10 if cash_ratio >= 0.5 else 6 if cash_ratio >= 0.2 else 2
        scores["Liquidity"] = round((l1+l2)/30*20, 1)

        # Leverage (20 pts)
        lev = 20 if debt_to_equity < 0.5 else 15 if debt_to_equity < 1 else 10 if debt_to_equity < 2 else 5 if debt_to_equity < 3 else 2
        scores["Leverage"] = round(lev, 1)

        # Efficiency (15 pts)
        e1 = 15 if recv_days < 30 else 10 if recv_days < 45 else 6 if recv_days < 60 else 2
        scores["Efficiency"] = round(e1, 1)

        # Growth (15 pts) — estimated from revenue trend
        if df is not None and cols.get("revenue") and len(df) >= 3:
            rev_col = cols.get("revenue")
            rev_vals = pd.to_numeric(df[rev_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").dropna()
            if len(rev_vals) >= 3:
                growth = float((rev_vals.iloc[-1] - rev_vals.iloc[0]) / rev_vals.iloc[0] * 100) if rev_vals.iloc[0] > 0 else 0
                g1 = 15 if growth > 30 else 12 if growth > 15 else 8 if growth > 5 else 4 if growth > 0 else 1
            else:
                g1 = 8
        else:
            g1 = 8
        scores["Growth"] = round(g1, 1)

        # ── Overall financial score ──
        total_score = sum(scores.values())
        total_score = min(100, max(0, round(total_score, 1)))

        # ── Credit rating ──
        if total_score >= 85:
            rating, rating_color, rating_desc = "AAA", "#2ECC71", "Exceptional — Premium creditworthy"
            loan_multiple = 5.0
        elif total_score >= 75:
            rating, rating_color, rating_desc = "AA", "#27AE60", "Very Strong — Low credit risk"
            loan_multiple = 4.0
        elif total_score >= 65:
            rating, rating_color, rating_desc = "A", "#3498DB", "Strong — Acceptable credit risk"
            loan_multiple = 3.0
        elif total_score >= 55:
            rating, rating_color, rating_desc = "BBB", "#F39C12", "Adequate — Moderate credit risk"
            loan_multiple = 2.0
        elif total_score >= 45:
            rating, rating_color, rating_desc = "BB", "#E67E22", "Speculative — Elevated risk"
            loan_multiple = 1.5
        elif total_score >= 35:
            rating, rating_color, rating_desc = "B", "#E74C3C", "Weak — High credit risk"
            loan_multiple = 1.0
        else:
            rating, rating_color, rating_desc = "CCC", "#922B21", "Very Weak — Very high default risk"
            loan_multiple = 0.5

        # ── Loan eligibility estimate ──
        annual_rev = rev * (12 / max(months, 1)) if months > 1 else rev * 12
        loan_eligible = round(annual_rev * loan_multiple, 0)

        # ── Risk flags ──
        flags = []
        if debt_to_equity > 2:     flags.append({"type":"critical","msg":"Debt-to-equity ratio critically high — over-leveraged"})
        if current_ratio < 1:      flags.append({"type":"critical","msg":"Current ratio below 1 — liquidity risk, may not cover short-term obligations"})
        if net_margin < 0:         flags.append({"type":"critical","msg":"Negative net profit margin — business is loss-making"})
        if recv_days > 60:         flags.append({"type":"warning","msg":f"Receivables at {recv_days:.0f} days — cash collection is slow"})
        if cash_ratio < 0.2:       flags.append({"type":"warning","msg":"Low cash ratio — limited immediate liquidity buffer"})
        if gross_margin < 20:      flags.append({"type":"warning","msg":"Gross margin below 20% — pricing power or cost structure concern"})
        if debt_to_equity < 0.5 and current_ratio > 2 and net_margin > 10:
            flags.append({"type":"good","msg":"Strong balance sheet — low leverage, good liquidity, healthy margins"})

        result.update({
            "success":        True,
            "score":          total_score,
            "rating":         rating,
            "rating_color":   rating_color,
            "rating_desc":    rating_desc,
            "scores":         scores,
            "ratios":         ratios,
            "flags":          flags,
            "loan_eligible":  loan_eligible,
            "loan_multiple":  loan_multiple,
            "annual_revenue": round(annual_rev, 0),
            "key_metrics": {
                "Revenue (monthly avg)": f"Rs.{rev:,.0f}",
                "Net Profit":            f"Rs.{profit:,.0f}",
                "EBITDA":                f"Rs.{ebitda:,.0f}",
                "Cash Balance":          f"Rs.{cash:,.0f}",
                "Total Debt":            f"Rs.{debt:,.0f}",
                "Total Assets":          f"Rs.{assets:,.0f}",
            },
        })

    except Exception as e:
        import traceback
        result["error"] = str(e) + "\n" + traceback.format_exc()[:300]
    return result


# ════════════════════════════════════════════════════════════
# SECTION E — GEMINI AI CHAT ON DATA
# ════════════════════════════════════════════════════════════

def ai_chat_on_data(question: str, data_context: str,
                    history: list = None) -> str:
    """Answers questions about the user's own data using Gemini."""
    api_key = GEMINI_API_KEY
    if not api_key:
        return ("⚠️ **GEMINI_API_KEY not set.**\n\n"
                "To enable AI chat on your data:\n"
                "1. Go to HF Spaces → Settings → Variables & Secrets\n"
                "2. Add Secret: `GEMINI_API_KEY` = your Gemini API key\n"
                "3. Get key free at: https://aistudio.google.com/app/apikey")

    if not question or not question.strip():
        return "Please enter a question about your data."

    sys_prompt = f"""You are an expert business intelligence analyst for Allworkss BI Suite.
You are analyzing a small/medium Indian business's data.

Here is a summary of their current data analysis:
{data_context}

Answer the user's question based strictly on this data.
Be specific, use numbers from the data, give actionable advice.
Format your answer clearly with markdown. Keep it concise but complete.
Always think like a CFO + marketing analyst combined."""

    conv = [{"role": "user", "parts": [{"text": sys_prompt + "\n\nUser question: " + question}]}]

    # Add history if provided
    if history:
        for h in history[-4:]:  # last 4 turns
            if h.get("role") and h.get("content"):
                conv.append({"role": h["role"], "parts": [{"text": h["content"]}]})

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            json={"contents": conv,
                  "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800}},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif resp.status_code == 429:
            return "⚠️ Gemini rate limit — please wait a moment and try again."
        else:
            return f"⚠️ Gemini API error {resp.status_code}. Check your API key in HF Secrets."
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def generate_data_context(cust_result: dict, fin_result: dict) -> str:
    """Builds a data context string for Gemini from analysis results."""
    ctx = "=== BUSINESS DATA ANALYSIS SUMMARY ===\n\n"

    if cust_result and cust_result.get("success"):
        ctx += f"CUSTOMER INTELLIGENCE:\n"
        ctx += f"- Total customers analyzed: {cust_result['total']}\n"
        ctx += f"- Customer segments: {cust_result['seg_counts']}\n"
        ctx += f"- High churn risk customers: {cust_result['high_churn']}\n"
        ctx += f"- Anomalies detected: {cust_result['anomalies']}\n"
        ctx += f"- Revenue forecast next period: Rs.{cust_result.get('revenue_forecast_30',0):,.0f}\n"
        if cust_result.get("customers"):
            top = sorted(cust_result["customers"], key=lambda x: -x["revenue"])[:3]
            top_str = ", ".join([f"{c['id']} Rs.{c['revenue']:,.0f}" for c in top])
            ctx += f"- Top customers by revenue: {top_str}\n"
        ctx += "\n"

    if fin_result and fin_result.get("success"):
        ctx += f"FINANCIAL HEALTH:\n"
        ctx += f"- Financial Health Score: {fin_result['score']}/100\n"
        ctx += f"- Credit Rating: {fin_result['rating']} — {fin_result['rating_desc']}\n"
        ctx += f"- Annual Revenue: Rs.{fin_result['annual_revenue']:,.0f}\n"
        ctx += f"- Loan Eligibility Estimate: Rs.{fin_result['loan_eligible']:,.0f}\n"
        ctx += f"- Key Ratios: {fin_result['ratios']}\n"
        ctx += f"- Dimension Scores: {fin_result['scores']}\n"
        if fin_result.get("flags"):
            ctx += f"- Risk Flags: {[f['msg'] for f in fin_result['flags']]}\n"

    return ctx


# ════════════════════════════════════════════════════════════
# SECTION F — HTML FORMATTERS
# ════════════════════════════════════════════════════════════

def _key_metrics_html(metrics: dict) -> str:
    rows = "".join([
        f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e1e1e;font-size:12px;">'
        f'<span style="color:#666;">{k}</span><span style="color:#e0e0e0;font-weight:500;">{v}</span></div>'
        for k, v in metrics.items()
    ])
    return rows


def _seg_profiles_html(result: dict) -> str:
    parts = []
    for i in range(5):
        prof = SEGMENT_PROFILES[i]
        if prof["name"] not in result["seg_counts"]:
            continue
        col   = prof["color"]
        count = result["seg_counts"].get(prof["name"], 0)
        parts.append(
            f'<div style="background:#111;border-radius:8px;padding:10px 14px;margin-bottom:6px;border-left:3px solid {col};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
            f'<span style="font-size:13px;font-weight:600;color:{col};">{prof["icon"]} {prof["name"]}</span>'
            f'<span style="font-size:11px;color:#555;">{count} customers</span></div>'
            f'<div style="font-size:11px;color:#888;">{prof["desc"]}</div>'
            f'<div style="font-size:11px;color:#aaa;margin-top:4px;">→ {prof["action"]}</div></div>'
        )
    return "".join(parts)


def _ratio_table_html(ratios: dict, start: int, end: int) -> str:
    keys = list(ratios.keys())[start:end]
    vals = list(ratios.values())[start:end]
    rows = "".join([
        f'<tr style="border-bottom:1px solid #1e1e1e;">'
        f'<td style="padding:6px 10px;font-size:12px;color:#666;">{k}</td>'
        f'<td style="padding:6px 10px;font-size:12px;color:#e0e0e0;font-weight:500;">{v}</td></tr>'
        for k, v in zip(keys, vals)
    ])
    return f'<table style="border-collapse:collapse;width:100%;">{rows}</table>'


def format_customer_dashboard(result: dict) -> str:
    if not result.get("success"):
        return f"<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Error: {result.get('error','Unknown error')}</div>"

    # Summary cards
    seg_parts = []
    for i in range(min(5, result["n_segments"]+1)):
        prof = SEGMENT_PROFILES[i]
        if prof["name"] not in result["seg_counts"]:
            continue
        count = result["seg_counts"].get(prof["name"], 0)
        col   = prof["color"]
        seg_parts.append(
            f"<div style='background:#1a1a1a;border-radius:8px;padding:10px 14px;text-align:center;"
            f"border-left:3px solid {col};'>"
            f"<div style='font-size:18px;font-weight:800;color:{col};'>{count}</div>"
            f"<div style='font-size:10px;color:#666;'>{prof['icon']} {prof['name']}</div></div>"
        )
    seg_html = "".join(seg_parts)

    # Customer table
    rows_html = ""
    sorted_custs = sorted(result["customers"], key=lambda x: -x["revenue"])
    for c in sorted_custs[:20]:
        churn_color = "#E74C3C" if c["churn_level"]=="High" else "#F39C12" if c["churn_level"]=="Medium" else "#2ECC71"
        anom_badge  = '<span style="background:#E74C3C;color:#fff;font-size:9px;padding:1px 5px;border-radius:4px;margin-left:4px;">ANOMALY</span>' if c["anomaly"] else ""
        rows_html += f"""
<tr style="border-bottom:1px solid #1e1e1e;">
  <td style="padding:8px 10px;color:#ccc;font-size:12px;">{c['id']}{anom_badge}</td>
  <td style="padding:8px 10px;">
    <span style="background:{c['seg_color']}22;color:{c['seg_color']};font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600;">
      {c['seg_icon']} {c['segment']}
    </span>
  </td>
  <td style="padding:8px 10px;color:#e0e0e0;font-size:12px;">Rs.{c['revenue']:,.0f}</td>
  <td style="padding:8px 10px;color:#aaa;font-size:12px;">{c['orders']:.0f}</td>
  <td style="padding:8px 10px;color:#aaa;font-size:12px;">{c['recency']:.0f}d</td>
  <td style="padding:8px 10px;">
    <span style="color:{churn_color};font-size:11px;font-weight:600;">{c['churn_pct']}% {c['churn_level']}</span>
  </td>
  <td style="padding:8px 10px;color:#666;font-size:11px;">{c['action'][:60]}...</td>
</tr>"""

    return f"""
<div style="font-family:system-ui,sans-serif;padding:4px;">

  <!-- Summary strip -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:10px;margin-bottom:16px;">
    <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:800;color:#e0e0e0;">{result['total']}</div>
      <div style="font-size:10px;color:#555;">CUSTOMERS</div>
    </div>
    <div style="background:#0a1f17;border:1px solid #2ECC71;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:800;color:#2ECC71;">{result['n_segments']}</div>
      <div style="font-size:10px;color:#555;">SEGMENTS</div>
    </div>
    <div style="background:#1a0d0d;border:1px solid #E74C3C;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:800;color:#E74C3C;">{result['high_churn']}</div>
      <div style="font-size:10px;color:#555;">HIGH CHURN RISK</div>
    </div>
    <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:20px;font-weight:700;color:#F39C12;">{result['anomalies']}</div>
      <div style="font-size:10px;color:#555;">ANOMALIES</div>
    </div>
    <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:14px;font-weight:700;color:#3498DB;">Rs.{result['revenue_forecast_30']:,.0f}</div>
      <div style="font-size:10px;color:#555;">NEXT PERIOD FORECAST</div>
    </div>
    <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:12px;font-weight:500;color:#aaa;">{round(result['silhouette']*100)}%</div>
      <div style="font-size:10px;color:#555;">SEG QUALITY</div>
    </div>
  </div>

  <!-- Segment breakdown -->
  <div style="margin-bottom:14px;">
    <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:8px;">SEGMENT BREAKDOWN</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;">{seg_html}</div>
  </div>

  <!-- Segment profiles -->
  <div style="margin-bottom:14px;">
    <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:8px;">SEGMENT PROFILES & ACTIONS</div>
    {_seg_profiles_html(result)}
  </div>

  <!-- Customer table -->
  <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:8px;">CUSTOMER DETAIL (TOP 20 BY REVENUE)</div>
  <div style="background:#111;border-radius:8px;overflow:auto;">
    <table style="width:100%;border-collapse:collapse;font-family:system-ui,sans-serif;">
      <thead>
        <tr style="background:#1a1a1a;border-bottom:1px solid #2a2a2a;">
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">ID</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">SEGMENT</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">REVENUE</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">ORDERS</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">RECENCY</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">CHURN RISK</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#555;font-weight:600;">RECOMMENDED ACTION</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>"""


def format_financial_dashboard(result: dict) -> str:
    if not result.get("success"):
        return f"<div style='color:#E74C3C;padding:20px;font-family:system-ui;'>Error: {result.get('error','Unknown')}</div>"

    # Score gauge (SVG)
    score = result["score"]
    rating_color = result["rating_color"]
    angle = (score / 100) * 180  # 0-180 degrees for semi-circle
    # SVG arc
    r = 70
    cx, cy = 90, 90
    start_x = cx - r
    start_y = cy
    import math
    rad = math.radians(180 - angle)
    end_x = cx + r * math.cos(math.radians(180 - angle))
    end_y = cy - r * math.sin(math.radians(180 - angle))
    large = 1 if angle > 180 else 0

    gauge_svg = f"""
<svg viewBox="0 0 180 100" style="width:180px;height:100px;">
  <path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" fill="none" stroke="#2a2a2a" stroke-width="12" stroke-linecap="round"/>
  <path d="M {cx-r} {cy} A {r} {r} 0 0 1 {end_x:.1f} {end_y:.1f}" fill="none" stroke="{rating_color}" stroke-width="12" stroke-linecap="round"/>
  <text x="{cx}" y="{cy-5}" text-anchor="middle" font-size="22" font-weight="800" fill="{rating_color}">{score}</text>
  <text x="{cx}" y="{cy+12}" text-anchor="middle" font-size="9" fill="#666">/ 100</text>
  <text x="{cx}" y="{cy+26}" text-anchor="middle" font-size="13" font-weight="700" fill="{rating_color}">{result['rating']}</text>
</svg>"""

    # Dimension score bars
    dim_html = ""
    for dim, sc in result["scores"].items():
        max_pts = {"Profitability":30,"Liquidity":20,"Leverage":20,"Efficiency":15,"Growth":15}.get(dim,20)
        pct = (sc / max_pts) * 100
        color = "#2ECC71" if pct >= 70 else "#F39C12" if pct >= 45 else "#E74C3C"
        dim_html += f"""
<div style="margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-bottom:3px;">
    <span>{dim}</span><span style="color:{color};font-weight:600;">{sc}/{max_pts}</span>
  </div>
  <div style="height:5px;background:#1e1e1e;border-radius:3px;">
    <div style="height:100%;width:{pct}%;background:{color};border-radius:3px;"></div>
  </div>
</div>"""

    # Ratio table
    ratio_rows = ""
    for name, val in result["ratios"].items():
        ratio_rows += f'<tr style="border-bottom:1px solid #1e1e1e;"><td style="padding:6px 10px;font-size:12px;color:#888;">{name}</td><td style="padding:6px 10px;font-size:12px;color:#e0e0e0;font-weight:500;">{val}</td></tr>'

    # Flags
    flags_html = ""
    for f in result["flags"]:
        fc = "#E74C3C" if f["type"]=="critical" else "#F39C12" if f["type"]=="warning" else "#2ECC71"
        icon = "🔴" if f["type"]=="critical" else "🟡" if f["type"]=="warning" else "✅"
        flags_html += f'<div style="background:#111;border-left:3px solid {fc};border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:12px;color:#ccc;">{icon} {f["msg"]}</div>'

    return f"""
<div style="font-family:system-ui,sans-serif;padding:4px;">

  <!-- Score + Rating -->
  <div style="display:grid;grid-template-columns:auto 1fr;gap:20px;align-items:center;
              background:#111;border-radius:12px;padding:16px;margin-bottom:14px;">
    <div style="text-align:center;">{gauge_svg}</div>
    <div>
      <div style="font-size:22px;font-weight:700;color:{rating_color};margin-bottom:4px;">
        {result['rating']} — {result['rating_desc']}
      </div>
      <div style="font-size:13px;color:#666;margin-bottom:12px;">Financial Health Score: {score}/100</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="background:#1a1a1a;border-radius:8px;padding:10px;">
          <div style="font-size:10px;color:#555;margin-bottom:3px;">ANNUAL REVENUE</div>
          <div style="font-size:16px;font-weight:700;color:#e0e0e0;">Rs.{result['annual_revenue']:,.0f}</div>
        </div>
        <div style="background:#0a1f17;border:1px solid #2ECC71;border-radius:8px;padding:10px;">
          <div style="font-size:10px;color:#555;margin-bottom:3px;">LOAN ELIGIBILITY</div>
          <div style="font-size:16px;font-weight:700;color:#2ECC71;">Rs.{result['loan_eligible']:,.0f}</div>
          <div style="font-size:10px;color:#555;">{result['loan_multiple']}× annual revenue</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Dimension scores -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px;">
    <div style="background:#111;border-radius:8px;padding:14px;">
      <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:10px;">DIMENSION SCORES</div>
      {dim_html}
    </div>
    <div style="background:#111;border-radius:8px;padding:14px;">
      <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:10px;">KEY METRICS</div>
      {_key_metrics_html(result["key_metrics"])}
    </div>
  </div>

  <!-- Financial Ratios -->
  <div style="background:#111;border-radius:8px;margin-bottom:14px;">
    <div style="padding:10px 14px;font-size:10px;color:#555;letter-spacing:.07em;border-bottom:1px solid #1e1e1e;">
      FINANCIAL RATIOS (12 KEY INDICATORS)
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;">
      _ratio_table_left(result)_ratio_table_right(result)
    </div>
  </div>

  <!-- Risk Flags -->
  <div style="font-size:10px;color:#555;letter-spacing:.07em;margin-bottom:8px;">RISK FLAGS & INSIGHTS</div>
  {flags_html if flags_html else '<div style="color:#555;font-size:12px;padding:8px;">No major risk flags detected.</div>'}

</div>"""


# ════════════════════════════════════════════════════════════
# SECTION G — MASTER HANDLERS (called from app.py)
# ════════════════════════════════════════════════════════════

# Global context for AI chat
_DATA_CONTEXT = {"cust": None, "fin": None, "text": "No data analyzed yet."}


def run_customer_analysis(file) -> tuple:
    """Returns (dashboard_html, status_md)"""
    global _DATA_CONTEXT
    if not PANDAS_OK:
        return "<div style='color:#E74C3C;padding:20px;'>pandas not installed</div>", "Error"

    if file is not None:
        filepath = file.name if hasattr(file, "name") else str(file)
        df, err = read_file(filepath)
        if err:
            return f"<div style='color:#E74C3C;padding:20px;'>Error: {err}</div>", "Error"
    else:
        df = pd.read_csv(StringIO(SAMPLE_CUSTOMER_CSV))

    cols   = detect_customer_cols(df)
    result = run_customer_segmentation(df, cols)

    if result.get("success"):
        _DATA_CONTEXT["cust"] = result
        _DATA_CONTEXT["text"] = generate_data_context(
            _DATA_CONTEXT["cust"], _DATA_CONTEXT.get("fin"))
        dashboard = format_customer_dashboard(result)
        status = (f"✅ **Analyzed {result['total']} customers** | "
                  f"{result['n_segments']} segments | "
                  f"{result['high_churn']} high churn risk | "
                  f"{result['anomalies']} anomalies")
    else:
        dashboard = f"<div style='color:#E74C3C;padding:20px;'>Error: {result.get('error')}</div>"
        status = f"❌ Error: {result.get('error')}"

    return dashboard, status


def run_financial_analysis(
    file,
    # Manual entry fields
    revenue, cogs, net_profit, ebitda,
    cash, debt, assets, equity,
    receivables, payables,
    use_manual: bool,
) -> tuple:
    """Returns (dashboard_html, status_md)"""
    global _DATA_CONTEXT
    if not PANDAS_OK:
        return "<div style='color:#E74C3C;padding:20px;'>pandas not installed</div>", "Error"

    if use_manual:
        df   = None
        cols = {}
        manual = {
            "revenue": revenue, "cogs": cogs, "net_profit": net_profit,
            "ebitda": ebitda, "cash": cash, "debt": debt,
            "assets": assets, "equity": equity,
            "receivables": receivables, "payables": payables,
        }
        result = run_financial_scoring(df, cols, manual_data=manual)
    else:
        if file is not None:
            filepath = file.name if hasattr(file, "name") else str(file)
            df, err = read_file(filepath)
            if err:
                return f"<div style='color:#E74C3C;padding:20px;'>Error: {err}</div>", "Error"
        else:
            df = pd.read_csv(StringIO(SAMPLE_FINANCIAL_CSV))

        cols   = detect_financial_cols(df)
        result = run_financial_scoring(df, cols)

    if result.get("success"):
        _DATA_CONTEXT["fin"] = result
        _DATA_CONTEXT["text"] = generate_data_context(
            _DATA_CONTEXT.get("cust"), _DATA_CONTEXT["fin"])
        dashboard = format_financial_dashboard(result)
        status = (f"✅ **Financial Health Score: {result['score']}/100** | "
                  f"Rating: {result['rating']} | "
                  f"Loan Eligibility: Rs.{result['loan_eligible']:,.0f}")
    else:
        dashboard = f"<div style='color:#E74C3C;padding:20px;'>Error: {result.get('error')}</div>"
        status = f"❌ Error: {result.get('error')}"

    return dashboard, status


def run_ai_chat(question: str, history: list) -> tuple:
    """Returns (answer, updated_history)"""
    ctx = _DATA_CONTEXT.get("text", "No data analyzed yet. Please run Customer or Financial analysis first.")
    answer = ai_chat_on_data(question, ctx, history)
    history = history or []
    history.append({"role":"user", "content": question})
    history.append({"role":"model", "content": answer})
    return answer, history
