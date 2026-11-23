import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

from data_gen.generate import generate


def records(directory, name):
    with (directory / f"{name}.csv").open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture(scope="module")
def fixture_directory(tmp_path_factory):
    output = tmp_path_factory.mktemp("synthetic") / "fixture"
    generate(output, seed=42)
    return output


def test_same_seed_reproduces_every_export(fixture_directory, tmp_path):
    repeated = tmp_path / "repeat"
    generate(repeated, seed=42)
    filenames = {path.name for path in fixture_directory.iterdir()}
    assert {path.name for path in repeated.iterdir()} == filenames
    for filename in filenames:
        assert (repeated / filename).read_bytes() == (fixture_directory / filename).read_bytes(), filename


def test_injected_rule_cases_match_operational_records(fixture_directory):
    batches = {batch["batch_id"]: batch for batch in records(fixture_directory, "batch")}
    shipments = {shipment["shipment_id"]: shipment for shipment in records(fixture_directory, "shipment")}
    quantity_used = defaultdict(Decimal)
    quantity_shipped = defaultdict(Decimal)
    input_mass = defaultdict(Decimal)
    for edge in records(fixture_directory, "batch_derivation"):
        assert batches[edge["input_batch_id"]]["production_date"] < batches[edge["output_batch_id"]]["production_date"]
        amount = Decimal(edge["quantity_used"])
        quantity_used[edge["input_batch_id"]] += amount
        input_mass[edge["output_batch_id"]] += amount
    late_shipments = set()
    for item in records(fixture_directory, "shipment_item"):
        batch_id = item["batch_id"]
        shipment = shipments[item["shipment_id"]]
        batch = batches[batch_id]
        assert shipment["shipment_date"] >= batch["production_date"]
        if shipment["shipment_date"] > batch["expiry_date"]:
            late_shipments.add((item["shipment_id"], batch_id))
        quantity_shipped[batch_id] += Decimal(item["quantity_shipped"])
    over_allocated = {
        batch_id for batch_id, batch in batches.items()
        if quantity_used[batch_id] + quantity_shipped[batch_id] > Decimal(batch["quantity"])
    }
    mass_excesses = {
        batch_id for batch_id, source_mass in input_mass.items()
        if Decimal(batches[batch_id]["quantity"]) > source_mass * Decimal("1.02")
    }
    labels = records(fixture_directory, "labels")
    assert mass_excesses == {row["id"] for row in labels if row["label"] == "MASS_BALANCE"}
    assert over_allocated == {row["id"] for row in labels if row["label"] in {"OVER_ALLOCATION", "UNIT_ERROR"}}
    assert late_shipments == {
        (row["id"], json.loads(row["parameters"])["batch_id"])
        for row in labels if row["label"] == "EXPIRED_SHIPMENT"
    }


def test_all_retail_series_support_weekly_forecast_evaluation(fixture_directory):
    products = {row["batch_id"]: row["product_name"] for row in records(fixture_directory, "batch")}
    retail_weeks = defaultdict(set)
    for price in records(fixture_directory, "price_record"):
        if price["supply_chain_stage"] == "RETAIL":
            day = date.fromisoformat(price["price_date"])
            retail_weeks[products[price["batch_id"]], price["market_location"]].add(
                day - timedelta(days=day.weekday())
            )
    assert len(retail_weeks) == 24
    for series in retail_weeks.values():
        assert len(series) >= 52
        assert (max(series) - min(series)).days == 7 * (len(series) - 1)
