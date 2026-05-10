-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  MASTER MIGRATION : Exécuter ce fichier unique pour créer tout le schéma
--  Ordre d'exécution garanti.
--
--  Usage :
--    psql -U jmj_admin -d jmj_synergie -f 008_master_migration.sql
-- =============================================================================

\set ON_ERROR_STOP on
\set VERBOSITY verbose

BEGIN;

\echo '==> 001 Extensions & Types'
\ir 001_extensions_and_types.sql

\echo '==> 002 Core Tables (Users, Clients, Orders)'
\ir 002_core_tables.sql

\echo '==> 003 Financial Tables (Invoices, Payments, Refunds)'
\ir 003_financial_tables.sql

\echo '==> 004 Documents & Audit'
\ir 004_documents_and_audit.sql

\echo '==> 005 Indexes'
\ir 005_indexes.sql

\echo '==> 006 Functions & Triggers'
\ir 006_functions_and_triggers.sql

\echo '==> 007 Views & RLS'
\ir 007_views_and_rls.sql

COMMIT;

\echo '✓ Schema JMJ Synergie créé avec succès.'
