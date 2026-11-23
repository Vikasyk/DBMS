-- =====================================================================
-- TraceFood  |  03_views.sql
-- Derived attributes and read models. Views marked [NL] are the ONLY
-- objects the natural-language query role may read.
-- =====================================================================
SET search_path = tracefood;

-- Available quantity is derived, never stored.
CREATE VIEW v_batch_stock AS
SELECT b.batch_id, b.product_name, b.unit,
       b.quantity                                          AS initial_quantity,
       COALESCE(u.used, 0)                                 AS quantity_used_as_input,
       COALESCE(s.shipped, 0)                              AS quantity_shipped,
       b.quantity - COALESCE(u.used, 0) - COALESCE(s.shipped, 0) AS available_quantity
FROM batch b
LEFT JOIN (SELECT input_batch_id, SUM(quantity_used) AS used
           FROM batch_derivation GROUP BY input_batch_id) u ON u.input_batch_id = b.batch_id
LEFT JOIN (SELECT batch_id, SUM(quantity_shipped) AS shipped
           FROM shipment_item GROUP BY batch_id) s ON s.batch_id = b.batch_id;

-- [NL] Batch overview incl. derived Batch_Type and Shelf_Life_Remaining.
CREATE VIEW v_batch_overview AS
SELECT b.batch_id, b.product_name, b.quantity, b.unit,
       b.production_date, b.expiry_date, b.status,
       CASE WHEN b.farm_id IS NOT NULL THEN 'ORIGINAL' ELSE 'PROCESSED' END AS batch_type,
       b.farm_id, f.farm_name,
       (b.expiry_date - CURRENT_DATE)                      AS shelf_life_remaining_days,
       s.quantity_used_as_input, s.quantity_shipped, s.available_quantity
FROM batch b
LEFT JOIN farm f        ON f.farm_id = b.farm_id
JOIN      v_batch_stock s ON s.batch_id = b.batch_id;

-- [NL] One row per lineage edge (input -> output).
CREATE VIEW v_lineage_edges AS
SELECT d.input_batch_id,  bi.product_name AS input_product,  d.quantity_used, bi.unit AS input_unit,
       d.output_batch_id, bo.product_name AS output_product, bo.quantity AS output_quantity,
       bo.unit AS output_unit, bo.production_date AS output_production_date
FROM batch_derivation d
JOIN batch bi ON bi.batch_id = d.input_batch_id
JOIN batch bo ON bo.batch_id = d.output_batch_id;

-- [NL] Which facility handled which batch (Processes relationship).
CREATE VIEW v_batch_facilities AS
SELECT bp.batch_id, b.product_name, bp.facility_id, pf.facility_name, pf.city AS facility_city,
       bp.processing_date, bp.operation_type
FROM batch_processing bp
JOIN batch b                ON b.batch_id = bp.batch_id
JOIN processing_facility pf ON pf.facility_id = bp.facility_id;

-- Mass balance of processed batches (input used vs output recorded).
CREATE VIEW v_mass_balance AS
SELECT d.output_batch_id                          AS batch_id,
       bo.product_name, bo.unit,
       SUM(d.quantity_used)                       AS total_input_quantity,
       bo.quantity                                AS output_quantity,
       bo.quantity - SUM(d.quantity_used)         AS difference,
       ROUND(bo.quantity / SUM(d.quantity_used), 4) AS yield_ratio,
       bool_and(bi.unit = bo.unit)                AS units_consistent,
       COUNT(*)                                   AS input_count
FROM batch_derivation d
JOIN batch bo ON bo.batch_id = d.output_batch_id
JOIN batch bi ON bi.batch_id = d.input_batch_id
GROUP BY d.output_batch_id, bo.product_name, bo.unit, bo.quantity;

-- [NL] Quality checks with product name.
CREATE VIEW v_quality_checks AS
SELECT q.check_id, q.batch_id, b.product_name, q.check_date, q.check_stage,
       q.result, q.contamination_type, q.remarks
FROM quality_check q JOIN batch b ON b.batch_id = q.batch_id;

-- Latest quality result per batch (DISTINCT ON is PostgreSQL-specific).
CREATE VIEW v_latest_quality AS
SELECT DISTINCT ON (batch_id) batch_id, check_id, check_date, check_stage, result, contamination_type
FROM quality_check
ORDER BY batch_id, check_date DESC, check_id DESC;

-- [NL] Shipment lines with destination retailer.
CREATE VIEW v_shipment_lines AS
SELECT si.shipment_id, sh.shipment_date, sh.source_location,
       si.batch_id, b.product_name, si.quantity_shipped, b.unit,
       sh.retailer_id, r.retailer_name, r.city AS retailer_city
FROM shipment_item si
JOIN shipment sh ON sh.shipment_id = si.shipment_id
JOIN batch b     ON b.batch_id     = si.batch_id
JOIN retailer r  ON r.retailer_id  = sh.retailer_id;

-- [NL] Derived Total_Shipment_Quantity, computed PER UNIT (never adds kg to L).
CREATE VIEW v_shipment_summary AS
SELECT sh.shipment_id, sh.shipment_date, sh.source_location,
       sh.retailer_id, r.retailer_name, r.city AS destination_city, r.state AS destination_state,
       sh.transportation_cost, b.unit,
       SUM(si.quantity_shipped) AS total_shipment_quantity,
       COUNT(si.batch_id)       AS batch_count
FROM shipment sh
JOIN retailer r            ON r.retailer_id  = sh.retailer_id
LEFT JOIN shipment_item si ON si.shipment_id = sh.shipment_id
LEFT JOIN batch b          ON b.batch_id     = si.batch_id
GROUP BY sh.shipment_id, sh.shipment_date, sh.source_location, sh.retailer_id,
         r.retailer_name, r.city, r.state, sh.transportation_cost, b.unit;

-- [NL] Price history with derived Price_Change_Percentage.
-- "Comparable previous observation" = previous observation of the SAME product,
-- unit, supply-chain stage and market location (window function LAG).
CREATE VIEW v_price_history AS
SELECT p.price_id, p.batch_id, b.product_name, b.unit, p.price_date,
       p.supply_chain_stage, p.market_location, p.selling_price, p.cost_per_unit,
       LAG(p.selling_price) OVER w AS previous_comparable_price,
       LAG(p.price_date)    OVER w AS previous_price_date,
       ROUND(100.0 * (p.selling_price - LAG(p.selling_price) OVER w)
             / NULLIF(LAG(p.selling_price) OVER w, 0), 2) AS price_change_percentage
FROM price_record p
JOIN batch b ON b.batch_id = p.batch_id
WINDOW w AS (PARTITION BY b.product_name, b.unit, p.supply_chain_stage, p.market_location
             ORDER BY p.price_date, p.price_id);

-- [NL] Monthly average price per product and stage, with stage-to-stage change.
CREATE VIEW v_stage_price_monthly AS
WITH m AS (
    SELECT b.product_name, b.unit,
           date_trunc('month', p.price_date)::date AS month,
           p.supply_chain_stage,
           AVG(p.selling_price) AS avg_price,
           COUNT(*)             AS observations
    FROM price_record p JOIN batch b ON b.batch_id = p.batch_id
    GROUP BY 1, 2, 3, 4
)
SELECT product_name, unit, month,
       ROUND(AVG(avg_price) FILTER (WHERE supply_chain_stage = 'FARM'), 2)   AS farm_avg_price,
       ROUND(AVG(avg_price) FILTER (WHERE supply_chain_stage = 'PROCESSING_WHOLESALE'), 2)
                                                                              AS wholesale_avg_price,
       ROUND(AVG(avg_price) FILTER (WHERE supply_chain_stage = 'RETAIL'), 2) AS retail_avg_price,
       ROUND(100.0 * (AVG(avg_price) FILTER (WHERE supply_chain_stage = 'RETAIL')
                    - AVG(avg_price) FILTER (WHERE supply_chain_stage = 'FARM'))
             / NULLIF(AVG(avg_price) FILTER (WHERE supply_chain_stage = 'FARM'), 0), 2)
                                                                              AS farm_to_retail_change_pct,
       SUM(observations) AS observations
FROM m
GROUP BY product_name, unit, month;

-- [NL] Alerts with product name.
CREATE VIEW v_alerts AS
SELECT a.alert_id, a.batch_id, b.product_name, a.alert_date, a.alert_type, a.detection_method,
       a.anomaly_score, a.description, a.related_shipment_id, a.related_price_id, a.alert_status
FROM anomaly_alert a JOIN batch b ON b.batch_id = a.batch_id;

-- [NL] Master data with multivalued contacts folded into one column.
CREATE VIEW v_farms AS
SELECT f.farm_id, f.farm_name, f.street, f.city, f.state, f.pin_code,
       string_agg(c.contact_no, ', ' ORDER BY c.contact_no) AS contact_numbers
FROM farm f LEFT JOIN farm_contact c ON c.farm_id = f.farm_id
GROUP BY f.farm_id;

CREATE VIEW v_facilities AS
SELECT facility_id, facility_name, street, city, state, pin_code FROM processing_facility;

CREATE VIEW v_retailers AS
SELECT r.retailer_id, r.retailer_name, r.street, r.city, r.state, r.pin_code,
       string_agg(c.contact_no, ', ' ORDER BY c.contact_no) AS contact_numbers
FROM retailer r LEFT JOIN retailer_contact c ON c.retailer_id = r.retailer_id
GROUP BY r.retailer_id;

-- Movement ledger per batch: every consumption and every shipment, dated.
CREATE VIEW v_batch_ledger AS
SELECT d.input_batch_id AS batch_id, bo.production_date AS event_date,
       'CONSUMED_BY' AS event_type, d.output_batch_id AS reference_id, d.quantity_used AS quantity
FROM batch_derivation d JOIN batch bo ON bo.batch_id = d.output_batch_id
UNION ALL
SELECT si.batch_id, sh.shipment_date, 'SHIPPED_IN', si.shipment_id, si.quantity_shipped
FROM shipment_item si JOIN shipment sh ON sh.shipment_id = si.shipment_id;
