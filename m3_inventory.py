# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m3_inventory.py — Smart Inventory Forecasting
#
#  ML Models:
#  - ARIMA    : statsmodels (classical time-series)
#  - Prophet  : Facebook Prophet (seasonal + trend)
#  - LSTM     : Keras/TensorFlow (deep learning)
#  - Ensemble : weighted average of all 3
#
#  Outputs:
#  - SKU-level demand forecasts (30/60/90 days)
#  - Reorder point + safety stock calculation
#  - Auto-generate Purchase Orders
#  - PDF report
#  - What-if scenario simulation
# ============================================================

import re, json, math, time, warnings
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from io import StringIO, BytesIO

warnings.filterwarnings("ignore")

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    ARIMA_OK = True
except ImportError:
    ARIMA_OK = False

try:
    from prophet import Prophet
    PROPHET_OK = True
except ImportError:
    try:
        from neuralprophet import NeuralProphet
        PROPHET_OK = True
    except ImportError:
        PROPHET_OK = False

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from sklearn.preprocessing import MinMaxScaler
    LSTM_OK = True
except ImportError:
    try:
        from sklearn.preprocessing import MinMaxScaler
        LSTM_OK = False
    except ImportError:
        LSTM_OK = False

try:
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    from fpdf import FPDF
    FPDF_OK = True
except ImportError:
    FPDF_OK = False


# ════════════════════════════════════════════════════════════
# SECTION A — DATA INGESTION
# ════════════════════════════════════════════════════════════

SAMPLE_CSV = """Date,SKU,Product,Category,Quantity_Sold,Unit_Price,Stock_Level,Lead_Time_Days
2024-01-01,SKU001,Rice 5kg,Grocery,45,320,500,7
2024-01-01,SKU002,Wheat Flour 10kg,Grocery,30,280,300,5
2024-01-01,SKU003,Sugar 1kg,Grocery,60,55,800,3
2024-01-08,SKU001,Rice 5kg,Grocery,52,320,455,7
2024-01-08,SKU002,Wheat Flour 10kg,Grocery,28,280,272,5
2024-01-08,SKU003,Sugar 1kg,Grocery,65,55,735,3
2024-01-15,SKU001,Rice 5kg,Grocery,48,320,407,7
2024-01-15,SKU002,Wheat Flour 10kg,Grocery,35,280,237,5
2024-01-15,SKU003,Sugar 1kg,Grocery,70,55,665,3
2024-01-22,SKU001,Rice 5kg,Grocery,55,320,352,7
2024-01-22,SKU002,Wheat Flour 10kg,Grocery,32,280,205,5
2024-01-22,SKU003,Sugar 1kg,Grocery,58,55,607,3
2024-02-01,SKU001,Rice 5kg,Grocery,50,320,302,7
2024-02-01,SKU002,Wheat Flour 10kg,Grocery,40,280,165,5
2024-02-01,SKU003,Sugar 1kg,Grocery,75,55,532,3
2024-02-08,SKU001,Rice 5kg,Grocery,60,325,242,7
2024-02-08,SKU002,Wheat Flour 10kg,Grocery,38,285,127,5
2024-02-08,SKU003,Sugar 1kg,Grocery,68,58,464,3
2024-02-15,SKU001,Rice 5kg,Grocery,58,325,184,7
2024-02-15,SKU002,Wheat Flour 10kg,Grocery,42,285,85,5
2024-02-15,SKU003,Sugar 1kg,Grocery,72,58,392,3
2024-02-22,SKU001,Rice 5kg,Grocery,65,325,119,7
2024-02-22,SKU002,Wheat Flour 10kg,Grocery,35,285,50,5
2024-02-22,SKU003,Sugar 1kg,Grocery,80,58,312,3
2024-03-01,SKU001,Rice 5kg,Grocery,70,330,49,7
2024-03-01,SKU002,Wheat Flour 10kg,Grocery,45,290,5,5
2024-03-01,SKU003,Sugar 1kg,Grocery,85,60,227,3
2024-03-08,SKU001,Rice 5kg,Grocery,68,330,181,7
2024-03-08,SKU002,Wheat Flour 10kg,Grocery,40,290,165,5
2024-03-08,SKU003,Sugar 1kg,Grocery,78,60,149,3
2024-03-15,SKU001,Rice 5kg,Grocery,75,330,106,7
2024-03-15,SKU002,Wheat Flour 10kg,Grocery,38,290,127,5
2024-03-15,SKU003,Sugar 1kg,Grocery,82,60,67,3
2024-03-22,SKU001,Rice 5kg,Grocery,72,330,34,7
2024-03-22,SKU002,Wheat Flour 10kg,Grocery,42,290,85,5
2024-03-22,SKU003,Sugar 1kg,Grocery,88,60,179,3
2024-04-01,SKU001,Rice 5kg,Grocery,80,335,154,7
2024-04-01,SKU002,Wheat Flour 10kg,Grocery,50,295,235,5
2024-04-01,SKU003,Sugar 1kg,Grocery,90,62,89,3
2024-04-08,SKU001,Rice 5kg,Grocery,78,335,76,7
2024-04-08,SKU002,Wheat Flour 10kg,Grocery,48,295,187,5
2024-04-08,SKU003,Sugar 1kg,Grocery,85,62,4,3
2024-04-15,SKU001,Rice 5kg,Grocery,82,335,194,7
2024-04-15,SKU002,Wheat Flour 10kg,Grocery,52,295,135,5
2024-04-15,SKU003,Sugar 1kg,Grocery,92,62,112,3
2024-04-22,SKU001,Rice 5kg,Grocery,85,335,109,7
2024-04-22,SKU002,Wheat Flour 10kg,Grocery,55,295,80,5
2024-04-22,SKU003,Sugar 1kg,Grocery,88,62,24,3"""


def read_inventory_file(filepath: str) -> tuple:
    """Reads uploaded CSV/Excel. Returns (df, error)."""
    if not PANDAS_OK:
        return None, "pandas not installed"
    path = Path(filepath)
    ext  = path.suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(filepath, encoding="utf-8", errors="replace")
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(filepath)
        else:
            return None, f"Unsupported file type: {ext}"
        return df, None
    except Exception as e:
        return None, str(e)


def detect_columns(df: pd.DataFrame) -> dict:
    """Auto-detects which columns map to date/sku/qty/stock/price/lead."""
    cols_up = {c: c.upper() for c in df.columns}
    def find(kws):
        for orig, up in cols_up.items():
            if any(k in up for k in kws):
                return orig
        return None

    return {
        "date":     find(["DATE","PERIOD","WEEK","MONTH","TIME"]),
        "sku":      find(["SKU","ITEM CODE","PRODUCT CODE","CODE","ID"]),
        "product":  find(["PRODUCT","ITEM","NAME","DESCRIPTION"]),
        "category": find(["CATEGORY","CAT","TYPE","GROUP"]),
        "qty":      find(["QTY","QUANTITY","SALES","SOLD","UNITS","DEMAND"]),
        "stock":    find(["STOCK","INVENTORY","ON HAND","BALANCE","LEVEL"]),
        "price":    find(["PRICE","RATE","COST","VALUE","MRP"]),
        "lead":     find(["LEAD","LEAD TIME","DAYS","REORDER DAYS"]),
    }


def prepare_sku_series(df: pd.DataFrame, cols: dict, sku_id: str) -> pd.Series:
    """Returns a clean time-series of quantity sold for one SKU."""
    sku_col = cols.get("sku") or cols.get("product")
    qty_col = cols.get("qty")
    date_col= cols.get("date")

    if not qty_col:
        return None, "No quantity/sales column found"

    if sku_col:
        mask = df[sku_col].astype(str) == sku_id
        sub  = df[mask].copy()
    else:
        sub = df.copy()

    if date_col:
        sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
        sub = sub.dropna(subset=[date_col]).sort_values(date_col)
        sub = sub.set_index(date_col)

    sub[qty_col] = pd.to_numeric(sub[qty_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce")
    series = sub[qty_col].dropna()

    if len(series) < 4:
        return None, f"Only {len(series)} data points — need at least 4"

    return series, None


# ════════════════════════════════════════════════════════════
# SECTION B — ML ENGINE 1: ARIMA
# ════════════════════════════════════════════════════════════

def forecast_arima(series: pd.Series, periods: int = 30) -> dict:
    """ARIMA forecasting. Auto-selects best (p,d,q) order."""
    result = {"model": "ARIMA", "forecast": [], "lower": [], "upper": [],
              "mae": None, "rmse": None, "success": False, "error": None}

    if not ARIMA_OK:
        result["error"] = "statsmodels not installed"
        return result

    try:
        vals = series.values.astype(float)

        # Try orders from simple to complex
        best_aic  = np.inf
        best_order = (1, 1, 1)
        for p in range(0, 3):
            for d in range(0, 2):
                for q in range(0, 3):
                    try:
                        m = ARIMA(vals, order=(p,d,q)).fit()
                        if m.aic < best_aic:
                            best_aic   = m.aic
                            best_order = (p, d, q)
                    except Exception:
                        pass

        model  = ARIMA(vals, order=best_order).fit()
        fc_res = model.get_forecast(steps=periods)
        fc_mean= fc_res.predicted_mean
        conf   = fc_res.conf_int(alpha=0.2)  # 80% CI

        # In-sample MAE/RMSE
        fitted = model.fittedvalues
        mae  = float(mean_absolute_error(vals[1:], fitted[1:])) if SKLEARN_OK else None
        rmse = float(np.sqrt(mean_squared_error(vals[1:], fitted[1:]))) if SKLEARN_OK else None

        result.update({
            "success":  True,
            "order":    best_order,
            "forecast": [max(0, round(float(v), 1)) for v in fc_mean],
            "lower":    [max(0, round(float(v), 1)) for v in conf.iloc[:, 0]],
            "upper":    [max(0, round(float(v), 1)) for v in conf.iloc[:, 1]],
            "mae":      round(mae, 2) if mae else None,
            "rmse":     round(rmse, 2) if rmse else None,
            "aic":      round(best_aic, 2),
        })

    except Exception as e:
        result["error"] = str(e)

    return result


# ════════════════════════════════════════════════════════════
# SECTION C — ML ENGINE 2: PROPHET
# ════════════════════════════════════════════════════════════

def forecast_prophet(series: pd.Series, periods: int = 30) -> dict:
    """Facebook Prophet forecasting with seasonality detection."""
    result = {"model": "Prophet", "forecast": [], "lower": [], "upper": [],
              "mae": None, "rmse": None, "success": False, "error": None}

    if not PROPHET_OK:
        result["error"] = "prophet not installed — add to requirements.txt"
        return result

    try:
        # Prophet needs a DataFrame with ds (date) and y (value)
        if isinstance(series.index, pd.DatetimeIndex):
            df_p = pd.DataFrame({"ds": series.index, "y": series.values})
        else:
            # Create weekly dates if no datetime index
            start = pd.Timestamp("2024-01-01")
            dates = [start + timedelta(weeks=i) for i in range(len(series))]
            df_p  = pd.DataFrame({"ds": dates, "y": series.values})

        df_p["y"] = pd.to_numeric(df_p["y"], errors="coerce")
        df_p = df_p.dropna()

        m = Prophet(
            yearly_seasonality  = len(df_p) >= 52,
            weekly_seasonality  = len(df_p) >= 14,
            daily_seasonality   = False,
            changepoint_prior_scale = 0.05,
            seasonality_prior_scale = 10,
            interval_width      = 0.80,
        )
        m.fit(df_p)

        future   = m.make_future_dataframe(periods=periods, freq="D")
        forecast = m.predict(future)
        fc_tail  = forecast.tail(periods)

        fitted_in = forecast.head(len(df_p))
        mae  = float(mean_absolute_error(df_p["y"], fitted_in["yhat"])) if SKLEARN_OK else None
        rmse = float(np.sqrt(mean_squared_error(df_p["y"], fitted_in["yhat"]))) if SKLEARN_OK else None

        result.update({
            "success":  True,
            "forecast": [max(0, round(float(v), 1)) for v in fc_tail["yhat"]],
            "lower":    [max(0, round(float(v), 1)) for v in fc_tail["yhat_lower"]],
            "upper":    [max(0, round(float(v), 1)) for v in fc_tail["yhat_upper"]],
            "trend":    [round(float(v), 1) for v in fc_tail["trend"]],
            "mae":      round(mae, 2) if mae else None,
            "rmse":     round(rmse, 2) if rmse else None,
        })

    except Exception as e:
        result["error"] = str(e)

    return result


# ════════════════════════════════════════════════════════════
# SECTION D — ML ENGINE 3: LSTM
# ════════════════════════════════════════════════════════════

def forecast_lstm(series: pd.Series, periods: int = 30) -> dict:
    """LSTM deep learning forecasting. Uses sliding window."""
    result = {"model": "LSTM", "forecast": [], "lower": [], "upper": [],
              "mae": None, "rmse": None, "success": False, "error": None}

    if not LSTM_OK:
        result["error"] = "TensorFlow not installed"
        return result

    if len(series) < 10:
        result["error"] = "Need at least 10 data points for LSTM"
        return result

    try:
        vals = series.values.astype(float).reshape(-1, 1)

        # Normalize
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(vals)

        # Build sequences
        window = min(7, len(scaled) - 2)
        X, y   = [], []
        for i in range(window, len(scaled)):
            X.append(scaled[i-window:i, 0])
            y.append(scaled[i, 0])
        X = np.array(X).reshape(-1, window, 1)
        y = np.array(y)

        # Build LSTM model
        model = Sequential([
            LSTM(32, return_sequences=True, input_shape=(window, 1)),
            Dropout(0.1),
            LSTM(16),
            Dropout(0.1),
            Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse")
        model.fit(X, y, epochs=50, batch_size=4, verbose=0)

        # Forecast
        last_seq = scaled[-window:].reshape(1, window, 1)
        preds    = []
        for _ in range(periods):
            pred = model.predict(last_seq, verbose=0)[0, 0]
            preds.append(pred)
            last_seq = np.roll(last_seq, -1, axis=1)
            last_seq[0, -1, 0] = pred

        preds_orig = scaler.inverse_transform(np.array(preds).reshape(-1, 1)).flatten()

        # Confidence interval: ±15% for LSTM
        ci_range = preds_orig * 0.15

        # In-sample error
        y_pred_scaled = model.predict(X, verbose=0).flatten()
        y_pred_orig   = scaler.inverse_transform(y_pred_scaled.reshape(-1,1)).flatten()
        y_true_orig   = scaler.inverse_transform(y.reshape(-1,1)).flatten()
        mae  = float(mean_absolute_error(y_true_orig, y_pred_orig)) if SKLEARN_OK else None
        rmse = float(np.sqrt(mean_squared_error(y_true_orig, y_pred_orig))) if SKLEARN_OK else None

        result.update({
            "success":  True,
            "forecast": [max(0, round(float(v), 1)) for v in preds_orig],
            "lower":    [max(0, round(float(v - c), 1)) for v, c in zip(preds_orig, ci_range)],
            "upper":    [max(0, round(float(v + c), 1)) for v, c in zip(preds_orig, ci_range)],
            "mae":      round(mae, 2) if mae else None,
            "rmse":     round(rmse, 2) if rmse else None,
        })

    except Exception as e:
        result["error"] = str(e)

    return result


# ════════════════════════════════════════════════════════════
# SECTION E — ENSEMBLE FORECASTER
# Weighted average of ARIMA + Prophet + LSTM
# ════════════════════════════════════════════════════════════

def ensemble_forecast(series: pd.Series, periods: int = 30) -> dict:
    """
    Runs all 3 models and creates a weighted ensemble.
    Better models (lower MAE) get higher weight.
    """
    arima_res   = forecast_arima(series, periods)
    prophet_res = forecast_prophet(series, periods)
    lstm_res    = forecast_lstm(series, periods)

    results_all = {
        "ARIMA":  arima_res,
        "Prophet":prophet_res,
        "LSTM":   lstm_res,
    }

    # Collect successful models
    successful = {k: v for k, v in results_all.items() if v["success"] and len(v["forecast"]) == periods}

    if not successful:
        # All failed — use moving average fallback
        vals   = series.values.astype(float)
        window = min(7, len(vals))
        ma     = float(np.mean(vals[-window:]))
        fc     = [round(ma, 1)] * periods
        return {
            "ensemble":  fc,
            "lower":     [round(max(0, ma * 0.8), 1)] * periods,
            "upper":     [round(ma * 1.2, 1)] * periods,
            "models":    results_all,
            "weights":   {"MovingAverage": 1.0},
            "fallback":  True,
        }

    # Weight by inverse MAE (better accuracy = higher weight)
    weights = {}
    for name, res in successful.items():
        mae = res.get("mae")
        if mae and mae > 0:
            weights[name] = 1.0 / mae
        else:
            weights[name] = 1.0

    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    # Weighted ensemble
    ensemble_fc = np.zeros(periods)
    ensemble_lo = np.zeros(periods)
    ensemble_hi = np.zeros(periods)

    for name, w in weights.items():
        res = successful[name]
        fc  = np.array(res["forecast"][:periods])
        lo  = np.array(res["lower"][:periods])
        hi  = np.array(res["upper"][:periods])
        ensemble_fc += w * fc
        ensemble_lo += w * lo
        ensemble_hi += w * hi

    return {
        "ensemble":  [max(0, round(float(v), 1)) for v in ensemble_fc],
        "lower":     [max(0, round(float(v), 1)) for v in ensemble_lo],
        "upper":     [max(0, round(float(v), 1)) for v in ensemble_hi],
        "models":    results_all,
        "weights":   {k: round(v, 3) for k, v in weights.items()},
        "fallback":  False,
    }


# ════════════════════════════════════════════════════════════
# SECTION F — INVENTORY INTELLIGENCE
# Reorder points, safety stock, EOQ, PO generation
# ════════════════════════════════════════════════════════════

def calculate_inventory_params(
    series: pd.Series,
    forecast_30: list,
    current_stock: float,
    lead_time_days: int,
    service_level: float = 0.95,
) -> dict:
    """
    Calculates all inventory management parameters.
    service_level: 0.95 = 95% (Z=1.65), 0.99 = 99% (Z=2.33)
    """
    vals      = series.values.astype(float)
    avg_daily = float(np.mean(vals)) / 7  # assuming weekly data
    std_daily = float(np.std(vals)) / 7

    # Z-score for service level
    z_scores = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
    z = z_scores.get(service_level, 1.65)

    # Safety Stock = Z × σ_daily × √lead_time
    safety_stock = round(z * std_daily * math.sqrt(lead_time_days), 0)

    # Reorder Point = (avg_daily × lead_time) + safety_stock
    reorder_point = round(avg_daily * lead_time_days + safety_stock, 0)

    # Days of stock remaining
    if avg_daily > 0:
        days_of_stock = round(current_stock / avg_daily, 0)
    else:
        days_of_stock = 999

    # EOQ (Economic Order Quantity) — assumes ordering cost Rs.500, holding 20% of price
    # Simplified: order enough for 30-day demand
    forecast_30_total = sum(forecast_30[:30]) if len(forecast_30) >= 30 else avg_daily * 30
    eoq = round(forecast_30_total + safety_stock, 0)

    # Status
    if current_stock <= 0:
        status = "OUT OF STOCK"
        alert  = "critical"
    elif current_stock <= safety_stock:
        status = "CRITICAL"
        alert  = "critical"
    elif current_stock <= reorder_point:
        status = "REORDER NOW"
        alert  = "warning"
    elif days_of_stock <= 14:
        status = "LOW STOCK"
        alert  = "warning"
    else:
        status = "OK"
        alert  = "good"

    return {
        "avg_daily_demand": round(avg_daily, 2),
        "std_daily":        round(std_daily, 2),
        "safety_stock":     int(safety_stock),
        "reorder_point":    int(reorder_point),
        "days_of_stock":    int(days_of_stock),
        "eoq":              int(eoq),
        "forecast_30_total":round(forecast_30_total, 0),
        "status":           status,
        "alert":            alert,
        "service_level":    f"{int(service_level*100)}%",
    }


def generate_purchase_order(sku_results: list, business_name: str = "Your Business") -> str:
    """Generates a formatted Purchase Order as markdown."""
    now = datetime.now()
    po_number = f"PO-{now.strftime('%Y%m%d')}-{random.randint(1000,9999)}"

    md = f"""# PURCHASE ORDER
**PO Number:** {po_number}
**Date:** {now.strftime('%d %B %Y')}
**Business:** {business_name}
**Generated by:** Allworkss BI Suite — Module 3

---

| # | SKU | Product | Order Qty | Unit Price | Total Value | Reorder Point | Safety Stock |
|---|---|---|---|---|---|---|---|
"""
    total_val = 0
    for i, item in enumerate(sku_results, 1):
        params = item.get("params", {})
        if params.get("alert") in ["critical", "warning"]:
            eoq   = params.get("eoq", 0)
            price = item.get("avg_price", 0)
            val   = round(eoq * price, 2)
            total_val += val
            md += f"| {i} | {item['sku']} | {item['product']} | {eoq} units | Rs.{price} | Rs.{val:,.2f} | {params.get('reorder_point',0)} | {params.get('safety_stock',0)} |\n"

    md += f"""
---
**Total PO Value:** Rs.{total_val:,.2f}

**Notes:**
- Order quantities based on 30-day ML demand forecast + safety stock
- Reorder points calculated at 95% service level
- Review and adjust quantities before sending to supplier

*This PO was auto-generated by Allworkss BI Suite Module 3 — Smart Inventory Forecasting*
"""
    return md


# ════════════════════════════════════════════════════════════
# SECTION G — SCENARIO SIMULATION
# What-if analysis for inventory planning
# ════════════════════════════════════════════════════════════

def run_scenario(
    base_forecast: list,
    scenario_type: str,
    param_value: float,
    current_stock: float,
    reorder_point: float,
    safety_stock: float,
    lead_time: int,
) -> dict:
    """
    Runs what-if scenarios on the base forecast.

    Scenarios:
    - demand_spike: demand increases by X%
    - demand_drop:  demand drops by X%
    - supplier_delay: lead time increases by X days
    - price_increase: cost goes up by X%
    - stockout:     what if we have a stockout for X days
    """
    result = {
        "scenario": scenario_type,
        "param":    param_value,
        "forecast": [],
        "impacts":  [],
        "recommendation": "",
    }

    fc = np.array(base_forecast, dtype=float)

    if scenario_type == "demand_spike":
        mult = 1 + (param_value / 100)
        fc_mod = fc * mult
        result["forecast"] = [max(0, round(float(v), 1)) for v in fc_mod]
        total_demand = float(np.sum(fc_mod[:30]))
        days_stock = current_stock / (float(np.mean(fc_mod)) / 7) if float(np.mean(fc_mod)) > 0 else 999
        result["impacts"] = [
            f"30-day demand increases to {round(total_demand)} units (+{param_value}%)",
            f"Current stock lasts {round(days_stock)} days under spike",
            f"Reorder point should increase to {round(reorder_point * mult)} units",
            f"Safety stock needed: {round(safety_stock * mult)} units",
        ]
        result["recommendation"] = (
            f"Pre-order {round(total_demand - current_stock + safety_stock * mult)} extra units immediately. "
            f"Negotiate priority delivery with supplier."
        ) if days_stock < 30 else "Stock adequate for demand spike — monitor weekly."

    elif scenario_type == "demand_drop":
        mult = 1 - (param_value / 100)
        fc_mod = fc * mult
        result["forecast"] = [max(0, round(float(v), 1)) for v in fc_mod]
        overstock = current_stock - float(np.sum(fc_mod[:30]))
        result["impacts"] = [
            f"30-day demand drops to {round(sum(fc_mod[:30]))} units (-{param_value}%)",
            f"Potential overstock: {round(max(0, overstock))} units",
            f"Holding cost risk: excess inventory for {round(overstock / (float(np.mean(fc_mod))/7))} days",
            f"Consider pausing next PO if overstock > safety stock",
        ]
        result["recommendation"] = (
            f"Pause or reduce next order by {round(overstock * 0.7)} units. "
            f"Consider promotions to clear slow stock."
        ) if overstock > safety_stock else "Drop within manageable range. No action needed."

    elif scenario_type == "supplier_delay":
        new_lead = lead_time + int(param_value)
        import math as _math
        avg_daily = float(np.mean(fc)) / 7
        new_rop   = round(avg_daily * new_lead + safety_stock, 0)
        days_stock = current_stock / avg_daily if avg_daily > 0 else 999
        result["forecast"] = list(base_forecast)
        result["impacts"] = [
            f"Lead time increases from {lead_time} to {new_lead} days",
            f"Reorder point must increase to {new_rop} units (from {round(reorder_point)})",
            f"Current stock covers only {round(days_stock)} days",
            f"Stockout risk: {'HIGH' if days_stock < new_lead else 'LOW'}",
        ]
        result["recommendation"] = (
            f"Place emergency order NOW. Current stock ({round(current_stock)} units) "
            f"insufficient for {new_lead}-day lead time."
        ) if days_stock < new_lead else f"Increase reorder point to {round(new_rop)} units as buffer."

    elif scenario_type == "price_increase":
        new_cost_mult = 1 + (param_value / 100)
        avg_daily     = float(np.mean(fc)) / 7
        eoq_units     = round(float(np.sum(fc[:30])) + safety_stock, 0)
        current_cost  = eoq_units * 100  # assume Rs.100 base
        new_cost      = current_cost * new_cost_mult
        result["forecast"] = list(base_forecast)
        result["impacts"] = [
            f"Unit cost increases by {param_value}%",
            f"30-day procurement cost: Rs.{round(new_cost):,} (was Rs.{round(current_cost):,})",
            f"Additional spend: Rs.{round(new_cost - current_cost):,}",
            f"Recommend bulk purchase before price hike if feasible",
        ]
        result["recommendation"] = (
            f"Buy {round(eoq_units * 1.5)} units now at current price to save "
            f"Rs.{round((new_cost - current_cost) * 0.5):,} in procurement cost."
        ) if param_value > 10 else "Minor price increase. Monitor and review quarterly pricing."

    elif scenario_type == "stockout":
        recovery_days = int(param_value)
        avg_daily     = float(np.mean(fc)) / 7
        lost_sales    = round(avg_daily * recovery_days, 0)
        result["forecast"] = list(base_forecast)
        result["impacts"] = [
            f"Stockout duration: {recovery_days} days",
            f"Estimated lost sales: {lost_sales} units",
            f"Customer impact: {round(recovery_days / 30 * 100)}% of monthly supply disrupted",
            f"Backorder risk: HIGH" if recovery_days > 7 else f"Backorder risk: MEDIUM",
        ]
        result["recommendation"] = (
            f"Source emergency stock from alternate supplier. "
            f"Notify customers of {recovery_days}-day delay. "
            f"Increase safety stock buffer to prevent recurrence."
        )

    return result

import random


# ════════════════════════════════════════════════════════════
# SECTION H — RESULTS FORMATTER
# ════════════════════════════════════════════════════════════

def format_forecast_chart(sku: str, product: str, series: pd.Series,
                           ensemble: dict, periods: int) -> str:
    """Renders an SVG-style HTML chart for the forecast."""
    historical = list(series.values[-20:])
    forecast   = ensemble["ensemble"][:periods]
    lower      = ensemble["lower"][:periods]
    upper      = ensemble["upper"][:periods]

    all_vals   = historical + forecast + lower + upper
    max_val    = max(all_vals) if all_vals else 1
    min_val    = min(0, min(all_vals))

    W, H    = 700, 200
    pad_l   = 50
    pad_r   = 20
    pad_t   = 20
    pad_b   = 30
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    def scale_x(i, total):
        return pad_l + (i / max(total - 1, 1)) * inner_w

    def scale_y(v):
        return pad_t + inner_h - ((v - min_val) / max(max_val - min_val, 1)) * inner_h

    n_hist = len(historical)
    n_fc   = len(forecast)
    total  = n_hist + n_fc

    # Confidence band
    band_pts_top  = " ".join([f"{scale_x(n_hist+i, total)},{scale_y(upper[i])}" for i in range(n_fc)])
    band_pts_bot  = " ".join([f"{scale_x(n_hist+i, total)},{scale_y(lower[i])}" for i in range(n_fc-1, -1, -1)])
    band_polygon  = band_pts_top + " " + band_pts_bot if band_pts_top else ""

    # Historical line
    hist_path = " ".join([f"{'M' if i==0 else 'L'}{scale_x(i,total)},{scale_y(v)}" for i,v in enumerate(historical)])

    # Forecast line
    fc_path = " ".join([f"{'M' if i==0 else 'L'}{scale_x(n_hist+i,total)},{scale_y(v)}" for i,v in enumerate(forecast)])
    # Connect last hist to first forecast
    if historical and forecast:
        connect = f"M{scale_x(n_hist-1,total)},{scale_y(historical[-1])} L{scale_x(n_hist,total)},{scale_y(forecast[0])}"
    else:
        connect = ""

    # Y grid lines
    grid_vals = [round(min_val + i*(max_val-min_val)/4) for i in range(5)]
    grid_html = ""
    for gv in grid_vals:
        gy = scale_y(gv)
        grid_html += f'<line x1="{pad_l}" y1="{gy}" x2="{W-pad_r}" y2="{gy}" stroke="#2a2a2a" stroke-width="1"/>'
        grid_html += f'<text x="{pad_l-4}" y="{gy+4}" text-anchor="end" font-size="9" fill="#555">{int(gv)}</text>'

    # Vertical divider (hist/forecast)
    div_x = scale_x(n_hist-1, total)

    html = f"""
<div style="background:#111;border-radius:10px;padding:14px;margin-bottom:14px;font-family:system-ui,sans-serif;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <div>
      <span style="font-size:13px;font-weight:600;color:#e0e0e0;">{sku} — {product}</span>
    </div>
    <div style="display:flex;gap:14px;font-size:11px;">
      <span><span style="color:#4a9eff;">&#9644;</span> Historical</span>
      <span><span style="color:#2ECC71;">&#9644;</span> Forecast</span>
      <span><span style="color:rgba(46,204,113,0.25);">&#9632;</span> 80% CI</span>
    </div>
  </div>
  <svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;overflow:visible;">
    {grid_html}
    {'<polygon points="' + band_polygon + '" fill="rgba(46,204,113,0.15)"/>' if band_polygon else ''}
    {'<path d="' + hist_path + '" fill="none" stroke="#4a9eff" stroke-width="2"/>' if hist_path else ''}
    {'<path d="' + connect + '" fill="none" stroke="#888" stroke-width="1" stroke-dasharray="4,3"/>' if connect else ''}
    {'<path d="' + fc_path + '" fill="none" stroke="#2ECC71" stroke-width="2.5"/>' if fc_path else ''}
    <line x1="{div_x}" y1="{pad_t}" x2="{div_x}" y2="{H-pad_b}" stroke="#444" stroke-width="1" stroke-dasharray="4,3"/>
    <text x="{div_x+4}" y="{pad_t+10}" font-size="9" fill="#666">Forecast</text>
    <text x="{pad_l}" y="{H-8}" font-size="9" fill="#555">Historical ({n_hist} pts)</text>
    <text x="{W-pad_r}" y="{H-8}" font-size="9" fill="#555" text-anchor="end">+{n_fc} days</text>
  </svg>
</div>"""
    return html


def format_sku_card(item: dict) -> str:
    """Formats one SKU result card."""
    params  = item.get("params", {})
    alert   = params.get("alert", "good")
    status  = params.get("status", "OK")

    status_colors = {"critical": "#E74C3C", "warning": "#F39C12", "good": "#2ECC71"}
    bg_colors     = {"critical": "#1a0a0a", "warning": "#1a1200", "good": "#0a1a0a"}
    color  = status_colors.get(alert, "#2ECC71")
    bg     = bg_colors.get(alert, "#111")

    weights_html = ""
    if item.get("ensemble", {}).get("weights"):
        w = item["ensemble"]["weights"]
        weights_html = "<div style='font-size:10px;color:#444;margin-top:6px;'>Model weights: " + \
            " | ".join([f"{k}: {round(v*100)}%" for k,v in w.items()]) + "</div>"

    return f"""
<div style="background:{bg};border:1px solid {color};border-radius:10px;padding:14px;margin-bottom:12px;font-family:system-ui,sans-serif;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
    <div>
      <div style="font-size:15px;font-weight:600;color:#e0e0e0;">{item['product']}</div>
      <div style="font-size:11px;color:#666;margin-top:2px;">{item['sku']} &nbsp;|&nbsp; {item.get('category','')}</div>
    </div>
    <div style="background:{color};color:#000;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;">
      {status}
    </div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-bottom:12px;">
    <div style="background:#1a1a1a;border-radius:6px;padding:8px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:{color};">{int(item.get('current_stock',0))}</div>
      <div style="font-size:10px;color:#555;">Current Stock</div>
    </div>
    <div style="background:#1a1a1a;border-radius:6px;padding:8px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#e0e0e0;">{int(params.get('reorder_point',0))}</div>
      <div style="font-size:10px;color:#555;">Reorder Point</div>
    </div>
    <div style="background:#1a1a1a;border-radius:6px;padding:8px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#e0e0e0;">{int(params.get('safety_stock',0))}</div>
      <div style="font-size:10px;color:#555;">Safety Stock</div>
    </div>
    <div style="background:#1a1a1a;border-radius:6px;padding:8px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#aaa;">{int(params.get('days_of_stock',0))}</div>
      <div style="font-size:10px;color:#555;">Days of Stock</div>
    </div>
    <div style="background:#1a1a1a;border-radius:6px;padding:8px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#2ECC71;">{int(params.get('forecast_30_total',0))}</div>
      <div style="font-size:10px;color:#555;">30-Day Forecast</div>
    </div>
    <div style="background:#1a1a1a;border-radius:6px;padding:8px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#F39C12;">{int(params.get('eoq',0))}</div>
      <div style="font-size:10px;color:#555;">Order Qty (EOQ)</div>
    </div>
  </div>

  <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:#666;">
    <span>Avg daily demand: <b style="color:#aaa;">{params.get('avg_daily_demand',0)}</b></span>
    <span>Lead time: <b style="color:#aaa;">{item.get('lead_time',7)} days</b></span>
    <span>Service level: <b style="color:#aaa;">{params.get('service_level','95%')}</b></span>
  </div>
  {weights_html}
</div>"""


# ════════════════════════════════════════════════════════════
# SECTION I — MASTER HANDLER
# ════════════════════════════════════════════════════════════

def run_inventory_forecast(
    file,
    forecast_days: int,
    service_level: float,
    lead_time_override: int,
) -> tuple:
    """
    Master entry point. Returns (summary_html, charts_html, alerts_html, po_md).
    """
    if not PANDAS_OK:
        err = "<div style='color:#E74C3C;font-family:system-ui;padding:20px;'>pandas not installed</div>"
        return err, "", "", ""

    # Load data
    if file is not None:
        filepath = file.name if hasattr(file, "name") else str(file)
        df, err = read_inventory_file(filepath)
        if err:
            return f"<div style='color:#E74C3C;font-family:system-ui;padding:20px;'>Error: {err}</div>", "", "", ""
    else:
        # Use sample data
        df = pd.read_csv(StringIO(SAMPLE_CSV))

    cols = detect_columns(df)

    if not cols.get("qty"):
        return "<div style='color:#E74C3C;font-family:system-ui;padding:20px;'>Could not detect quantity/sales column. Check column names.</div>", "", "", ""

    # Get unique SKUs
    sku_col  = cols.get("sku") or cols.get("product")
    prod_col = cols.get("product") or cols.get("sku")
    cat_col  = cols.get("category")
    stk_col  = cols.get("stock")
    pri_col  = cols.get("price")
    lead_col = cols.get("lead")

    skus = df[sku_col].astype(str).unique() if sku_col else ["ALL"]

    sku_results = []
    charts_html = ""
    alerts_html = ""

    for sku_id in skus[:6]:  # limit to 6 SKUs for performance
        series, err = prepare_sku_series(df, cols, sku_id)
        if err or series is None or len(series) < 4:
            continue

        # Get metadata
        if sku_col:
            mask    = df[sku_col].astype(str) == sku_id
            sub_df  = df[mask]
        else:
            sub_df = df

        product  = str(sub_df[prod_col].iloc[-1]) if prod_col and prod_col in sub_df else sku_id
        category = str(sub_df[cat_col].iloc[-1])  if cat_col  and cat_col  in sub_df else ""
        cur_stock= float(pd.to_numeric(sub_df[stk_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").iloc[-1]) if stk_col and stk_col in sub_df else float(series.values[-1] * 3)
        avg_price= float(pd.to_numeric(sub_df[pri_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").mean()) if pri_col and pri_col in sub_df else 100
        lead_time= int(float(pd.to_numeric(sub_df[lead_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").iloc[-1])) if lead_col and lead_col in sub_df and not pd.isna(sub_df[lead_col].iloc[-1]) else lead_time_override

        # Run ensemble forecast
        ensemble = ensemble_forecast(series, forecast_days)

        # Inventory params
        params = calculate_inventory_params(
            series, ensemble["ensemble"], cur_stock, lead_time, service_level
        )

        item = {
            "sku":          sku_id,
            "product":      product,
            "category":     category,
            "current_stock":cur_stock,
            "avg_price":    avg_price,
            "lead_time":    lead_time,
            "series":       series,
            "ensemble":     ensemble,
            "params":       params,
        }
        sku_results.append(item)

        # Chart
        charts_html += format_forecast_chart(sku_id, product, series, ensemble, forecast_days)

        # Alert card
        alerts_html += format_sku_card(item)

    if not sku_results:
        return "<div style='color:#E74C3C;font-family:system-ui;padding:20px;'>No valid SKU data found. Check your CSV format.</div>", "", "", ""

    # Summary
    critical = [r for r in sku_results if r["params"]["alert"] == "critical"]
    warning  = [r for r in sku_results if r["params"]["alert"] == "warning"]
    good     = [r for r in sku_results if r["params"]["alert"] == "good"]

    models_used = []
    if ARIMA_OK:   models_used.append("ARIMA")
    if PROPHET_OK: models_used.append("Prophet")
    if LSTM_OK:    models_used.append("LSTM")
    if not models_used: models_used.append("Moving Average (fallback)")

    summary_html = f"""
<div style="font-family:system-ui,sans-serif;">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px;">
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:24px;font-weight:800;color:#e0e0e0;">{len(sku_results)}</div>
    <div style="font-size:10px;color:#555;">SKUs ANALYZED</div>
  </div>
  <div style="background:#1a0a0a;border:1px solid #E74C3C;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:24px;font-weight:800;color:#E74C3C;">{len(critical)}</div>
    <div style="font-size:10px;color:#555;">CRITICAL</div>
  </div>
  <div style="background:#1a1200;border:1px solid #F39C12;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:24px;font-weight:800;color:#F39C12;">{len(warning)}</div>
    <div style="font-size:10px;color:#555;">WARNINGS</div>
  </div>
  <div style="background:#0a1a0a;border:1px solid #2ECC71;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:24px;font-weight:800;color:#2ECC71;">{len(good)}</div>
    <div style="font-size:10px;color:#555;">HEALTHY</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;text-align:center;">
    <div style="font-size:16px;font-weight:600;color:#4a9eff;">{forecast_days}d</div>
    <div style="font-size:10px;color:#555;">FORECAST HORIZON</div>
  </div>
  <div style="background:#1a1a1a;border-radius:8px;padding:12px;">
    <div style="font-size:11px;color:#2ECC71;font-weight:500;">ML Models</div>
    <div style="font-size:10px;color:#666;margin-top:2px;">{" + ".join(models_used)}</div>
    <div style="font-size:10px;color:#555;">Ensemble weighted</div>
  </div>
</div>
</div>"""

    # PO markdown
    po_md = generate_purchase_order(sku_results)

    return summary_html, charts_html, alerts_html, po_md


def run_scenario_simulation(
    file, sku_select: str,
    scenario_type: str, param_value: float,
    forecast_days: int, lead_time_override: int,
) -> str:
    """Runs what-if scenario for a selected SKU."""
    if not PANDAS_OK:
        return "<div style='color:#E74C3C;'>pandas not installed</div>"

    if file is not None:
        filepath = file.name if hasattr(file, "name") else str(file)
        df, err = read_inventory_file(filepath)
        if err:
            return f"<div style='color:#E74C3C;'>Error: {err}</div>"
    else:
        df = pd.read_csv(StringIO(SAMPLE_CSV))

    cols    = detect_columns(df)
    sku_col = cols.get("sku") or cols.get("product")
    stk_col = cols.get("stock")

    # Find the selected SKU
    if sku_col and sku_select:
        target_sku = sku_select
    else:
        target_sku = df[sku_col].astype(str).iloc[0] if sku_col else "ALL"

    series, err = prepare_sku_series(df, cols, target_sku)
    if err or series is None:
        return f"<div style='color:#E74C3C;'>Could not prepare series: {err}</div>"

    ensemble = ensemble_forecast(series, forecast_days)
    base_fc  = ensemble["ensemble"]

    if sku_col:
        mask     = df[sku_col].astype(str) == target_sku
        sub_df   = df[mask]
    else:
        sub_df = df

    cur_stock  = float(pd.to_numeric(sub_df[stk_col].astype(str).str.replace(r"[^\d.]","",regex=True), errors="coerce").iloc[-1]) if stk_col and stk_col in sub_df else float(series.values[-1]*3)
    params     = calculate_inventory_params(series, base_fc, cur_stock, lead_time_override)
    reorder_pt = params["reorder_point"]
    safety_stk = params["safety_stock"]

    scenario = run_scenario(
        base_fc, scenario_type, param_value,
        cur_stock, reorder_pt, safety_stk, lead_time_override,
    )

    SCENARIO_NAMES = {
        "demand_spike":    f"Demand Spike +{param_value}%",
        "demand_drop":     f"Demand Drop -{param_value}%",
        "supplier_delay":  f"Supplier Delay +{param_value} days",
        "price_increase":  f"Price Increase +{param_value}%",
        "stockout":        f"Stockout Scenario {param_value} days",
    }
    title = SCENARIO_NAMES.get(scenario_type, scenario_type)

    impact_html = "".join([
        f'<div style="display:flex;gap:8px;padding:8px;background:#1a1a1a;border-radius:6px;margin-bottom:6px;font-size:12px;">'
        f'<span style="color:#F39C12;flex-shrink:0;">&#9654;</span>'
        f'<span style="color:#ccc;">{impact}</span></div>'
        for impact in scenario["impacts"]
    ])

    rec_color = "#E74C3C" if "emergency" in scenario["recommendation"].lower() or "immediately" in scenario["recommendation"].lower() else "#2ECC71"

    return f"""
<div style="font-family:system-ui,sans-serif;background:#111;border-radius:10px;padding:16px;">
  <div style="font-size:14px;font-weight:700;color:#e0e0e0;margin-bottom:4px;">Scenario: {title}</div>
  <div style="font-size:12px;color:#666;margin-bottom:14px;">SKU: {target_sku} | Base stock: {round(cur_stock)} units</div>

  <div style="font-size:11px;color:#888;letter-spacing:0.06em;margin-bottom:8px;">IMPACT ANALYSIS</div>
  {impact_html}

  <div style="background:#0d1a1a;border:1px solid {rec_color};border-radius:8px;padding:12px;margin-top:12px;">
    <div style="font-size:10px;color:{rec_color};font-weight:700;letter-spacing:0.06em;margin-bottom:6px;">RECOMMENDATION</div>
    <div style="font-size:13px;color:#e0e0e0;">{scenario['recommendation']}</div>
  </div>

  <div style="margin-top:12px;font-size:11px;color:#444;">
    Scenario forecast ({forecast_days} days): min={round(min(scenario['forecast'][:30]),1)} | 
    avg={round(sum(scenario['forecast'][:30])/30,1)} | 
    max={round(max(scenario['forecast'][:30]),1)} units/period
  </div>
</div>"""


def get_sku_list(file) -> list:
    """Returns list of SKUs from uploaded file (for dropdown)."""
    if not PANDAS_OK:
        return ["SKU001", "SKU002", "SKU003"]
    try:
        if file is not None:
            filepath = file.name if hasattr(file, "name") else str(file)
            df, err  = read_inventory_file(filepath)
        else:
            df = pd.read_csv(StringIO(SAMPLE_CSV))

        cols    = detect_columns(df)
        sku_col = cols.get("sku") or cols.get("product")
        if sku_col:
            return list(df[sku_col].astype(str).unique()[:20])
    except Exception:
        pass
    return ["SKU001", "SKU002", "SKU003"]
