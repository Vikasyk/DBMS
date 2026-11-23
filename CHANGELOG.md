# Changelog

## React website

- Replaced the Streamlit UI with a responsive React operations dashboard and dedicated workflows.
- Added keyboard record lookup, live price charts, and a zoomable batch lineage graph.
- Updated the local setup to start Vite alongside FastAPI.

## Full lab implementation

- Added deterministic synthetic data, transactional loading, and a measured downstream index comparison.
- Added historical yield alerts, trained and evaluated the price Isolation Forest, and compared four forecasting methods.
- Completed the Streamlit recording and analytics screens and added the optional local Ollama fallback with PostgreSQL reader enforcement.
- Serialized same-day lineage checks to protect against concurrent direct SQL inserts that would complete a cycle. The data model and SQL API signatures are unchanged.
- Rejected NaN in quantity, price and anomaly scores. Widened score precision to keep legitimate extreme discrepancies recordable.
- Added the lab report, editable design diagrams, and complete local demonstration.

## Initial implementation

- Added the PostgreSQL schema, triggers, views, routines, roles, and demo fixture from Appendix A of the v2 specification.
- Made installation preserve existing schemas. Local role passwords are set during setup and application routines require explicit execution privileges.
- Preserved the two-digit minimum for farm, facility, and retailer IDs while allowing longer IDs. Extended deferred origin checks to cover removal or reassignment of input edges.
