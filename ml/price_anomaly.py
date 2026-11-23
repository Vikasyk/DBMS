"""Train and score comparable price observations in chronological order."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

GROUP = ["product_name", "unit", "supply_chain_stage", "market_location"]
FEATURES = ["robust_z", "pct_change", "markup", "markup_missing"]
MODEL_VERSION = "price_iforest_v1"
MIN_PRICE_HISTORY = 5


def _mad(values):
    return np.median(np.abs(values - np.median(values)))


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["price_date"] = pd.to_datetime(data["price_date"])
    data = data.sort_values([*GROUP, "price_date", "price_id"]).reset_index(drop=True)
    data["selling_price"] = data["selling_price"].astype(float)
    data["ref_median"] = np.nan
    data["robust_z"] = np.nan
    for _, group in data.groupby(GROUP, sort=False):
        history = group.set_index("price_date")["selling_price"]
        window = history.rolling("30D", closed="left", min_periods=MIN_PRICE_HISTORY)
        median = window.median().to_numpy()
        mad = window.apply(_mad, raw=True).to_numpy()
        scale = np.maximum.reduce([mad, 0.01 * np.abs(median), np.full(len(group), 0.01)])
        data.loc[group.index, "ref_median"] = median
        data.loc[group.index, "robust_z"] = 0.6745 * (history.to_numpy() - median) / scale
    data["pct_change"] = pd.to_numeric(data["price_change_percentage"])
    cost = pd.to_numeric(data["cost_per_unit"])
    data["markup"] = data["selling_price"].div(cost.where(cost > 0))
    data["markup_missing"] = data["markup"].isna().astype(int)
    return data


@dataclass
class PriceModel:
    forest: IsolationForest
    reference_scores: np.ndarray
    threshold: float
    training_end: pd.Timestamp
    version: str = MODEL_VERSION


def _features(frame: pd.DataFrame):
    return frame[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)


def fit_model(train: pd.DataFrame, seed: int = 42) -> PriceModel:
    inputs = _features(train)
    forest = IsolationForest(n_estimators=200, contamination="auto", random_state=seed)
    forest.fit(inputs)
    return PriceModel(forest, np.sort(-forest.score_samples(inputs)), 1.0, train["price_date"].max())


def score_prices(model: PriceModel, frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if result.empty:
        result["ml_score"] = pd.Series(dtype=float)
        return result
    raw = -model.forest.score_samples(_features(result))
    result["ml_score"] = np.searchsorted(model.reference_scores, raw, side="left") / len(model.reference_scores)
    return result


def explain_price(row, model: PriceModel) -> str:
    observations = []
    if abs(row.robust_z) >= 3.5:
        observations.append(f"{row.robust_z:+.1f} robust SDs from the 30-day median {row.ref_median:.2f}")
    if abs(row.pct_change) >= 50:
        observations.append(f"{row.pct_change:+.1f}% versus the previous comparable observation")
    if pd.notna(row.markup):
        observations.append(f"selling price was {row.markup:.2f} times the recorded unit cost")
    evidence = ", ".join(observations) or "the price features together were unusual"
    return (
        f"Price {row.price_id} recorded INR {row.selling_price:.2f}/{row.unit} for "
        f"{row.product_name} at {row.market_location} ({row.supply_chain_stage}). "
        f"Observed evidence: {evidence}. More unusual than {100 * row.ml_score:.1f}% "
        f"of the synthetic training observations ({model.version}). "
        "Check for pricing or unit-entry errors, missing costs, or a genuine market change."
    )
