-- ClickHouse Migration: Add status column to evaluation_jobs for lifecycle tracking

-- Add status column after engine for readability
ALTER TABLE budeval.evaluation_jobs
    ADD COLUMN IF NOT EXISTS status LowCardinality(String) AFTER engine;

-- Optional index to speed up filtering by status
CREATE INDEX IF NOT EXISTS idx_status_jobs
ON budeval.evaluation_jobs (status)
TYPE bloom_filter GRANULARITY 1;
