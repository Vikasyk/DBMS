from fastapi import APIRouter, Request
from psycopg.types.json import Jsonb

from ..db import app_pool
from ..models import HandlingCreate, ProcessingCreate


router = APIRouter(tags=["Processing"])


@router.post("/processing", status_code=201)
def register_processing(body: ProcessingCreate, request: Request):
    inputs = [item.model_dump() for item in body.inputs]
    with app_pool(request).connection() as conn:
        row = conn.execute(
            """CALL tracefood.sp_register_processing(%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)""",
            (body.product_name, body.quantity, body.unit, body.production_date, body.expiry_date,
             body.facility_id, body.operation_type,
             Jsonb([item.model_dump(mode="json") for item in body.inputs]), body.allow_over_allocation),
        ).fetchone()
        return {"batch_id": row["p_output_batch_id"], "inputs": inputs, "message": "Processing recorded"}


@router.post("/batches/{batch_id}/handling", status_code=201)
def register_handling(batch_id: str, body: HandlingCreate, request: Request):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """INSERT INTO tracefood.batch_processing (facility_id, batch_id, processing_date, operation_type)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (body.facility_id, batch_id, body.processing_date, body.operation_type),
        ).fetchone()
