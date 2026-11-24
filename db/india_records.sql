-- Run only in the new, empty India database before installing operational triggers.
SET search_path = tracefood;
CREATE FUNCTION india_source.app_id(source_id text, prefix text) RETURNS varchar
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT prefix || split_part(source_id, '-', 2)::int::text
$$;
SET search_path = tracefood, india_source;
ALTER TABLE batch DROP CONSTRAINT batch_unit_check, ALTER COLUMN unit TYPE varchar(60),
    DROP CONSTRAINT batch_product_name_check;
ALTER TABLE batch_derivation ALTER COLUMN quantity_used DROP NOT NULL;
ALTER TABLE shipment_item ALTER COLUMN quantity_shipped DROP NOT NULL;
ALTER TABLE batch_processing ALTER COLUMN processing_date DROP NOT NULL, ALTER COLUMN operation_type DROP NOT NULL;
ALTER TABLE quality_check ALTER COLUMN check_stage DROP NOT NULL;
ALTER TABLE shipment ADD COLUMN reported_quantity numeric, ADD COLUMN reported_unit varchar(60),
    ADD COLUMN reported_city varchar(60), ADD COLUMN reported_state varchar(60);
ALTER TABLE anomaly_alert ALTER COLUMN batch_id DROP NOT NULL, DROP CONSTRAINT anomaly_alert_alert_type_check,
    ALTER COLUMN alert_type TYPE varchar(80), DROP CONSTRAINT anomaly_alert_detection_method_check;
ALTER TABLE price_record DROP CONSTRAINT price_record_supply_chain_stage_check;

INSERT INTO tracefood.farm
SELECT app_id(farm_id,'F'), farm_name, street, city, state, pin_code FROM india_source.farm;
INSERT INTO tracefood.farm_contact
SELECT DISTINCT app_id(farm_id,'F'), replace(n,'-','') FROM india_source.farm
CROSS JOIN LATERAL unnest(ARRAY[contact_no,alt_contact_no]) n WHERE n IS NOT NULL;
INSERT INTO tracefood.processing_facility
SELECT app_id(facility_id,'PF'),facility_name,street,city,state,pin_code FROM india_source.processing_facility;
INSERT INTO tracefood.retailer
SELECT app_id(retailer_id,'R'),retailer_name,street,city,state,pin_code FROM india_source.retailer;
INSERT INTO tracefood.retailer_contact
SELECT app_id(retailer_id,'R'),replace(contact_no,'-','') FROM india_source.retailer WHERE contact_no IS NOT NULL;

INSERT INTO tracefood.batch(batch_id,product_name,quantity,unit,production_date,expiry_date,farm_id)
SELECT app_id(batch_id,'B'), product_name,quantity::numeric,CASE unit WHEN 'KG' THEN 'kg' ELSE unit END,
       production_date::date,expiry_date::date,app_id(origin_farm_id,'F') FROM india_source.batch;
INSERT INTO tracefood.batch_derivation
SELECT app_id(batch_id,'B'),app_id(input_batch_id,'B'),NULL::numeric FROM india_source.batch WHERE input_batch_id IS NOT NULL
UNION SELECT app_id(output_batch_id,'B'),app_id(batch_id,'B'),NULL FROM india_source.batch WHERE output_batch_id IS NOT NULL;
INSERT INTO tracefood.batch_processing
SELECT app_id(processed_by_fac_id,'PF'),app_id(batch_id,'B'),NULL,NULL FROM india_source.batch WHERE processed_by_fac_id IS NOT NULL;

INSERT INTO tracefood.quality_check
SELECT app_id(check_id,'QC'),app_id(batch_id,'B'),check_date::date,NULL,
       CASE status WHEN 'Pass' THEN 'PASS' WHEN 'Fail' THEN 'FAIL' ELSE 'INCONCLUSIVE' END,
       nullif(contamination_type,'None'),remarks FROM india_source.quality_check;
INSERT INTO tracefood.shipment
SELECT app_id(shipment_id,'S'),shipment_date::date,concat_ws(', ',source_city,source_state),
       app_id(retailer_id,'R'),transportation_cost_inr::numeric,quantity_shipped::numeric,
       CASE unit WHEN 'KG' THEN 'kg' ELSE unit END,destination_city,destination_state FROM india_source.shipment;
INSERT INTO tracefood.shipment_item
SELECT s.shipment_id,b.batch_id,
       CASE WHEN count(*) OVER (PARTITION BY s.shipment_id)=1 AND b.unit=s.reported_unit THEN s.reported_quantity END
FROM india_source.batch_shipment x
JOIN tracefood.shipment s ON s.shipment_id=app_id(x.shipment_id,'S')
JOIN tracefood.batch b ON b.batch_id=app_id(x.batch_id,'B');
INSERT INTO tracefood.price_record
SELECT app_id(price_id,'P'),app_id(batch_id,'B'),price_date::date,
       CASE supply_chain_stage WHEN 'Farm Gate' THEN 'FARM' WHEN 'Retail' THEN 'RETAIL'
           WHEN 'Wholesale Mandi' THEN 'PROCESSING_WHOLESALE' ELSE supply_chain_stage END,
       selling_price_inr::numeric,cost_per_unit_inr::numeric,market_location FROM india_source.price_record;
INSERT INTO tracefood.anomaly_alert
SELECT app_id(alert_id,'A'),app_id(batch_id,'B'),alert_date::date,alert_type,'WORKBOOK',
       anomaly_score::numeric,description,app_id(triggered_shipment_id,'S'),NULL,
       CASE WHEN resolved::boolean THEN 'REVIEWED' ELSE 'OPEN' END FROM india_source.anomaly_alert;

DO $$
DECLARE t record; maximum bigint;
BEGIN
  FOR t IN SELECT * FROM (VALUES ('farm','farm_id','farm_seq'),('processing_facility','facility_id','facility_seq'),
    ('retailer','retailer_id','retailer_seq'),('batch','batch_id','batch_seq'),('quality_check','check_id','check_seq'),
    ('shipment','shipment_id','shipment_seq'),('price_record','price_id','price_seq'),('anomaly_alert','alert_id','alert_seq'))
    AS v(tbl,col,seq)
  LOOP
    EXECUTE format('SELECT max(substring(%I from ''[0-9]+$'')::bigint) FROM tracefood.%I',t.col,t.tbl) INTO maximum;
    PERFORM setval(('tracefood.'||t.seq)::regclass,maximum);
  END LOOP;
  IF (SELECT count(*) FROM tracefood.shipment_item) <> (SELECT count(*) FROM india_source.batch_shipment) THEN
    RAISE EXCEPTION 'Unmatched batch or shipment in workbook bridge';
  END IF;
END $$;
