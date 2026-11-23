from fastapi import APIRouter, Request

from ..db import app_pool, require_record
from ..models import PageOffset, PageSize, RetailerCreate, ShipmentCreate
from ..services.lineage import origin_farms, require_batch


router = APIRouter(tags=["Distribution"])


@router.post("/retailers", status_code=201)
def create_retailer(body: RetailerCreate, request: Request):
    with app_pool(request).connection() as conn:
        retailer = conn.execute(
            """INSERT INTO tracefood.retailer (retailer_name, street, city, state, pin_code)
               VALUES (%(retailer_name)s, %(street)s, %(city)s, %(state)s, %(pin_code)s)
               RETURNING retailer_id""",
            body.model_dump(),
        ).fetchone()
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO tracefood.retailer_contact (retailer_id, contact_no) VALUES (%s, %s)",
                [(retailer["retailer_id"], number) for number in body.contact_numbers],
            )
        return conn.execute(
            "SELECT * FROM tracefood.v_retailers WHERE retailer_id = %s", (retailer["retailer_id"],),
        ).fetchone()


@router.get("/retailers")
def list_retailers(request: Request, limit: PageSize = 100, offset: PageOffset = 0):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """SELECT * FROM tracefood.v_retailers
               ORDER BY retailer_name, retailer_id LIMIT %s OFFSET %s""",
            (limit, offset),
        ).fetchall()


def shipment_details(conn, shipment_id):
    totals = conn.execute(
        "SELECT * FROM tracefood.v_shipment_summary WHERE shipment_id = %s ORDER BY unit", (shipment_id,),
    ).fetchall()
    require_record(totals[0] if totals else None, "Shipment", shipment_id)
    items = conn.execute(
        "SELECT * FROM tracefood.v_shipment_lines WHERE shipment_id = %s ORDER BY batch_id", (shipment_id,),
    ).fetchall()
    return {"shipment_id": shipment_id, "totals": totals, "items": items}


@router.post("/shipments", status_code=201)
def create_shipment(body: ShipmentCreate, request: Request):
    with app_pool(request).connection() as conn:
        # Processing acquires the same locks in this order before measuring input stock.
        conn.execute(
            "SELECT batch_id FROM tracefood.batch WHERE batch_id = ANY(%s) ORDER BY batch_id FOR UPDATE",
            ([item.batch_id for item in body.items],),
        ).fetchall()
        shipment = conn.execute(
            """INSERT INTO tracefood.shipment (shipment_date, source_location, retailer_id, transportation_cost)
               VALUES (%(shipment_date)s, %(source_location)s, %(retailer_id)s, %(transportation_cost)s)
               RETURNING shipment_id""",
            body.model_dump(),
        ).fetchone()
        shipment_id = shipment["shipment_id"]
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO tracefood.shipment_item (shipment_id, batch_id, quantity_shipped)
                   VALUES (%s, %s, %s)""",
                [(shipment_id, item.batch_id, item.quantity_shipped) for item in body.items],
            )
        return shipment_details(conn, shipment_id)


@router.get("/shipments/{shipment_id}")
def read_shipment(shipment_id: str, request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return shipment_details(conn, shipment_id)


@router.get("/batches/{batch_id}/provenance")
def batch_provenance(batch_id: str, request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        require_batch(conn, batch_id)
        return {
            "batch_id": batch_id,
            "origin_farms": origin_farms(conn, batch_id),
            "upstream": conn.execute("SELECT * FROM tracefood.fn_upstream(%s)", (batch_id,)).fetchall(),
        }
