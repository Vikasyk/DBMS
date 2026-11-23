from datetime import date, timedelta

import pandas as pd

from ml.forecast import evaluate_forecast
from ml.price_anomaly import build_features, explain_price, fit_model, score_prices
from ml.yield_anomaly import score_yields


def test_price_features_exclude_current_and_same_day_observations(tmp_path):
    import joblib

    frame = pd.DataFrame([
        {"price_id": f"P{i}", "product_name": "Tomato", "unit": "kg",
         "supply_chain_stage": "RETAIL", "market_location": "Bengaluru",
         "price_date": date(2025, 1, min(i, 8)), "selling_price": 40 if i < 8 else 95 + i,
         "price_change_percentage": None, "cost_per_unit": None}
        for i in range(1, 10)
    ])
    features = build_features(frame)
    assert list(features.tail(2)["ref_median"]) == [40, 40]
    assert list(features.tail(2)["markup_missing"]) == [1, 1]
    model = fit_model(features.iloc[:7])
    saved = tmp_path / "model.joblib"
    joblib.dump(model, saved)
    scored = score_prices(joblib.load(saved), features.iloc[7:])
    assert scored["ml_score"].between(0, 1).all()
    assert "P8" in explain_price(next(scored.itertuples(index=False)), model)


def test_yield_features_use_previous_dates_in_the_same_group():
    frame = pd.DataFrame([
        {"batch_id": f"B{100 + i}", "product_name": "Tomato Puree", "operation_type": "PULPING",
         "production_date": date(2025, 1, min(i, 11)), "yield_ratio": 0.75 if i < 11 else 0.25}
        for i in range(1, 13)
    ])
    result = score_yields(frame)
    assert result.head(10)["yield_z"].isna().all()
    assert list(result.tail(2)["history_count"]) == [10, 10]
    assert (result.tail(2)["yield_z"] < -3.5).all()


def test_forecast_gate_and_rolling_evaluation():
    weeks = [
        {"week": date(2025, 1, 6) + timedelta(weeks=i), "price": 25 + i * 0.5}
        for i in range(76)
    ]
    assert not evaluate_forecast(weeks[:51])["supported"]
    assert not evaluate_forecast(weeks[:40] + weeks[41:])["supported"]
    result = evaluate_forecast(weeks)
    assert result["supported"]
    assert result["model"] == "Holt-Winters"
    assert len(result["forecast"]) == 4
    assert result["forecast"][0]["price"] == 63.0
    assert all(row["origins"] > 0 and row["mae"] >= 0 for row in result["metrics"])
