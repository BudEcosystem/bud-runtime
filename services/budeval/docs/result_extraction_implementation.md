# Result Extraction Implementation Guide

## Overview
This document provides complete implementation for extracting evaluation results using a Kubernetes extraction job approach.

**Requirements**:
- ✅ NO database storage - just parse and return structured results
- ✅ NO direct PVC path access (portable across deployments)
- ✅ Use Kubernetes extraction job to mount PVC
- ✅ All K8s operations via Ansible
- ✅ Return scores with run_id in workflow state
- ✅ Send results with notification

## Architecture

```
Monitoring Completes (Jobs Succeeded)
    ↓
Call extract_eval_results Activity
    ↓
AnsibleOrchestrator.extract_job_results()
    ↓
Deploy K8s Extraction Job (via Ansible)
    ├─ Mount eval-datasets-pvc-rwx
    ├─ Run Python script to parse CSV
    └─ Output JSON to stdout
    ↓
Ansible retrieves results via kubectl logs
    ↓
Return structured results to workflow
    ↓
Store in workflow state (update_workflow_data_in_statestore)
    ↓
Send with completion notification
```

## Result Format

```json
{
  "success": true,
  "results": [
    {
      "run_id": "test-monitor-check-001",
      "eval_id": "223e4567-e89b-12d3-a456-426614174020",
      "status": "success",
      "scores": [
        {
          "dataset": "demo_gsm8k",
          "metric": "accuracy",
          "score": 65.62,
          "version": "1d7fe4"
        }
      ]
    }
  ]
}
```

---

## 1. Ansible Playbook: `extract_results_k8s.yml`

**File**: `budeval/ansible/playbooks/extract_results_k8s.yml`

```yaml
---
- name: Extract Evaluation Results from PVC
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    kubeconfig_path: ""
    namespace: "default"
    eval_id: ""
    run_ids: ""  # Comma-separated run IDs
    temp_id: ""

  tasks:
    - name: Ensure required variables are provided
      ansible.builtin.assert:
        that:
          - namespace is defined
          - namespace | length > 0
          - eval_id is defined
          - eval_id | length > 0
          - run_ids is defined
          - run_ids | length > 0
          - temp_id is defined
          - temp_id | length > 0
        fail_msg: "namespace, eval_id, run_ids, and temp_id must be provided"

    - name: Create Python extraction script
      ansible.builtin.set_fact:
        extraction_script: |
          import csv
          import json
          import glob
          import os
          from pathlib import Path

          def extract_results(eval_id, run_id):
              """Extract results for a single run."""
              base_path = f"/workspace/shared/results/{eval_id}/opencompass-{run_id}"

              if not os.path.exists(base_path):
                  return {
                      "run_id": run_id,
                      "eval_id": eval_id,
                      "status": "error",
                      "error": "Results directory not found",
                      "scores": []
                  }

              # Find summary CSV files (may be in timestamped subdirectories)
              csv_files = glob.glob(f"{base_path}/*/summary/summary_*.csv")
              if not csv_files:
                  # Try direct path without timestamp
                  csv_files = glob.glob(f"{base_path}/summary/summary_*.csv")

              if not csv_files:
                  return {
                      "run_id": run_id,
                      "eval_id": eval_id,
                      "status": "error",
                      "error": "No CSV results found",
                      "scores": []
                  }

              # Use latest CSV file
              csv_file = sorted(csv_files)[-1]

              # Parse CSV
              scores = []
              try:
                  with open(csv_file, 'r') as f:
                      reader = csv.DictReader(f)
                      for row in reader:
                          dataset = row.get('dataset', '')
                          version = row.get('version', '')
                          metric = row.get('metric', '')
                          mode = row.get('mode', '')

                          # Model score is the last column (not dataset/version/metric/mode)
                          score_cols = [k for k in row.keys()
                                       if k not in ['dataset', 'version', 'metric', 'mode']]

                          if score_cols:
                              try:
                                  score_value = float(row[score_cols[0]])
                                  scores.append({
                                      "dataset": dataset,
                                      "version": version,
                                      "metric": metric,
                                      "mode": mode,
                                      "score": score_value
                                  })
                              except (ValueError, TypeError):
                                  continue

                  return {
                      "run_id": run_id,
                      "eval_id": eval_id,
                      "status": "success",
                      "scores": scores,
                      "csv_file": csv_file
                  }

              except Exception as e:
                  return {
                      "run_id": run_id,
                      "eval_id": eval_id,
                      "status": "error",
                      "error": str(e),
                      "scores": []
                  }

          # Main execution
          eval_id = os.environ.get("EVAL_ID", "")
          run_ids_str = os.environ.get("RUN_IDS", "")

          results_list = []
          for run_id in run_ids_str.split(","):
              run_id = run_id.strip()
              if run_id:
                  result = extract_results(eval_id, run_id)
                  results_list.append(result)

          # Output results as JSON
          print(json.dumps({"success": True, "results": results_list}))

    - name: Create extraction job manifest
      ansible.builtin.set_fact:
        extraction_job:
          apiVersion: batch/v1
          kind: Job
          metadata:
            name: "extract-results-{{ temp_id }}"
            namespace: "{{ namespace }}"
          spec:
            ttlSecondsAfterFinished: 300  # Clean up after 5 minutes
            template:
              spec:
                containers:
                  - name: extractor
                    image: python:3.10-slim
                    command: ["python", "-c"]
                    args:
                      - "{{ extraction_script }}"
                    env:
                      - name: EVAL_ID
                        value: "{{ eval_id }}"
                      - name: RUN_IDS
                        value: "{{ run_ids }}"
                    volumeMounts:
                      - name: eval-datasets-shared
                        mountPath: /workspace/shared
                volumes:
                  - name: eval-datasets-shared
                    persistentVolumeClaim:
                      claimName: eval-datasets-pvc-rwx
                restartPolicy: Never
            backoffLimit: 2

    - name: Apply extraction job
      kubernetes.core.k8s:
        state: present
        definition: "{{ extraction_job }}"
        kubeconfig: "{{ kubeconfig_path if kubeconfig_path else omit }}"

    - name: Wait for extraction job to complete
      kubernetes.core.k8s_info:
        api_version: batch/v1
        kind: Job
        name: "extract-results-{{ temp_id }}"
        namespace: "{{ namespace }}"
        kubeconfig: "{{ kubeconfig_path if kubeconfig_path else omit }}"
      register: job_status
      until: >
        (job_status.resources[0].status.succeeded | default(0)) > 0 or
        (job_status.resources[0].status.failed | default(0)) > 0
      retries: 60
      delay: 5

    - name: Check if job succeeded
      ansible.builtin.fail:
        msg: "Extraction job failed"
      when: (job_status.resources[0].status.failed | default(0)) > 0

    - name: Get pod name for extraction job
      kubernetes.core.k8s_info:
        api_version: v1
        kind: Pod
        namespace: "{{ namespace }}"
        label_selectors:
          - "job-name=extract-results-{{ temp_id }}"
        kubeconfig: "{{ kubeconfig_path if kubeconfig_path else omit }}"
      register: extraction_pod

    - name: Get logs from extraction pod
      kubernetes.core.k8s_log:
        api_version: v1
        kind: Pod
        name: "{{ extraction_pod.resources[0].metadata.name }}"
        namespace: "{{ namespace }}"
        kubeconfig: "{{ kubeconfig_path if kubeconfig_path else omit }}"
      register: extraction_logs
      when: extraction_pod.resources | length > 0

    - name: Parse extraction results
      ansible.builtin.set_fact:
        extraction_results: "{{ extraction_logs.log | from_json }}"
      when: extraction_logs.log is defined

    - name: Write results to temporary file
      ansible.builtin.copy:
        content: "{{ extraction_results | to_nice_json }}"
        dest: "/tmp/extraction_results_{{ temp_id }}.json"
      when: extraction_results is defined

    - name: Delete extraction job
      kubernetes.core.k8s:
        api_version: batch/v1
        kind: Job
        name: "extract-results-{{ temp_id }}"
        namespace: "{{ namespace }}"
        state: absent
        kubeconfig: "{{ kubeconfig_path if kubeconfig_path else omit }}"
      ignore_errors: true
```

---

## 2. AnsibleOrchestrator Method

**File**: `budeval/evals/ansible_orchestrator.py`

Add this method to the `AnsibleOrchestrator` class (after the `check_jobs_status` method):

```python
def extract_job_results(
    self,
    eval_id: str,
    run_ids: list[str],
    kubeconfig: Optional[str] = None
) -> dict:
    """Extract results from completed evaluation jobs using Kubernetes extraction job.

    This method:
    1. Deploys a Kubernetes Job that mounts the eval-datasets PVC
    2. Runs a Python script to parse OpenCompass CSV results
    3. Retrieves the parsed results via kubectl logs
    4. Returns structured results with run_id

    Args:
        eval_id: Evaluation request ID
        run_ids: List of run IDs (job names) to extract results for
        kubeconfig: Optional kubeconfig JSON

    Returns:
        {
            "success": bool,
            "results": [
                {
                    "run_id": "...",
                    "eval_id": "...",
                    "status": "success|error",
                    "scores": [
                        {
                            "dataset": "demo_gsm8k",
                            "metric": "accuracy",
                            "score": 65.62,
                            "version": "1d7fe4"
                        }
                    ]
                }
            ]
        }
    """
    temp_id = f"extract-{uuid.uuid4().hex[:8]}"
    playbook = "extract_results_k8s.yml"

    files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

    # Build Extra Args
    namespace = StorageConfig.get_current_namespace()
    extravars["namespace"] = namespace
    extravars["eval_id"] = eval_id
    extravars["run_ids"] = ",".join(run_ids)
    extravars["temp_id"] = temp_id

    logger.info(f"Extracting results for eval_id={eval_id}, run_ids={run_ids}")

    # Run The Playbook
    try:
        self._run_ansible_playbook(playbook, temp_id, files, extravars)

        # Read results from temporary file created by playbook
        results_file = Path(tempfile.gettempdir()) / f"extraction_results_{temp_id}.json"

        if results_file.exists():
            with open(results_file, 'r') as f:
                extraction_results = json.load(f)
            results_file.unlink()  # Clean up

            logger.info(f"Successfully extracted results for {len(run_ids)} runs")
            return extraction_results
        else:
            logger.error("Extraction results file not found")
            return {
                "success": False,
                "results": [],
                "error": "Results file not created"
            }

    except Exception as e:
        logger.error(f"Failed to extract results: {e}", exc_info=True)
        return {
            "success": False,
            "results": [],
            "error": str(e)
        }
```

---

## 3. Workflow Activity

**File**: `budeval/evals/workflows.py`

Add this activity method to the `EvaluationWorkflow` class (after line 495, before `verify_cluster_connection`):

```python
@dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
@staticmethod
def extract_eval_results(
    ctx: wf.WorkflowActivityContext,
    extract_request: str,
) -> dict:
    """Extract evaluation results from completed jobs.

    Args:
        ctx: Workflow activity context
        extract_request: JSON string with:
            {
                "eval_id": "...",
                "completed_jobs": ["job1", "job2", ...]
            }

    Returns:
        {
            "success": bool,
            "results": [...]
        }
    """
    logger = logging.getLogger("::EVAL:: ExtractEvalResults")

    workflow_id = ctx.workflow_id
    request = json.loads(extract_request)

    eval_id = request.get("eval_id")
    completed_jobs = request.get("completed_jobs", [])
    kubeconfig = request.get("kubeconfig")

    logger.info(f"Extracting results for {len(completed_jobs)} completed jobs")

    try:
        results = AnsibleOrchestrator().extract_job_results(
            eval_id=eval_id,
            run_ids=completed_jobs,
            kubeconfig=kubeconfig
        )

        return results

    except Exception as e:
        error_msg = f"Error extracting results for workflow_id: {workflow_id}, error: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "results": [],
            "error": str(e)
        }
```

---

## 4. Workflow Integration

**File**: `budeval/evals/workflows.py`

Update the `evaluate_model` workflow method at **line 427** (where the comment says `# ====================  Result Extraction   ====================`):

```python
# ====================  Result Extraction   ====================

# Notification - Starting result extraction
notification_req.payload.event = "extract_results"
notification_req.payload.content = NotificationContent(
    title="Extracting evaluation results",
    message=f"Extracting results from {len(monitoring_result.get('completed_jobs', []))} completed jobs",
    status=WorkflowStatus.RUNNING,
)
dapr_workflows.publish_notification(
    workflow_id=instance_id,
    notification=notification_req,
    target_topic_name=evaluate_model_request_json.source_topic,
    target_name=evaluate_model_request_json.source,
)

# Extract results from completed jobs
extraction_input = {
    "eval_id": evaluate_model_request_json.eval_id,
    "completed_jobs": monitoring_result.get("completed_jobs", []),
}

extraction_result = yield ctx.call_activity(
    EvaluationWorkflow.extract_eval_results,
    input=json.dumps(extraction_input),
)

logger.debug(f"Extraction result: {extraction_result}")

# Store results in workflow state
if extraction_result.get("success"):
    update_workflow_data_in_statestore(
        instance_id,
        {
            "extraction_results": extraction_result.get("results", []),
            "extraction_status": "completed"
        },
    )

    # Build results summary for notification
    total_scores = sum(len(r.get("scores", [])) for r in extraction_result.get("results", []))
    results_summary = f"Extracted {total_scores} scores from {len(extraction_result.get('results', []))} runs"

    # Notify that extraction succeeded
    notification_req.payload.event = "extract_results"
    notification_req.payload.content = NotificationContent(
        title="Results extracted successfully",
        message=results_summary,
        status=WorkflowStatus.COMPLETED,
    )
    dapr_workflows.publish_notification(
        workflow_id=instance_id,
        notification=notification_req,
        target_topic_name=evaluate_model_request_json.source_topic,
        target_name=evaluate_model_request_json.source,
    )

    # Send final completion notification WITH RESULTS
    notification_req.payload.event = "evaluate_model_status"
    notification_req.payload.content = NotificationContent(
        title="Evaluation Completed Successfully",
        message=results_summary,
        status=WorkflowStatus.COMPLETED,
        metadata={"results": extraction_result.get("results", [])}  # Include results in notification
    )
    dapr_workflows.publish_notification(
        workflow_id=instance_id,
        notification=notification_req,
        target_topic_name=evaluate_model_request_json.source_topic,
        target_name=evaluate_model_request_json.source,
    )

else:
    # Notify that extraction failed
    notification_req.payload.event = "extract_results"
    notification_req.payload.content = NotificationContent(
        title="Result extraction failed",
        message=extraction_result.get("error", "Unknown error"),
        status=WorkflowStatus.FAILED,
    )
    dapr_workflows.publish_notification(
        workflow_id=instance_id,
        notification=notification_req,
        target_topic_name=evaluate_model_request_json.source_topic,
        target_name=evaluate_model_request_json.source,
    )

# ====================  End Result Extraction   ====================
```

---

## 5. Update Workflow Steps

**File**: `budeval/evals/workflows.py`

Update the `workflow_steps` list in the `__call__` method (around line 606) to include result extraction:

```python
workflow_steps = [
    WorkflowStep(
        id="verify_cluster_connection",
        title="Verifying Cluster Connection",
        description="Verify if the cluster is reachable",
    ),
    WorkflowStep(
        id="preparing_eval_engine",
        title="Preparing Eval Engine",
        description="Warming up eval engine",
    ),
    WorkflowStep(
        id="deploy_eval_job",
        title="Deploying Evaluation Jobs",
        description="Deploy the evaluation job to the cluster",
    ),
    WorkflowStep(
        id="monitor_eval_job_progress",
        title="Monitoring Evaluation Job Progress",
        description="Monitor the progress of the evaluation job",
    ),
    WorkflowStep(
        id="extract_results",
        title="Extracting Results",
        description="Extract and parse evaluation results",
    ),
]
```

---

## 6. Testing Instructions

### Test the Complete Flow

1. **Start the service**:
   ```bash
   cd /mnt/HC_Volume_103274798/bud-runtime/services/budeval
   dapr run --run-file ./app.yaml
   ```

2. **Trigger an evaluation** (via your existing API/test script)

3. **Monitor workflow progress**:
   - Cluster verification
   - Engine config creation
   - Job deployment
   - Job monitoring
   - **Result extraction** ← New step
   - Completion notification with results

4. **Verify results**:
   - Check workflow state store for `extraction_results`
   - Check notification payload for results
   - Verify JSON structure matches expected format

### Manual Testing of Extraction

```bash
# Test extraction playbook directly
cd /mnt/HC_Volume_103274798/bud-runtime/services/budeval

# Run extraction for a completed job
ansible-playbook budeval/ansible/playbooks/extract_results_k8s.yml \
  -e "namespace=default" \
  -e "eval_id=223e4567-e89b-12d3-a456-426614174020" \
  -e "run_ids=test-monitor-check-001" \
  -e "temp_id=test-extract-001"

# Check results
cat /tmp/extraction_results_test-extract-001.json
```

---

## Error Handling

The implementation handles these error cases:

1. **Results directory not found**: Returns error status with message
2. **No CSV files found**: Returns error status with message
3. **CSV parsing errors**: Catches exceptions, returns error status
4. **Job execution failures**: Ansible playbook fails, returns error to workflow
5. **Timeout waiting for job**: Ansible retries exhaust, returns error

All errors are:
- Logged with context (eval_id, run_id, workflow_id)
- Returned in structured format
- Included in failure notifications
- Stored in workflow state

---

## Result Structure Details

### Success Response
```json
{
  "success": true,
  "results": [
    {
      "run_id": "test-job-001",
      "eval_id": "223e4567-e89b-12d3-a456-426614174020",
      "status": "success",
      "scores": [
        {
          "dataset": "demo_gsm8k",
          "version": "1d7fe4",
          "metric": "accuracy",
          "mode": "gen",
          "score": 65.62
        }
      ],
      "csv_file": "/workspace/shared/results/.../summary_20251016_235030.csv"
    }
  ]
}
```

### Error Response
```json
{
  "success": false,
  "results": [
    {
      "run_id": "test-job-002",
      "eval_id": "223e4567-e89b-12d3-a456-426614174020",
      "status": "error",
      "error": "Results directory not found",
      "scores": []
    }
  ]
}
```

---

## Cleanup

The extraction job automatically cleans itself up:
- `ttlSecondsAfterFinished: 300` (5 minutes)
- Playbook also explicitly deletes the job after retrieving logs
- Temporary files (`/tmp/extraction_results_*.json`) are deleted after reading

---

## Summary

This implementation:
- ✅ Uses Kubernetes extraction job (portable, no direct PVC paths)
- ✅ All K8s operations via Ansible
- ✅ No database storage - results in workflow state only
- ✅ Returns structured scores with run_id
- ✅ Includes results in completion notification
- ✅ Handles errors gracefully
- ✅ Auto-cleanup of resources

The results are available in:
1. Workflow state store (via `update_workflow_data_in_statestore`)
2. Completion notification metadata
3. Accessible via workflow API queries
