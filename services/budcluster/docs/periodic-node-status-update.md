# Periodic Node Status Update

This document describes the periodic job mechanism for keeping cluster node status up-to-date in the state store.

## Overview

The periodic node status update job ensures that the cluster node information in the state store remains synchronized with the actual cluster state. This prevents issues where deployments might proceed even when nodes are unavailable or tainted.

## Components

### 1. API Endpoint
- **Path**: `/cluster/periodic-node-status-update`
- **Method**: POST
- **Purpose**: Triggers node status update for all active clusters

### 2. Dapr Cron Binding
- **Component Name**: `periodic-node-status-update`
- **Type**: `bindings.cron`
- **Schedule**: Every 3 minutes (`@every 3m`)
- **Target Route**: `/cluster/periodic-node-status-update`

### 3. Implementation Details

The binding performs the following steps:
1. Dapr cron binding triggers the endpoint every 3 minutes
2. Retrieves all clusters with status `AVAILABLE` or `NOT_AVAILABLE`
3. Triggers the `UpdateClusterStatusWorkflow` for each cluster
4. Each workflow updates the node information in the state store
5. Logs success/failure metrics

## Setup Instructions

### Dapr Binding Configuration

The Dapr binding is automatically configured via the component file:
- **Location**: `services/budcluster/.dapr/components/binding.yaml`
- **Auto-loaded**: When budcluster starts with Dapr sidecar

No manual setup is required - the binding is automatically active when the service runs.

### Verifying Binding Status

Check Dapr component status:

```bash
dapr components -k
```

Look for the `periodic-node-status-update` binding component.

### Manual Trigger

To manually trigger the node status update:

```bash
curl -X POST "http://localhost:8002/cluster/periodic-node-status-update" \
  -H "Content-Type: application/json"
```

## Node Status Detection

The system detects the following node conditions:
- **Ready**: Node is healthy and can accept workloads
- **NotReady**: Node is not ready to accept pods
- **Unschedulable**: Node is marked as unschedulable (cordoned)
- **UnderPressure**: Node has resource pressure (memory, disk, PID)

Nodes with taints are also properly detected and marked as unavailable.

## Integration with BudSim

BudSim filters nodes based on their status:
- Only nodes with `status: true` are considered available
- Nodes in problematic states (NotReady, Unschedulable, UnderPressure) are excluded
- If no available nodes are found, the simulation fails with an appropriate error message

## Monitoring

The job logs the following information:
- Number of clusters processed
- Success/failure count for each run
- Specific errors for failed updates

Check logs:
```bash
kubectl logs -n bud-system deployment/budcluster-daprd -c daprd | grep "periodic-node-status"
```

## Troubleshooting

### Binding Not Running
1. Check if the binding component is loaded: `dapr components -k`
2. Verify the binding YAML syntax in `.dapr/components/binding.yaml`
3. Check Dapr sidecar logs for binding errors

### Node Status Not Updating
1. Check budcluster logs for workflow execution errors
2. Verify cluster credentials are valid
3. Ensure network connectivity to clusters

### State Store Issues
1. Verify Redis/state store is accessible
2. Check for state store key conflicts
3. Review Dapr state store component configuration
