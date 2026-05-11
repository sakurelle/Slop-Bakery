\set ON_ERROR_STOP on

\i 00_drop.sql
\i 01_schema.sql
\i 02_constraints.sql
\i 03_indexes.sql
\i ../security/04_security_roles.sql
\i ../audit/05_audit.sql
\i ../seed/06_seed.sql
\i ../checks/07_test_queries.sql
