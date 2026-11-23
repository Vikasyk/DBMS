# TraceFood

TraceFood is a DBMS lab project that tracks food batches from farms through processing and distribution. PostgreSQL stores lineage, enforces integrity, and calculates available stock. A React website uses FastAPI for data entry, interactive lineage, quality investigations, read-only simulations, price analytics, anomaly review, and natural-language queries.

The design follows [the v2 project specification](TraceFood_Project_Specification_v2.pdf). SQL scripts 01–06 provide the schema, integrity rules, views, routines, roles, and synthetic demo records from Appendix A.

## Run locally

Use Python 3.11+, PostgreSQL 16+, and Node.js 22.12+. Run these commands from the project folder. The examples use PowerShell.

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
