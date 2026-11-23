"""Historical yield comparisons for products made with the same operation."""

import numpy as np
import pandas as pd

MIN_YIELD_HISTORY = 10
YIELD_THRESHOLD = 3.5


def score_yields(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["production_date"] = pd.to_datetime(result["production_date"])
    result["yield_ratio"] = result["yield_ratio"].astype(float)
    result = result.sort_values(["product_name", "operation_type", "production_date", "batch_id"])
    result["history_count"] = 0
    result["ref_yield"] = np.nan
    result["yield_z"] = np.nan
    for _, group in result.groupby(["product_name", "operation_type"], sort=False):
        ratios = group["yield_ratio"].to_numpy()
        days = group["production_date"].to_numpy()
        for day in np.unique(days):
            first, last = days.searchsorted(day, side="left"), days.searchsorted(day, side="right")
            ids = group.index[first:last]
            result.loc[ids, "history_count"] = first
            if first < MIN_YIELD_HISTORY:
                continue
            history = ratios[:first]
            median = np.median(history)
            mad = np.median(np.abs(history - median))
            scale = mad if mad else max(0.01 * abs(median), 0.0001)
            result.loc[ids, "ref_yield"] = median
            result.loc[ids, "yield_z"] = 0.6745 * (ratios[first:last] - median) / scale
    return result


def explain_yield(row) -> str:
    direction = "above" if row.yield_z > 0 else "below"
    return (
        f"Batch {row.batch_id} yielded {row.yield_ratio:.3f} {row.unit}/{row.unit} of "
        f"{row.product_name} ({row.operation_type}), {abs(row.yield_z):.1f} robust SDs {direction} "
        f"the median {row.ref_yield:.3f} across {row.history_count} comparable earlier batches. "
        "Check the recorded input quantities, units, and any change in the process."
    )
