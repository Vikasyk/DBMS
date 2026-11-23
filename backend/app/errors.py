import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from psycopg import Error
from psycopg_pool import PoolTimeout


logger = logging.getLogger(__name__)


def database_error(_request: Request, error: Error) -> JSONResponse:
    primary = error.diag.message_primary
    detail = error.diag.message_detail
    if error.sqlstate == "23505":
        status, message = 409, "A record with the same identifier or association already exists"
    elif error.sqlstate == "23503":
        status, message = 422, detail or primary or "Unknown referenced ID"
    elif error.sqlstate == "23514":
        status, message = 422, primary or "A value failed database validation"
    elif error.sqlstate == "P0001":
        status, message = 422, primary or "The record violates a database rule"
    elif error.sqlstate in {"22001", "22003"}:
        status, message = 422, primary or "A value exceeds the allowed size"
    elif error.sqlstate == "25006":
        status, message = 403, "Writes are forbidden in this read-only transaction"
    elif error.sqlstate == "57014":
        status, message = 504, "Query took too long"
    elif error.sqlstate in {"40001", "40P01"}:
        status, message = 409, "The data changed during this operation. Retry the request."
    else:
        logger.error("Unexpected database error (SQLSTATE %s)", error.sqlstate, exc_info=error)
        status, message = 500, "The database operation failed"
    return JSONResponse({"detail": message}, status_code=status)


def pool_timeout(_request: Request, _error: PoolTimeout) -> JSONResponse:
    return JSONResponse({"detail": "Database connection unavailable"}, status_code=503)
