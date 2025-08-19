# Volume Management Quick Start Guide

This guide provides quick instructions for working with volumes in BudEval.

## Quick Commands

### Check Volume Status

```bash
# Check if eval-datasets volume exists
kubectl get pvc eval-datasets-pvc -n budeval

# Check all volumes in budeval namespace
kubectl get pvc -n budeval

# Check volume details
kubectl describe pvc eval-datasets-pvc -n budeval
```

### Initialize Volumes Manually

```bash
# Using the API endpoint
curl -X POST http://localhost:8099/evals/init-volume

# Check environment and configuration
python check_volume_env.py

# Check volume status
python check_volume.py
```

### Clean Up Volumes

```bash
# Delete shared dataset volume
kubectl delete pvc eval-datasets-pvc -n budeval

# Delete all job volumes
kubectl delete pvc -l app=budeval -n budeval

# Clean up orphaned PVs
kubectl get pv | grep Released | awk '{print $1}' | xargs kubectl delete pv
```

## Common Scenarios

### Starting Fresh

1. Clean up existing volumes:
   ```bash
   kubectl delete pvc --all -n budeval
   ```

2. Start the application:
   ```bash
   dapr run --run-file ./app.yaml --config .dapr/dapr_config.yaml
   ```

3. Verify volume creation:
   ```bash
   kubectl get pvc -n budeval
   ```

### Debugging Volume Issues

1. Check application logs:
   ```bash
   # Check for volume initialization logs
   tail -f /home/ubuntu/bud-serve-eval/logs/app.log | grep -E "(Volume|eval-datasets)"

   # Check Dapr logs
   tail -f /home/ubuntu/bud-serve-eval/.dapr/logs/budeval_app_*.log
   ```

2. Check Kubernetes events:
   ```bash
   kubectl get events -n budeval --sort-by='.lastTimestamp'
   ```

3. Verify storage class:
   ```bash
   kubectl get storageclass
   ```

### Local Development Setup

1. Ensure k3s is running:
   ```bash
   sudo systemctl status k3s
   ```

2. Verify local-path provisioner:
   ```bash
   kubectl get pods -n kube-system | grep local-path
   ```

3. Start the application:
   ```bash
   dapr run --run-file ./app.yaml --config .dapr/dapr_config.yaml
   ```

### Production Deployment

1. Set environment variable:
   ```bash
   export BUDEVAL_ENV=production
   ```

2. Ensure storage class supports ReadWriteMany:
   ```bash
   kubectl describe storageclass <your-storage-class>
   ```

3. Deploy application with appropriate configurations

## Environment Variables

```bash
# Override environment detection
export BUDEVAL_ENV=production  # or 'local'

# Check current configuration
python -c "from budeval.commons.storage_config import StorageConfig; print(StorageConfig.get_environment())"
```

## Verification Steps

### After Application Startup

1. Check logs for initialization:
   ```bash
   grep "BUDEVAL SERVICE STARTUP" /home/ubuntu/bud-serve-eval/logs/app.log
   grep "Volume initialization completed" /home/ubuntu/bud-serve-eval/logs/app.log
   ```

2. Verify PVC creation:
   ```bash
   kubectl get pvc eval-datasets-pvc -n budeval -o yaml
   ```

3. Check PVC status (should be "Bound"):
   ```bash
   kubectl get pvc -n budeval
   ```

### After Job Submission

1. Check job pod volumes:
   ```bash
   # Get job pod name
   kubectl get pods -n budeval -l job-name=<job-id>

   # Check volume mounts
   kubectl describe pod <pod-name> -n budeval | grep -A5 "Mounts:"
   ```

2. Verify dataset volume is read-only:
   ```bash
   kubectl exec -it <pod-name> -n budeval -- ls -la /datasets
   ```

## Troubleshooting Checklist

- [ ] Application logs show volume initialization?
- [ ] PVC exists in budeval namespace?
- [ ] PVC status is "Bound"?
- [ ] Storage class exists and is default?
- [ ] For local: Using ReadWriteOnce?
- [ ] For production: Storage class supports ReadWriteMany?
- [ ] Job pods have volumes mounted?
- [ ] Dataset volume mounted as read-only?

## Quick Fixes

### PVC Won't Bind

```bash
# Check storage class
kubectl get storageclass

# If no default storage class, set one
kubectl patch storageclass <storage-class-name> -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### Permission Issues

```bash
# Check PVC access modes
kubectl get pvc eval-datasets-pvc -n budeval -o jsonpath='{.spec.accessModes[*]}'

# For local development, ensure using RWO
# For production, ensure storage class supports RWX
```

### Volume Not Mounting in Pods

```bash
# Check if PVC is in same namespace as pod
kubectl get pvc -n budeval

# Check pod events
kubectl describe pod <pod-name> -n budeval

# Check if volume names match
kubectl get pod <pod-name> -n budeval -o yaml | grep -A10 volumes:
```

## Support Scripts Location

- `check_volume.py` - Check if volumes exist
- `check_volume_env.py` - Check environment configuration
- `cleanup_old_volume.sh` - Clean up old volumes
- `test_optional_kubeconfig.py` - Test kubeconfig handling
- `example_api_usage.py` - API usage examples

All scripts are in: `/home/ubuntu/bud-serve-eval/`
