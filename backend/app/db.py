from contextlib import asynccontextmanager, ExitStack

from fastapi import FastAPI, HTTPException, Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import load_settings
from .nlq.llm_client import configured_provider, view_schema


def configure_reader(conn):
    conn.read_only = True
    with conn.transaction():
        role = conn.execute(
            """SELECT session_user = 'tracefood_nl_reader'
                      AND current_user = 'tracefood_nl_reader'
                      AND NOT pg_catalog.pg_has_role(current_user, 'tracefood_app', 'MEMBER')
                      AND NOT pg_catalog.has_schema_privilege('tracefood', 'CREATE')
                      AND NOT pg_catalog.has_table_privilege('tracefood.batch', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')
                      AND current_setting('transaction_read_only') = 'on'
                      AS authorized_reader""",
        ).fetchone()
        if not role["authorized_reader"]:
            raise RuntimeError("DB_NL_URL must use the restricted tracefood_nl_reader role.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    provider = configured_provider()
    with ExitStack() as stack:
        app.state.db_app = stack.enter_context(ConnectionPool(
            settings.db_app_url, min_size=1, max_size=8, timeout=5, open=False,
            kwargs={"row_factory": dict_row},
        ))
        app.state.db_nl = stack.enter_context(ConnectionPool(
            settings.db_nl_url, min_size=1, max_size=4, timeout=5, open=False,
            kwargs={"row_factory": dict_row}, configure=configure_reader,
        ))
        schema = None
        if provider is not None:
            with app.state.db_nl.connection() as conn:
                schema = view_schema(conn)
        app.state.nl_provider = provider
        app.state.nl_schema = schema
        try:
            yield
        finally:
            app.state.nl_provider = None
            app.state.nl_schema = None


def app_pool(request: Request) -> ConnectionPool:
    return request.app.state.db_app


def nl_pool(request: Request) -> ConnectionPool:
    return request.app.state.db_nl


def require_record(row, resource: str, identifier: str):
    if row is None:
        raise HTTPException(404, f"{resource} {identifier} was not found")
    return row
