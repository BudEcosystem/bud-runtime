-- ClickHouse Migration: Fix evaluation_jobs table deduplication issue
-- The original table used ORDER BY (model_name, job_start_time, job_id) which prevented proper deduplication
-- This migration recreates the table with ORDER BY (job_id) for correct ReplacingMergeTree behavior

-- Step 1: Create new table with corrected structure
CREATE TABLE IF NOT EXISTS budeval.evaluation_jobs_new (
    job_id String,
    experiment_id Nullable(String),
    model_name LowCardinality(String),
    engine LowCardinality(String),
    status LowCardinality(String),
    job_start_time DateTime64(3),
    job_end_time DateTime64(3),
    job_duration_seconds Float32,
    overall_accuracy Float32,
    total_datasets UInt16,
    total_examples UInt32,
    total_correct UInt32,
    extracted_at DateTime64(3),
    created_at DateTime64(3) DEFAULT now(),
    updated_at DateTime64(3) DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (job_id)  -- Key change: Only job_id for proper deduplication
PARTITION BY toYYYYMM(job_start_time)
SETTINGS index_granularity = 8192;

-- Step 2: Copy deduplicated data from old table
-- This query will keep only the latest version of each job_id
INSERT INTO budeval.evaluation_jobs_new
SELECT
    job_id,
    experiment_id,
    model_name,
    engine,
    status,
    job_start_time,
    job_end_time,
    job_duration_seconds,
    overall_accuracy,
    total_datasets,
    total_examples,
    total_correct,
    extracted_at,
    created_at,
    updated_at
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY updated_at DESC) as rn
    FROM budeval.evaluation_jobs
) WHERE rn = 1;

-- Step 3: Recreate indexes on new table
CREATE INDEX IF NOT EXISTS idx_job_id_jobs_new
ON budeval.evaluation_jobs_new (job_id)
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_experiment_id_jobs_new
ON budeval.evaluation_jobs_new (experiment_id)
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_status_jobs_new
ON budeval.evaluation_jobs_new (status)
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_model_name_jobs_new
ON budeval.evaluation_jobs_new (model_name)
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_job_start_time_jobs_new
ON budeval.evaluation_jobs_new (job_start_time)
TYPE minmax GRANULARITY 1;

-- Step 4: Atomic table swap
RENAME TABLE budeval.evaluation_jobs TO budeval.evaluation_jobs_old;
RENAME TABLE budeval.evaluation_jobs_new TO budeval.evaluation_jobs;

-- Step 5: Drop old table (commented out for safety - run manually after verification)
-- DROP TABLE IF EXISTS budeval.evaluation_jobs_old;

-- Optimization: Force merge to deduplicate immediately
OPTIMIZE TABLE budeval.evaluation_jobs FINAL;
