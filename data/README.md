# Synthetic research dataset

This fixture provides intentionally generated records for testing and demonstration. It contains no actual suppliers, prices, or contamination observations. Keep it in a separate PostgreSQL database from the small demo fixture.

## Generate and load

From the project root, generate into a path that does not exist. The defaults use seed `42` and `data/synthetic`. With the same Python environment, seed, and dependencies, the CSV files are byte-identical.

```powershell
python -m data_gen.generate --seed 42 --output data/synthetic
createdb -U postgres tracefood_synthetic
psql -X -U postgres -d tracefood_synthetic -v ON_ERROR_STOP=1 --single-transaction -f db/01_schema.sql -f db/02_integrity.sql -f db/03_views.sql -f db/04_functions.sql -f db/05_roles.sql
$env:DB_OWNER_URL = 'postgresql://postgres@127.0.0.1:5432/tracefood_synthetic'
python -m data_gen.load --input data/synthetic
```

Configure PostgreSQL authentication for the database owner using a password file or the local environment. The loader expects an empty TraceFood schema. It loads the table CSVs in foreign-key order under one transaction, advances sequences, runs the rule detectors, and analyzes the tables. PostgreSQL evaluates the deferred origin constraint before commit. The loader keeps `labels.csv` as an offline evaluation file.

## Generation settings and measured counts

The fixture covers January 2025 through June 2026. It uses Faker's `en_IN` names, eight Karnataka cities for supply chain participants, and Bengaluru, Mysuru, and Hubballi for price histories. Raw batches cover tomato, onion, potato, and mango. Recipes create tomato puree, tomato onion masala, mango pulp, and potato chips. The masala includes puree, which creates multilevel lineage. Prices combine a synthetic seasonal cycle, stage multipliers, market variation, and noise. Retail prices give 24 product and market series with uninterrupted weekly coverage.

| Table or group | Seed 42 rows |
| --- | ---: |
| Farm and contacts | 25 farms, 33 contacts |
| Processing facility | 6 |
| Retailer and contacts | 30 retailers, 43 contacts |
| Batch | 3,000 original, 1,200 processed |
| Batch derivation | 2,357 |
| Batch processing | 1,200 |
| Shipment and items | 2,500 shipments, 6,171 items |
| Quality check | 5,000, including 150 failed checks |
| Price record | 20,000 |
| Rule alerts after load | 125 |

The generated `manifest.json` records counts for each output and anomaly category. `labels.csv` uses columns `entity`, `id`, `label`, and `parameters`. The last field is a JSON object containing the planted variation and, when relevant, its related record IDs.

| Label | Seed 42 cases | Evidence ID |
| --- | ---: | --- |
| MASS_BALANCE | 24 | Processed batch |
| OVER_ALLOCATION | 63 | Batch and related shipment in parameters |
| UNIT_ERROR | 13 | Batch and related shipment in parameters |
| EXPIRED_SHIPMENT | 25 | Shipment and related batch in parameters |
| YIELD_OUTLIER | 18 | Processed batch |
| PRICE_SPIKE | 200 | Price record |
| PRICE_DROP | 200 | Price record |

## Lineage index experiment

Run the comparison on the isolated synthetic database. It collects full PostgreSQL plans with the index present and then drops the index in a transaction that always rolls back.

```powershell
python -m data_gen.explain --repeats 5 --output data/synthetic/downstream-explain.json
```

On PostgreSQL 16.15, `B2481` returned seven descendants in both configurations. The measured median execution times across five runs after warmup were 1.044 ms with the lineage input index and 1.190 ms without it. The plans used an index scan with the index available and a sequential scan of the lineage table after dropping it. These timings describe this fixture on the lab machine.
