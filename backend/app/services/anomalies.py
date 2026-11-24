from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from ml.price_anomaly import MODEL_VERSION, build_features, explain_price, fit_model, score_prices
from ml.yield_anomaly import YIELD_THRESHOLD, explain_yield, score_yields

MODEL_PATH = Path(__file__).resolve().parents[3] / "ml" / "models" / f"{MODEL_VERSION}.joblib"
PRICE_HISTORY = "SELECT * FROM tracefood.v_price_history"
YIELD_HISTORY = """
    SELECT mb.*, b.production_date, operation.operation_type
    FROM tracefood.v_mass_balance mb
    JOIN tracefood.batch b USING (batch_id)
    JOIN LATERAL (
        SELECT CASE
            WHEN count(DISTINCT bp.operation_type) = 1 THEN min(bp.operation_type)
            WHEN count(DISTINCT bp.operation_type)
                 FILTER (WHERE bp.operation_type IN ('PULPING', 'MIXING', 'OTHER')) = 1
            THEN min(bp.operation_type)
                 FILTER (WHERE bp.operation_type IN ('PULPING', 'MIXING', 'OTHER'))
        END AS operation_type
        FROM tracefood.batch_processing bp
        WHERE bp.batch_id = b.batch_id AND bp.processing_date = b.production_date
    ) operation ON true
    WHERE mb.units_consistent AND operation.operation_type IS NOT NULL
"""
INSERT_ALERT = """
    INSERT INTO tracefood.anomaly_alert
        (batch_id, alert_type, detection_method, anomaly_score, description, related_price_id)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT DO NOTHING
"""


@lru_cache(maxsize=1)
def _load_model(path, modified_ns):
    # The path refers to the project's model produced by ml.evaluate.
    return joblib.load(path)


def run_detection(conn, tolerance):
    rules = conn.execute(
        "SELECT tracefood.fn_run_rule_checks(%s) AS new_alerts", (tolerance,)
    ).fetchone()
    counts = {"RULE": rules["new_alerts"], "STATISTICAL": 0, "ML": 0}
    notes = []

    yields = pd.DataFrame(conn.execute(YIELD_HISTORY).fetchall())
    if yields.empty:
        notes.append("Yield detection needs comparable units and an identifiable creation operation.")
    else:
        scored = score_yields(yields)
        if scored["yield_z"].isna().any():
            notes.append("Yield comparisons with fewer than ten earlier comparable batches were skipped.")
        records = [
            (row.batch_id, "YIELD_OUTLIER", "STATISTICAL", round(abs(row.yield_z), 4), explain_yield(row), None)
            for row in scored[scored["yield_z"].abs() >= YIELD_THRESHOLD].itertuples(index=False)
        ]
        with conn.cursor() as cursor:
            cursor.executemany(INSERT_ALERT, records)
            counts["STATISTICAL"] = cursor.rowcount

    from_workbook = conn.execute("SELECT to_regnamespace('india_source') IS NOT NULL AS yes").fetchone()["yes"]
    if not from_workbook and not MODEL_PATH.is_file():
        notes.append("Price detection needs the trained Isolation Forest artifact.")
        return counts, notes

    prices = pd.DataFrame(conn.execute(PRICE_HISTORY).fetchall())
    if not prices.empty:
        features = build_features(prices)
        if from_workbook:
            cutoff = features.price_date.quantile(0.8)
            train = features[(features.price_date <= cutoff) & features.robust_z.notna()]
            if len(train) < 2:
                notes.append("The workbook has too few comparable earlier prices to train a price detector.")
                return counts, notes
            model = fit_model(train)
            features = features[features.robust_z.notna() & (features.price_date > cutoff)]
        else:
            model = _load_model(MODEL_PATH, MODEL_PATH.stat().st_mtime_ns)
        eligible = features[features["price_date"] > model.training_end]
        if not eligible.empty:
            scored = score_prices(model, eligible)
            records = [
                (row.batch_id, "PRICE_OUTLIER", "ML", round(row.ml_score, 4), explain_price(row, model), row.price_id)
                for row in scored[scored["ml_score"] >= model.threshold].itertuples(index=False)
            ]
            with conn.cursor() as cursor:
                cursor.executemany(INSERT_ALERT, records)
                counts["ML"] = cursor.rowcount
            return counts, notes
    notes.append("Price detection needs observations after the model's training cutoff.")
    return counts, notes
