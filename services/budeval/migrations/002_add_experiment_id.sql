-- ClickHouse Migration: Add experiment_id column for tracking evaluations back to experiments
-- This migration adds experiment_id to evaluation tables to track which experiment triggered the evaluation

-- Add experiment_id column to evaluation_jobs table
ALTER TABLE budeval.evaluation_jobs
    ADD COLUMN IF NOT EXISTS experiment_id Nullable(String) AFTER job_id;

-- Add experiment_id column to dataset_results table
ALTER TABLE budeval.dataset_results
    ADD COLUMN IF NOT EXISTS experiment_id Nullable(String) AFTER job_id;

-- Add experiment_id column to predictions table
ALTER TABLE budeval.predictions
    ADD COLUMN IF NOT EXISTS experiment_id Nullable(String) AFTER job_id;

-- Create index for efficient experiment_id lookups
CREATE INDEX IF NOT EXISTS idx_experiment_id_jobs
ON budeval.evaluation_jobs (experiment_id)
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_experiment_id_results
ON budeval.dataset_results (experiment_id)
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_experiment_id_predictions
ON budeval.predictions (experiment_id)
TYPE bloom_filter GRANULARITY 1;
