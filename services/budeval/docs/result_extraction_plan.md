# Evaluation Result Extraction Plan

## Overview
Plan for extracting, processing, and storing OpenCompass evaluation results from Kubernetes jobs.

## Current State Analysis

### Result Location Structure
```
/workspace/shared/results/{eval_id}/opencompass-{run_id}/{timestamp}/
├── summary/
│   ├── summary_{timestamp}.txt
│   ├── summary_{timestamp}.csv
│   └── summary_{timestamp}.md
├── predictions/
│   └── {model_name}/
│       └── {dataset_name}.json
└── configs/
    └── eval_config.py
```

### Example from Completed Job
**Job**: `test-heredoc-fix-001`
**Eval ID**: `223e4567-e89b-12d3-a456-426614174020`
**Timestamp**: `20251016_235030`

**Results Found**:
- `/workspace/shared/results/223e4567-e89b-12d3-a456-426614174020/opencompass-test-heredoc-fix-001/20251016_235030/summary/summary_20251016_235030.csv`
- `/workspace/shared/results/223e4567-e89b-12d3-a456-426614174020/opencompass-test-heredoc-fix-001/20251016_235030/summary/summary_20251016_235030.md`
- `/workspace/shared/results/223e4567-e89b-12d3-a456-426614174020/opencompass-test-heredoc-fix-001/20251016_235030/summary/summary_20251016_235030.txt`

**Sample Result Content (CSV)**:
```csv
dataset,version,metric,mode,gpt-oss-20b
demo_gsm8k,1d7fe4,accuracy,gen,65.62
```

**Sample Result Content (Markdown)**:
```markdown
| dataset | version | metric | mode | gpt-oss-20b |
|----- | ----- | ----- | ----- | -----|
| demo_gsm8k | 1d7fe4 | accuracy | gen | 65.62 |
```

## Extraction Strategy

### Option 1: Direct PVC Access (Recommended for Development)
**Method**: Access files directly from host-mounted PVC path
**Path**: `/var/lib/rancher/k3s/storage/pvc-fd3106f0-ca44-44c9-b5c9-449698d6d6fe_development_eval-datasets-pvc/results/`

**Pros**:
- Fast, direct access
- No Kubernetes API calls needed
- Works when pods are terminated

**Cons**:
- Only works on the node where PV is mounted
- Not portable across different storage backends

### Option 2: kubectl cp (Simple for Testing)
**Method**: Use kubectl to copy files from completed pods
**Command**: `kubectl cp {namespace}/{pod}:{container_path} {local_path}`

**Pros**:
- Works across any Kubernetes cluster
- No special permissions needed

**Cons**:
- Requires pod to be running or recently completed
- Doesn't work after TTL cleanup

### Option 3: Kubernetes Job with Result Extraction (Production Ready)
**Method**: Deploy a sidecar container or separate job to extract results
**Approach**:
1. Job completes evaluation
2. Extract job reads from shared PVC
3. Pushes results to object storage (MinIO/S3) or API endpoint

**Pros**:
- Works in production environments
- Scalable and automated
- Storage-agnostic

**Cons**:
- More complex setup
- Requires additional job orchestration

### Option 4: Ansible Playbook Extraction (Hybrid Approach)
**Method**: Ansible playbook that connects to cluster and extracts results
**Components**:
- Query job completion status
- Find result directories in PVC
- Copy files using kubectl or direct mount
- Parse and format results
- Store in database/object storage

**Pros**:
- Automated and repeatable
- Can be integrated with workflow
- Handles multiple jobs

**Cons**:
- Requires Ansible runner
- Cluster access needed

## Recommended Implementation Plan

### Phase 1: Parse Results from PVC (Current Approach)
**Implementation**: Python service method in `budeval`

```python
class ResultsProcessor:
    def extract_eval_results(self, eval_id: str, run_id: str) -> dict:
        """
        Extract results from PVC mount point.

        Args:
            eval_id: Evaluation request ID
            run_id: Specific run ID

        Returns:
            {
                "eval_id": "...",
                "run_id": "...",
                "timestamp": "...",
                "results": [
                    {
                        "dataset": "demo_gsm8k",
                        "version": "1d7fe4",
                        "metric": "accuracy",
                        "mode": "gen",
                        "score": 65.62
                    }
                ],
                "summary_files": {
                    "csv": "/path/to/summary.csv",
                    "md": "/path/to/summary.md",
                    "txt": "/path/to/summary.txt"
                }
            }
        """
        pass
```

**Steps**:
1. Scan PVC results directory: `/var/lib/rancher/k3s/storage/.../results/{eval_id}/opencompass-{run_id}/`
2. Find latest timestamp directory
3. Read CSV/JSON files
4. Parse results into structured format
5. Store in ClickHouse for analytics
6. Return formatted results

### Phase 2: Workflow Integration
**Add to `workflows.py`**:

```python
@dapr_workflows.register_activity
@staticmethod
def extract_eval_results(ctx: wf.WorkflowActivityContext, extract_request: str) -> dict:
    """Extract and process evaluation results after job completion."""
    request = json.loads(extract_request)

    # Wait for job to complete
    # Extract results from PVC
    # Parse and format
    # Store in database
    # Return summary

    return {
        "status": "success",
        "results": {...}
    }
```

### Phase 3: Database Schema for Results
**ClickHouse Table** (already exists in budmetrics):

```sql
-- Evaluation results table
CREATE TABLE IF NOT EXISTS evaluation_results (
    eval_id UUID,
    run_id String,
    dataset_id String,
    dataset_version String,
    metric_name String,
    metric_value Float64,
    mode String,
    model_name String,
    timestamp DateTime,
    metadata String  -- JSON with additional info
) ENGINE = MergeTree()
ORDER BY (eval_id, run_id, timestamp);
```

### Phase 4: Result File Format Parsing

**CSV Parser**:
```python
import csv

def parse_csv_results(csv_path: str) -> list[dict]:
    """Parse OpenCompass CSV results."""
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    results = []
    for row in rows:
        # row = {'dataset': 'demo_gsm8k', 'version': '1d7fe4',
        #        'metric': 'accuracy', 'mode': 'gen', 'gpt-oss-20b': '65.62'}

        model_columns = [k for k in row.keys()
                        if k not in ['dataset', 'version', 'metric', 'mode']]

        for model_col in model_columns:
            results.append({
                'dataset': row['dataset'],
                'version': row['version'],
                'metric': row['metric'],
                'mode': row['mode'],
                'model_name': model_col,
                'score': float(row[model_col])
            })

    return results
```

**JSON Predictions Parser** (for detailed analysis):
```python
import json

def parse_predictions(predictions_path: str) -> list[dict]:
    """Parse detailed prediction results."""
    with open(predictions_path, 'r') as f:
        predictions = json.load(f)

    # OpenCompass prediction format:
    # [
    #   {
    #     "origin_prompt": "...",
    #     "prediction": "...",
    #     "gold": "...",
    #     "correct": true/false
    #   }
    # ]

    return predictions
```

## Result Processing Workflow

### Step-by-Step Flow

```
1. Job Completion
   ↓
2. Workflow detects completion (poll or event)
   ↓
3. Extract Results Activity
   ├─ Find result directory in PVC
   ├─ Identify latest timestamp folder
   ├─ Read summary CSV/MD/TXT
   └─ Read predictions JSON (optional)
   ↓
4. Parse and Validate
   ├─ Parse CSV to structured data
   ├─ Validate scores are numeric
   └─ Check for required fields
   ↓
5. Store Results
   ├─ Insert into ClickHouse (evaluation_results table)
   ├─ Store raw files in MinIO (optional)
   └─ Update workflow status in PostgreSQL
   ↓
6. Notify
   ├─ Publish results to pub/sub
   └─ Send notification to budapp
   ↓
7. Cleanup (optional)
   └─ Delete Kubernetes job (TTL handles this)
```

## File Organization for Extracted Results

### Option A: Keep in PVC
```
/workspace/shared/results/
└── {eval_id}/
    └── opencompass-{run_id}/
        └── {timestamp}/
            ├── summary/
            ├── predictions/
            └── configs/
```

**Retention**: 30 days, then cleanup

### Option B: Copy to MinIO
```
s3://bud-eval-results/
└── {eval_id}/
    └── {run_id}/
        ├── summary_{timestamp}.csv
        ├── summary_{timestamp}.md
        ├── predictions_{timestamp}.json
        └── metadata.json
```

**Retention**: Indefinite, with versioning

### Option C: Database Only
- Store only parsed metrics in ClickHouse
- Archive raw files for 7 days
- Purge after archival period

**Recommended**: Hybrid (Database + MinIO archive)

## API Response Format

### GET /evals/{eval_id}/results

```json
{
  "eval_id": "223e4567-e89b-12d3-a456-426614174020",
  "experiment_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "runs": [
    {
      "run_id": "test-heredoc-fix-001",
      "dataset_id": "demo_gsm8k",
      "status": "completed",
      "timestamp": "2025-10-16T23:52:41Z",
      "results": [
        {
          "metric": "accuracy",
          "score": 65.62,
          "mode": "gen",
          "dataset_version": "1d7fe4"
        }
      ],
      "files": {
        "summary_csv": "s3://bud-eval-results/.../summary.csv",
        "summary_md": "s3://bud-eval-results/.../summary.md",
        "predictions": "s3://bud-eval-results/.../predictions.json"
      }
    }
  ]
}
```

## Error Handling

### Common Issues

1. **Results directory not found**
   - Cause: Job failed before writing results
   - Action: Check job logs, mark eval as failed

2. **Incomplete results**
   - Cause: Job terminated early
   - Action: Partial results extraction, flag as incomplete

3. **Parse errors**
   - Cause: Unexpected result format
   - Action: Log error, store raw file, manual review

4. **PVC access issues**
   - Cause: Volume not mounted, permissions
   - Action: Fall back to kubectl cp or API extraction

## Next Steps

### Immediate (Phase 1)
1. ✅ Fix heredoc script generation bug
2. ✅ Verify results are written to PVC
3. ⏳ Create `ResultsProcessor` class
4. ⏳ Add CSV parsing logic
5. ⏳ Test with completed job results

### Short-term (Phase 2)
1. Add workflow activity for result extraction
2. Integrate with existing evaluation workflow
3. Store results in ClickHouse
4. Add API endpoint to retrieve results

### Long-term (Phase 3)
1. Implement MinIO archival
2. Add result comparison features
3. Create result visualization endpoints
4. Implement result caching

## Configuration

### Environment Variables
```bash
# PVC mount path (for direct access)
EVAL_RESULTS_PVC_PATH=/var/lib/rancher/k3s/storage/pvc-fd3106f0-ca44-44c9-b5c9-449698d6d6fe_development_eval-datasets-pvc

# Alternative: Use symbolic name
EVAL_DATASETS_PVC_NAME=eval-datasets-pvc-rwx

# Result retention period (days)
EVAL_RESULTS_RETENTION_DAYS=30

# MinIO configuration (for archival)
MINIO_ENDPOINT=http://minio:9000
MINIO_BUCKET=bud-eval-results
```

## Monitoring and Observability

### Metrics to Track
- Number of evaluations completed
- Average time to extract results
- Result file sizes
- Parse success/failure rates
- Storage usage in PVC

### Logs to Capture
- Result extraction start/completion
- Parse errors with file path
- Storage operations (PVC, MinIO)
- Cleanup operations

## Security Considerations

1. **PVC Access**: Ensure only authorized services can read results
2. **Result Data**: May contain model outputs - consider data sensitivity
3. **API Authentication**: Require auth for result retrieval
4. **File Permissions**: Restrict write access to job pods only

## Testing Strategy

### Unit Tests
- CSV parsing with various formats
- JSON predictions parsing
- Error handling for missing files

### Integration Tests
- End-to-end: Submit eval → Extract results → Store in DB
- PVC access verification
- ClickHouse insertion validation

### Performance Tests
- Large result files (1000+ predictions)
- Concurrent result extractions
- PVC I/O under load

---

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Author**: Claude Code
**Status**: Draft - Ready for Implementation
