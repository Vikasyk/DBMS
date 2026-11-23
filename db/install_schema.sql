\set ON_ERROR_STOP on
BEGIN;
\ir 01_schema.sql
\ir 02_integrity.sql
\ir 03_views.sql
\ir 04_functions.sql
\ir 05_roles.sql
\ir 07_lineage_concurrency.sql
\ir 08_numeric_integrity.sql
COMMIT;
