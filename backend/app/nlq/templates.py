QUERIES = {
    "origin": """SELECT f.*, COALESCE(u.depth, 0) AS depth
                   FROM tracefood.fn_origin_farms(%(batch_id)s) f
                   LEFT JOIN tracefood.fn_upstream(%(batch_id)s) u ON u.batch_id = f.original_batch_id
                   ORDER BY depth, f.original_batch_id LIMIT 200""",
    "downstream": """SELECT b.batch_id, b.product_name, b.unit, b.status, d.depth
                       FROM tracefood.fn_downstream(%(batch_id)s) d
                       JOIN tracefood.v_batch_overview b USING (batch_id)
                       ORDER BY d.depth, b.batch_id LIMIT 200""",
    "upstream": """WITH ancestors AS (
                       SELECT * FROM tracefood.fn_upstream(%(batch_id)s)
                   )
                   SELECT e.input_batch_id, e.input_product, e.quantity_used, e.input_unit,
                          e.output_batch_id, e.output_product, a.depth
                   FROM tracefood.v_lineage_edges e JOIN ancestors a ON a.batch_id = e.input_batch_id
                   WHERE e.output_batch_id = %(batch_id)s
                      OR e.output_batch_id IN (SELECT batch_id FROM ancestors)
                   ORDER BY a.depth, e.input_batch_id, e.output_batch_id LIMIT 200""",
    "retailers_of_derived": """SELECT DISTINCT retailer_id, retailer_name, retailer_city
                                 FROM tracefood.fn_impact_shipments(%(batch_id)s)
                                 ORDER BY retailer_id LIMIT 200""",
    "failed_checks": """SELECT * FROM tracefood.v_quality_checks WHERE result = 'FAIL'
                        ORDER BY check_date DESC, check_id DESC LIMIT 200""",
    "quantity_anomalies": """SELECT * FROM tracefood.v_alerts
                             WHERE alert_type IN ('MASS_BALANCE', 'OVER_ALLOCATION', 'YIELD_OUTLIER')
                             ORDER BY alert_date DESC, alert_id LIMIT 200""",
    "product_trend": """SELECT * FROM tracefood.v_stage_price_monthly
                        WHERE product_name = %(product)s AND (
                          %(months)s::int IS NULL OR
                          month >= date_trunc('month', CURRENT_DATE - make_interval(months => %(months)s))::date
                        )
                        ORDER BY month DESC, unit LIMIT 200""",
    "batch_prices": """SELECT * FROM tracefood.v_price_history WHERE batch_id = %(batch_id)s
                       ORDER BY price_date DESC, price_id LIMIT 200""",
    "shipments_of_batch": """SELECT * FROM tracefood.v_shipment_lines WHERE batch_id = %(batch_id)s
                              ORDER BY shipment_date, shipment_id LIMIT 200""",
    "expiring": """SELECT batch_id, product_name, expiry_date, shelf_life_remaining_days
                   FROM tracefood.v_batch_overview WHERE shelf_life_remaining_days BETWEEN 0 AND %(days)s
                   ORDER BY expiry_date, batch_id LIMIT 200""",
}
