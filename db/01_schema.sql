-- =====================================================================
-- TraceFood  |  01_schema.sql  |  PostgreSQL 16+
-- Tables, domains, keys and single-table CHECK constraints.
-- Mapping: 8 ER entities + 2 multivalued-attribute tables + 3 M:N tables
-- =====================================================================
CREATE SCHEMA tracefood;
SET search_path = tracefood;

-- ---------- Domains (reusable column types with built-in rules) ----------
CREATE DOMAIN qty_t   AS NUMERIC(12,3) CHECK (VALUE > 0);
CREATE DOMAIN money_t AS NUMERIC(12,2) CHECK (VALUE >= 0);
CREATE DOMAIN pin_t   AS CHAR(6)       CHECK (VALUE ~ '^[1-9][0-9]{5}$');
CREATE DOMAIN phone_t AS VARCHAR(15)   CHECK (VALUE ~ '^\+?[0-9]{10,14}$');

-- ---------- Sequences used to build readable IDs (F01, B101, S501 ...) ----------
CREATE SEQUENCE farm_seq     START 1;
CREATE SEQUENCE facility_seq START 1;
CREATE SEQUENCE retailer_seq START 1;
CREATE SEQUENCE batch_seq    START 101;
CREATE SEQUENCE check_seq    START 1;
CREATE SEQUENCE shipment_seq START 501;
CREATE SEQUENCE price_seq    START 1;
CREATE SEQUENCE alert_seq    START 1;

-- ---------- Entity 1: FARM (Location = composite, Contact_No = multivalued) ----------
-- Master-data IDs have at least two digits and keep longer sequence values intact.
CREATE TABLE farm (
    farm_id    VARCHAR(10)  PRIMARY KEY
               DEFAULT ('F' || to_char(nextval('tracefood.farm_seq'), 'FM999999900'))
               CHECK (farm_id ~ '^F[0-9]+$'),
    farm_name  VARCHAR(100) NOT NULL,
    street     VARCHAR(150),
    city       VARCHAR(60)  NOT NULL,
    state      VARCHAR(60)  NOT NULL,
    pin_code   pin_t        NOT NULL
);
CREATE TABLE farm_contact (                       -- multivalued attribute
    farm_id    VARCHAR(10) REFERENCES farm(farm_id) ON DELETE CASCADE,
    contact_no phone_t,
    PRIMARY KEY (farm_id, contact_no)
);

-- ---------- Entity 3: PROCESSING_FACILITY ----------
CREATE TABLE processing_facility (
    facility_id   VARCHAR(10)  PRIMARY KEY
                  DEFAULT ('PF' || to_char(nextval('tracefood.facility_seq'), 'FM99999900'))
                  CHECK (facility_id ~ '^PF[0-9]+$'),
    facility_name VARCHAR(100) NOT NULL,
    street        VARCHAR(150),
    city          VARCHAR(60)  NOT NULL,
    state         VARCHAR(60)  NOT NULL,
    pin_code      pin_t        NOT NULL
);

-- ---------- Entity 5: RETAILER ----------
CREATE TABLE retailer (
    retailer_id   VARCHAR(10)  PRIMARY KEY
                  DEFAULT ('R' || to_char(nextval('tracefood.retailer_seq'), 'FM999999900'))
                  CHECK (retailer_id ~ '^R[0-9]+$'),
    retailer_name VARCHAR(100) NOT NULL,
    street        VARCHAR(150),
    city          VARCHAR(60)  NOT NULL,
    state         VARCHAR(60)  NOT NULL,
    pin_code      pin_t        NOT NULL
);
CREATE TABLE retailer_contact (                   -- multivalued attribute
    retailer_id VARCHAR(10) REFERENCES retailer(retailer_id) ON DELETE CASCADE,
    contact_no  phone_t,
    PRIMARY KEY (retailer_id, contact_no)
);

-- ---------- Entity 2: BATCH  (+ Produces: FARM 1:N BATCH via nullable farm_id) ----------
-- quantity = INITIAL recorded quantity; it is never decremented.
-- Available quantity and Shelf_Life_Remaining are DERIVED (see 03_views.sql).
-- farm_id NOT NULL  <=> ORIGINAL batch;  farm_id NULL <=> PROCESSED batch (must have inputs).
CREATE TABLE batch (
    batch_id        VARCHAR(12) PRIMARY KEY
                    DEFAULT ('B' || nextval('tracefood.batch_seq'))
                    CHECK (batch_id ~ '^B[0-9]+$'),
    product_name    VARCHAR(60) NOT NULL
                    CHECK (product_name = initcap(btrim(product_name))),
    quantity        qty_t       NOT NULL,
    unit            VARCHAR(5)  NOT NULL CHECK (unit IN ('kg', 'L', 'unit')),
    production_date DATE        NOT NULL,
    expiry_date     DATE        NOT NULL,
    status          VARCHAR(12) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'ON_HOLD', 'RECALLED', 'CLOSED')),
    farm_id         VARCHAR(10) REFERENCES farm(farm_id) ON DELETE RESTRICT,
    CONSTRAINT chk_batch_dates CHECK (expiry_date >= production_date)
);

-- ---------- Derived_From: recursive M:N on BATCH (relationship attr Quantity_Used) ----------
-- quantity_used is expressed in the INPUT batch's unit.
CREATE TABLE batch_derivation (
    output_batch_id VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    input_batch_id  VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    quantity_used   qty_t       NOT NULL,
    PRIMARY KEY (output_batch_id, input_batch_id),
    CONSTRAINT chk_no_self_derivation CHECK (output_batch_id <> input_batch_id)
);

-- ---------- Processes: PROCESSING_FACILITY M:N BATCH ----------
-- v2: relationship attributes processing_date + operation_type added (see change log).
CREATE TABLE batch_processing (
    facility_id     VARCHAR(10) NOT NULL REFERENCES processing_facility(facility_id) ON DELETE RESTRICT,
    batch_id        VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    processing_date DATE        NOT NULL,
    operation_type  VARCHAR(15) NOT NULL
                    CHECK (operation_type IN ('CLEANING', 'SORTING', 'PULPING', 'MIXING',
                                              'PACKAGING', 'COLD_STORAGE', 'OTHER')),
    PRIMARY KEY (facility_id, batch_id)
);

-- ---------- Entity 6: QUALITY_CHECK  (Undergoes: BATCH 1:N QUALITY_CHECK) ----------
CREATE TABLE quality_check (
    check_id           VARCHAR(12) PRIMARY KEY
                       DEFAULT ('QC' || nextval('tracefood.check_seq')),
    batch_id           VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    check_date         DATE        NOT NULL,
    check_stage        VARCHAR(12) NOT NULL                 -- v2 recommended attribute
                       CHECK (check_stage IN ('FARM', 'PROCESSING', 'DISTRIBUTION', 'RETAIL')),
    result             VARCHAR(12) NOT NULL CHECK (result IN ('PASS', 'FAIL', 'INCONCLUSIVE')),
    contamination_type VARCHAR(40),
    remarks            TEXT,
    CONSTRAINT chk_pass_has_no_contaminant CHECK (result <> 'PASS' OR contamination_type IS NULL),
    CONSTRAINT chk_fail_names_contaminant  CHECK (result <> 'FAIL' OR contamination_type IS NOT NULL)
);

-- ---------- Entity 4: SHIPMENT  (Receives: RETAILER 1:N SHIPMENT) ----------
-- v2: the free-text Destination attribute is replaced by retailer_id (single source of truth).
CREATE TABLE shipment (
    shipment_id         VARCHAR(12) PRIMARY KEY
                        DEFAULT ('S' || nextval('tracefood.shipment_seq')),
    shipment_date       DATE         NOT NULL,
    source_location     VARCHAR(150) NOT NULL,
    retailer_id         VARCHAR(10)  NOT NULL REFERENCES retailer(retailer_id) ON DELETE RESTRICT,
    transportation_cost money_t      NOT NULL
);

-- ---------- Included_In: BATCH M:N SHIPMENT (relationship attr Quantity_Shipped) ----------
CREATE TABLE shipment_item (
    shipment_id      VARCHAR(12) NOT NULL REFERENCES shipment(shipment_id) ON DELETE RESTRICT,
    batch_id         VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    quantity_shipped qty_t       NOT NULL,           -- in the batch's unit
    PRIMARY KEY (shipment_id, batch_id)
);

-- ---------- Entity 7: PRICE_RECORD  (Has: BATCH 1:N PRICE_RECORD) ----------
-- selling_price and cost_per_unit are per ONE unit of the batch's unit (e.g. Rs/kg).
CREATE TABLE price_record (
    price_id           VARCHAR(12) PRIMARY KEY
                       DEFAULT ('P' || nextval('tracefood.price_seq')),
    batch_id           VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    price_date         DATE        NOT NULL,
    supply_chain_stage VARCHAR(20) NOT NULL
                       CHECK (supply_chain_stage IN ('FARM', 'PROCESSING_WHOLESALE', 'RETAIL')),
    selling_price      money_t     NOT NULL,
    cost_per_unit      money_t,                       -- may be unknown
    market_location    VARCHAR(60) NOT NULL
);

-- ---------- Entity 8: ANOMALY_ALERT  (Triggers: BATCH 1:N ANOMALY_ALERT) ----------
-- v2: detection_method (required), related_shipment_id / related_price_id and
--     alert_status (recommended) added. anomaly_score is NOT a fraud probability.
CREATE TABLE anomaly_alert (
    alert_id            VARCHAR(12) PRIMARY KEY
                        DEFAULT ('A' || nextval('tracefood.alert_seq')),
    batch_id            VARCHAR(12) NOT NULL REFERENCES batch(batch_id) ON DELETE RESTRICT,
    alert_date          DATE        NOT NULL DEFAULT CURRENT_DATE,
    alert_type          VARCHAR(20) NOT NULL
                        CHECK (alert_type IN ('MASS_BALANCE', 'OVER_ALLOCATION', 'EXPIRED_SHIPMENT',
                                              'YIELD_OUTLIER', 'PRICE_OUTLIER')),
    detection_method    VARCHAR(12) NOT NULL CHECK (detection_method IN ('RULE', 'STATISTICAL', 'ML')),
    anomaly_score       NUMERIC(10,4) CHECK (anomaly_score >= 0),
    description         TEXT        NOT NULL,
    related_shipment_id VARCHAR(12) REFERENCES shipment(shipment_id) ON DELETE RESTRICT,
    related_price_id    VARCHAR(12) REFERENCES price_record(price_id) ON DELETE RESTRICT,
    alert_status        VARCHAR(10) NOT NULL DEFAULT 'OPEN'
                        CHECK (alert_status IN ('OPEN', 'REVIEWED', 'DISMISSED'))
);
