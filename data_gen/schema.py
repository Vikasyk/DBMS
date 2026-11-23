TABLE_COLUMNS = {
    "farm": ("farm_id", "farm_name", "street", "city", "state", "pin_code"),
    "farm_contact": ("farm_id", "contact_no"),
    "processing_facility": ("facility_id", "facility_name", "street", "city", "state", "pin_code"),
    "retailer": ("retailer_id", "retailer_name", "street", "city", "state", "pin_code"),
    "retailer_contact": ("retailer_id", "contact_no"),
    "batch": ("batch_id", "product_name", "quantity", "unit", "production_date", "expiry_date", "status", "farm_id"),
    "batch_derivation": ("output_batch_id", "input_batch_id", "quantity_used"),
    "batch_processing": ("facility_id", "batch_id", "processing_date", "operation_type"),
    "shipment": ("shipment_id", "shipment_date", "source_location", "retailer_id", "transportation_cost"),
    "shipment_item": ("shipment_id", "batch_id", "quantity_shipped"),
    "quality_check": ("check_id", "batch_id", "check_date", "check_stage", "result", "contamination_type", "remarks"),
    "price_record": ("price_id", "batch_id", "price_date", "supply_chain_stage", "selling_price", "cost_per_unit",
                     "market_location"),
    "anomaly_alert": ("alert_id", "batch_id", "alert_date", "alert_type", "detection_method", "anomaly_score",
                      "description", "related_shipment_id", "related_price_id", "alert_status"),
}

SEQUENCES = {
    "farm_seq": ("farm", "farm_id", "F", 1),
    "facility_seq": ("processing_facility", "facility_id", "PF", 1),
    "retailer_seq": ("retailer", "retailer_id", "R", 1),
    "batch_seq": ("batch", "batch_id", "B", 101),
    "check_seq": ("quality_check", "check_id", "QC", 1),
    "shipment_seq": ("shipment", "shipment_id", "S", 501),
    "price_seq": ("price_record", "price_id", "P", 1),
    "alert_seq": ("anomaly_alert", "alert_id", "A", 1),
}

LABEL_COLUMNS = ("entity", "id", "label", "parameters")
