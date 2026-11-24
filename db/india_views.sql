SET search_path = tracefood;
CREATE UNIQUE INDEX IF NOT EXISTS ix_source_batch_app_id ON india_source.batch(india_source.app_id(batch_id,'B'));
CREATE UNIQUE INDEX IF NOT EXISTS ix_source_alert_app_id ON india_source.anomaly_alert(india_source.app_id(alert_id,'A'));
CREATE UNIQUE INDEX IF NOT EXISTS ix_source_check_app_id ON india_source.quality_check(india_source.app_id(check_id,'QC'));
-- Aggregate only complete measurements. Missing line weights cannot be charged to a batch.
CREATE OR REPLACE VIEW v_batch_stock AS
SELECT b.batch_id,b.product_name,b.unit,b.quantity AS initial_quantity,
       u.amount AS quantity_used_as_input,s.amount AS quantity_shipped,
       CASE WHEN u.incomplete OR s.incomplete THEN NULL
            ELSE b.quantity-coalesce(u.amount,0)-coalesce(s.amount,0) END AS available_quantity
FROM batch b
LEFT JOIN LATERAL (SELECT CASE WHEN count(*)=count(quantity_used) THEN coalesce(sum(quantity_used),0) END AS amount,
    count(*)<>count(quantity_used) AS incomplete FROM batch_derivation WHERE input_batch_id=b.batch_id) u ON true
LEFT JOIN LATERAL (SELECT CASE WHEN count(*)=count(quantity_shipped) THEN coalesce(sum(quantity_shipped),0) END AS amount,
    count(*)<>count(quantity_shipped) AS incomplete FROM shipment_item WHERE batch_id=b.batch_id) s ON true;

CREATE OR REPLACE VIEW v_batch_overview AS
SELECT b.batch_id,b.product_name,b.quantity,b.unit,b.production_date,b.expiry_date,b.status,
       CASE WHEN EXISTS (SELECT FROM batch_derivation d WHERE d.output_batch_id=b.batch_id)
            THEN 'PROCESSED' ELSE 'ORIGINAL' END AS batch_type,b.farm_id,f.farm_name,
       b.expiry_date-CURRENT_DATE AS shelf_life_remaining_days,s.quantity_used_as_input,
       s.quantity_shipped,s.available_quantity,x.batch_id AS source_batch_id,x.lot_number,x.category,x.grade
FROM batch b LEFT JOIN farm f USING(farm_id) JOIN v_batch_stock s USING(batch_id)
LEFT JOIN india_source.batch x ON india_source.app_id(x.batch_id,'B')=b.batch_id;

CREATE OR REPLACE VIEW v_shipment_summary AS
SELECT sh.shipment_id,sh.shipment_date,sh.source_location,sh.retailer_id,r.retailer_name,
       coalesce(sh.reported_city,r.city)::varchar(60) AS destination_city,
       coalesce(sh.reported_state,r.state)::varchar(60) AS destination_state,
       sh.transportation_cost,coalesce(sh.reported_unit,b.unit)::varchar(60) AS unit,
       coalesce(sh.reported_quantity,sum(si.quantity_shipped)) AS total_shipment_quantity,
       count(si.batch_id) AS batch_count
FROM shipment sh JOIN retailer r USING(retailer_id) LEFT JOIN shipment_item si USING(shipment_id)
LEFT JOIN batch b USING(batch_id)
GROUP BY sh.shipment_id,r.retailer_id,coalesce(sh.reported_unit,b.unit);

CREATE OR REPLACE VIEW v_alerts AS
SELECT a.alert_id,a.batch_id,b.product_name,a.alert_date,a.alert_type,a.detection_method,a.anomaly_score,
       a.description,a.related_shipment_id,a.related_price_id,a.alert_status,
       x.severity,india_source.app_id(x.check_id,'QC') AS related_check_id,x.action_taken
FROM anomaly_alert a LEFT JOIN batch b USING(batch_id)
LEFT JOIN india_source.anomaly_alert x ON india_source.app_id(x.alert_id,'A')=a.alert_id;

CREATE OR REPLACE VIEW v_quality_checks AS
SELECT q.check_id,q.batch_id,b.product_name,q.check_date,q.check_stage,q.result,q.contamination_type,q.remarks,
       x.status AS source_result,india_source.app_id(x.facility_id,'PF') AS inspecting_facility
FROM quality_check q JOIN batch b USING(batch_id) LEFT JOIN india_source.quality_check x
ON india_source.app_id(x.check_id,'QC')=q.check_id;

-- Speed up date-ordered lists and finding the latest test for a single batch.
CREATE INDEX IF NOT EXISTS ix_india_alert_date ON anomaly_alert(alert_date DESC, alert_id);
CREATE INDEX IF NOT EXISTS ix_india_check_result_date ON quality_check(result,check_date DESC,check_id DESC);
CREATE INDEX IF NOT EXISTS ix_india_shipment_date ON shipment(shipment_date DESC,shipment_id DESC);
CREATE INDEX IF NOT EXISTS ix_india_check_latest ON quality_check(batch_id,check_date DESC,check_id DESC);
CREATE INDEX IF NOT EXISTS ix_india_batch_recent ON batch(production_date DESC,batch_id);
