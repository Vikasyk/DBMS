from fastapi import APIRouter, HTTPException, Request

from ..db import app_pool, require_record
from ..models import QualityCheckCreate, SimulationRequest
from ..services.contamination import impact_report, quality_history
from ..services.lineage import require_batch


router = APIRouter(tags=["Quality and investigations"])


@router.post("/quality-checks", status_code=201)
def create_quality_check(body: QualityCheckCreate, request: Request):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """INSERT INTO tracefood.quality_check
                   (batch_id, check_date, check_stage, result, contamination_type, remarks)
               VALUES (%(batch_id)s, %(check_date)s, %(check_stage)s, %(result)s,
                       %(contamination_type)s, %(remarks)s)
               RETURNING *""",
            body.model_dump(),
        ).fetchone()


@router.get("/batches/{batch_id}/quality-checks")
def batch_quality_checks(batch_id: str, request: Request):
    with app_pool(request).connection() as conn:
        require_batch(conn, batch_id)
        return quality_history(conn, batch_id)


@router.get("/investigations/{check_id}")
def investigate(check_id: str, request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        check = conn.execute(
            "SELECT * FROM tracefood.v_quality_checks WHERE check_id = %s", (check_id,),
        ).fetchone()
        require_record(check, "Quality check", check_id)
        if check["result"] != "FAIL":
            raise HTTPException(422, "An investigation requires a failed quality check")
        return impact_report(conn, check["batch_id"], triggering_check=check)


@router.post("/simulate/contamination")
def simulate(body: SimulationRequest, request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return impact_report(conn, body.batch_id)
