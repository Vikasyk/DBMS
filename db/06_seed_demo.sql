-- =====================================================================
-- TraceFood  |  06_seed_demo.sql  — small, hand-made DEMO FIXTURE (synthetic)
-- Mirrors the examples in the specification (B101, B102 -> B103; S501, S502)
-- and plants one example of each rule-based anomaly. Used by the test suite.
-- =====================================================================
SET search_path = tracefood;
BEGIN;   -- one transaction: the deferred origin check runs at COMMIT

INSERT INTO farm VALUES
 ('F01', 'Green Valley Farm',      'Survey No. 12, Narasapura', 'Kolar',          'Karnataka', '563101'),
 ('F02', 'Sunrise Organic Farm',   'Nandi Road',                'Chikkaballapur', 'Karnataka', '562101'),
 ('F03', 'Deccan Onion Growers',   'Holalkere Road',            'Chitradurga',    'Karnataka', '577501');
INSERT INTO farm_contact VALUES ('F01', '9845012345'), ('F01', '9845098765'),
                                ('F02', '9900011122'), ('F03', '9480033344');

INSERT INTO processing_facility VALUES
 ('PF01', 'FreshPro Foods',      'Peenya Industrial Area', 'Bengaluru', 'Karnataka', '560058'),
 ('PF02', 'AgroPack Industries', 'Hebbal Industrial Area', 'Mysuru',    'Karnataka', '570016');

INSERT INTO retailer VALUES
 ('R01', 'DailyMart Jayanagar', '4th Block, Jayanagar', 'Bengaluru', 'Karnataka', '560041'),
 ('R02', 'City Fresh Stores',   'Sayyaji Rao Road',     'Mysuru',    'Karnataka', '570001'),
 ('R03', 'GreenBasket',         'Vidyanagar',           'Hubballi',  'Karnataka', '580020');
INSERT INTO retailer_contact VALUES ('R01', '08026630000'), ('R02', '08212420000'),
                                    ('R03', '08362370000');

-- Original (farm) batches
INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date, farm_id) VALUES
 ('B101', 'Tomato', 100, 'kg', '2026-01-05', '2026-01-19', 'F01'),
 ('B102', 'Tomato',  50, 'kg', '2026-01-06', '2026-01-20', 'F02'),
 ('B104', 'Onion',  120, 'kg', '2026-01-04', '2026-02-15', 'F03'),
 ('B106', 'Tomato',  50, 'kg', '2026-01-07', '2026-01-21', 'F01'),
 ('B108', 'Tomato', 200, 'kg', '2026-01-05', '2026-01-19', 'F02');

-- Processed batches (farm_id NULL) + lineage + Processes rows
INSERT INTO batch (batch_id, product_name, quantity, unit, production_date, expiry_date) VALUES
 ('B103', 'Tomato Puree',        80, 'kg', '2026-01-08', '2026-04-08'),
 ('B105', 'Tomato Onion Masala', 30, 'kg', '2026-01-12', '2026-03-12'),
 ('B107', 'Tomato Puree',        95, 'kg', '2026-01-09', '2026-04-09');   -- planted mass-balance anomaly
INSERT INTO batch_derivation VALUES
 ('B103', 'B101', 60), ('B103', 'B102', 20),     -- spec example: 60 + 20 -> 80
 ('B105', 'B103', 10), ('B105', 'B104', 20),
 ('B107', 'B106', 50), ('B107', 'B102', 30);     -- 80 in -> 95 out
INSERT INTO batch_processing VALUES
 ('PF01', 'B103', '2026-01-08', 'PULPING'),
 ('PF02', 'B105', '2026-01-12', 'MIXING'),
 ('PF01', 'B107', '2026-01-09', 'PULPING'),
 ('PF01', 'B101', '2026-01-07', 'CLEANING');      -- handling without a new identity

-- Shipments (destination = retailer)
INSERT INTO shipment VALUES
 ('S501', '2026-01-10', 'FreshPro Foods, Bengaluru',            'R01', 1500),
 ('S502', '2026-01-11', 'FreshPro Foods, Bengaluru',            'R02', 2200),
 ('S503', '2026-01-15', 'AgroPack Industries, Mysuru',          'R03', 3400),
 ('S504', '2026-01-07', 'Sunrise Organic Farm, Chikkaballapur', 'R01',  900),
 ('S505', '2026-01-25', 'Sunrise Organic Farm, Chikkaballapur', 'R03', 2600);
INSERT INTO shipment_item VALUES
 ('S501', 'B103', 50), ('S501', 'B104', 30),
 ('S502', 'B103', 20),
 ('S503', 'B104', 80), ('S503', 'B105', 25),     -- B104 outflows reach 130 > 120 (planted)
 ('S504', 'B108', 120),
 ('S505', 'B108', 40);                           -- after B108 expiry (planted)

-- Quality checks
INSERT INTO quality_check VALUES
 ('QC1', 'B101', '2026-01-05', 'FARM',       'PASS', NULL,     NULL),
 ('QC2', 'B102', '2026-01-06', 'FARM',       'PASS', NULL,     NULL),
 ('QC3', 'B103', '2026-01-09', 'PROCESSING', 'PASS', NULL,     NULL),
 ('QC4', 'B103', '2026-01-14', 'RETAIL',     'FAIL', 'E. coli',
         'Sample taken at DailyMart Jayanagar (R01)'),
 ('QC5', 'B107', '2026-01-10', 'PROCESSING', 'PASS', NULL,     NULL);

-- Price observations (Rs per kg; illustrative)
INSERT INTO price_record VALUES
 ('P1',  'B108', '2026-01-05', 'FARM',                 20.00, 14.00, 'Chikkaballapur'),
 ('P2',  'B108', '2026-01-06', 'PROCESSING_WHOLESALE', 28.00, 22.00, 'Bengaluru'),
 ('P3',  'B108', '2026-01-07', 'RETAIL',               40.00, 31.00, 'Bengaluru'),
 ('P4',  'B108', '2026-01-09', 'RETAIL',               42.00, 31.00, 'Bengaluru'),
 ('P5',  'B108', '2026-01-11', 'RETAIL',               41.00, 31.00, 'Bengaluru'),
 ('P6',  'B108', '2026-01-13', 'RETAIL',               92.00, 31.00, 'Bengaluru'),   -- planted spike
 ('P7',  'B101', '2026-01-05', 'FARM',                 19.50, 14.00, 'Kolar'),
 ('P8',  'B106', '2026-01-07', 'FARM',                 21.00, 14.50, 'Kolar'),
 ('P9',  'B103', '2026-01-08', 'PROCESSING_WHOLESALE', 85.00, 60.00, 'Bengaluru'),
 ('P10', 'B107', '2026-01-09', 'PROCESSING_WHOLESALE', 86.00, 61.00, 'Bengaluru');

COMMIT;

-- Move sequences past the hand-written IDs so new rows get fresh IDs
SELECT setval('farm_seq', 3), setval('facility_seq', 2), setval('retailer_seq', 3),
       setval('batch_seq', 108), setval('check_seq', 5), setval('shipment_seq', 505),

       setval('price_seq', 10);
