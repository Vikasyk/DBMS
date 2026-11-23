-- =====================================================================
-- TraceFood  |  02_integrity.sql
-- Cross-table integrity rules (triggers) and indexes.
-- Principle: constraints/triggers REJECT the impossible;
--            rule checks and ML only FLAG the implausible (see 04_functions.sql).
-- =====================================================================
SET search_path = tracefood;

-- ---------- T1. Lineage rules on batch_derivation ----------
--  (a) an ORIGINAL (farm) batch cannot have input batches
--  (b) an input batch cannot be produced after its output batch
--  (c) the new edge must not create a cycle (lineage must stay a DAG)
CREATE OR REPLACE FUNCTION fn_trg_derivation_check() RETURNS trigger
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    v_out batch%ROWTYPE;
    v_in  batch%ROWTYPE;
BEGIN
    SELECT * INTO v_out FROM batch WHERE batch_id = NEW.output_batch_id;
    SELECT * INTO v_in  FROM batch WHERE batch_id = NEW.input_batch_id;

    IF v_out.farm_id IS NOT NULL THEN
        RAISE EXCEPTION 'Batch % is an ORIGINAL farm batch and cannot have input batches',
                        NEW.output_batch_id;
    END IF;

    IF v_in.production_date > v_out.production_date THEN
        RAISE EXCEPTION 'Input batch % (produced %) is newer than output batch % (produced %)',
                        NEW.input_batch_id, v_in.production_date,
                        NEW.output_batch_id, v_out.production_date;
    END IF;

    IF EXISTS (
        WITH RECURSIVE down(batch_id) AS (
            SELECT NEW.output_batch_id::varchar
            UNION                                   -- UNION (not ALL) also stops on bad data
            SELECT d.output_batch_id
            FROM   batch_derivation d JOIN down ON d.input_batch_id = down.batch_id
        )
        SELECT 1 FROM down WHERE batch_id = NEW.input_batch_id
    ) THEN
        RAISE EXCEPTION 'Edge % -> % would create a cycle in batch lineage',
                        NEW.input_batch_id, NEW.output_batch_id;
    END IF;

    RETURN NEW;
END $$;

CREATE TRIGGER trg_derivation_check
BEFORE INSERT OR UPDATE ON batch_derivation
FOR EACH ROW EXECUTE FUNCTION fn_trg_derivation_check();

-- ---------- T2. Every batch has exactly ONE kind of origin (checked at COMMIT) ----------
--  ORIGINAL : farm_id IS NOT NULL and no input rows
--  PROCESSED: farm_id IS NULL and at least one input row
--  DEFERRABLE INITIALLY DEFERRED lets a processed batch and its input rows be
--  inserted in the same transaction.
CREATE OR REPLACE FUNCTION fn_trg_batch_origin_check() RETURNS trigger
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    v_batch_id   VARCHAR;
    v_farm       VARCHAR;
    v_has_inputs BOOLEAN;
BEGIN
    IF TG_TABLE_NAME = 'batch_derivation' THEN
        v_batch_id := OLD.output_batch_id;
    ELSE
        v_batch_id := NEW.batch_id;
    END IF;

    SELECT farm_id INTO v_farm FROM batch WHERE batch_id = v_batch_id;
    IF NOT FOUND THEN RETURN NULL; END IF;
    v_has_inputs := EXISTS (SELECT 1 FROM batch_derivation WHERE output_batch_id = v_batch_id);

    IF v_farm IS NULL AND NOT v_has_inputs THEN
        RAISE EXCEPTION 'Batch % has neither a farm of origin nor any input batch', v_batch_id;
    ELSIF v_farm IS NOT NULL AND v_has_inputs THEN
        RAISE EXCEPTION 'Batch % has both a farm of origin and input batches', v_batch_id;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_batch_origin_check
AFTER INSERT OR UPDATE OF farm_id ON batch
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION fn_trg_batch_origin_check();

-- Deleting or moving an input can leave its former output without an origin.
CREATE CONSTRAINT TRIGGER trg_derivation_origin_check
AFTER DELETE OR UPDATE OF output_batch_id ON batch_derivation
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION fn_trg_batch_origin_check();

-- ---------- T3. Events cannot happen before the batch was produced ----------
-- Generic trigger: TG_ARGV[0] = name of the date column in the triggering table.
CREATE OR REPLACE FUNCTION fn_trg_event_after_production() RETURNS trigger
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    v_event_date DATE := (to_jsonb(NEW) ->> TG_ARGV[0])::date;
    v_prod_date  DATE;
BEGIN
    SELECT production_date INTO v_prod_date FROM batch WHERE batch_id = NEW.batch_id;
    IF v_event_date < v_prod_date THEN
        RAISE EXCEPTION '%.% (%) is before the production date (%) of batch %',
                        TG_TABLE_NAME, TG_ARGV[0], v_event_date, v_prod_date, NEW.batch_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_qc_date      BEFORE INSERT OR UPDATE ON quality_check
FOR EACH ROW EXECUTE FUNCTION fn_trg_event_after_production('check_date');
CREATE TRIGGER trg_price_date   BEFORE INSERT OR UPDATE ON price_record
FOR EACH ROW EXECUTE FUNCTION fn_trg_event_after_production('price_date');
CREATE TRIGGER trg_process_date BEFORE INSERT OR UPDATE ON batch_processing
FOR EACH ROW EXECUTE FUNCTION fn_trg_event_after_production('processing_date');

-- shipment_item has no date of its own; compare with the parent shipment's date.
CREATE OR REPLACE FUNCTION fn_trg_shipment_item_check() RETURNS trigger
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    v_ship_date DATE;
    v_prod_date DATE;
BEGIN
    SELECT shipment_date   INTO v_ship_date FROM shipment WHERE shipment_id = NEW.shipment_id;
    SELECT production_date INTO v_prod_date FROM batch    WHERE batch_id    = NEW.batch_id;
    IF v_ship_date < v_prod_date THEN
        RAISE EXCEPTION 'Shipment % (%) is dated before batch % was produced (%)',
                        NEW.shipment_id, v_ship_date, NEW.batch_id, v_prod_date;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_shipment_item_check BEFORE INSERT OR UPDATE ON shipment_item
FOR EACH ROW EXECUTE FUNCTION fn_trg_shipment_item_check();

-- ---------- Indexes (PKs are indexed automatically) ----------
CREATE INDEX ix_batch_farm          ON batch(farm_id);
CREATE INDEX ix_batch_product       ON batch(product_name);
CREATE INDEX ix_derivation_input    ON batch_derivation(input_batch_id);   -- downstream traversal
CREATE INDEX ix_processing_batch    ON batch_processing(batch_id);
CREATE INDEX ix_qc_batch_date       ON quality_check(batch_id, check_date);
CREATE INDEX ix_shipment_retailer   ON shipment(retailer_id);
CREATE INDEX ix_shipment_item_batch ON shipment_item(batch_id);
CREATE INDEX ix_price_batch         ON price_record(batch_id);
CREATE INDEX ix_price_date          ON price_record(price_date);
CREATE INDEX ix_alert_batch         ON anomaly_alert(batch_id);
-- De-duplication: the same finding is never stored twice (detector uses ON CONFLICT DO NOTHING)
CREATE UNIQUE INDEX ux_alert_dedup ON anomaly_alert
       (batch_id, alert_type, COALESCE(related_shipment_id, '-'), COALESCE(related_price_id, '-'));
