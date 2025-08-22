# BudEval Job Lifecycle Documentation

## Overview

The BudEval platform orchestrates AI model evaluation jobs on Kubernetes clusters. This document describes the complete lifecycle of an evaluation job from submission to completion.

## Job Lifecycle Phases

### 1. Job Submission (`POST /evals/start`)

When a client submits an evaluation request:

```json
{
  "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
  "model_name": "gpt-4",
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "kubeconfig": null  // Optional, uses local k3s.yaml if not provided
}
```

**What happens:**
- Request validation via Pydantic schemas
- Background volume initialization check (non-blocking)
- Workflow instance creation with unique ID
- Immediate response with workflow metadata

### 2. Workflow Orchestration

The evaluation workflow consists of three main activities:

```
┌─────────────────────────┐
│ verify_cluster_         │
│ connection              │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ deploy_eval_job         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ monitor_eval_job_       │
│ progress                │
└─────────────────────────┘
```

### 3. Cluster Verification

**Purpose:** Ensure Kubernetes cluster is accessible before job deployment

**Process:**
- Runs `verify_cluster_k8s.yml` Ansible playbook
- Tests cluster connectivity using provided or default kubeconfig
- Returns verification status

**Success criteria:**
- Cluster API is reachable
- Namespace exists or can be created

### 4. Job Deployment

**Purpose:** Create Kubernetes resources for the evaluation job

**Resources created:**
1. **Persistent Volume Claims (PVCs)**
   - Data PVC: `{job_id}-data-pvc` (10Gi)
   - Output PVC: `{job_id}-output-pvc` (10Gi)
   - Both use dynamic provisioning with storage class

2. **Kubernetes Job**
   - Container image: Configurable per engine (default: busybox for testing)
   - Volume mounts:
     - `/data` - Job-specific data volume
     - `/output` - Job-specific output volume
     - `/datasets` - Shared evaluation datasets (read-only)
   - Environment variables:
     - `ENGINE_ARGS` - JSON-encoded evaluation parameters

**Storage configuration (environment-aware):**
```python
# Local development
{
  "access_mode": "ReadWriteOnce",
  "storage_class": "local-path",
  "data_size": "10Gi",
  "output_size": "10Gi"
}

# Production
{
  "access_mode": "ReadWriteOnce",bu
  "storage_class": "",  # Use cluster default
  "data_size": "20Gi",
  "output_size": "20Gi"
}
```

### 5. Job Execution

**Container lifecycle:**
1. PVCs are created in Pending state
2. Job pod is scheduled
3. Storage provisioner creates PVs dynamically
4. PVCs bind to PVs when pod starts
5. Container executes with mounted volumes
6. Evaluation process runs
7. Results written to output volume

**Example test container:**
```bash
echo 'Starting evaluation job...'
echo 'Engine args:'; echo $ENGINE_ARGS
echo 'Waiting 20 seconds...'
sleep 20
echo 'Job completed successfully!'
```

### 6. Job Monitoring

**Purpose:** Track job progress and detect completion

**Monitoring loop:**
- Polls job status every 5 seconds
- Checks job phase and pod status
- Updates workflow state in database
- Publishes status notifications via Dapr

**Status transitions:**
```
Pending → Running → Succeeded/Failed
```

**Status details include:**
- Job phase (Active, Complete, Failed)
- Pod counts (active, succeeded, failed)
- PVC binding status
- Error messages if any

### 7. Job Completion

**TTL (Time To Live):**
- Jobs have `ttlSecondsAfterFinished: 3600` (1 hour)
- Kubernetes automatically cleans up completed jobs after TTL

**Completion states:**
- **Succeeded**: Exit code 0, all pods completed
- **Failed**: Non-zero exit code or exceeded retry limit
- **Active**: Still running

## API Endpoints

### Submit Evaluation
```bash
POST /evals/start
Content-Type: application/json

{
  "eval_request_id": "uuid",
  "model_name": "model-name",
  "api_key": "api-key",
  "base_url": "https://api.example.com"
}
```

### Check Job Status
```bash
GET /evals/status/{job_id}
```

Response:
```json
{
  "job_id": "eval-123e4567-e89b-12d3-a456-426614174000",
  "status": "succeeded",
  "namespace": "budeval",
  "details": {
    "status": "succeeded",
    "phase": "Complete",
    "active": "0",
    "succeeded": "1",
    "failed": "0",
    "pod_count": "1",
    "data_pvc_status": "Bound",
    "output_pvc_status": "Bound"
  }
}
```

### Cleanup Job Resources
```bash
DELETE /evals/cleanup/{job_id}
```

Removes:
- Kubernetes Job
- Data PVC and PV
- Output PVC and PV

## Volume Management

### Shared Evaluation Datasets Volume
- **Name**: `eval-datasets-pvc`
- **Size**: 10Gi (local), 100Gi (production)
- **Access**: ReadWriteOnce (local), ReadWriteMany (production)
- **Content**: OpenCompass datasets (~7.8GB)
- **Initialization**: Automatic on first use

### Job-Specific Volumes
- Created per evaluation job
- Isolated data and output storage
- Automatically cleaned up with job

## Error Handling

### Common Issues and Solutions

1. **PVC Pending State**
   - Local-path storage: Normal until pod mounts it
   - Production: Check storage class and capacity

2. **Job Failed**
   - Check container logs: `kubectl logs -n budeval job/{job_id}`
   - Verify engine arguments and API credentials
   - Check resource limits and quotas

3. **Workflow Stuck**
   - Check Dapr workflow worker status
   - Verify database connectivity
   - Review ansible playbook execution logs

## Configuration Files

- **Storage Config**: `budeval/commons/storage_config.py`
- **Ansible Playbooks**: `budeval/ansible/playbooks/`
  - `verify_cluster_k8s.yml`
  - `submit_job_with_volumes_k8s.yml`
  - `get_job_status_k8s.yml`
  - `cleanup_job_resources_k8s.yml`
- **Engine Registry**: `budeval/registry/engines/`

## Monitoring and Debugging

### Check Dataset Status
```bash
./dataset-status
```

### View Application Logs
```bash
tail -f /home/ubuntu/bud-serve-eval/.dapr/logs/budeval_app_*.log
```

### Kubernetes Commands
```bash
# List all evaluation jobs
kubectl get jobs -n budeval

# Check job details
kubectl describe job -n budeval {job_id}

# View job logs
kubectl logs -n budeval job/{job_id}

# List PVCs
kubectl get pvc -n budeval
```

## Best Practices

1. **Resource Management**
   - Set appropriate volume sizes based on dataset requirements
   - Configure job TTL to prevent resource accumulation
   - Monitor PVC usage and clean up orphaned volumes

2. **Error Recovery**
   - Implement retry logic in evaluation containers
   - Use init containers for pre-flight checks
   - Set appropriate job backoff limits

3. **Security**
   - Never log sensitive credentials
   - Use Kubernetes secrets for API keys
   - Restrict volume access with appropriate permissions

## Future Enhancements

1. **Job Prioritization**: Implement priority classes for urgent evaluations
2. **Resource Quotas**: Set namespace quotas to prevent resource exhaustion
3. **Result Persistence**: Archive evaluation results to object storage
4. **Multi-cluster Support**: Deploy jobs across multiple clusters for scale
5. **Real-time Logs**: Stream container logs via WebSocket API
