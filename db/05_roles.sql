-- =====================================================================
-- TraceFood  |  05_roles.sql   (run as the database owner / superuser)
-- Least privilege: the application role cannot delete traceability history;
-- the natural-language role can only SELECT curated views, read-only, with a timeout.
-- Set local login credentials separately as the database owner.
-- =====================================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tracefood_app') THEN
        CREATE ROLE tracefood_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tracefood_nl_reader') THEN
        CREATE ROLE tracefood_nl_reader LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA tracefood TO tracefood_app, tracefood_nl_reader;
REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA tracefood FROM PUBLIC, tracefood_nl_reader;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA tracefood TO tracefood_app;

-- Application role: insert and read everything; no DELETE on history tables
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA tracefood TO tracefood_app;
GRANT USAGE, SELECT  ON ALL SEQUENCES IN SCHEMA tracefood TO tracefood_app;
GRANT UPDATE ON tracefood.farm, tracefood.processing_facility, tracefood.retailer TO tracefood_app;
GRANT DELETE ON tracefood.farm_contact, tracefood.retailer_contact TO tracefood_app;
GRANT UPDATE (status)       ON tracefood.batch         TO tracefood_app;   -- column-level privilege
GRANT UPDATE (alert_status) ON tracefood.anomaly_alert TO tracefood_app;

-- Natural-language role: curated views only
REVOKE ALL ON ALL TABLES IN SCHEMA tracefood FROM tracefood_nl_reader;
GRANT SELECT ON tracefood.v_batch_overview, tracefood.v_lineage_edges, tracefood.v_batch_facilities,
                tracefood.v_quality_checks, tracefood.v_shipment_lines, tracefood.v_shipment_summary,
                tracefood.v_price_history, tracefood.v_stage_price_monthly, tracefood.v_alerts,
                tracefood.v_farms, tracefood.v_facilities, tracefood.v_retailers
             TO tracefood_nl_reader;
ALTER ROLE tracefood_nl_reader SET default_transaction_read_only = on;
ALTER ROLE tracefood_nl_reader SET statement_timeout = '3s';
ALTER ROLE tracefood_nl_reader SET search_path = tracefood;
ALTER ROLE tracefood_app       SET search_path = tracefood;
