from datetime import datetime, timezone

from ..db import require_record
from .lineage import origin_farms


def quality_history(conn, batch_id):
    return conn.execute(
        """SELECT * FROM tracefood.v_quality_checks WHERE batch_id = %s
           ORDER BY check_date DESC, check_id DESC""",
        (batch_id,),
    ).fetchall()


def impact_report(conn, batch_id, *, triggering_check=None):
    batches = conn.execute("SELECT * FROM tracefood.fn_impact_batches(%s)", (batch_id,)).fetchall()
    require_record(batches[0] if batches else None, "Batch", batch_id)
    shipments = conn.execute("SELECT * FROM tracefood.fn_impact_shipments(%s)", (batch_id,)).fetchall()
    retailers = sorted({row["retailer_id"] for row in shipments})
    report = {
        "generated_at": datetime.now(timezone.utc),
        "batch_id": batch_id,
        "batches": batches,
        "shipments": shipments,
        "retailers": retailers,
        "retailer_count": len(retailers),
        "caveat": "Lineage indicates potential exposure. A failed quality check is evidence for the batch tested.",
    }
    if triggering_check is None:
        return {
            **report,
            "mode": "SIMULATION",
            "banner": "SIMULATION - hypothetical scenario; no records were created or changed",
        }
    window = conn.execute(
        "SELECT * FROM tracefood.fn_contamination_window(%s)", (triggering_check["check_id"],),
    ).fetchone()
    return {
        **report,
        "mode": "REAL INVESTIGATION",
        "banner": "REAL INVESTIGATION - based on a recorded failed quality check",
        "triggering_check": triggering_check,
        "quality_checks": quality_history(conn, batch_id),
        "contamination_window": window,
        "origin_farms": origin_farms(conn, batch_id),
    }
