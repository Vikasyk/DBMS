-- Run as a PostgreSQL superuser on a database loaded with the demo fixture.
-- psql -X -d tracefood -f db/tests/regression.sql
\set ON_ERROR_STOP on
SET search_path = tracefood, pg_temp;

CREATE OR REPLACE FUNCTION pg_temp.require(passed boolean, label text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF passed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'TraceFood regression failed: %', label;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.expect_error(command text, states text[], message_pattern text)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE command;
    RAISE EXCEPTION 'Expected SQLSTATE % for: %', states, command;
EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE <> ALL(states) OR SQLERRM !~* message_pattern THEN
        RAISE;
    END IF;
END;
$$;

\echo 'Testing fixture queries and anomaly rules (T01-T13)'
BEGIN;
-- ALTER SEQUENCE RESTART is transactional, including on rollback of this test.
ALTER SEQUENCE alert_seq RESTART WITH 900000;
ALTER SEQUENCE batch_seq RESTART WITH 900000;
DELETE FROM anomaly_alert WHERE detection_method = 'RULE';

SELECT pg_temp.require(
    (SELECT array_agg(format('%s:%s', batch_id, depth) ORDER BY depth, batch_id)
     FROM fn_downstream('B101')) = ARRAY['B103:1', 'B105:2'],
    'T01 downstream lineage');
SELECT pg_temp.require(
    (SELECT array_agg(format('%s:%s', batch_id, depth) ORDER BY depth, batch_id)
     FROM fn_upstream('B105')) = ARRAY['B103:1', 'B104:1', 'B101:2', 'B102:2'],
    'T02 upstream lineage');
SELECT pg_temp.require(
    (SELECT array_agg(format('%s:%s', original_batch_id, farm_id) ORDER BY original_batch_id)
     FROM fn_origin_farms('B105')) = ARRAY['B101:F01', 'B102:F02', 'B104:F03'],
    'T03 farms of origin');
SELECT pg_temp.require(
    (SELECT array_agg(format('%s:%s:%s', batch_id, relation, split_part(assessment, ':', 1))
                      ORDER BY batch_id)
     FROM fn_impact_batches('B103')) = ARRAY[
        'B101:UPSTREAM:POSSIBLE SOURCE', 'B102:UPSTREAM:POSSIBLE SOURCE',
        'B103:SELECTED:CONFIRMED', 'B105:DOWNSTREAM:POTENTIALLY AFFECTED'
    ], 'T04 investigation batch assessments');
SELECT pg_temp.require(
    (SELECT array_agg(format('%s:%s:%s:%s:%s', shipment_id, batch_id,
                            trim_scale(quantity_shipped), unit, retailer_id) ORDER BY shipment_id)
     FROM fn_impact_shipments('B103')) = ARRAY['S501:B103:50:kg:R01', 'S502:B103:20:kg:R02',
                                             'S503:B105:25:kg:R03'],
    'T05 investigation affected shipment lines');
SELECT pg_temp.require(
    (SELECT last_pass_check_id = 'QC3' AND last_pass_batch_id = 'B103'
         AND last_pass_date = DATE '2026-01-09' AND last_pass_stage = 'PROCESSING'
         AND failed_batch_id = 'B103' AND fail_date = DATE '2026-01-14' AND fail_stage = 'RETAIL'
     FROM fn_contamination_window('QC4')),
    'T06 contamination window');
SELECT pg_temp.require(
    (SELECT array_agg(DISTINCT retailer_id::text ORDER BY retailer_id::text)
     FROM fn_impact_shipments('B101')) = ARRAY['R01', 'R02', 'R03'],
    'T07 simulated retailers');
SELECT pg_temp.require(
    (SELECT array_agg(selling_price::numeric ORDER BY price_date)
                 = ARRAY[40.00, 42.00, 41.00, 92.00]
        AND array_agg(price_change_percentage ORDER BY price_date)
                 = ARRAY[NULL, 5.00, -2.38, 124.39]::numeric[]
     FROM v_price_history
     WHERE product_name = 'Tomato' AND unit = 'kg' AND supply_chain_stage = 'RETAIL'
       AND market_location = 'Bengaluru'),
    'T08 comparable price changes');
SELECT pg_temp.require(
    (SELECT farm_avg_price = 20.17 AND wholesale_avg_price = 28.00 AND retail_avg_price = 53.75
         AND farm_to_retail_change_pct = 166.53
     FROM v_stage_price_monthly
     WHERE product_name = 'Tomato' AND unit = 'kg' AND month = DATE '2026-01-01'),
    'T09 monthly stage prices');
SELECT pg_temp.require(
    (SELECT total_input_quantity = 80 AND output_quantity = 95 AND yield_ratio = 1.1875
         AND units_consistent
     FROM v_mass_balance WHERE batch_id = 'B107'),
    'T10 mass balance');
SELECT pg_temp.require(
    (SELECT array_agg(available_quantity ORDER BY batch_id)
     FROM v_batch_overview WHERE batch_id IN ('B101', 'B104')) = ARRAY[40, -10]::numeric[],
    'T11 available quantities');
SELECT pg_temp.require(
    (SELECT total_shipment_quantity = 105 AND batch_count = 2
     FROM v_shipment_summary WHERE shipment_id = 'S503' AND unit = 'kg'),
    'T12 total shipment quantity');
SELECT pg_temp.require(fn_run_rule_checks() = 3, 'T13 initial rule alerts');
SELECT pg_temp.require(fn_run_rule_checks() = 0, 'T13 rule alert deduplication');
SELECT pg_temp.require(
    (SELECT array_agg(format('%s:%s:%s:%s', batch_id, alert_type,
                             trim_scale(anomaly_score), coalesce(related_shipment_id, '-'))
                      ORDER BY batch_id)
     FROM v_alerts WHERE detection_method = 'RULE') = ARRAY[
        'B104:OVER_ALLOCATION:0.0833:S503', 'B107:MASS_BALANCE:0.1875:-',
        'B108:EXPIRED_SHIPMENT:6:S505'
    ], 'T13 rule alert evidence and scores');

\echo 'Testing processing transactions under the application role (PR1-PR3)'
SET LOCAL ROLE tracefood_app;
DO $$
DECLARE
    output_id varchar;
BEGIN
    CALL sp_register_processing('Tomato Puree', 10, 'kg', DATE '2026-01-13', DATE '2026-03-13',
        'PF01', 'PULPING', '[{"batch_id":"B101","quantity_used":10}]', FALSE, output_id);
    IF output_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM batch b JOIN batch_derivation d ON d.output_batch_id = b.batch_id
        JOIN batch_processing p USING (batch_id)
        WHERE b.batch_id = output_id AND b.farm_id IS NULL AND b.quantity = 10
          AND d.input_batch_id = 'B101' AND d.quantity_used = 10 AND p.facility_id = 'PF01'
          AND p.processing_date = DATE '2026-01-13' AND p.operation_type = 'PULPING'
    ) THEN
        RAISE EXCEPTION 'PR1 valid processing did not create all its records';
    END IF;

    BEGIN
        CALL sp_register_processing('Tomato Puree', 35, 'kg', DATE '2026-01-14', DATE '2026-03-14',
            'PF01', 'PULPING', '[{"batch_id":"B101","quantity_used":35}]', FALSE, output_id);
        RAISE EXCEPTION 'PR2 processing accepted an over-allocation without permission';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM !~ 'Input batch B101 has only 30(\.0+)? available' THEN
            RAISE;
        END IF;
    END;

    CALL sp_register_processing('Tomato Puree', 35, 'kg', DATE '2026-01-14', DATE '2026-03-14',
        'PF01', 'PULPING', '[{"batch_id":"B101","quantity_used":35}]', TRUE, output_id);
    IF (SELECT available_quantity FROM v_batch_stock WHERE batch_id = 'B101') IS DISTINCT FROM -5
       OR NOT EXISTS (SELECT 1 FROM batch_derivation
                      WHERE output_batch_id = output_id AND input_batch_id = 'B101'
                        AND quantity_used = 35) THEN
        RAISE EXCEPTION 'PR3 processing did not record an explicitly allowed over-allocation';
    END IF;
    IF fn_run_rule_checks() <> 1 THEN
        RAISE EXCEPTION 'PR3 expected one new over-allocation alert';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM anomaly_alert WHERE batch_id = 'B101' AND alert_type = 'OVER_ALLOCATION'
          AND anomaly_score = 0.05 AND description LIKE '%' || output_id || '%'
    ) THEN
        RAISE EXCEPTION 'PR3 permitted over-allocation was not flagged with evidence';
    END IF;
END;
$$;
SET CONSTRAINTS ALL IMMEDIATE;
ROLLBACK;

\echo 'Testing cross-table integrity and domains (N01-N11)'
BEGIN;
SELECT pg_temp.expect_error($sql$INSERT INTO batch_derivation VALUES ('B103', 'B103', 1)$sql$,
    ARRAY['23514', 'P0001'], 'cycle|self'); -- N01
SELECT pg_temp.expect_error($sql$INSERT INTO batch_derivation VALUES ('B101', 'B104', 1)$sql$,
    ARRAY['23514', 'P0001'], 'original'); -- N02
SELECT pg_temp.expect_error($sql$INSERT INTO batch_derivation VALUES ('B103', 'B107', 1)$sql$,
    ARRAY['23514', 'P0001'], 'newer than'); -- N03

-- Same-day batches let this case exercise the cycle check independently of the date check.
INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date) VALUES
    ('B90001', 'Tomato Puree', 1, 'kg', '2026-01-13', '2026-03-13'),
    ('B90002', 'Tomato Puree', 1, 'kg', '2026-01-13', '2026-03-13');
INSERT INTO batch_derivation VALUES ('B90001', 'B101', 1), ('B90002', 'B90001', 1);
INSERT INTO batch_processing VALUES
    ('PF01', 'B90001', '2026-01-13', 'PULPING'), ('PF01', 'B90002', '2026-01-13', 'PULPING');
SELECT pg_temp.expect_error($sql$INSERT INTO batch_derivation VALUES ('B90001', 'B90002', 1)$sql$,
    ARRAY['23514', 'P0001'], 'cycle'); -- N04

DO $$
BEGIN
    INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date)
    VALUES ('B90003', 'Tomato Puree', 1, 'kg', '2026-01-13', '2026-03-13');
    -- Fire the deferred trigger at the same integrity boundary as a commit.
    SET CONSTRAINTS ALL IMMEDIATE;
    RAISE EXCEPTION 'N05 accepted a processed batch without inputs';
EXCEPTION WHEN raise_exception OR check_violation THEN
    IF SQLERRM !~ 'neither a farm of origin nor any input batch' THEN
        RAISE;
    END IF;
END;
$$;

DO $$
BEGIN
    DELETE FROM batch_derivation WHERE output_batch_id = 'B105';
    SET CONSTRAINTS ALL IMMEDIATE;
    RAISE EXCEPTION 'Deleting all inputs left an originless processed batch';
EXCEPTION WHEN raise_exception OR check_violation THEN
    IF SQLERRM !~ 'Batch B105 has neither a farm of origin nor any input batch' THEN
        RAISE;
    END IF;
END;
$$;

SELECT pg_temp.expect_error($sql$
    INSERT INTO quality_check VALUES ('QC90001', 'B101', '2026-01-08', 'FARM', 'PASS', 'Example', NULL)
$sql$, ARRAY['23514'], 'chk_pass_has_no_contaminant'); -- N06
SELECT pg_temp.expect_error($sql$
    INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date, farm_id)
    VALUES ('B90004', 'Tomato', -1, 'kg', '2026-01-13', '2026-03-13', 'F01')
$sql$, ARRAY['23514'], 'qty_t'); -- N07
SELECT pg_temp.expect_error($sql$INSERT INTO shipment_item VALUES ('S504', 'B105', 1)$sql$,
    ARRAY['23514', 'P0001'], 'before batch .* was produced'); -- N08
SELECT pg_temp.expect_error($sql$
    INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date, farm_id)
    VALUES ('B90005', 'tomato', 1, 'kg', '2026-01-13', '2026-03-13', 'F01')
$sql$, ARRAY['23514'], 'product_name'); -- N09
SELECT pg_temp.expect_error($sql$
    INSERT INTO quality_check VALUES ('QC90002', 'B101', '2026-01-04', 'FARM', 'PASS', NULL, NULL)
$sql$, ARRAY['23514', 'P0001'], 'before the production date'); -- N10
SELECT pg_temp.expect_error($sql$
    INSERT INTO farm VALUES ('F90001', 'Test Farm', NULL, 'Kolar', 'Karnataka', '012345')
$sql$, ARRAY['23514'], 'pin_t'); -- N11
ROLLBACK;

\echo 'Testing simulation read-only guarantees (S01-S02)'
BEGIN;
CREATE FUNCTION pg_temp.try_write_quality() RETURNS void LANGUAGE plpgsql STABLE AS $$
BEGIN
    INSERT INTO tracefood.quality_check
    VALUES ('QC90003', 'B101', '2026-01-08', 'FARM', 'PASS', NULL, NULL);
END;
$$;
SELECT pg_temp.expect_error('SELECT pg_temp.try_write_quality()', ARRAY['0A000'],
    'not allowed in a non-volatile function'); -- S01
ROLLBACK;

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL ROLE tracefood_app;
DO $$
BEGIN
    IF (SELECT count(*) FROM quality_check) <> 5 THEN
        RAISE EXCEPTION 'S02 expected five checks in the demo fixture';
    END IF;
    IF (SELECT array_agg(format('%s:%s', batch_id, split_part(assessment, ':', 1)) ORDER BY batch_id)
        FROM fn_impact_batches('B101')) IS DISTINCT FROM ARRAY[
            'B101:SELECTED', 'B103:CONFIRMED', 'B105:POTENTIALLY AFFECTED'
        ] OR (SELECT count(DISTINCT retailer_id) FROM fn_impact_shipments('B101')) <> 3
          OR (SELECT count(*) FROM quality_check) <> 5 THEN
        RAISE EXCEPTION 'S02 read-only simulation returned unexpected results';
    END IF;
    BEGIN
        INSERT INTO quality_check VALUES ('QC90004', 'B101', '2026-01-08', 'FARM', 'PASS', NULL, NULL);
        RAISE EXCEPTION 'S02 application role could write inside the read-only transaction';
    EXCEPTION WHEN read_only_sql_transaction THEN NULL;
    END;
END;
$$;
ROLLBACK;

\echo 'Testing application and natural-language role privileges (A01-A03, R01-R04)'
BEGIN;
SET LOCAL ROLE tracefood_app;
DO $$
BEGIN
    BEGIN
        DELETE FROM quality_check WHERE check_id = 'QC1';
        RAISE EXCEPTION 'A01 application role could delete quality history';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;

    UPDATE batch SET status = 'ON_HOLD' WHERE batch_id = 'B101';
    IF (SELECT status FROM batch WHERE batch_id = 'B101') IS DISTINCT FROM 'ON_HOLD' THEN
        RAISE EXCEPTION 'A02 application role could not update status';
    END IF;
    BEGIN
        UPDATE batch SET quantity = 101 WHERE batch_id = 'B101';
        RAISE EXCEPTION 'A02 application role could update recorded initial quantity';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;

    INSERT INTO quality_check VALUES ('QC90005', 'B101', '2026-01-08', 'FARM', 'PASS', NULL, NULL);
    IF NOT EXISTS (SELECT 1 FROM quality_check WHERE check_id = 'QC90005') THEN
        RAISE EXCEPTION 'A03 application role could not insert a check';
    END IF;
END;
$$;
ROLLBACK;

-- SET ROLE preserves the login session's settings. Check the reader's startup
-- defaults separately and apply those settings explicitly for runtime checks.
SELECT pg_temp.require(
    (SELECT array_agg(setting) @> ARRAY['default_transaction_read_only=on', 'statement_timeout=3s']
     FROM pg_db_role_setting s
     CROSS JOIN LATERAL unnest(s.setconfig) AS settings(setting)
     WHERE s.setrole = 'tracefood_nl_reader'::regrole
       AND s.setdatabase IN (0, (SELECT oid FROM pg_database WHERE datname = current_database()))),
    'R03/R04 reader startup defaults');

BEGIN;
SET LOCAL ROLE tracefood_nl_reader;
DO $$
BEGIN
    IF (SELECT count(*) FROM v_batch_overview) <> 8 THEN
        RAISE EXCEPTION 'R01 curated view did not return the fixture';
    END IF;
    BEGIN
        PERFORM 1 FROM batch;
        RAISE EXCEPTION 'R02 natural-language role could read a base table';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO quality_check VALUES ('QC90006', 'B101', '2026-01-08', 'FARM', 'PASS', NULL, NULL);
        RAISE EXCEPTION 'R03 natural-language role had write privileges';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    IF has_function_privilege(current_user, 'tracefood.fn_run_rule_checks(numeric)', 'EXECUTE') THEN
        RAISE EXCEPTION 'R03 natural-language role could execute a write routine';
    END IF;
END;
$$;
ROLLBACK;

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL ROLE tracefood_nl_reader;
SET LOCAL statement_timeout = '3s';
DO $$
BEGIN
    BEGIN
        INSERT INTO quality_check VALUES ('QC90007', 'B101', '2026-01-08', 'FARM', 'PASS', NULL, NULL);
        RAISE EXCEPTION 'R03 natural-language role wrote in a read-only transaction';
    EXCEPTION WHEN read_only_sql_transaction OR insufficient_privilege THEN NULL;
    END;
    PERFORM pg_sleep(5);
    RAISE EXCEPTION 'R04 statement timeout did not cancel the long query';
EXCEPTION WHEN query_canceled THEN
    IF SQLERRM !~* 'statement timeout' THEN
        RAISE;
    END IF;
END;
$$;
ROLLBACK;

\echo 'Testing finite quantities and large anomaly scores'
BEGIN;
ALTER SEQUENCE alert_seq RESTART WITH 900000;
SELECT pg_temp.expect_error(
    $sql$ SELECT 'NaN'::qty_t $sql$, ARRAY['23514'], 'qty_t_finite');
SELECT pg_temp.expect_error(
    $sql$ SELECT 'NaN'::money_t $sql$, ARRAY['23514'], 'money_t_finite');
INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date)
VALUES ('B8901', 'Tomato Puree', 900000, 'kg', '2026-01-08', '2026-04-08');
INSERT INTO batch_derivation VALUES ('B8901', 'B101', 0.001);
SELECT fn_run_rule_checks();
SELECT pg_temp.require(
    (SELECT anomaly_score FROM v_alerts WHERE batch_id = 'B8901' AND alert_type = 'MASS_BALANCE') = 899999999,
    'extreme but finite excess remains recordable');
ROLLBACK;

\echo 'TraceFood database regression checks passed.'
