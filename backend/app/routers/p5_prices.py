from datetime import date
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..db import app_pool
from ..models import PageOffset, PageSize, PriceCreate, PriceStage, Unit
from ..services.prices import weekly_retail_history
from ml.forecast import evaluate_forecast


router = APIRouter(tags=["Prices"])


@router.post("/prices", status_code=201)
def create_price(body: PriceCreate, request: Request):
    with app_pool(request).connection() as conn:
        price = conn.execute(
            """INSERT INTO tracefood.price_record
                   (batch_id, price_date, supply_chain_stage, selling_price, cost_per_unit, market_location)
               VALUES (%(batch_id)s, %(price_date)s, %(supply_chain_stage)s, %(selling_price)s,
                       %(cost_per_unit)s, %(market_location)s)
               RETURNING price_id""",
            body.model_dump(),
        ).fetchone()
        return conn.execute(
            "SELECT * FROM tracefood.v_price_history WHERE price_id = %s", (price["price_id"],),
        ).fetchone()


@router.get("/prices/history")
def price_history(
    request: Request,
    batch_id: Optional[str] = None,
    product: Optional[str] = None,
    stage: Optional[PriceStage] = None,
    market: Optional[str] = None,
    unit: Optional[Unit] = None,
    sort: Literal["recent", "movement"] = "recent",
    from_date: Annotated[Optional[date], Query(alias="from")] = None,
    to_date: Annotated[Optional[date], Query(alias="to")] = None,
    limit: PageSize = 100,
    offset: PageOffset = 0,
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "The from date must be on or before the to date")
    with app_pool(request).connection() as conn:
        return conn.execute(
            """SELECT * FROM tracefood.v_price_history
               WHERE (%(batch_id)s::text IS NULL OR batch_id = %(batch_id)s)
                 AND (%(product)s::text IS NULL OR lower(product_name) = lower(%(product)s))
                 AND (%(stage)s::text IS NULL OR supply_chain_stage = %(stage)s)
                 AND (%(market)s::text IS NULL OR lower(market_location) = lower(%(market)s))
                 AND (%(unit)s::text IS NULL OR unit = %(unit)s)
                 AND (%(from_date)s::date IS NULL OR price_date >= %(from_date)s)
                 AND (%(to_date)s::date IS NULL OR price_date <= %(to_date)s)
                 AND (%(sort)s = 'recent' OR price_change_percentage IS NOT NULL)
               ORDER BY CASE WHEN %(sort)s = 'movement' THEN abs(price_change_percentage) END DESC NULLS LAST,
                        price_date DESC, price_id LIMIT %(limit)s OFFSET %(offset)s""",
            {"batch_id": batch_id, "product": product, "stage": stage, "market": market,
             "unit": unit, "sort": sort, "from_date": from_date, "to_date": to_date,
             "limit": limit, "offset": offset},
        ).fetchall()


@router.get("/prices/forecast")
def forecast(
    request: Request,
    product: Annotated[str, Query(min_length=1, max_length=60)],
    market: Annotated[str, Query(min_length=1, max_length=60)],
    unit: Unit = "kg",
):
    with app_pool(request).connection() as conn:
        rows = weekly_retail_history(conn, product, market, unit)
    return {"product": product, "market": market, "unit": unit, **evaluate_forecast(rows)}


@router.get("/prices/stage-comparison")
def stage_comparison(
    request: Request,
    product: Optional[str] = None,
    unit: Optional[Unit] = None,
    limit: PageSize = 100,
    offset: PageOffset = 0,
):
    with app_pool(request).connection() as conn:
        return conn.execute(
            """SELECT * FROM tracefood.v_stage_price_monthly
               WHERE (%(product)s::text IS NULL OR lower(product_name) = lower(%(product)s))
                 AND (%(unit)s::text IS NULL OR unit = %(unit)s)
               ORDER BY month DESC, product_name, unit LIMIT %(limit)s OFFSET %(offset)s""",
            {"product": product, "unit": unit, "limit": limit, "offset": offset},
        ).fetchall()
