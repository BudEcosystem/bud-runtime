-- Migration script to add authentication metadata columns to ModelInferenceDetails table
-- This adds api_key_id, user_id, and api_key_project_id for tracking API usage

-- Add new columns to ModelInferenceDetails table
ALTER TABLE ModelInferenceDetails
ADD COLUMN IF NOT EXISTS api_key_id UUID,
ADD COLUMN IF NOT EXISTS user_id UUID,
ADD COLUMN IF NOT EXISTS api_key_project_id UUID;

-- Add indexes for efficient querying by api_key_id
ALTER TABLE ModelInferenceDetails
ADD INDEX IF NOT EXISTS idx_api_key_id (api_key_id) TYPE minmax GRANULARITY 1;

-- Add index for efficient querying by user_id
ALTER TABLE ModelInferenceDetails
ADD INDEX IF NOT EXISTS idx_user_id (user_id) TYPE minmax GRANULARITY 1;

-- Add index for efficient querying by api_key_project_id
ALTER TABLE ModelInferenceDetails
ADD INDEX IF NOT EXISTS idx_api_key_project_id (api_key_project_id) TYPE minmax GRANULARITY 1;

-- Verify the changes
SELECT 'ModelInferenceDetails table updated with authentication metadata columns' as status;
