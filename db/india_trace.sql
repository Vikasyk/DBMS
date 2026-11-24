SET search_path = tracefood;
CREATE UNIQUE INDEX IF NOT EXISTS ix_source_shipment_app_id ON india_source.shipment(india_source.app_id(shipment_id,'S'));
CREATE OR REPLACE VIEW v_shipment_lines AS
SELECT si.shipment_id, sh.shipment_date, sh.source_location, si.batch_id, b.product_name,
       si.quantity_shipped, b.unit, sh.retailer_id, r.retailer_name, r.city AS retailer_city,
       sh.reported_city AS destination_city, sh.reported_state AS destination_state,
       sh.reported_quantity, sh.reported_unit, x.status AS shipment_status,
       x.carrier_name, x.transport_mode, x.actual_delivery_date, x.expected_delivery_date
FROM shipment_item si JOIN shipment sh USING(shipment_id) JOIN batch b USING(batch_id)
JOIN retailer r USING(retailer_id)
LEFT JOIN india_source.shipment x ON india_source.app_id(x.shipment_id,'S')=si.shipment_id;
CREATE OR REPLACE VIEW v_quality_checks AS
SELECT q.check_id,q.batch_id,b.product_name,q.check_date,q.check_stage,q.result,q.contamination_type,q.remarks,
       x.status AS source_result,india_source.app_id(x.facility_id,'PF') AS inspecting_facility,
       pf.facility_name AS inspecting_facility_name,x.inspector_id,x.lab_test_code,
       x.temperature_c,x.humidity_pct,x.ph_level,x.moisture_pct
FROM quality_check q JOIN batch b USING(batch_id) LEFT JOIN india_source.quality_check x
ON india_source.app_id(x.check_id,'QC')=q.check_id LEFT JOIN processing_facility pf
ON pf.facility_id=india_source.app_id(x.facility_id,'PF');
CREATE OR REPLACE VIEW v_batch_facilities AS
SELECT bp.batch_id,b.product_name,bp.facility_id,pf.facility_name,pf.city AS facility_city,
       bp.processing_date,bp.operation_type,pf.state AS facility_state,pf.street,pf.pin_code
FROM batch_processing bp JOIN batch b USING(batch_id) JOIN processing_facility pf USING(facility_id);
