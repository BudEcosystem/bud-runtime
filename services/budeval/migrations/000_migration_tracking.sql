-- ClickHouse Migration: Create migration tracking system
-- This migration must run first to establish the migration tracking table
-- It's idempotent and safe to run multiple times

-- Create migration tracking table to record applied migrations
CREATE TABLE IF NOT EXISTS budeval.schema_migrations (
    version String,           -- Migration version/filename (e.g., '001_initial_schema')
    checksum String,          -- SHA256 hash of migration content for integrity check
    executed_at DateTime64(3) DEFAULT now(),  -- When the migration was applied
    execution_time_ms UInt32, -- How long the migration took to execute
    success Bool DEFAULT 1,   -- Whether migration succeeded
    error_message Nullable(String)  -- Error details if migration failed
) ENGINE = MergeTree()
ORDER BY (version, executed_at)
PRIMARY KEY version
SETTINGS index_granularity = 8192;

-- Create index for quick lookups
CREATE INDEX IF NOT EXISTS idx_migration_version
ON budeval.schema_migrations (version)
TYPE bloom_filter GRANULARITY 1;

-- Insert record for this migration itself (bootstrap)
-- Using INSERT ... SELECT to avoid duplicate entries
INSERT INTO budeval.schema_migrations (version, checksum, execution_time_ms)
SELECT
    '000_migration_tracking' AS version,
    'bootstrap' AS checksum,
    0 AS execution_time_ms
WHERE NOT EXISTS (
    SELECT 1 FROM budeval.schema_migrations
    WHERE version = '000_migration_tracking'
);
