from typing import Optional

from fastapi import APIRouter, Request

from ..db import app_pool, require_record
from ..models import AlertStatus, AlertStatusUpdate, PageOffset, PageSize, RuleRun
from ..services.anomalies import run_detection


router = APIRouter(tags=["Anomalies"])


@router.post("/anomalies/run")
def run_anomalies(request: Request, body: Optional[RuleRun] = None):
    settings = body or RuleRun()
    with app_pool(request).connection() as conn:
        counts, notes = run_detection(conn, settings.tolerance)
        methods = [method for method, count in counts.items() if count]
        method = "MULTIPLE" if len(methods) > 1 else next(iter(methods), "RULE")
        return {
            "new_alerts": sum(counts.values()),
            "detection_method": method,
            "counts": counts,
            "notes": notes,
            "tolerance": settings.tolerance,
        }


@router.get("/anomalies")
def list_alerts(
    request: Request,
    status: Optional[AlertStatus] = None,
    batch_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: PageSize = 100,
    offset: PageOffset = 0,
):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """SELECT * FROM tracefood.v_alerts
               WHERE (%(status)s::text IS NULL OR alert_status = %(status)s)
                 AND (%(batch_id)s::text IS NULL OR batch_id = %(batch_id)s)
                 AND (%(alert_type)s::text IS NULL OR alert_type = %(alert_type)s)
               ORDER BY alert_date DESC, alert_id LIMIT %(limit)s OFFSET %(offset)s""",
            {"status": status, "batch_id": batch_id, "alert_type": alert_type, "limit": limit, "offset": offset},
        ).fetchall()


@router.get("/anomalies/{alert_id}")
def alert_details(alert_id: str, request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        alert = conn.execute("SELECT * FROM tracefood.v_alerts WHERE alert_id = %s", (alert_id,)).fetchone()
        require_record(alert, "Alert", alert_id)
        evidence = {}
        if alert["alert_type"] in {"MASS_BALANCE", "YIELD_OUTLIER"}:
            evidence["mass_balance"] = conn.execute(
                "SELECT * FROM tracefood.v_mass_balance WHERE batch_id = %s", (alert["batch_id"],),
            ).fetchone()
        if alert["alert_type"] == "OVER_ALLOCATION":
            evidence["ledger"] = conn.execute(
                """SELECT * FROM tracefood.v_batch_ledger WHERE batch_id = %s
                   ORDER BY event_date, event_type, reference_id""",
                (alert["batch_id"],),
            ).fetchall()
        if alert["related_shipment_id"] is not None:
            evidence["shipment_line"] = conn.execute(
                "SELECT * FROM tracefood.v_shipment_lines WHERE shipment_id = %s AND batch_id = %s",
                (alert["related_shipment_id"], alert["batch_id"]),
            ).fetchone()
        if alert["related_price_id"] is not None:
            evidence["price"] = conn.execute(
                "SELECT * FROM tracefood.v_price_history WHERE price_id = %s", (alert["related_price_id"],),
            ).fetchone()
        return {**alert, "evidence": evidence}


@router.patch("/anomalies/{alert_id}")
def update_alert(alert_id: str, body: AlertStatusUpdate, request: Request):
    with app_pool(request).connection() as conn:
        row = conn.execute(
            """UPDATE tracefood.anomaly_alert SET alert_status = %s WHERE alert_id = %s
               RETURNING alert_id, alert_status""",
            (body.alert_status, alert_id),
        ).fetchone()
        return require_record(row, "Alert", alert_id)
