# Deploying TensorZero on Kubernetes with Helm

> [!IMPORTANT]
>
> This is a reference deployment setup contributed by the community.
> Feedback and enhancements are welcome!

This example shows how to deploy the TensorZero (including the TensorZero Gateway, the TensorZero UI, and a ClickHouse database) on Kubernetes using Helm.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Ingress controller installed in your cluster (e.g. `traefik-ingress-controller-v3`)
- StorageClass configured for persistent volumes (e.g. `ebs-gp3-retain`)
- Sufficient resources for running ClickHouse and TensorZero services (recommend at least 4GB memory for minikube)

## Installing the Chart

To install the chart with the release name `tensorzero`:

```bash
# Create a namespace for tensorzero
kubectl create namespace tensorzero

# Install the chart
helm upgrade --install tensorzero .  -f values.yaml -n tensorzero
```

For local development or testing with minikube, you can use port forwarding to access the services:

```bash
# Port forward the gateway service (replace <your-model-name> with the value of modelName)
kubectl port-forward service/<your-model-name> -n tensorzero 3000:3000 &


## Uninstalling the Chart

To uninstall the `tensorzero` deployment, run:

```bash
helm uninstall tensorzero -n tensorzero
```

## Configuration

The following table lists the configurable parameters of the chart and their default values.

### Gateway Configuration

| Parameter                    | Description                | Default                         |
| ---------------------------- | -------------------------- | ------------------------------- |
| `gateway.replicaCount`       | Number of gateway replicas | `1`                             |
| `gateway.image.repository`   | Gateway image repository   | `tensorzero/gateway`            |
| `gateway.image.tag`          | Gateway image tag          | `latest`                        |
| `gateway.image.pullPolicy`   | Gateway image pull policy  | `IfNotPresent`                  |
| `gateway.service.type`       | Gateway service type       | `ClusterIP`                     |
| `gateway.service.port`       | Gateway service port       | `3000`                          |
| `gateway.resources.limits`   | Gateway resource limits    | `cpu: 2000m, memory: 4096Mi`    |
| `gateway.resources.requests` | Gateway resource requests  | `cpu: 2000m, memory: 4096Mi`    |
