from fastapi import APIRouter, HTTPException, Request
from psycopg import DataError, ProgrammingError

from ..db import app_pool, nl_pool
from ..models import NaturalLanguageQuestion
from ..nlq.llm_client import ProviderUnavailable
from ..nlq.router import EXAMPLES, route
from ..nlq.templates import QUERIES
from ..nlq.validator import RESULT_LIMIT, RejectedQuery, validate
from ..services.contamination import impact_report, quality_history
from ..services.lineage import get_batch, get_lineage, origin_farms


router = APIRouter(tags=["Reports and queries"])


@router.post("/query/nl")
def natural_language_query(body: NaturalLanguageQuestion, request: Request):
    intent, parameters = route(body.question)
    if intent == "unsupported":
        return generated_query(body.question, request)

    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '3s'")
        if intent == "simulate":
            simulation = impact_report(conn, parameters["batch_id"])
            return {"intent": intent, "answer": simulation["banner"], "rows": simulation["batches"],
                    "row_count": len(simulation["batches"]), "parameters": parameters,
                    "sql": "tracefood.fn_impact_batches and tracefood.fn_impact_shipments",
                    "simulation": simulation}
        query = QUERIES[intent]
        rows = conn.execute(query, parameters or None).fetchall()
        return query_result(intent, rows, query, parameters)


def generated_query(question: str, request: Request):
    provider = getattr(request.app.state, "nl_provider", None)
    if provider is not None:
        try:
            candidate = provider.generate(question, request.app.state.nl_schema)
            if candidate != "CANNOT_ANSWER":
                query = validate(candidate)
                with nl_pool(request).connection() as conn:
                    conn.execute("SET TRANSACTION READ ONLY")
                    conn.execute("SET LOCAL statement_timeout = '3s'")
                    conn.execute("SET LOCAL search_path = pg_catalog, pg_temp")
                    cursor = conn.execute(query)
                    columns = [column.name for column in cursor.description]
                    if len(columns) != len(set(columns)):
                        raise RejectedQuery("The generated result has duplicate column names.")
                    rows = cursor.fetchall()
                return query_result("generated_sql", rows, query, {})
        except ProviderUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except RejectedQuery as exc:
            return rejected_query(str(exc))
        except (DataError, ProgrammingError):
            return rejected_query("The generated query could not be evaluated using the curated views.")

    return {"intent": "unsupported", "answer": "I can answer the kinds of questions shown below.",
            "rows": [], "row_count": 0, "sql": None, "parameters": {}, "simulation": None,
            "examples": EXAMPLES}


def rejected_query(reason: str):
    return {"intent": "rejected", "answer": reason, "rows": [], "row_count": 0, "sql": None,
            "parameters": {}, "simulation": None, "examples": EXAMPLES}


def query_result(intent, rows, query, parameters):
    answer = f"Returned {len(rows)} matching records." if rows else "No matching records were found."
    if len(rows) == RESULT_LIMIT:
        answer = f"Showing up to {RESULT_LIMIT} matching records."
    return {"intent": intent, "answer": answer, "rows": rows, "row_count": len(rows),
            "sql": query, "parameters": parameters, "simulation": None}


@router.get("/dashboard/summary")
def dashboard_summary(request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        counts = conn.execute(
            """SELECT (SELECT count(*) FROM tracefood.batch) AS batches,
                      (SELECT count(*) FROM tracefood.v_alerts WHERE alert_status = 'OPEN') AS open_alerts,
                      (SELECT count(*) FROM tracefood.v_quality_checks
                       WHERE result = 'FAIL' AND check_date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE)
                          AS recent_failed_checks,
                      (SELECT count(*) FROM tracefood.shipment) AS shipments""",
        ).fetchone()
        alert_types = conn.execute(
            """SELECT alert_type, count(*) AS count FROM tracefood.v_alerts
               WHERE alert_status = 'OPEN' GROUP BY alert_type ORDER BY alert_type""",
        ).fetchall()
        checks = conn.execute(
            """SELECT * FROM tracefood.v_quality_checks WHERE result = 'FAIL'
               ORDER BY check_date DESC, check_id DESC LIMIT 5""",
        ).fetchall()
        shipments = conn.execute(
            """SELECT DISTINCT shipment_id, shipment_date, source_location, retailer_id,
                               retailer_name, destination_city
               FROM tracefood.v_shipment_summary ORDER BY shipment_date DESC, shipment_id DESC LIMIT 5""",
        ).fetchall()
        series = conn.execute(
            """SELECT b.product_name AS product,b.unit,p.market_location AS market
               FROM tracefood.price_record p JOIN tracefood.batch b USING(batch_id)
               WHERE p.supply_chain_stage='RETAIL' GROUP BY 1,2,3
               ORDER BY count(DISTINCT p.price_date) DESC, max(p.price_date) DESC,1,2,3 LIMIT 1"""
        ).fetchone()
        workbook = conn.execute("SELECT to_regnamespace('india_source') IS NOT NULL AS present").fetchone()
        return {"counts": counts, "open_alerts_by_type": alert_types, "retail_series": series,
                "dataset": "India supply-chain workbook · simulated records" if workbook["present"] else None,
                "recent_failed_checks": checks, "recent_shipments": shipments}


@router.get("/reports/batch/{batch_id}")
def batch_report(batch_id: str, request: Request):
    with app_pool(request).connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        batch = get_batch(conn, batch_id)
        facilities = conn.execute(
            """SELECT * FROM tracefood.v_batch_facilities WHERE batch_id = %s
               ORDER BY processing_date, facility_id""",
            (batch_id,),
        ).fetchall()
        shipments = conn.execute(
            """SELECT * FROM tracefood.v_shipment_lines WHERE batch_id = %s
               ORDER BY shipment_date, shipment_id""",
            (batch_id,),
        ).fetchall()
        return {"batch": batch, "lineage": get_lineage(conn, batch_id, check_batch=False),
                "origin_farms": origin_farms(conn, batch_id), "facilities": facilities,
                "quality_checks": quality_history(conn, batch_id), "shipments": shipments}
