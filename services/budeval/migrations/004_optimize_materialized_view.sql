-- ClickHouse Migration: Optimize materialized view to avoid POPULATE on every startup
-- This migration recreates the materialized view without POPULATE to prevent expensive rebuilds

-- Drop the existing materialized view if it exists
DROP VIEW IF EXISTS budeval.model_performance_trends;

-- Recreate without POPULATE - it will start aggregating new data from this point
-- For historical data, we can run a separate one-time backfill if needed
CREATE MATERIALIZED VIEW IF NOT EXISTS budeval.model_performance_trends
ENGINE = AggregatingMergeTree()
ORDER BY (model_name, dataset_name, eval_date)
AS SELECT
    model_name,
    dataset_name,
    toDate(evaluated_at) as eval_date,
    avgState(accuracy) as avg_accuracy,       -- Average accuracy per day
    countState() as eval_count,               -- Number of evaluations per day
    maxState(accuracy) as max_accuracy,       -- Best accuracy per day
    minState(accuracy) as min_accuracy        -- Worst accuracy per day
FROM budeval.dataset_results
GROUP BY model_name, dataset_name, eval_date;

-- One-time backfill for existing data (only if table has data)
-- This is done as a separate INSERT to avoid POPULATE on every startup
INSERT INTO budeval.model_performance_trends
SELECT
    model_name,
    dataset_name,
    toDate(evaluated_at) as eval_date,
    avgState(accuracy) as avg_accuracy,
    countState() as eval_count,
    maxState(accuracy) as max_accuracy,
    minState(accuracy) as min_accuracy
FROM budeval.dataset_results
WHERE evaluated_at < now()  -- Only historical data
GROUP BY model_name, dataset_name, eval_date;
