# Volume Management in BudEval

This document describes the volume management system in BudEval, including automatic volume provisioning, environment-aware configuration, and shared dataset storage.

## Overview

BudEval uses Kubernetes Persistent Volumes (PV) and Persistent Volume Claims (PVC) to manage storage for evaluation jobs. The system automatically provisions volumes without requiring manual PV creation or hostPath mounting.

## Key Features

- **Automatic Volume Provisioning**: Volumes are created on application startup
- **Environment-Aware Configuration**: Different settings for development vs production
- **Dynamic Storage Provisioning**: No manual PV creation required
- **Shared Dataset Volume**: A common volume for evaluation datasets
- **Job-Specific Volumes**: Separate volumes for each evaluation job

## Architecture

### Volume Types

1. **Shared Dataset Volume (`eval-datasets`)**
   - Mounted at `/datasets` in evaluation pods
   - Read-only access for evaluation jobs
   - Persistent across all jobs
   - Created once during application startup

2. **Job-Specific Volumes**
   - **Data Volume**: Mounted at `/data` for job input
   - **Output Volume**: Mounted at `/output` for job results
   - Created per evaluation job
   - Cleaned up after job completion (based on TTL)

### Storage Classes

The system uses explicit storage class configuration per environment:

- **Local Development**: `local-path` (Rancher Local Path Provisioner)
- **Production**: Empty string (uses cluster default)

#### Storage Class Configuration

Storage classes are configured in `budeval/commons/storage_config.py`:

```python
"local": {
    "eval_datasets": {
        "storage_class": "local-path",  # Explicit for K3s
        # ...
    }
},
"production": {
    "eval_datasets": {
        "storage_class": "",  # Use cluster default
        # ...
    }
}
```

#### Local Path Provisioner Behavior

The `local-path` storage class has special characteristics:
- **Binding Mode**: `WaitForFirstConsumer` - PVCs remain Pending until a pod uses them
- **Volume Provisioning**: PVs are created only when a pod schedules and requests the volume
- **Node Affinity**: Volumes are tied to specific nodes where pods are scheduled

## Environment Detection

The system automatically detects the environment and applies appropriate configurations:

```python
# Detection logic
if os.path.exists("/home/ubuntu/bud-serve-eval/k3s.yaml"):
    environment = "local"
else:
    environment = os.environ.get("BUDEVAL_ENV", "production")
```

### Configuration by Environment

| Setting | Local Development | Production |
|---------|------------------|------------|
| **Shared Dataset Volume** |
| Access Mode | ReadWriteOnce | ReadWriteMany |
| Size | 10Gi | 100Gi |
| Storage Class | local-path | "" (default) |
| **Job Volumes** |
| Access Mode | ReadWriteOnce | ReadWriteOnce |
| Data Size | 5Gi | 20Gi |
| Output Size | 5Gi | 20Gi |
| Storage Class | local-path | "" (default) |

## Implementation Details

### Startup Volume Initialization

When the application starts, it automatically ensures the shared dataset volume exists:

```python
# budeval/main.py
@app.on_event("startup")
async def startup_event():
    """Initialize required volumes on startup."""
    volume_init = VolumeInitializer()
    await volume_init.ensure_eval_datasets_volume()
```

### Volume Initialization Process

1. **Environment Detection**: Determines if running locally or in production
2. **Configuration Loading**: Loads appropriate storage settings
3. **PVC Creation**: Creates PVC if it doesn't exist
4. **First Consumer Trigger**: For `local-path`, creates temporary pod to trigger binding
5. **Dynamic Provisioning**: Kubernetes storage class provisions the actual PV

### Ansible Playbooks

The system uses Ansible playbooks for Kubernetes operations:

#### `ensure_eval_datasets_volume.yml`
- Ensures namespace exists
- Checks if PVC exists
- Creates PVC with environment-specific settings
- Creates temporary pod to trigger binding (for WaitForFirstConsumer)
- Waits for PVC to be bound
- Cleans up temporary pod

#### `submit_job_with_volumes_k8s.yml`
- Creates job-specific PVCs
- Mounts all required volumes to the job pod
- Includes the shared dataset volume as read-only

## API Endpoints

### Volume Initialization

```bash
POST /evals/init-volume
```

Manually trigger volume initialization (useful for testing):

```bash
curl -X POST http://localhost:8099/evals/init-volume
```

Response:
```json
{
  "status": "success",
  "message": "Volume initialization completed"
}
```

## Configuration

### Storage Configuration Module

The `budeval/commons/storage_config.py` module provides centralized storage configuration:

```python
from budeval.commons.storage_config import StorageConfig

# Get environment
env = StorageConfig.get_environment()

# Get eval datasets configuration
eval_config = StorageConfig.get_eval_datasets_config()
# Returns: {"access_mode": "...", "size": "...", "storage_class": "..."}

# Get job volumes configuration
job_config = StorageConfig.get_job_volumes_config()
# Returns: {"access_mode": "...", "data_size": "...", "output_size": "...", "storage_class": "..."}
```

### Environment Variables

- `BUDEVAL_ENV`: Set to override environment detection (values: `local`, `production`)

## Job Volume Mounting

When an evaluation job is created, it automatically gets access to:

```yaml
volumeMounts:
  - name: data-volume
    mountPath: /data
  - name: output-volume
    mountPath: /output
  - name: eval-datasets
    mountPath: /datasets
    readOnly: true
```

## Troubleshooting

### Check Volume Status

Use the provided check scripts:

```bash
# Check if volumes exist
python check_volume.py

# Check environment and configuration
python check_volume_env.py
```

### Troubleshooting Storage Class Issues

#### Issue: "no persistent volumes available for this claim and no storage class is set"

This error occurs when the PVC has an empty `storageClassName` field.

**Diagnosis:**
```bash
kubectl describe pvc eval-datasets-pvc -n budeval
# Look for: StorageClass: <unset>
```

**Solution:**
1. Update storage configuration:
   ```python
   # In budeval/commons/storage_config.py
   "storage_class": "local-path",  # Instead of ""
   ```

2. Delete and recreate the PVC:
   ```bash
   kubectl delete pvc eval-datasets-pvc -n budeval
   # Restart application or call POST /evals/init-volume
   ```

#### Issue: PVC stuck in Pending with WaitForFirstConsumer

This is normal behavior for `local-path` storage class.

**Diagnosis:**
```bash
kubectl get storageclass local-path -o yaml | grep volumeBindingMode
# Should show: volumeBindingMode: WaitForFirstConsumer
```

**Solution (Manual):**
```bash
# Create a temporary pod to trigger binding
kubectl run volume-trigger --image=busybox:1.36 --restart=Never -n budeval \
  --overrides='{
    "spec": {
      "containers": [{
        "name": "volume-trigger",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "echo Volume initialized && sleep 10"],
        "volumeMounts": [{"name": "data", "mountPath": "/data"}]
      }],
      "volumes": [{
        "name": "data",
        "persistentVolumeClaim": {"claimName": "eval-datasets-pvc"}
      }]
    }
  }'

# Wait for binding, then clean up
kubectl delete pod volume-trigger -n budeval
```

### Manual Volume Operations

```bash
# List PVCs
kubectl get pvc -n budeval

# List PVs
kubectl get pv

# Describe a PVC
kubectl describe pvc eval-datasets-pvc -n budeval
```

### Common Issues

1. **PVC Pending State with "no storage class is set"**
   - **Cause**: Empty `storageClassName` in PVC definition
   - **Solution**: Ensure storage configuration specifies proper storage class
   - **Local Fix**: Set `storage_class: "local-path"` in `storage_config.py`
   - **Check**: `kubectl describe pvc <pvc-name> -n budeval`

2. **PVC Pending with WaitForFirstConsumer**
   - **Cause**: `local-path` storage class waits for pod to schedule
   - **Solution**: Create a pod that uses the PVC to trigger binding
   - **Check**: `kubectl get storageclass local-path -o yaml | grep volumeBindingMode`

3. **Storage Class Not Found**
   - Check if storage class exists: `kubectl get storageclass`
   - Verify storage class supports the requested access mode
   - Check available storage capacity

4. **Access Mode Conflicts**
   - Local development: Use ReadWriteOnce (RWO)
   - Production: Ensure storage class supports ReadWriteMany (RWX) if needed

5. **Volume Not Mounting**
   - Verify PVC exists in the same namespace as the pod
   - Check pod events: `kubectl describe pod <pod-name> -n budeval`
   - Ensure PVC is in "Bound" state before pod creation

## Development Guidelines

### Adding New Volumes

1. Update storage configuration in `storage_config.py`
2. Create/update Ansible playbook for volume creation
3. Add volume mount to job template in `ansible_orchestrator.py`

### Testing Volume Creation

1. Clean up existing volumes:
   ```bash
   kubectl delete pvc eval-datasets-pvc -n budeval
   ```

2. Restart the application to trigger volume creation:
   ```bash
   dapr run --run-file ./app.yaml --config .dapr/dapr_config.yaml
   ```

3. Verify volume creation:
   ```bash
   kubectl get pvc -n budeval
   ```

## Best Practices

1. **No HostPath**: Always use dynamic provisioning instead of hostPath
2. **Environment-Specific Settings**: Use appropriate access modes and sizes
3. **Cleanup**: Implement proper cleanup for job-specific volumes
4. **Monitoring**: Check volume usage and adjust sizes as needed
5. **Backup**: Implement backup strategies for critical data

## Migration from HostPath

If migrating from hostPath volumes:

1. Backup any existing data
2. Delete old PV/PVC with hostPath
3. Let the system create new dynamically provisioned volumes
4. Restore data if needed

## Security Considerations

1. **Read-Only Mounts**: Shared datasets are mounted read-only in jobs
2. **Namespace Isolation**: Volumes are namespace-scoped
3. **Access Control**: Use Kubernetes RBAC to control volume access
4. **Encryption**: Enable encryption at rest based on storage class capabilities

## Future Enhancements

1. **Volume Snapshots**: Implement backup using volume snapshots
2. **Dynamic Resizing**: Support volume expansion when needed
3. **Multi-Region**: Support for cross-region volume replication
4. **Metrics**: Add volume usage monitoring and alerts