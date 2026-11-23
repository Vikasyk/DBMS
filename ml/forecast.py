"""Walk-forward evaluation and four-week forecasting for one retail series."""

from datetime import date, timedelta

import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing

MIN_WEEKS = 52
HORIZON = 4
YEAR = 52
NAIVE = "Last observed price"
MOVING_AVERAGE = "Four-week moving average"
SEASONAL_NAIVE = "Same week last year"
HOLT_WINTERS = "Holt-Winters"


def _predict(method, values, seasonal):
    if method == NAIVE:
        return np.repeat(values[-1], HORIZON)
    if method == MOVING_AVERAGE:
        return np.repeat(np.mean(values[-HORIZON:]), HORIZON)
    if method == SEASONAL_NAIVE:
        return values[-YEAR:-YEAR + HORIZON]
    options = {"seasonal": "add", "seasonal_periods": YEAR} if seasonal else {}
    model = ExponentialSmoothing(values, trend="add", initialization_method="estimated", **options)
    return np.asarray(model.fit().forecast(HORIZON))


def evaluate_forecast(rows) -> dict:
    """Use the latest consecutive segment and compare methods on identical origins."""
    by_week = {row["week"]: float(row["price"]) for row in rows}
    history = [{"week": week, "price": value} for week, value in sorted(by_week.items())]
    segment = []
    for row in history:
        if segment and row["week"] - segment[-1]["week"] != timedelta(weeks=1):
            segment = []
        segment.append(row)

    response = {"history": history, "forecast": [], "metrics": [], "model": None, "seasonal": False,
                "weeks_available": len(history), "consecutive_weeks": len(segment)}
    if len(segment) < MIN_WEEKS:
        return {
            **response, "supported": False,
            "reason": f"Forecasting needs 52 consecutive weeks. The latest continuous series has {len(segment)}.",
        }

    values = np.array([row["price"] for row in segment])
    seasonal = len(values) >= 2 * YEAR + HORIZON
    methods = [NAIVE, MOVING_AVERAGE]
    min_training = 2 * YEAR if seasonal else 26
    if len(values) >= YEAR + HORIZON:
        methods.append(SEASONAL_NAIVE)
        min_training = max(min_training, YEAR)
    methods.append(HOLT_WINTERS)

    origins = sorted(range(len(values) - HORIZON, min_training - 1, -HORIZON)[:8])
    actual = np.concatenate([values[end:end + HORIZON] for end in origins])
    metrics = []
    for method in methods:
        predictions = np.concatenate([
            np.maximum(0, _predict(method, values[:end], seasonal)) for end in origins
        ])
        errors = np.abs(actual - predictions)
        metrics.append({
            "model": method,
            "mae": float(np.mean(errors)),
            "mape": float(np.mean(errors / np.abs(actual)) * 100) if np.all(actual != 0) else None,
            "origins": len(origins),
        })

    selected = min(metrics, key=lambda metric: metric["mae"])
    last_week: date = segment[-1]["week"]
    predictions = np.maximum(0, _predict(selected["model"], values, seasonal))
    return {
        **response,
        "supported": True,
        "reason": "",
        "model": selected["model"],
        "seasonal": seasonal and selected["model"] == HOLT_WINTERS,
        "forecast": [
            {"week": last_week + timedelta(weeks=step), "price": round(float(value), 2)}
            for step, value in enumerate(predictions, start=1)
        ],
        "metrics": metrics,
    }
