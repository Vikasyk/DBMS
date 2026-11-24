# TraceFood

TraceFood is a DBMS lab project that tracks food batches from farms through processing and distribution. PostgreSQL stores lineage, enforces integrity, and calculates available stock. A React website uses FastAPI for data entry, interactive lineage, quality investigations, read-only simulations, price analytics, anomaly review, and natural-language queries.

The design follows [the v2 project specification](TraceFood_Project_Specification_v2.pdf). SQL scripts 01–06 provide the schema, integrity rules, views, routines, roles, and synthetic demo records from Appendix A.

## How the system fits together

The browser loads a React single-page application from Vite. Its `/api` requests are proxied to FastAPI, which validates request bodies with Pydantic and uses separate Psycopg connection pools for application operations and restricted natural-language queries. PostgreSQL is the source of truth: its constraints, triggers, views, and functions enforce and report on the supply chain. The analytics modules use recorded data for anomaly detection and forecasting. Ollama is optional; the built-in question catalogue works without it.

```text
Browser -> Vite/React (:5173) -> /api proxy -> FastAPI (:8000)
                                                   |-> app role -> PostgreSQL (:5432)
                                                   |-> read-only NL role -> curated views
                                                   |-> optional local Ollama
```

This is a lab and demonstration system. The bundled fixture and synthetic research data are artificial; potential exposure in a lineage report is not proof of contamination, and an anomaly score is not a fraud probability. Price differences do not by themselves establish profit.

## Repository map

| Path | Purpose |
| --- | --- |
| `backend/app/main.py`, `config.py`, `db.py`, `errors.py` | API entry point, environment settings, database pools, and error handling. |
| `backend/app/models.py` | Request schemas, field limits, supported values, and validation. |
| `backend/app/routers/p1_master.py` through `p7_query.py` | HTTP endpoints for master data, processing, quality, shipments, prices, alerts, questions, and reports. |
| `backend/app/services/` | Lineage, contamination, price, and anomaly service logic. |
| `backend/app/nlq/` | Question templates, routing, generated SQL validation, and optional Ollama client. |
| `frontend/src/main.jsx`, `ui.jsx`, `api.js` | Frontend entry point, shared UI, and API access. |
| `frontend/src/pages/` and CSS files | Dashboard, operations, tracing, insights, and styling. |
| `db/01_schema.sql`–`08_numeric_integrity.sql` | Schema, integrity, views, functions, roles, demo records, and later integrity/concurrency changes. |
| `db/install_schema.sql`, `db/install_demo.sql` | Ordered installation entry points; the latter also loads the demo. |
| `db/tests/regression.sql` | Database regression and permissions checks. |
| `data_gen/`, `data/` | Synthetic dataset generation, loading, index experiment, and data notes. |
| `ml/` | Price and yield anomaly detection, forecasting, evaluation, notebooks, and a synthetic trained model. |
| `tests/` | Python tests for the API, analytics, natural-language queries, generator, and concurrent lineage. |
| `docs/` | Demo walkthrough, lab report, diagrams, and recorded experiment results. |
| `compose.yaml`, `.env.example`, `requirements*.txt`, `frontend/package*.json` | Database service, configuration template, and dependency manifests. |

## Configuration reference

Copy `.env.example` to `.env` in the project root. The backend loads this file at startup; existing environment variables take precedence. The file is ignored by Git and should contain local credentials, not shared secrets.

| Variable | Meaning |
| --- | --- |
| `POSTGRES_PASSWORD` | Administrator password used when Compose first initializes its PostgreSQL volume. Changing it later does not change an existing database password. |
| `POSTGRES_PORT` | Host port for the Compose database, default `5432`; update both database URLs if changed. |
| `DB_APP_URL` | PostgreSQL connection URL for `tracefood_app`, used by ordinary API operations. |
| `DB_NL_URL` | PostgreSQL connection URL for `tracefood_nl_reader`, required even without Ollama. The API checks this role's restrictions. |
| `LLM_PROVIDER` | `none` (default) or `ollama` for optional fallback questions. |
| `LLM_MODEL` | Name of an installed local Ollama model when using `ollama`. |
| `OLLAMA_BASE_URL` | Local loopback HTTP(S) Ollama origin, default `http://127.0.0.1:11434`. |
| `TRACEFOOD_API_TARGET` | Optional Vite proxy target, default `http://127.0.0.1:8000`; set it in the frontend environment before starting Vite. |
| `TRACEFOOD_RUN_DB_TESTS` | Set to `1` to enable tests requiring the demo database. |
| `TRACEFOOD_TEST_OWNER_URL` | Administrator connection for the optional two-connection concurrency test; use a disposable fixture database. |

The synthetic commands below pass `TRACEFOOD_OWNER_URL` explicitly as `--database-url`. The loader and index experiment also accept `DB_OWNER_URL` as their own default. Database URLs have the form `postgresql://user:password@host:port/database`; percent-encode special characters in credentials. Restart the API after changing its settings.

## Run locally

Use Python 3.11+, PostgreSQL 16+, and Node.js 22.12+. Run these commands from the project folder. The examples use PowerShell.

### Active India workbook database

This workspace uses `tracefood_india` with the supplied `food-supply-chain-INDIA-FINAL.xlsx`. Its nine sheets contain 50,000 farms, 3,000 facilities, 10,000 retailers, 50,000 batches, 60,000 quality checks, 50,000 shipments, 15,000 alerts, 50,000 price records and 87,337 shipment memberships. The data is simulated. The local generation scripts describe how the records were produced.

Open **Batch trace** and search for `BATCH-00001` or `B1`. Follow the input/output links, open a shipment, and inspect its retailer. The workbook ID and lot number appear in the batch detail. Global search also accepts workbook shipment, quality check and alert IDs. **Ask TraceFood** accepts workbook batch IDs in catalogue questions.

The import retains the spreadsheet columns in the owner-only `india_source` schema, records the file SHA-256 and row counts in `india_source.manifest`, and populates the relational tables in `tracefood`. The application uses its existing short ID prefixes and the numeric part of each workbook ID. Both declared farm origins and explicit processing inputs are preserved. Reported shipment totals keep their original units. A batch receives a shipment quantity only for a single-member shipment in a matching unit. Unknown input usage and partial allocations leave available stock unknown. The workbook records processing facilities without operation names or processing dates. Conditional and pending checks map to INCONCLUSIVE, with the original result in the quality view. Resolved imported alerts map to REVIEWED. Shipment-only alerts link directly to the shipment.

Source dates sometimes disagree. In this workbook 6,337 of 12,508 input/output links have an input dated after its output. There are also 30,138 checks and 24,857 prices dated before batch production. These dates are retained for inspection. The importer loads historical rows before installing the date triggers that validate subsequent operational writes. Sparse retail series may be ineligible for forecasting. Price anomaly training on this database requires prior comparable workbook observations.

To reproduce the import on a new PostgreSQL server, create an **empty** database, install the dependencies, set `DB_OWNER_URL` to its administrator connection, and run this from the project root:

```powershell
.\.venv\Scripts\python.exe -m data_gen.import_india .\food-supply-chain-INDIA-FINAL.xlsx
```

On a fresh cluster, set passwords for the two created roles as in the setup below and point both application URLs at the imported database. Source loading and operational installation each commit atomically. A retry can reuse a completed source load of the same file. Existing operational schemas are protected. The demo walkthrough and fixture regression suite later in this document apply to the small demo database.

### Restart the project-local Windows setup

If this workspace already has the project-local PostgreSQL setup under `.local`, start its existing database, API, and frontend from three PowerShell terminals in the project root:

```powershell
.\.local\pgsql\bin\pg_ctl.exe -D D:\TraceFood-India\pgdata -l D:\TraceFood-India\postgres.log -o "-p 55433 -h 127.0.0.1" -w start
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm.cmd run dev
```

The database command returns after starting PostgreSQL; the API and frontend commands remain running in their respective terminals. Open `http://127.0.0.1:5173` and check `http://127.0.0.1:8000/health`. If PostgreSQL is already running, skip the first command. To stop it when finished, run `.\.local\pgsql\bin\pg_ctl.exe -D .local\pgdata -m fast -w stop` from the project root. The database is not installed as a Windows service and must be started again after a restart. Its data and administrator password file are in ignored `.local`; application credentials are in ignored `.env`. Preserve these files if you want to keep the database and its data. The setup below describes creating a separate installation from scratch; do not run the demo installer again on this existing database.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Edit `.env` to set local passwords. Use the same application and reader passwords when prompted by `\password` below. URL-encode special characters in the passwords inside the connection URLs. If you change the database port, also update both connection URLs.

### PostgreSQL with Docker Desktop

Start Docker Desktop, then bring up PostgreSQL and load the demo once into the empty database.

```powershell
docker compose up -d --wait db
docker compose exec db psql -X -U postgres -d tracefood -f /tracefood/db/install_demo.sql
docker compose exec db psql -X -U postgres -d tracefood
```

In the psql prompt, set both login passwords, then quit.

```text
\password tracefood_app
\password tracefood_nl_reader
\q
```

### Existing PostgreSQL 16+ installation

Create an empty database and run the setup as a PostgreSQL administrator. Use `-h` and `-p` to target your instance if needed.

```powershell
createdb -U postgres tracefood
psql -X -U postgres -d tracefood -f db/install_demo.sql
psql -X -U postgres -d tracefood
```

At the psql prompt, use the same two `\password` commands from the Docker setup.

### API and interface

Start the API and interface in separate terminals.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open [TraceFood](http://127.0.0.1:5173) or the [interactive API reference](http://127.0.0.1:8000/docs). The React server proxies `/api` to FastAPI at `http://127.0.0.1:8000`. To use a separate API instance, set `TRACEFOOD_API_TARGET` before running Vite.

For a local production-build check, run `npm.cmd run build` and `npm.cmd run preview` from `frontend`. The preview uses the same API proxy.

## Try the demo

1. Open **Batch trace** and select `B101` to see downstream batches `B103` and `B105`.
2. Open **Quality checks** and enter `QC4`, or use **Find a record** in the top bar. The report shows the failed check for `B103`, possible sources, downstream batch `B105`, and three retailers.
3. In **What-if simulation**, simulate `B101`. The report identifies retailers `R01`, `R02`, and `R03` in a read-only transaction.
4. Open **Anomalies** and run detection to produce the three seeded quantity and expiry alerts. Open any alert to inspect its evidence.
5. In **Ask TraceFood**, enter “Which retailers received products derived from B101?” to see the matching records and the SQL template used.

See the [full demonstration](docs/DEMO.md), [lab report](docs/TraceFood_Lab_Report.docx), [editable ER and schema drawings](docs/TraceFood_Diagrams.drawio), and [editable data flow drawings](docs/TraceFood_DFD.drawio).

## Database regression checks

Run as the PostgreSQL administrator against the freshly loaded demo fixture, before the anomaly walkthrough or other demo writes.

```powershell
docker compose exec db psql -X -U postgres -d tracefood -f /tracefood/db/tests/regression.sql
# Or, with native PostgreSQL:
psql -X -U postgres -d tracefood -f db/tests/regression.sql
```

The regression suite covers lineage, impact, price and stock views, rule alerts, integrity, and role privileges. It rolls back its fixture changes. For an earlier installation apply `db/07_lineage_concurrency.sql`, then `db/08_numeric_integrity.sql` once as the database owner with `psql -v ON_ERROR_STOP=1 --single-transaction -f <script>`. Same-day lineage writes use READ COMMITTED by default and also support SERIALIZABLE transactions that retry on serialization failure.

## API tests

Run the Python tests with the demo database configured in `.env`. The live tests use the fixture and leave its records intact.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:TRACEFOOD_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest
```

To include the two-connection lineage test, set `TRACEFOOD_TEST_OWNER_URL` to the administrator DSN for a disposable database containing the fixture and current schema.

## Synthetic analytics

The demo fixture is intentionally small. For statistical and ML alerts and forecasting, generate and load the full synthetic dataset into a separate database. Keep the sample database for the recording walkthrough.

```powershell
createdb -U postgres tracefood_synthetic
psql -X -U postgres -d tracefood_synthetic -f db/install_schema.sql
.\.venv\Scripts\python.exe -m data_gen.generate --output data/synthetic
.\.venv\Scripts\python.exe -m data_gen.load --database-url $env:TRACEFOOD_OWNER_URL --input data/synthetic
.\.venv\Scripts\python.exe -m ml.evaluate --database-url $env:TRACEFOOD_OWNER_URL
```

Set `TRACEFOOD_OWNER_URL` to the administrator connection for `tracefood_synthetic`. For Docker, create the database and run psql inside the service, as in the demo setup. Use the local PG host and port for the Python loader. To use the synthetic data in the UI, set `DB_APP_URL` and `DB_NL_URL` to the same two role credentials with `tracefood_synthetic` as the database, then restart the API.

The trained artifact in [ml/models](ml/models) uses only synthetic examples. [Measured results](docs/results.json) include detector performance and a rolling forecast comparison. The benchmark also records the [measured PostgreSQL plans](docs/downstream_explain.json). Forecasting uses at least 52 consecutive completed calendar weeks within the recorded dataset's date range. Forecasts and anomaly scores are demonstrations on synthetic data.

## Natural-language query modes

The 11 catalogue questions use fixed SQL templates and need no model service. To enable fallback questions, run Ollama with an installed model locally and set `LLM_PROVIDER=ollama`, `LLM_MODEL` to its name, and `OLLAMA_BASE_URL` to its loopback URL. On startup the API reads the 12 permitted view schemas using the reader role. Each generated query must pass SQL validation and executes through that role with a three-second statement timeout and at most 200 returned rows.

## Dashboard image

The built-in ImageGen tool created the farm banner in [harvest-landscape.webp](frontend/public/harvest-landscape.webp).

> Aerial drone photograph of tidy curved rows of healthy green crops on a Karnataka farm at early sunrise. Rich cool forest greens, soft golden light washing the upper right, distinct farm-row texture, editorial agricultural photography. Field rows and details concentrated on the right two thirds, with simple dark green shadows on the far left for the separate text overlay. Wide landscape framing with no text, logos, or watermark.

## Data model and rules

The `tracefood` schema contains farms and their contacts, processing facilities, retailers and their contacts, batches, batch derivations, processing events, quality checks, shipments and shipment items, price records, and anomaly alerts. A derivation links an input batch to an output batch and records the quantity consumed in the input unit. A shipment may contain multiple batches; each item records its own quantity. IDs use prefixes such as `F`, `PF`, `R`, `B`, `QC`, `S`, `P`, and `A`.

Original batches belong to a farm; processed batches have input lineage. Initial batch quantity is retained: available stock is calculated from recorded consumption and shipments. Quantities must be positive and use `kg`, `L`, or `unit`; monetary amounts cannot be negative. Expiry cannot precede production. Product names are normalized to title case. The database validates origin, event dates, lineage and shipment relationships, including prevention of invalid cycles. Processing can explicitly allow over-allocation for investigation, which may be surfaced by the rule checks. Same-day concurrent lineage changes require the transaction behavior described above.

Quality results are `PASS`, `FAIL`, or `INCONCLUSIVE`; a failure names a contaminant and a pass cannot. Alerts can be reviewed or dismissed and include rule, statistical, or ML detection methods. The contamination investigation combines recorded failures, possible upstream sources, downstream batches, shipments, and the recorded time window. Simulation is read-only. Reports are limited by the completeness and dates of recorded observations.

The database exposes stock, batch, lineage, facility, quality, shipment, price, alert, and ledger views. Recursive functions traverse lineage and determine possible impacts; other routines calculate the contamination window and run rule checks. Indexes support commonly used lookup and traversal paths. The app and restricted natural-language reader have different grants; do not replace the reader credentials with an administrator account.

## API reference

Interactive request schemas, response details, and examples are available at `/docs` once the API is running; the OpenAPI document is at `/openapi.json`. Endpoints below are relative to `http://127.0.0.1:8000`. Requests sent through Vite use the `/api` prefix. JSON request bodies reject unknown fields. IDs and values are validated by the API and database; list endpoints that expose pagination limit pages to at most 200 records.

| Area | Method and path | Purpose |
| --- | --- | --- |
| Service | `GET /health` | Check both database pools. |
| Farms | `POST /farms`, `GET /farms`, `GET /farms/{farm_id}` | Create, list, or inspect farms. |
| Facilities | `POST /facilities`, `GET /facilities` | Create or list processing facilities. |
| Batches | `POST /batches`, `GET /batches`, `GET /batches/{batch_id}`, `PATCH /batches/{batch_id}/status` | Register farm batches, find them, and update status. |
| Lineage | `GET /batches/{batch_id}/lineage`, `GET /batches/{batch_id}/provenance`, `GET /reports/batch/{batch_id}` | Inspect relationships, provenance, and batch reporting. |
| Processing | `POST /processing`, `POST /batches/{batch_id}/handling` | Record a processed output or a handling event. |
| Quality | `POST /quality-checks`, `GET /batches/{batch_id}/quality-checks`, `GET /investigations/{check_id}`, `POST /simulate/contamination` | Record observations, investigate a failure, or simulate impact. |
| Distribution | `POST /retailers`, `GET /retailers`, `POST /shipments`, `GET /shipments/{shipment_id}` | Manage retailers and shipments. |
| Prices | `POST /prices`, `GET /prices/history`, `GET /prices/stage-comparison`, `GET /prices/forecast` | Record and compare prices, inspect history, and forecast. |
| Alerts | `POST /anomalies/run`, `GET /anomalies`, `GET /anomalies/{alert_id}`, `PATCH /anomalies/{alert_id}` | Run detectors, inspect evidence, and review alerts. |
| Questions and dashboard | `POST /query/nl`, `GET /dashboard/summary` | Ask a supported question or retrieve dashboard totals. |

For example, after starting all services, `Invoke-RestMethod http://127.0.0.1:8000/health` should return a status of `ok`; `Invoke-RestMethod http://127.0.0.1:8000/batches/B101/lineage` queries the demo lineage. See `/docs` for required fields and filters before submitting writes.

## Operations and troubleshooting

- Run commands from the inner project directory containing `compose.yaml`, unless a command explicitly changes to `frontend`. Keep the API and Vite terminals running while using the site. Stop each with Ctrl+C; `docker compose stop db` stops the database while retaining its volume.
- `docker compose up -d --wait db` needs a running Docker engine. Alternatively use an existing PostgreSQL server and the native setup above. Install scripts target a new, empty database; do not rerun them over existing data. The Compose volume persists across restarts, including initialized passwords and changes.
- If ports are occupied, select a free PostgreSQL host port in `.env` and update both URLs. For Vite, use `npm.cmd run dev -- --port 5174`; the API port can be changed in the Uvicorn command and `TRACEFOOD_API_TARGET` must match it.
- Connection or health errors: check that PostgreSQL is running, the database and schema were installed, both role passwords match the URLs, and the host and port are correct. The reader role must be `tracefood_nl_reader` with the installed restricted grants.
- If the interface loads but API requests fail, check the API terminal, `/health`, and Vite's proxy target. A running frontend alone cannot supply database results.
- If forecast history is insufficient, use the separate synthetic dataset as described above; the small demo intentionally lacks the required history. If an uncatalogued natural-language question fails, check the optional Ollama configuration and local model; fixed catalogue questions do not require Ollama.
- Dependency installation requires access to the Python and npm package registries. Use the versions in the manifests and `npm.cmd ci` for the locked frontend dependencies. On Windows, Python packages with native extensions need compatible wheels for the chosen Python version.
- Database tests can change data temporarily; use the fresh demo fixture as instructed. The optional concurrency test requires a disposable database. For generated data, choose a new output directory: the generator does not overwrite an existing dataset.

For reproducibility and detailed dataset counts, detector labels, and index timings, see [data/README.md](data/README.md), [docs/results.json](docs/results.json), and [docs/downstream_explain.json](docs/downstream_explain.json). The notebooks are exploratory; the application entry point is the FastAPI module, not a notebook.
## Regional commodity prices

Open the dashboard or `/prices` for dated Indian commodity market reports. Select a commodity and a state or union territory to compare reporting markets. The price column distinguishes a modal price (the most commonly reported trading price), an average, a quoted rate and a reported range. The unit selector converts all price columns between rupees per kg and per quintal using 100 kg per quintal. Grade, variety, market and reporting date matter when comparing two observations.

The browser checks the public [KrashiMitra daily CSV archive](https://github.com/kunal-rajput-317/mandi-data) for today's Indian reporting date and then earlier dates, up to seven days back. Mandi price data via KrashiMitra, sourced from [AGMARKNET / data.gov.in](https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi). Archive data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The browser retains the last successfully loaded file when local storage is available. Reloading the page or selecting Refresh market reports checks again. No API key is required.

The project also includes dated November 2026 reports from the Spices Board, the Meghalaya State Agricultural Marketing Board and MandiPulse. Each displayed row links to its source. When the archive cannot be reached, the page identifies the saved-data fallback. Coverage varies by trading day and market. Missing prices appear as a dash. An empty selection means the loaded sources have no matching quote. Batch history, stage comparisons, anomalies and forecasting use the separate project transaction dataset, which includes simulated prices.
The regional markets page also bundles the 1 November 2026 AGMARKNET export with 8,885 quotes for 163 commodities across 22 states and union territories. Each row links to its archived source and retains its reporting date.
