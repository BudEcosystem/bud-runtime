-- ClickHouse Migration: Initial Schema for budeval Results Storage
-- This file creates the initial database schema for storing evaluation results in ClickHouse
-- Run with: clickhouse-client --queries-file migrations/001_initial_schema.sql

-- Create database
CREATE DATABASE IF NOT EXISTS budeval;

-- Main evaluation jobs table (ReplacingMergeTree for updates)
-- Optimized ordering key for time-series queries by model
CREATE TABLE IF NOT EXISTS budeval.evaluation_jobs (
    job_id String,
    model_name LowCardinality(String),  -- Low cardinality optimization for better compression
    engine LowCardinality(String),      -- opencompass, etc.
    job_start_time DateTime64(3),       -- Millisecond precision
    job_end_time DateTime64(3),
    job_duration_seconds Float32,
    overall_accuracy Float32,
    total_datasets UInt16,
    total_examples UInt32,
    total_correct UInt32,
    extracted_at DateTime64(3),
    created_at DateTime64(3) DEFAULT now(),
    updated_at DateTime64(3) DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)  -- Use updated_at as version column
ORDER BY (model_name, job_start_time, job_id)  -- Optimized for queries by model and time
PRIMARY KEY (model_name, job_start_time)
PARTITION BY toYYYYMM(job_start_time)  -- Monthly partitions for efficient data management
SETTINGS index_granularity = 8192;

-- Dataset-level results (wide denormalized table for performance)
CREATE TABLE IF NOT EXISTS budeval.dataset_results (
    job_id String,
    model_name LowCardinality(String),
    dataset_name LowCardinality(String),  -- gsm8k, hellaswag, etc.
    accuracy Float32,
    total_examples UInt32,
    correct_examples UInt32,
    evaluated_at DateTime64(3),
    metadata String CODEC(ZSTD(3)),  -- JSON metadata with high compression
    created_at DateTime64(3) DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (model_name, dataset_name, evaluated_at, job_id)
PRIMARY KEY (model_name, dataset_name, evaluated_at)
PARTITION BY toYYYYMM(evaluated_at)
SETTINGS index_granularity = 8192;

-- Individual predictions (heavily compressed for text storage)
-- This table can grow very large, so we use aggressive compression and TTL
CREATE TABLE IF NOT EXISTS budeval.predictions (
    job_id String,
    model_name LowCardinality(String),
    dataset_name LowCardinality(String),
    example_id String,                          -- example identifier within dataset
    prediction_text String CODEC(ZSTD(3)),     -- Model's complete reasoning and output
    origin_prompt String CODEC(ZSTD(3)),       -- Original question with few-shot examples
    model_answer String CODEC(ZSTD(3)),        -- Extracted model answer
    correct_answer String CODEC(ZSTD(3)),      -- Gold standard answer
    is_correct Bool,                            -- Whether prediction was correct
    evaluated_at DateTime64(3),
    created_at DateTime64(3) DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (model_name, dataset_name, evaluated_at, job_id, example_id)
PRIMARY KEY (model_name, dataset_name, evaluated_at)
PARTITION BY toYYYYMM(evaluated_at)
TTL toDate(evaluated_at) + INTERVAL 6 MONTH DELETE  -- Auto-cleanup old predictions after 6 months
SETTINGS index_granularity = 8192;

-- Materialized view for model performance trends
-- Pre-aggregates common analytical queries for instant results
CREATE MATERIALIZED VIEW IF NOT EXISTS budeval.model_performance_trends
ENGINE = AggregatingMergeTree()
ORDER BY (model_name, dataset_name, eval_date)
POPULATE  -- Populate with existing data
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

-- Bloom filter indexes for fast job lookups
-- These enable efficient filtering without full table scans
CREATE INDEX IF NOT EXISTS idx_job_id_jobs 
ON budeval.evaluation_jobs (job_id) 
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_job_id_results 
ON budeval.dataset_results (job_id) 
TYPE bloom_filter GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_job_id_predictions 
ON budeval.predictions (job_id) 
TYPE bloom_filter GRANULARITY 1;

-- Minmax indexes for efficient date range queries
CREATE INDEX IF NOT EXISTS idx_evaluated_at_results 
ON budeval.dataset_results (evaluated_at) 
TYPE minmax GRANULARITY 1;

CREATE INDEX IF NOT EXISTS idx_evaluated_at_predictions 
ON budeval.predictions (evaluated_at) 
TYPE minmax GRANULARITY 1;

-- Set compression settings at database level
-- ALTER DATABASE budeval MODIFY SETTING compress_block_size = 65536;
-- ALTER DATABASE budeval MODIFY SETTING compress_method = 'zstd';

-- Create user for application access (optional - adjust as needed)
-- CREATE USER IF NOT EXISTS budeval_app IDENTIFIED BY 'your_password_here';
-- GRANT SELECT, INSERT, ALTER ON budeval.* TO budeval_app;

-- Display table information
SELECT 
    database,
    table,
    engine,
    total_rows,
    total_bytes,
    formatReadableSize(total_bytes) as size
FROM system.tables 
WHERE database = 'budeval'
ORDER BY total_bytes DESC;

-- Show partition information
SELECT 
    database,
    table,
    partition,
    rows,
    bytes_on_disk,
    formatReadableSize(bytes_on_disk) as size_on_disk
FROM system.parts 
WHERE database = 'budeval' AND active = 1
ORDER BY bytes_on_disk DESC;
