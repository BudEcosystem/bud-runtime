-- ClickHouse Migration: Add evaluation_id field to store the original request UUID
-- This migration adds evaluation_id as a separate field from job_id (Kubernetes job ID)
-- evaluation_id = UUID from StartEvaluationRequest
-- job_id = Kubernetes job ID (e.g., opencompass-<uuid>)

-- Add evaluation_id to evaluation_jobs table
ALTER TABLE budeval.evaluation_jobs
ADD COLUMN IF NOT EXISTS evaluation_id Nullable(String) AFTER job_id;

-- Add evaluation_id to dataset_results table
ALTER TABLE budeval.dataset_results
ADD COLUMN IF NOT EXISTS evaluation_id Nullable(String) AFTER job_id;

-- Add evaluation_id to predictions table
ALTER TABLE budeval.predictions
ADD COLUMN IF NOT EXISTS evaluation_id Nullable(String) AFTER job_id;

-- Add bloom filter index for evaluation_id lookups on evaluation_jobs
CREATE INDEX IF NOT EXISTS idx_evaluation_id_jobs
ON budeval.evaluation_jobs (evaluation_id)
TYPE bloom_filter GRANULARITY 1;

-- Add bloom filter index for evaluation_id lookups on dataset_results
CREATE INDEX IF NOT EXISTS idx_evaluation_id_results
ON budeval.dataset_results (evaluation_id)
TYPE bloom_filter GRANULARITY 1;

-- Add bloom filter index for evaluation_id lookups on predictions
CREATE INDEX IF NOT EXISTS idx_evaluation_id_predictions
ON budeval.predictions (evaluation_id)
TYPE bloom_filter GRANULARITY 1;

-- Display table information after migration
SELECT
    database,
    table,
    name as column_name,
    type as column_type,
    position
FROM system.columns
WHERE database = 'budeval'
  AND table IN ('evaluation_jobs', 'dataset_results', 'predictions')
  AND name IN ('job_id', 'evaluation_id', 'experiment_id')
ORDER BY table, position;
