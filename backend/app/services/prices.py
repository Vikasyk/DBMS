def weekly_retail_history(conn, product, market, unit):
    # Use only calendar weeks contained in the recorded data period.
    return conn.execute(
        """WITH bounds AS (
               SELECT date_trunc('week', min(price_date) + 6) AS first_week,
                      LEAST(date_trunc('week', CURRENT_DATE),
                            date_trunc('week', max(price_date) + 1)) AS end_week
               FROM tracefood.price_record
           )
           SELECT date_trunc('week', price_date)::date AS week, avg(selling_price) AS price
           FROM tracefood.v_price_history CROSS JOIN bounds
           WHERE lower(product_name) = lower(%s) AND lower(market_location) = lower(%s)
             AND unit = %s AND supply_chain_stage = 'RETAIL'
             AND price_date >= first_week AND price_date < end_week
           GROUP BY 1 ORDER BY 1""",
        (product, market, unit),
    ).fetchall()
