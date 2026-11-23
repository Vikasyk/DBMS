"""Train the price model and measure all detectors on labeled synthetic data."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row

from backend.app.services.anomalies import PRICE_HISTORY, YIELD_HISTORY
from backend.app.services.prices import weekly_retail_history
from ml.forecast import evaluate_forecast
from ml.price_anomaly import MODEL_VERSION, build_features, fit_model, score_prices
from ml.yield_anomaly import YIELD_THRESHOLD, score_yields


def classification(actual, detected):
    truth, predictions = set(actual), set(detected)
    tp = len(truth & predictions)
    fp = len(predictions - truth)
    fn = len(truth - predictions)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def periods(dates):
    days = sorted(pd.to_datetime(dates).unique())
    if len(days) < 20:
        raise ValueError("Evaluation requires at least 20 distinct dates in the synthetic dataset")
    return pd.Timestamp(days[int(len(days) * 0.70) - 1]), pd.Timestamp(days[int(len(days) * 0.85) - 1])


def _measure_rules(alerts, labels):
    detected = {kind: set() for kind in ("MASS_BALANCE", "OVER_ALLOCATION", "EXPIRED_SHIPMENT")}
    for row in alerts:
        if row["alert_type"] == "EXPIRED_SHIPMENT":
            key = (row["related_shipment_id"], row["batch_id"])
        else:
            key = row["batch_id"]
        detected[row["alert_type"]].add(key)

    planted = {kind: set(labels.loc[labels["label"] == kind, "id"]) for kind in detected}
    planted["EXPIRED_SHIPMENT"] = {
        (row.id, json.loads(row.parameters)["batch_id"])
        for row in labels[labels["label"] == "EXPIRED_SHIPMENT"].itertuples(index=False)
    }
    unit_errors = set(labels.loc[labels["label"] == "UNIT_ERROR", "id"])
    # Unit errors are legitimate positives for either of the two quantity rules.
    result = {
        kind: classification(truth, detected[kind] - (unit_errors - truth))
        for kind, truth in planted.items()
    }
    result["UNIT_ERROR"] = {
        "detected": len(unit_errors & (detected["MASS_BALANCE"] | detected["OVER_ALLOCATION"])),
        "planted": len(unit_errors),
    }
    return result


def _measure_prices(prices, labels, train_end, validation_end):
    features = build_features(prices)
    labelled = labels[labels["label"].isin(["PRICE_SPIKE", "PRICE_DROP"])]
    positive_ids = set(labelled["id"])
    train = features[features["price_date"] <= train_end]
    valid = features[(features["price_date"] > train_end) & (features["price_date"] <= validation_end)]
    test = features[features["price_date"] > validation_end]
    model = fit_model(train)
    scored_valid, scored_test = score_prices(model, valid), score_prices(model, test)
    valid_positives = positive_ids.intersection(valid["price_id"])
    best_threshold = None
    for threshold in np.linspace(0.80, 1.00, 201):
        metric = classification(valid_positives, scored_valid.loc[scored_valid["ml_score"] >= threshold, "price_id"])
        rank = (metric["f1"] or 0, float(threshold))
        if best_threshold is None or rank > best_threshold:
            best_threshold = rank
    model.threshold = best_threshold[1]
    ml_ids = set(scored_test.loc[scored_test["ml_score"] >= model.threshold, "price_id"])
    robust_ids = set(scored_test.loc[scored_test["robust_z"].abs() >= 3.5, "price_id"])
    test_ids = set(test["price_id"])
    metrics = {}
    for kind in ("ALL_PRICE_ANOMALIES", "PRICE_SPIKE", "PRICE_DROP"):
        positives = positive_ids if kind == "ALL_PRICE_ANOMALIES" else set(labelled.loc[labelled["label"] == kind, "id"])
        other_anomalies = positive_ids - positives
        truth = test_ids & positives
        metrics[kind] = {
            "isolation_forest": classification(truth, ml_ids - other_anomalies),
            "robust_z": classification(truth, robust_ids - other_anomalies),
        }
    return model, {
        "training_rows": len(train), "validation_rows": len(valid), "test_rows": len(test),
        "validation_f1": best_threshold[0], "threshold": model.threshold, "held_out": metrics,
    }


def evaluate(database_url, labels_path, model_dir, result_path):
    labels = pd.read_csv(labels_path, dtype={"id": str})
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        alerts = conn.execute(
            "SELECT batch_id, alert_type, related_shipment_id FROM tracefood.v_alerts WHERE detection_method = 'RULE'"
        ).fetchall()
        prices = pd.DataFrame(conn.execute(PRICE_HISTORY).fetchall())
        yields = pd.DataFrame(conn.execute(YIELD_HISTORY).fetchall())
        weekly = weekly_retail_history(conn, "Tomato", "Bengaluru", "kg")
        counts = conn.execute("""SELECT
            (SELECT count(*) FROM tracefood.batch) AS batches,
            (SELECT count(*) FROM tracefood.batch_derivation) AS lineage_edges,
            (SELECT count(*) FROM tracefood.shipment) AS shipments,
            (SELECT count(*) FROM tracefood.quality_check) AS quality_checks,
            (SELECT count(*) FROM tracefood.price_record) AS prices,
            (SELECT current_setting('server_version')) AS postgresql""").fetchone()

    if len(prices) < 100 or yields.empty or labels.empty or not alerts:
        raise ValueError("Load the full labeled synthetic dataset and run database rule checks first")
    train_end, validation_end = periods(prices["price_date"])
    model, price_metrics = _measure_prices(prices, labels, train_end, validation_end)
    yield_scores = score_yields(yields)
    held_yields = yield_scores[yield_scores["production_date"] > validation_end]
    yield_truth = set(held_yields["batch_id"]) & set(labels.loc[labels["label"] == "YIELD_OUTLIER", "id"])
    yield_predictions = held_yields.loc[held_yields["yield_z"].abs() >= YIELD_THRESHOLD, "batch_id"]
    forecast = evaluate_forecast(weekly)
    result = {
        "data": "Synthetic only", **counts, "labels": len(labels),
        "training_end": train_end.date().isoformat(), "validation_end": validation_end.date().isoformat(),
        "rules": _measure_rules(alerts, labels),
        "yield_held_out": {"tested": len(held_yields), "scored": int(held_yields["yield_z"].notna().sum()),
                           "threshold": YIELD_THRESHOLD, **classification(yield_truth, yield_predictions)},
        "price_anomaly": price_metrics,
        "forecast_tomato_bengaluru": {
            key: forecast[key] for key in ("supported", "reason", "model", "consecutive_weeks", "metrics", "forecast")
        },
    }
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / f"{MODEL_VERSION}.joblib", compress=3)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--labels", type=Path, default=Path("data/synthetic/labels.csv"))
    parser.add_argument("--model-dir", type=Path, default=Path("ml/models"))
    parser.add_argument("--output", type=Path, default=Path("docs/results.json"))
    args = parser.parse_args()
    results = evaluate(args.database_url, args.labels, args.model_dir, args.output)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
