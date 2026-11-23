-- Serialize direct same-day edges before checking for a cycle. Edges across
-- different production dates already have a strict chronological order.
SET search_path = tracefood;

CREATE OR REPLACE FUNCTION fn_trg_derivation_check() RETURNS trigger
LANGUAGE plpgsql
SET search_path = tracefood, pg_temp
AS $$
DECLARE
    v_out batch%ROWTYPE;
    v_in batch%ROWTYPE;
    v_day_key INTEGER;
    v_old_input VARCHAR;
    v_old_output VARCHAR;
BEGIN
    SELECT * INTO v_out FROM batch WHERE batch_id = NEW.output_batch_id;
    SELECT * INTO v_in FROM batch WHERE batch_id = NEW.input_batch_id;

    IF v_out.farm_id IS NOT NULL THEN
        RAISE EXCEPTION 'Batch % is an ORIGINAL farm batch and cannot have input batches',
                        NEW.output_batch_id;
    END IF;
    IF v_in.production_date > v_out.production_date THEN
        RAISE EXCEPTION 'Input batch % (produced %) is newer than output batch % (produced %)',
                        NEW.input_batch_id, v_in.production_date, NEW.output_batch_id, v_out.production_date;
    END IF;
    IF v_in.production_date = v_out.production_date THEN
        -- READ COMMITTED reads a fresh graph after the lock wait. SERIALIZABLE
        -- detects a stale snapshot through SSI. REPEATABLE READ cannot do either.
        IF current_setting('transaction_isolation') = 'repeatable read' THEN
            RAISE EXCEPTION 'Same-day lineage writes require READ COMMITTED or SERIALIZABLE isolation';
        END IF;
        v_day_key := CASE v_out.production_date
            WHEN 'infinity'::date THEN 2147483647
            WHEN '-infinity'::date THEN -2147483648
            ELSE v_out.production_date - DATE '2000-01-01'
        END;
        PERFORM pg_advisory_xact_lock(20261120, v_day_key);
    END IF;

    IF TG_OP = 'UPDATE' THEN
        v_old_input := OLD.input_batch_id;
        v_old_output := OLD.output_batch_id;
    END IF;
    IF EXISTS (
        WITH RECURSIVE down(batch_id) AS (
            SELECT NEW.output_batch_id::varchar
            UNION
            SELECT d.output_batch_id
            FROM batch_derivation d JOIN down ON d.input_batch_id = down.batch_id
            WHERE (d.input_batch_id, d.output_batch_id) IS DISTINCT FROM (v_old_input, v_old_output)
        )
        SELECT 1 FROM down WHERE batch_id = NEW.input_batch_id
    ) THEN
        RAISE EXCEPTION 'Edge % -> % would create a cycle in batch lineage',
                        NEW.input_batch_id, NEW.output_batch_id;
    END IF;
    RETURN NEW;
END $$;
