# Multi-Dataset Extraction (MMLU and Complex Benchmarks)

## Overview

The extraction system **automatically handles multiple datasets** in a single evaluation job. When a job evaluates MMLU (which has 57+ subsets) or other complex benchmarks, all scores are extracted correctly.

## How It Works

### OpenCompass CSV Format

For benchmarks with multiple subsets (like MMLU), OpenCompass creates a CSV with **one row per subset**:

```csv
dataset,version,metric,mode,gpt-oss-20b
mmlu_abstract_algebra,e78857,accuracy,gen,45.00
mmlu_anatomy,e78857,accuracy,gen,63.70
mmlu_astronomy,e78857,accuracy,gen,68.42
mmlu_business_ethics,e78857,accuracy,gen,64.00
mmlu_clinical_knowledge,e78857,accuracy,gen,69.81
...
mmlu-average,e78857,accuracy,gen,56.91
```

### Extraction Behavior

Our extraction script:

1. **Reads all rows** from the CSV file
2. **Creates a score object for each row**
3. **Returns an array** of all scores

```python
# Each CSV row becomes one score object
for row in csv.DictReader(file):
    scores.append({
        "dataset": row['dataset'],      # mmlu_anatomy, mmlu_physics, etc.
        "metric": row['metric'],         # accuracy
        "score": float(row['model']),   # 63.70, 45.00, etc.
        "version": row['version'],       # e78857
        "mode": row['mode']              # gen
    })
```

### Result Structure

**Single run with MMLU (16 subsets shown, actual MMLU has 57)**:

```json
{
  "run_id": "test-mmlu-001",
  "eval_id": "test-eval-mmlu",
  "status": "success",
  "scores": [
    {
      "dataset": "mmlu_abstract_algebra",
      "metric": "accuracy",
      "score": 45.0,
      "version": "e78857",
      "mode": "gen"
    },
    {
      "dataset": "mmlu_anatomy",
      "metric": "accuracy",
      "score": 63.7,
      "version": "e78857",
      "mode": "gen"
    },
    ...
    {
      "dataset": "mmlu-average",
      "metric": "accuracy",
      "score": 56.91,
      "version": "e78857",
      "mode": "gen"
    }
  ]
}
```

## Common Benchmarks with Multiple Datasets

### MMLU (Massive Multitask Language Understanding)
- **Subsets**: 57 tasks across different domains
- **Format**: Each task gets its own row + an average row
- **Example datasets**:
  - `mmlu_abstract_algebra`
  - `mmlu_anatomy`
  - `mmlu_astronomy`
  - `mmlu-average` (overall score)

### CEVAL (Chinese Evaluation Benchmark)
- **Subsets**: 52 tasks
- **Format**: Similar to MMLU
- **Example datasets**:
  - `ceval_computer_network`
  - `ceval_operating_system`
  - `ceval-average`

### BBH (Big Bench Hard)
- **Subsets**: 23 challenging tasks
- **Format**: One row per task
- **Example datasets**:
  - `bbh_boolean_expressions`
  - `bbh_causal_judgement`
  - `bbh_date_understanding`

### AGIEval
- **Subsets**: Multiple exam-based tasks
- **Format**: One row per exam type

## Workflow Response Example

When the workflow completes with MMLU evaluation:

```json
{
  "success": true,
  "results": [
    {
      "run_id": "mmlu-eval-001",
      "eval_id": "123e4567-e89b-12d3-a456-426614173345",
      "status": "success",
      "scores": [
        // All 57 MMLU subsets here
        {"dataset": "mmlu_abstract_algebra", "score": 45.0},
        {"dataset": "mmlu_anatomy", "score": 63.7},
        // ... 55 more subsets ...
        {"dataset": "mmlu-average", "score": 56.91}
      ]
    }
  ]
}
```

## Finding the Average Score

For benchmarks with multiple subsets, OpenCompass typically includes an average/summary row:

### Identifying Average Rows

```python
# Filter for average scores
avg_scores = [
    s for s in scores
    if 'average' in s['dataset'].lower() or
       'overall' in s['dataset'].lower()
]

# MMLU average
mmlu_avg = next((s for s in scores if s['dataset'] == 'mmlu-average'), None)
if mmlu_avg:
    print(f"MMLU Overall Score: {mmlu_avg['score']}")
```

### Manual Calculation

You can also calculate the average from individual subsets:

```python
# Get individual subset scores (exclude average rows)
individual_scores = [
    s['score'] for s in scores
    if 'average' not in s['dataset'].lower()
]

# Calculate average
manual_avg = sum(individual_scores) / len(individual_scores)
```

## Notification Format

When sending results in notifications, you can choose the level of detail:

### Option 1: Summary Only (Recommended for Notifications)
```python
# Extract just the average score
avg_score = next((s for s in scores if 'average' in s['dataset'].lower()), None)

notification_metadata = {
    "run_id": "mmlu-eval-001",
    "summary": {
        "dataset": "mmlu",
        "average_score": avg_score['score'] if avg_score else None,
        "total_subsets": len(scores) - 1  # Exclude average row
    }
}
```

### Option 2: Full Details (For API/Storage)
```python
# Include all subset scores
notification_metadata = {
    "run_id": "mmlu-eval-001",
    "all_scores": scores,  # All 57+ scores
    "summary": {
        "average": avg_score['score'],
        "best_subset": max(scores, key=lambda s: s['score']),
        "worst_subset": min(scores, key=lambda s: s['score'])
    }
}
```

### Option 3: Grouped by Category (Smart Aggregation)
```python
# Group MMLU subsets by domain
from collections import defaultdict

grouped = defaultdict(list)
for score in scores:
    # Extract domain from dataset name
    # mmlu_college_biology -> college
    parts = score['dataset'].split('_')
    if len(parts) > 1:
        domain = parts[1]  # college, high_school, etc.
        grouped[domain].append(score['score'])

# Calculate domain averages
domain_averages = {
    domain: sum(scores) / len(scores)
    for domain, scores in grouped.items()
}

notification_metadata = {
    "run_id": "mmlu-eval-001",
    "overall_average": avg_score['score'],
    "domain_performance": domain_averages
}
```

## Storage Considerations

### Workflow State
- **Store full details** in workflow state
- Allows querying individual subset scores later
- Example: `{"extraction_results": [{"scores": [...]}]}`

### Notification
- **Send summary** in notification
- Reduces payload size
- Highlights key metrics
- Example: `{"average": 56.91, "subsets": 57}`

### Database (if needed in future)
- **One row per score** in results table
- Allows filtering/aggregation
- Example schema:
  ```sql
  eval_id | run_id | dataset | metric | score
  --------|--------|---------|--------|------
  123...  | mmlu.. | mmlu_an.| accur..| 63.7
  123...  | mmlu.. | mmlu_as.| accur..| 68.42
  ```

## Example: Processing MMLU Results in Workflow

Here's how to handle MMLU results in the workflow after extraction:

```python
# After extraction
extraction_result = yield ctx.call_activity(
    EvaluationWorkflow.extract_eval_results,
    input=json.dumps(extraction_input),
)

if extraction_result.get("success"):
    for run_result in extraction_result.get("results", []):
        scores = run_result.get("scores", [])

        # Find average score
        avg_score = next(
            (s for s in scores if 'average' in s['dataset'].lower()),
            None
        )

        # Count subsets
        subset_count = len([s for s in scores if 'average' not in s['dataset'].lower()])

        # Build notification message
        if avg_score:
            message = f"MMLU Evaluation Complete: {avg_score['score']:.2f}% average across {subset_count} subsets"
        else:
            message = f"Evaluation Complete: {len(scores)} scores extracted"

        # Store full results in workflow state
        update_workflow_data_in_statestore(
            instance_id,
            {
                "extraction_results": extraction_result.get("results"),
                "summary": {
                    "average_score": avg_score['score'] if avg_score else None,
                    "total_subsets": subset_count
                }
            }
        )

        # Send notification with summary
        notification_req.payload.content = NotificationContent(
            title="Evaluation Completed",
            message=message,
            status=WorkflowStatus.COMPLETED,
            metadata={
                "average_score": avg_score['score'] if avg_score else None,
                "subset_count": subset_count,
                "run_id": run_result['run_id']
            }
        )
```

## Performance Impact

### MMLU (57 subsets)
- **Extraction time**: ~10-15 seconds (same as single dataset)
- **Response size**: ~5-10 KB (57 score objects)
- **Notification size**: Can be reduced to <1 KB with summary only

### Large Benchmarks (100+ subsets)
- **Extraction time**: ~10-20 seconds
- **Response size**: ~10-20 KB
- **Recommendation**: Send summary in notification, full data in workflow state

## Best Practices

### 1. Always Include Average
When filtering scores for display, include the average row:
```python
# Good: Keep average for summary
important_scores = [s for s in scores if 'average' in s['dataset'].lower() or s['score'] > 70]
```

### 2. Group Related Datasets
For UI display, group related subsets:
```python
# MMLU subsets by domain
college_scores = [s for s in scores if 'college' in s['dataset']]
high_school_scores = [s for s in scores if 'high_school' in s['dataset']]
```

### 3. Highlight Key Metrics
In notifications, focus on actionable information:
```python
best = max(scores, key=lambda s: s['score'])
worst = min(scores, key=lambda s: s['score'])

message = f"MMLU: {avg_score['score']:.1f}% avg | Best: {best['dataset']} ({best['score']:.1f}%) | Worst: {worst['dataset']} ({worst['score']:.1f}%)"
```

### 4. Provide Drill-down Capability
Store full results for detailed analysis:
- Workflow state: Full extraction results
- Notification: Summary + link to details
- API endpoint: Return full results on request

## Conclusion

✅ **The extraction system handles multi-dataset benchmarks automatically**

- Each CSV row becomes a score object
- All subsets are extracted and returned
- Supports any number of datasets (1 to 100+)
- Average scores are preserved
- No code changes needed for different benchmarks

**For MMLU with 57 subsets**: You get 58 score objects (57 subsets + 1 average)
**For simple benchmarks**: You get 1 score object
**For complex multi-metric benchmarks**: You get all metrics and all subsets

The system is flexible and handles any OpenCompass CSV format automatically! 🎉
