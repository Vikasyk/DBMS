"""Generate one deterministic, entirely synthetic TraceFood dataset."""

import argparse
import bisect
import csv
import json
import math
import random
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

from .schema import LABEL_COLUMNS, TABLE_COLUMNS


START = date(2025, 1, 1)
END = date(2026, 6, 30)
ONE_DAY = timedelta(days=1)
DEFAULT_OUTPUT = Path("data/synthetic")
RAW_SHELF_LIFE = {"Tomato": (10, 15), "Onion": (30, 60), "Potato": (60, 90), "Mango": (7, 12)}
BASE_PRICES = {
    "Tomato": 20, "Onion": 26, "Potato": 22, "Mango": 65,
    "Tomato Puree": 61, "Tomato Onion Masala": 78, "Mango Pulp": 112, "Potato Chips": 95,
}
KARNATAKA_CITIES = {
    "Bengaluru": "560001", "Mysuru": "570001", "Hubballi": "580020",
    "Kolar": "563101", "Chikkaballapur": "562101", "Chitradurga": "577501",
    "Tumakuru": "572101", "Mandya": "571401",
}
MARKETS = {"Bengaluru": 1.03, "Mysuru": 0.98, "Hubballi": 1.01}
PRICE_STAGES = ("FARM", "PROCESSING_WHOLESALE", "RETAIL")
DEFECTS = ("Salmonella", "E. coli", "Listeria", "Pesticide Residue", "Aflatoxin", "Foreign Matter")


@dataclass(frozen=True)
class Recipe:
    name: str
    ingredients: tuple[str, ...]
    operation: str
    yield_range: tuple[float, float]
    start_offset: int = 1


RECIPES = (
    Recipe("Tomato Puree", ("Tomato",), "PULPING", (0.60, 0.80)),
    Recipe("Tomato Onion Masala", ("Tomato Puree", "Onion"), "MIXING", (0.95, 1.00), 3),
    Recipe("Mango Pulp", ("Mango",), "PULPING", (0.55, 0.70)),
    Recipe("Potato Chips", ("Potato",), "OTHER", (0.25, 0.35)),
)


@dataclass
class Batch:
    identifier: str
    product: str
    date: date
    expiry: date
    quantity: int
    remaining: int
    farm: str | None
    last_used: date | None = None

    def row(self):
        return (
            self.identifier, self.product, kg(self.quantity), "kg", self.date, self.expiry, "ACTIVE", self.farm,
        )


@dataclass
class Shipment:
    identifier: str
    date: date
    retailer: str
    source: str
    cost: float
    items: dict[str, int]

    def row(self):
        return self.identifier, self.date, self.source, self.retailer, f"{self.cost:.2f}"


def kg(milli_kg):
    """Render quantities maintained as integer thousandths of a kilogram."""
    whole, fraction = divmod(milli_kg, 1000)
    return f"{whole}.{fraction:03d}"


def label(entity, identifier, anomaly, **parameters):
    return entity, identifier, anomaly, json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def make_master_data(rng, fake, tables):
    for table, count, prefix, suffix in (
        ("farm", 25, "F", "Farm"),
        ("processing_facility", 6, "PF", "Food Processing"),
        ("retailer", 30, "R", "Market"),
    ):
        for index in range(1, count + 1):
            identifier = f"{prefix}{index:02d}"
            city = rng.choice(tuple(KARNATAKA_CITIES))
            name = f"{fake.last_name()} {suffix} {index}"
            street = f"{index} {fake.first_name()} Road"
            tables[table].append((identifier, name, street, city, "Karnataka", KARNATAKA_CITIES[city]))
            if table == "farm" or table == "retailer":
                for _ in range(1 + int(rng.random() < 0.25)):
                    phone = f"+91{rng.randint(7_000_000_000, 9_999_999_999)}"
                    tables[f"{table}_contact"].append((identifier, phone))


def make_original_batches(rng, tables):
    days = (END - START).days + 1
    products = tuple(RAW_SHELF_LIFE)
    sources = [row[0] for row in tables["farm"]]
    # Place at least one batch of every raw product on the first day.
    roster = [(START, product) for product in products]
    roster.extend(
        (START + index * ONE_DAY, products[(index + offset) % len(products)])
        for offset in range(5)
        for index in range(days)
    )
    roster.extend(
        (START + rng.randrange(days) * ONE_DAY, rng.choice(products))
        for _ in range(3000 - len(roster))
    )
    batches = []
    for index, (production, product) in enumerate(sorted(roster), 101):
        lifetime = rng.randint(*RAW_SHELF_LIFE[product])
        quantity = rng.randint(150, 320) * 1000
        batches.append(Batch(
            f"B{index}", product, production, production + lifetime * ONE_DAY,
            quantity, quantity, rng.choice(sources),
        ))
    return batches


def make_processed_batches(rng, batches, tables, labels):
    by_product = defaultdict(list)
    for batch in batches:
        by_product[batch.product].append(batch)

    mass_balance = set(rng.sample(range(300), 24))
    yield_outliers = set(rng.sample(range(300), 18))
    available_facilities = [row[0] for row in tables["processing_facility"]]
    schedule = sorted(
        (START + (recipe.start_offset + index * ((END - START).days - recipe.start_offset) // 299) * ONE_DAY,
         recipe_order, index)
        for recipe_order, recipe in enumerate(RECIPES)
        for index in range(300)
    )
    for production, recipe_order, index in schedule:
        recipe = RECIPES[recipe_order]
        identifier = f"B{101 + len(batches)}"
        ingredients = list(recipe.ingredients)
        if len(ingredients) == 1:
            ingredients *= rng.randint(1, 3)
        chosen = set()
        input_total = 0
        for ingredient in ingredients:
            candidates = [
                item for item in by_product[ingredient]
                if item.date < production <= item.expiry and item.remaining >= 1000
                and item.identifier not in chosen
            ]
            if not candidates and len(recipe.ingredients) == 1 and chosen:
                break
            source = rng.choice(candidates)
            amount = min(source.remaining, rng.randint(14, 45) * 1000)
            chosen.add(source.identifier)
            source.remaining -= amount
            source.last_used = production
            input_total += amount
            tables["batch_derivation"].append((identifier, source.identifier, kg(amount)))

        ratio = rng.uniform(*recipe.yield_range)
        quantity = round(input_total * ratio)
        if recipe.name == "Tomato Onion Masala" and index in mass_balance:
            multiplier = rng.uniform(1.15, 1.40)
            labels.append(label("batch", identifier, "MASS_BALANCE", multiplier=round(multiplier, 4),
                                clean_output_kg=kg(quantity), input_kg=kg(input_total)))
            quantity = round(quantity * multiplier)
        if recipe.name == "Tomato Puree" and index in yield_outliers:
            low_ratio = rng.uniform(0.26, 0.34)
            labels.append(label("batch", identifier, "YIELD_OUTLIER", usual_yield=round(ratio, 4),
                                observed_yield=round(low_ratio, 4)))
            quantity = round(input_total * low_ratio)
        batch = Batch(
            identifier, recipe.name, production, production + rng.randint(60, 180) * ONE_DAY,
            quantity, quantity, None,
        )
        batches.append(batch)
        by_product[recipe.name].append(batch)
        tables["batch_processing"].append((rng.choice(available_facilities), identifier, production, recipe.operation))


def make_shipments(rng, batches, tables):
    days = (END - START).days + 1
    source_locations = [f"{row[1]}, {row[3]}" for row in tables["farm"] + tables["processing_facility"]]
    retailers = [row[0] for row in tables["retailer"]]
    shipment_dates = sorted(START + rng.randrange(days) * ONE_DAY for _ in range(2500))
    shipments = []
    for index, shipment_date in enumerate(shipment_dates, 501):
        candidates = [
            batch for batch in batches
            if batch.date <= shipment_date <= batch.expiry and batch.remaining >= 3000
        ]
        size = min(len(candidates), rng.randint(1, 4))
        items = {}
        for batch in rng.sample(candidates, size):
            amount = min(batch.remaining, rng.randint(8, 45) * 1000)
            batch.remaining -= amount
            items[batch.identifier] = amount
        if not items:
            raise RuntimeError(f"No available batches for shipment on {shipment_date}")
        shipments.append(Shipment(
            f"S{index}", shipment_date, rng.choice(retailers), rng.choice(source_locations),
            rng.uniform(300, 3700), items,
        ))
    return shipments


def inject_shipment_anomalies(rng, batches, shipments, labels):
    by_id = {batch.identifier: batch for batch in batches}
    excluded = {identifier for entity, identifier, _, _ in labels if entity == "batch"}
    singleton_shipments = [
        shipment for shipment in shipments if len(shipment.items) == 1
        and by_id[next(iter(shipment.items))].expiry < END
        and next(iter(shipment.items)) not in excluded
    ]
    for shipment in rng.sample(singleton_shipments, 25):
        batch_id = next(iter(shipment.items))
        batch = by_id[batch_id]
        delay = rng.randint(1, min(10, (END - batch.expiry).days))
        labels.append(label("shipment", shipment.identifier, "EXPIRED_SHIPMENT", days_late=delay,
                            batch_id=batch_id, clean_date=shipment.date.isoformat()))
        shipment.date = batch.expiry + delay * ONE_DAY
        excluded.add(batch_id)

    last_shipments = {}
    for shipment in sorted(shipments, key=lambda item: (item.date, item.identifier)):
        for batch_id in shipment.items:
            batch = by_id[batch_id]
            if batch_id not in excluded and (batch.last_used is None or shipment.date > batch.last_used):
                last_shipments[batch_id] = shipment

    volume_cases = round(4200 * 0.015)
    unit_cases = round(4200 * 0.003)
    for index, batch_id in enumerate(rng.sample(list(last_shipments), volume_cases + unit_cases)):
        batch = by_id[batch_id]
        shipment = last_shipments[batch_id]
        clean_amount = shipment.items[batch_id]
        if index < volume_cases:
            excess_percent = rng.randint(5, 30)
            extra = batch.remaining + round(batch.quantity * excess_percent / 100)
            shipment.items[batch_id] += extra
            labels.append(label("batch", batch_id, "OVER_ALLOCATION", excess_percent=excess_percent,
                                shipment_id=shipment.identifier, clean_shipped_kg=kg(clean_amount)))
        else:
            shipment.items[batch_id] *= 1000
            labels.append(label("batch", batch_id, "UNIT_ERROR", multiplier=1000, shipment_id=shipment.identifier,
                                clean_shipped_kg=kg(clean_amount)))


def make_quality_checks(rng, batches):
    failed = set(rng.sample(range(5000), 150))
    inspections = []
    for index, batch in enumerate([*batches, *rng.choices(batches, k=5000 - len(batches))]):
        stage = ("FARM" if batch.farm else "PROCESSING") if rng.random() < 0.7 else rng.choice(
            ("DISTRIBUTION", "RETAIL")
        )
        max_delay = min(12, (END - batch.date).days, (batch.expiry - batch.date).days)
        inspection_date = batch.date + rng.randint(0, max_delay) * ONE_DAY
        defect = rng.choice(DEFECTS) if index in failed else None
        inspections.append((f"QC{index + 1}", batch.identifier, inspection_date, stage,
                            "FAIL" if defect else "PASS", defect, None))
    return inspections


def make_prices(rng, batches, labels):
    active_by_product = defaultdict(list)
    for batch in sorted(batches, key=lambda item: item.date):
        active_by_product[batch.product].append(batch)
    by_product_dates = {
        product: [item.date for item in items] for product, items in active_by_product.items()
    }
    regular = []
    supplementary = []
    for day_num in range((END - START).days + 1):
        observed = START + day_num * ONE_DAY
        for product, all_batches in active_by_product.items():
            boundary = bisect.bisect_right(by_product_dates[product], observed)
            recent = [batch for batch in reversed(all_batches[max(0, boundary - 12):boundary])
                      if observed <= batch.expiry]
            if not recent:
                continue
            for stage_index, stage in enumerate(PRICE_STAGES):
                if stage == "FARM" and product not in RAW_SHELF_LIFE:
                    continue
                for market_index, market in enumerate(MARKETS):
                    target = regular if (day_num + stage_index + market_index) % 2 == 0 else supplementary
                    target.append((observed, product, stage, market, rng.choice(recent).identifier))
    observations = sorted(regular + rng.sample(supplementary, 20_000 - len(regular)))
    eligible = [index for index, point in enumerate(observations) if point[0] >= START + 30 * ONE_DAY]
    price_anomalies = {index: i < 200 for i, index in enumerate(rng.sample(eligible, 400))}
    prices = []
    for index, (observed, product, stage, market, batch_id) in enumerate(observations):
        price_id = f"P{index + 1}"
        seasonal_day = (observed - START).days
        seasonal = 1 + 0.25 * math.sin(2 * math.pi * seasonal_day / 365)
        stage_factor = 1.0
        if stage == "PROCESSING_WHOLESALE":
            stage_factor = rng.uniform(1.3, 1.5)
        if stage == "RETAIL":
            stage_factor = rng.uniform(1.8, 2.2)
        price = BASE_PRICES[product] * seasonal * stage_factor * MARKETS[market] * rng.gauss(1, 0.04)
        cost = None if rng.random() < 0.05 else f"{price * rng.uniform(0.66, 0.83):.2f}"
        if index in price_anomalies:
            spike = price_anomalies[index]
            multiplier = rng.uniform(1.6, 2.5) if spike else rng.uniform(0.4, 0.6)
            labels.append(label("price", price_id, "PRICE_SPIKE" if spike else "PRICE_DROP",
                                multiplier=round(multiplier, 4), clean_price=round(price, 2)))
            price *= multiplier
        prices.append((price_id, batch_id, observed, stage, f"{price:.2f}", cost, market))
    return prices


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def generate(output, seed=42):
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Choose an output directory that does not exist: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    tables = {table: [] for table in TABLE_COLUMNS}
    labels = []
    make_master_data(rng, fake, tables)
    batches = make_original_batches(rng, tables)
    make_processed_batches(rng, batches, tables, labels)
    shipments = make_shipments(rng, batches, tables)
    inject_shipment_anomalies(rng, batches, shipments, labels)
    tables["batch"] = [batch.row() for batch in batches]
    tables["shipment"] = [shipment.row() for shipment in shipments]
    tables["shipment_item"] = [
        (shipment.identifier, batch_id, kg(amount)) for shipment in shipments
        for batch_id, amount in shipment.items.items()
    ]
    tables["quality_check"] = make_quality_checks(rng, batches)
    tables["price_record"] = make_prices(rng, batches, labels)

    summary = {
        "dataset": "TraceFood synthetic research fixture",
        "seed": seed,
        "first_date": START.isoformat(),
        "last_date": END.isoformat(),
        "tables": {table: len(rows) for table, rows in tables.items()},
        "labels": dict(Counter(item[2] for item in labels)),
    }
    with tempfile.TemporaryDirectory(prefix=".tf-", dir=output.parent) as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir()
        for table, columns in TABLE_COLUMNS.items():
            write_csv(staged / f"{table}.csv", columns, tables[table])
        write_csv(staged / "labels.csv", LABEL_COLUMNS, sorted(labels))
        (staged / "manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged.rename(output)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    try:
        summary = generate(arguments.output, arguments.seed)
    except FileExistsError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
