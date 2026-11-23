-- =====================================================================
-- TraceFood  |  04_functions.sql
-- Lineage traversal (recursive CTEs), contamination impact, contamination
-- window, transactional processing procedure, rule-based anomaly checks.
-- All read-only functions are STABLE: PostgreSQL refuses INSERT/UPDATE/DELETE
-- inside them, which is what makes the what-if simulation provably read-only.
-- =====================================================================
SET search_path = tracefood;

-- ---------- F1. All downstream (derived) batches of a batch ----------
CREATE OR REPLACE FUNCTION fn_downstream(p_batch VARCHAR)
RETURNS TABLE (batch_id VARCHAR, depth INT)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE down AS (
        SELECT d.output_batch_id AS bid, 1 AS lvl,
               ARRAY[d.input_batch_id, d.output_batch_id]::varchar[] AS path
        FROM   tracefood.batch_derivation d
        WHERE  d.input_batch_id = p_batch
        UNION ALL
        SELECT d.output_batch_id, down.lvl + 1, down.path || d.output_batch_id
        FROM   tracefood.batch_derivation d
        JOIN   down ON d.input_batch_id = down.bid
        WHERE  NOT d.output_batch_id = ANY (down.path)          -- cycle guard
    )
    SELECT bid, MIN(lvl) FROM down GROUP BY bid ORDER BY 2, 1;
$$;

-- ---------- F2. All upstream (input / ancestor) batches of a batch ----------
CREATE OR REPLACE FUNCTION fn_upstream(p_batch VARCHAR)
RETURNS TABLE (batch_id VARCHAR, depth INT)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE up AS (
        SELECT d.input_batch_id AS bid, 1 AS lvl,
               ARRAY[d.output_batch_id, d.input_batch_id]::varchar[] AS path
        FROM   tracefood.batch_derivation d
        WHERE  d.output_batch_id = p_batch
        UNION ALL
        SELECT d.input_batch_id, up.lvl + 1, up.path || d.input_batch_id
        FROM   tracefood.batch_derivation d
        JOIN   up ON d.output_batch_id = up.bid
        WHERE  NOT d.input_batch_id = ANY (up.path)
    )
    SELECT bid, MIN(lvl) FROM up GROUP BY bid ORDER BY 2, 1;
$$;

-- ---------- F3. Farms of origin of any batch (original or processed) ----------
CREATE OR REPLACE FUNCTION fn_origin_farms(p_batch VARCHAR)
RETURNS TABLE (original_batch_id VARCHAR, product_name VARCHAR, farm_id VARCHAR,
               farm_name VARCHAR, city VARCHAR)
LANGUAGE sql STABLE AS $$
    SELECT b.batch_id, b.product_name, f.farm_id, f.farm_name, f.city
    FROM  (SELECT p_batch AS bid
           UNION
           SELECT u.batch_id FROM tracefood.fn_upstream(p_batch) u) x
    JOIN   tracefood.batch b ON b.batch_id = x.bid
    JOIN   tracefood.farm  f ON f.farm_id  = b.farm_id
    ORDER BY b.batch_id;
$$;

-- ---------- F4. Contamination impact: batches ----------
-- relation   : SELECTED (the batch under investigation), DOWNSTREAM, UPSTREAM
-- assessment : distinguishes confirmed observations from potential exposure.
CREATE OR REPLACE FUNCTION fn_impact_batches(p_batch VARCHAR)
RETURNS TABLE (batch_id VARCHAR, product_name VARCHAR, relation TEXT, depth INT,
               has_failed_check BOOLEAN, assessment TEXT)
LANGUAGE sql STABLE AS $$
    WITH related AS (
        SELECT p_batch::varchar AS bid, 'SELECTED'::text AS rel, 0 AS lvl
        UNION ALL SELECT d.batch_id, 'DOWNSTREAM', d.depth FROM tracefood.fn_downstream(p_batch) d
        UNION ALL SELECT u.batch_id, 'UPSTREAM',   u.depth FROM tracefood.fn_upstream(p_batch)   u
    )
    SELECT r.bid, b.product_name, r.rel, r.lvl,
           EXISTS (SELECT 1 FROM tracefood.quality_check q
                   WHERE q.batch_id = r.bid AND q.result = 'FAIL') AS failed,
           CASE
             WHEN EXISTS (SELECT 1 FROM tracefood.quality_check q
                          WHERE q.batch_id = r.bid AND q.result = 'FAIL')
                  THEN 'CONFIRMED: has its own failed quality check'
             WHEN r.rel = 'SELECTED'   THEN 'SELECTED: no failed check recorded for this batch'
             WHEN r.rel = 'DOWNSTREAM' THEN 'POTENTIALLY AFFECTED: derived from the selected batch'
             ELSE 'POSSIBLE SOURCE: input of the selected batch - investigate'
           END
    FROM related r JOIN tracefood.batch b ON b.batch_id = r.bid
    ORDER BY CASE r.rel WHEN 'SELECTED' THEN 0 WHEN 'DOWNSTREAM' THEN 1 ELSE 2 END, r.lvl, r.bid;
$$;

-- ---------- F5. Contamination impact: shipments and retailers ----------
-- Shipments that carried the selected batch or any DOWNSTREAM batch.
CREATE OR REPLACE FUNCTION fn_impact_shipments(p_batch VARCHAR)
RETURNS TABLE (shipment_id VARCHAR, shipment_date DATE, batch_id VARCHAR, product_name VARCHAR,
               quantity_shipped NUMERIC, unit VARCHAR, retailer_id VARCHAR,
               retailer_name VARCHAR, retailer_city VARCHAR)
LANGUAGE sql STABLE AS $$
    SELECT sl.shipment_id, sl.shipment_date, sl.batch_id, sl.product_name,
           sl.quantity_shipped, sl.unit, sl.retailer_id, sl.retailer_name, sl.retailer_city
    FROM   tracefood.v_shipment_lines sl
    WHERE  sl.batch_id IN (SELECT i.batch_id FROM tracefood.fn_impact_batches(p_batch) i
                           WHERE i.relation IN ('SELECTED', 'DOWNSTREAM'))
    ORDER BY sl.shipment_date, sl.shipment_id, sl.batch_id;
$$;

-- ---------- F6. Possible contamination window for a FAILED check ----------
-- Window = (latest PASS on the failed batch or any of its ancestors, the FAIL date].
-- It is a possible window only; it does not establish cause, place or time.
CREATE OR REPLACE FUNCTION fn_contamination_window(p_check_id VARCHAR)
RETURNS TABLE (failed_check_id VARCHAR, failed_batch_id VARCHAR, fail_date DATE, fail_stage VARCHAR,
               last_pass_check_id VARCHAR, last_pass_batch_id VARCHAR, last_pass_date DATE,
               last_pass_stage VARCHAR, note TEXT)
LANGUAGE sql STABLE AS $$
    WITH f AS (
        SELECT * FROM tracefood.quality_check WHERE check_id = p_check_id AND result = 'FAIL'
    ),
    candidates AS (
        SELECT f.batch_id AS bid FROM f
        UNION
        SELECT u.batch_id FROM f, tracefood.fn_upstream(f.batch_id) u
    ),
    last_pass AS (
        SELECT q.* FROM tracefood.quality_check q, f
        WHERE  q.batch_id IN (SELECT bid FROM candidates)
          AND  q.result = 'PASS' AND q.check_date <= f.check_date
        ORDER BY q.check_date DESC, q.check_id DESC
        LIMIT 1
    )
    SELECT f.check_id, f.batch_id, f.check_date, f.check_stage,
           lp.check_id, lp.batch_id, lp.check_date, lp.check_stage,
           CASE WHEN lp.check_id IS NULL
                THEN 'No earlier PASS on this batch or its inputs: window is open-ended'
                ELSE 'Possible window between the last recorded PASS and the FAIL; '
                     || 'inputs that were never checked may also be involved'
           END
    FROM f LEFT JOIN last_pass lp ON TRUE;
$$;

-- ---------- P1. Register a processing event atomically (stored procedure) ----------
-- Creates the output batch, its lineage rows and its Processes row in ONE transaction.
-- Input rows are locked (FOR UPDATE) so two sessions cannot over-consume the same batch.
-- p_inputs: '[{"batch_id":"B101","quantity_used":60}, {"batch_id":"B102","quantity_used":20}]'
CREATE OR REPLACE PROCEDURE sp_register_processing(
    p_product_name          VARCHAR,
    p_quantity              NUMERIC,
    p_unit                  VARCHAR,
    p_production_date       DATE,
    p_expiry_date           DATE,
    p_facility_id           VARCHAR,
    p_operation_type        VARCHAR,
    p_inputs                JSONB,
    p_allow_over_allocation BOOLEAN DEFAULT FALSE,
    INOUT p_output_batch_id VARCHAR DEFAULT NULL)
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    r       RECORD;
    v_avail NUMERIC;
BEGIN
    IF p_inputs IS NULL OR jsonb_array_length(p_inputs) = 0 THEN
        RAISE EXCEPTION 'A processed batch needs at least one input batch';
    END IF;

    PERFORM 1 FROM tracefood.batch
    WHERE  batch_id IN (SELECT x ->> 'batch_id' FROM jsonb_array_elements(p_inputs) x)
    ORDER BY batch_id
    FOR UPDATE;

    FOR r IN SELECT x ->> 'batch_id' AS bid, (x ->> 'quantity_used')::numeric AS qty
             FROM jsonb_array_elements(p_inputs) x
    LOOP
        SELECT available_quantity INTO v_avail FROM tracefood.v_batch_stock WHERE batch_id = r.bid;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Input batch % does not exist', r.bid;
        END IF;
        IF r.qty > v_avail AND NOT COALESCE(p_allow_over_allocation, FALSE) THEN
            RAISE EXCEPTION 'Input batch % has only % available but % was requested '
                            '(set p_allow_over_allocation to record it anyway; it will be flagged)',
                            r.bid, v_avail, r.qty;
        END IF;
    END LOOP;

    INSERT INTO tracefood.batch (product_name, quantity, unit, production_date, expiry_date, farm_id)
    VALUES (p_product_name, p_quantity, p_unit, p_production_date, p_expiry_date, NULL)
    RETURNING batch_id INTO p_output_batch_id;

    INSERT INTO tracefood.batch_derivation (output_batch_id, input_batch_id, quantity_used)
    SELECT p_output_batch_id, x ->> 'batch_id', (x ->> 'quantity_used')::numeric
    FROM   jsonb_array_elements(p_inputs) x;

    INSERT INTO tracefood.batch_processing (facility_id, batch_id, processing_date, operation_type)
    VALUES (p_facility_id, p_output_batch_id, p_production_date, p_operation_type);
END $$;

-- ---------- F7. Rule-based (deterministic) anomaly checks ----------
-- Writes RULE alerts; returns how many NEW alerts were stored.
-- p_tolerance: relative tolerance for measurement error (0.02 = 2 %).
CREATE OR REPLACE FUNCTION fn_run_rule_checks(p_tolerance NUMERIC DEFAULT 0.02)
RETURNS INTEGER
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    v_new INT := 0;
    v_n   INT;
BEGIN
    -- R1  Mass balance: output exceeds recorded input (same units only)
    INSERT INTO tracefood.anomaly_alert (batch_id, alert_type, detection_method,
                                         anomaly_score, description)
    SELECT m.batch_id, 'MASS_BALANCE', 'RULE',
           ROUND(m.difference / m.total_input_quantity, 4),
           format('Recorded output %s %s exceeds total recorded input %s %s by %s %s (%s%%) and no '
                  'additional input is recorded. Possible causes: data-entry or unit error, missing '
                  'input record, legitimate addition. This is not evidence of fraud.',
                  m.output_quantity, m.unit, m.total_input_quantity, m.unit,
                  m.difference, m.unit, ROUND(100 * m.difference / m.total_input_quantity, 2))
    FROM   tracefood.v_mass_balance m
    WHERE  m.units_consistent
      AND  m.output_quantity > m.total_input_quantity * (1 + p_tolerance)
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_n = ROW_COUNT;  v_new := v_new + v_n;

    -- R2  Over-allocation: consumption + shipments exceed the initial quantity.
    --     Flags the FIRST event (in date order) at which the running total crosses the limit.
    INSERT INTO tracefood.anomaly_alert (batch_id, alert_type, detection_method, anomaly_score,
                                         description, related_shipment_id)
    SELECT x.batch_id, 'OVER_ALLOCATION', 'RULE',
           ROUND((x.cumulative_out - x.initial_quantity) / x.initial_quantity, 4),
           format('Batch %s: recorded outflows reach %s %s at %s %s on %s, but only %s %s were recorded '
                  'as produced (excess %s %s). Check for missing or mistyped records.',
                  x.batch_id, x.cumulative_out, x.unit, x.event_type, x.reference_id, x.event_date,
                  x.initial_quantity, x.unit, x.cumulative_out - x.initial_quantity, x.unit),
           CASE WHEN x.event_type = 'SHIPPED_IN' THEN x.reference_id END
    FROM (
        SELECT l.*, b.quantity AS initial_quantity, b.unit,
               SUM(l.quantity) OVER (PARTITION BY l.batch_id
                                     ORDER BY l.event_date, l.event_type, l.reference_id
                                     ROWS UNBOUNDED PRECEDING) AS cumulative_out
        FROM tracefood.v_batch_ledger l JOIN tracefood.batch b ON b.batch_id = l.batch_id
    ) x
    WHERE x.cumulative_out > x.initial_quantity * (1 + p_tolerance)
      AND x.cumulative_out - x.quantity <= x.initial_quantity * (1 + p_tolerance)
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_n = ROW_COUNT;  v_new := v_new + v_n;

    -- R3  Shipment dated after the batch's expiry date
    INSERT INTO tracefood.anomaly_alert (batch_id, alert_type, detection_method, anomaly_score,
                                         description, related_shipment_id)
    SELECT si.batch_id, 'EXPIRED_SHIPMENT', 'RULE', (sh.shipment_date - b.expiry_date),
           format('Batch %s (expiry %s) was shipped in %s on %s, %s day(s) after expiry.',
                  si.batch_id, b.expiry_date, si.shipment_id, sh.shipment_date,
                  sh.shipment_date - b.expiry_date),
           si.shipment_id
    FROM   tracefood.shipment_item si
    JOIN   tracefood.shipment sh ON sh.shipment_id = si.shipment_id
    JOIN   tracefood.batch b     ON b.batch_id     = si.batch_id
    WHERE  sh.shipment_date > b.expiry_date
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_n = ROW_COUNT;  v_new := v_new + v_n;

    RETURN v_new;
END $$;
