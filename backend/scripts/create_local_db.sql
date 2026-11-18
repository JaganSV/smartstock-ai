-- Creates the local application role and database (ADR-013 native PostgreSQL 16).
-- Run as the PostgreSQL superuser; the password is supplied as a psql variable, never hard-coded:
--   psql -U postgres -h localhost -v ON_ERROR_STOP=1 -v app_password='<value of POSTGRES_PASSWORD in .env>' \
--        -f backend/scripts/create_local_db.sql
-- (`make db-create` does this using .env.) Idempotent. No extensions are created (ADR-014).

SELECT format('CREATE ROLE smartstock LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartstock')
\gexec

SELECT 'CREATE DATABASE smartstock OWNER smartstock'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'smartstock')
\gexec

-- Dedicated database for integration tests (BOB-P1-01). Same owner; no extensions.
SELECT 'CREATE DATABASE smartstock_test OWNER smartstock'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'smartstock_test')
\gexec
