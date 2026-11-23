from typing import Literal, Optional

from fastapi import APIRouter, Request

from ..db import app_pool, require_record
from ..models import BatchCreate, BatchStatus, BatchStatusUpdate, FacilityCreate, FarmCreate, PageOffset, PageSize
from ..services.lineage import get_batch, get_lineage


router = APIRouter(tags=["Master records and batches"])


@router.post("/farms", status_code=201)
def create_farm(body: FarmCreate, request: Request):
    with app_pool(request).connection() as conn:
        farm = conn.execute(
            """INSERT INTO tracefood.farm (farm_name, street, city, state, pin_code)
               VALUES (%(farm_name)s, %(street)s, %(city)s, %(state)s, %(pin_code)s)
               RETURNING farm_id""",
            body.model_dump(),
        ).fetchone()
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO tracefood.farm_contact (farm_id, contact_no) VALUES (%s, %s)",
                [(farm["farm_id"], number) for number in body.contact_numbers],
            )
        return conn.execute(
            "SELECT * FROM tracefood.v_farms WHERE farm_id = %s", (farm["farm_id"],),
        ).fetchone()


@router.get("/farms")
def list_farms(request: Request, limit: PageSize = 100, offset: PageOffset = 0):
    with app_pool(request).connection() as conn:
        return conn.execute(
            "SELECT * FROM tracefood.v_farms ORDER BY farm_name, farm_id LIMIT %s OFFSET %s", (limit, offset),
        ).fetchall()


@router.get("/farms/{farm_id}")
def farm_details(farm_id: str, request: Request):
    with app_pool(request).connection() as conn:
        row = conn.execute("SELECT * FROM tracefood.v_farms WHERE farm_id = %s", (farm_id,)).fetchone()
        return require_record(row, "Farm", farm_id)


@router.post("/facilities", status_code=201)
def create_facility(body: FacilityCreate, request: Request):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """INSERT INTO tracefood.processing_facility (facility_name, street, city, state, pin_code)
               VALUES (%(facility_name)s, %(street)s, %(city)s, %(state)s, %(pin_code)s)
               RETURNING *""",
            body.model_dump(),
        ).fetchone()


@router.get("/facilities")
def list_facilities(request: Request, limit: PageSize = 100, offset: PageOffset = 0):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """SELECT * FROM tracefood.v_facilities
               ORDER BY facility_name, facility_id LIMIT %s OFFSET %s""",
            (limit, offset),
        ).fetchall()


@router.post("/batches", status_code=201)
def create_batch(body: BatchCreate, request: Request):
    with app_pool(request).connection() as conn:
        batch = conn.execute(
            """INSERT INTO tracefood.batch (product_name, quantity, unit, production_date, expiry_date, farm_id)
               VALUES (%(product_name)s, %(quantity)s, %(unit)s, %(production_date)s, %(expiry_date)s, %(farm_id)s)
               RETURNING batch_id""",
            body.model_dump(),
        ).fetchone()
        return get_batch(conn, batch["batch_id"])


@router.get("/batches")
def list_batches(
    request: Request,
    product: Optional[str] = None,
    status: Optional[BatchStatus] = None,
    farm_id: Optional[str] = None,
    limit: PageSize = 100,
    offset: PageOffset = 0,
):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """SELECT * FROM tracefood.v_batch_overview
               WHERE (%(product)s::text IS NULL OR strpos(lower(product_name), lower(%(product)s)) > 0)
                 AND (%(status)s::text IS NULL OR status = %(status)s)
                 AND (%(farm_id)s::text IS NULL OR farm_id = %(farm_id)s)
               ORDER BY production_date DESC, batch_id LIMIT %(limit)s OFFSET %(offset)s""",
            {"product": product, "status": status, "farm_id": farm_id, "limit": limit, "offset": offset},
        ).fetchall()


@router.get("/batches/{batch_id}")
def batch_details(batch_id: str, request: Request):
    with app_pool(request).connection() as conn:
        return get_batch(conn, batch_id)


@router.patch("/batches/{batch_id}/status")
def update_status(batch_id: str, body: BatchStatusUpdate, request: Request):
    with app_pool(request).connection() as conn:
        row = conn.execute(
            "UPDATE tracefood.batch SET status = %s WHERE batch_id = %s RETURNING batch_id, status",
            (body.status, batch_id),
        ).fetchone()
        return require_record(row, "Batch", batch_id)


@router.get("/batches/{batch_id}/lineage")
def batch_lineage(batch_id: str, request: Request, direction: Literal["up", "down", "both"] = "both"):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return get_lineage(conn, batch_id, direction)
