-- Run this migration with psql --single-transaction or through install_schema.sql.
SET search_path = tracefood;

ALTER DOMAIN qty_t ADD CONSTRAINT qty_t_finite CHECK (VALUE <> 'NaN'::numeric);
ALTER DOMAIN money_t ADD CONSTRAINT money_t_finite CHECK (VALUE <> 'NaN'::numeric);

-- Recreate the dependent read model and restore the original grants.
DROP VIEW v_alerts;
ALTER TABLE anomaly_alert ALTER COLUMN anomaly_score TYPE NUMERIC(30,4);
ALTER TABLE anomaly_alert ADD CONSTRAINT chk_anomaly_score_finite
    CHECK (anomaly_score <> 'NaN'::numeric);

CREATE VIEW v_alerts AS
SELECT a.alert_id, a.batch_id, b.product_name, a.alert_date, a.alert_type, a.detection_method,
       a.anomaly_score, a.description, a.related_shipment_id, a.related_price_id, a.alert_status
FROM anomaly_alert a JOIN batch b ON b.batch_id = a.batch_id;
GRANT SELECT, INSERT ON v_alerts TO tracefood_app;
GRANT SELECT ON v_alerts TO tracefood_nl_reader;
