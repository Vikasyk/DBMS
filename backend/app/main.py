from fastapi import FastAPI, Request
from psycopg import Error
from psycopg_pool import PoolTimeout

from .db import app_pool, lifespan, nl_pool
from .errors import database_error, pool_timeout
from .routers import p1_master, p2_processing, p3_quality, p4_shipments, p5_prices, p6_anomalies, p7_query


app = FastAPI(title="TraceFood API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(Error, database_error)
app.add_exception_handler(PoolTimeout, pool_timeout)

for router in (p1_master, p2_processing, p3_quality, p4_shipments, p5_prices, p6_anomalies, p7_query):
    app.include_router(router.router)


@app.get("/health", tags=["Service"])
def health(request: Request):
    for pool in (app_pool(request), nl_pool(request)):
        with pool.connection() as conn:
            conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}
