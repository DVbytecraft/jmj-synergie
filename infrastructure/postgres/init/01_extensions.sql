-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Set locale & timezone
SET timezone = 'UTC';

-- Partial index for non-deleted records (performance optimization)
-- These are created after Alembic migrations run
