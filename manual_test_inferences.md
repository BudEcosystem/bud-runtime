# Manual Testing Guide for Inference Request/Prompt Listing Feature

This guide provides step-by-step instructions for manually testing the inference request/prompt listing feature.

## Prerequisites

1. All services should be running:
   - BudMetrics (port 8004)
   - BudApp (port 8000) 
   - BudAdmin (port 8007)
   - ClickHouse database
   - PostgreSQL database

2. You should have a valid user account and authentication token.

## Test Data Setup

### 1. Insert Sample Data into ClickHouse

First, connect to ClickHouse and run these queries to insert test data:

```sql
-- Insert sample model inference data
INSERT INTO ModelInference (
    inference_id, timestamp, project_id, endpoint_id, model_id,
    model_name, model_provider, is_chat, is_success,
    input_tokens, output_tokens, response_time_ms, cost, cached, ip_address
) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', now() - interval 1 hour, 
     'proj-123', 'ep-456', 'model-789',
     'gpt-4', 'openai', true, true,
     150, 250, 1234, 0.0045, false, '192.168.1.100'),
    ('550e8400-e29b-41d4-a716-446655440002', now() - interval 2 hour,
     'proj-123', 'ep-456', 'model-789',
     'gpt-3.5-turbo', 'openai', true, true,
     100, 180, 567, 0.0028, true, '192.168.1.101'),
    ('550e8400-e29b-41d4-a716-446655440003', now() - interval 3 hour,
     'proj-123', 'ep-457', 'model-790',
     'claude-3-opus', 'anthropic', true, false,
     200, 0, 5000, 0.0, false, '192.168.1.102');

-- Insert corresponding chat data
INSERT INTO ChatInference (
    inference_id, timestamp, system_prompt, messages, output, finish_reason
) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', now() - interval 1 hour,
     'You are a helpful AI assistant.',
     '[{"role":"user","content":"What is the capital of France?"},{"role":"assistant","content":"The capital of France is Paris."}]',
     'The capital of France is Paris.',
     'stop'),
    ('550e8400-e29b-41d4-a716-446655440002', now() - interval 2 hour,
     NULL,
     '[{"role":"user","content":"Explain quantum computing"},{"role":"assistant","content":"Quantum computing uses quantum bits..."}]',
     'Quantum computing uses quantum bits...',
     'stop'),
    ('550e8400-e29b-41d4-a716-446655440003', now() - interval 3 hour,
     'You are an expert programmer.',
     '[{"role":"user","content":"Write a Python function"},{"role":"assistant","content":""}]',
     '',
     'error');

-- Insert sample details
INSERT INTO ModelInferenceDetails (
    inference_id, timestamp, raw_request, raw_response, processing_time_ms
) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', now() - interval 1 hour,
     '{"model":"gpt-4","messages":[{"role":"user","content":"What is the capital of France?"}],"temperature":0.7}',
     '{"id":"chatcmpl-123","object":"chat.completion","created":1234567890,"model":"gpt-4","choices":[{"index":0,"message":{"role":"assistant","content":"The capital of France is Paris."},"finish_reason":"stop"}],"usage":{"prompt_tokens":150,"completion_tokens":250,"total_tokens":400}}',
     1000);

-- Insert sample feedback
INSERT INTO ModelInferenceFeedback (
    feedback_id, inference_id, timestamp, feedback_type, metric_name, value
) VALUES
    ('fb-001', '550e8400-e29b-41d4-a716-446655440001', now() - interval 30 minute,
     'boolean', 'helpful', 1),
    ('fb-002', '550e8400-e29b-41d4-a716-446655440001', now() - interval 20 minute,
     'float', 'quality_rating', 4.5),
    ('fb-003', '550e8400-e29b-41d4-a716-446655440001', now() - interval 10 minute,
     'comment', 'user_comment', 'Great response, very helpful!');
```

### 2. Create Test Entities in PostgreSQL

Create test project, endpoint, and model if they don't exist:

```sql
-- Insert test project
INSERT INTO projects (id, name, organization_id, created_by, created_at, updated_at)
VALUES ('proj-123', 'Test Project', 'org-123', 'user-123', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- Insert test model
INSERT INTO models (id, name, display_name, provider, modality, created_at, updated_at)
VALUES 
    ('model-789', 'gpt-4', 'GPT-4', 'openai', 'text', NOW(), NOW()),
    ('model-790', 'claude-3-opus', 'Claude 3 Opus', 'anthropic', 'text', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- Insert test endpoints
INSERT INTO endpoints (id, name, project_id, model_id, status, created_at, updated_at)
VALUES 
    ('ep-456', 'Test Endpoint 1', 'proj-123', 'model-789', 'active', NOW(), NOW()),
    ('ep-457', 'Test Endpoint 2', 'proj-123', 'model-790', 'active', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;
```

## API Testing

### 1. Test BudMetrics Directly

```bash
# List inferences
curl -X POST http://localhost:8004/api/v1/observability/inferences/list \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-123",
    "from_date": "'$(date -u -d '7 days ago' '+%Y-%m-%dT%H:%M:%S.%3NZ')'",
    "limit": 10,
    "offset": 0
  }'

# Get inference details
curl -X GET http://localhost:8004/api/v1/observability/inferences/550e8400-e29b-41d4-a716-446655440001

# Get inference feedback
curl -X GET http://localhost:8004/api/v1/observability/inferences/550e8400-e29b-41d4-a716-446655440001/feedback
```

### 2. Test BudApp Proxy (requires authentication)

```bash
# First, get an auth token (replace with your credentials)
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your-username", "password": "your-password"}' \
  | jq -r '.access_token')

# List inferences through BudApp
curl -X POST http://localhost:8000/api/v1/metrics/inferences/list \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "project_id": "proj-123",
    "from_date": "'$(date -u -d '7 days ago' '+%Y-%m-%dT%H:%M:%S.%3NZ')'",
    "limit": 10,
    "offset": 0
  }'

# Get inference details through BudApp
curl -X GET http://localhost:8000/api/v1/metrics/inferences/550e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer $TOKEN"

# Get inference feedback through BudApp
curl -X GET http://localhost:8000/api/v1/metrics/inferences/550e8400-e29b-41d4-a716-446655440001/feedback \
  -H "Authorization: Bearer $TOKEN"
```

## Frontend Testing

### 1. Access BudAdmin

1. Open http://localhost:8007 in your browser
2. Log in with your credentials
3. Navigate to a project (e.g., "Test Project")
4. Click on the "Inferences" tab

### 2. Test List View

- [ ] Verify the inference list loads with test data
- [ ] Check that pagination works (if you have >20 items)
- [ ] Test sorting by clicking column headers (Timestamp, Tokens, Latency, Cost)
- [ ] Verify the prompt and response previews show correctly
- [ ] Check that status tags (Success/Failed, Cached) display properly

### 3. Test Filtering

- [ ] Click "Show Advanced" to reveal all filters
- [ ] Test date range picker:
  - Select a custom date range
  - Use quick date buttons (Last 1 hour, Last 24 hours, etc.)
- [ ] Toggle "Show only successful" switch
- [ ] Test token count filters (Min/Max Tokens)
- [ ] Test latency filter (Max Latency)
- [ ] Click "Clear" to reset all filters

### 4. Test Detail View

- [ ] Click the eye icon on any inference row
- [ ] Verify the detail modal opens
- [ ] Check all tabs:
  - **Overview**: Basic information displays correctly
  - **Messages**: User/assistant messages show with proper formatting
  - **Performance**: Token counts, latency, and cost display
  - **Raw Data**: JSON request/response with syntax highlighting
  - **Feedback**: Ratings, boolean values, and comments display

### 5. Test Export Functionality

- [ ] Click "Export CSV" button
- [ ] Verify CSV file downloads with inference data
- [ ] Click "Export JSON" button
- [ ] Verify JSON file downloads with inference data

### 6. Test Actions

- [ ] Click copy icon to copy inference ID
- [ ] In detail modal, test "Copy" buttons for messages
- [ ] Test "Download" buttons for raw request/response data

## Expected Results

1. **List View**: Should display inferences with all columns populated
2. **Filtering**: Should update the list based on selected filters
3. **Detail Modal**: Should show comprehensive information about each inference
4. **Export**: Should generate valid CSV/JSON files with inference data
5. **Performance**: List should load quickly even with many records

## Troubleshooting

### If no data appears:
1. Check that all services are running
2. Verify ClickHouse has data: `clickhouse-client -q "SELECT count(*) FROM ModelInference"`
3. Check browser console for errors
4. Verify authentication is working

### If API calls fail:
1. Check service logs: `docker logs <container_name>`
2. Verify network connectivity between services
3. Check that database connections are working
4. Look for CORS or authentication errors

### Common Issues:
- **Empty inference list**: Check project_id matches in test data
- **Authentication errors**: Refresh token or log in again
- **Missing entity names**: Ensure PostgreSQL has matching project/endpoint/model records
- **Slow performance**: Check ClickHouse query performance with EXPLAIN