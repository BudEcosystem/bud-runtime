# Bud Stack Helm Chart

This Helm chart deploys a comprehensive set of microservices and infrastructure components for the Bud ecosystem, leveraging Dapr for inter-service communication and observability. It includes deployments for core applications, databases, caching, monitoring, and related tools.

## Overview

This chart is designed to deploy the following components:

*   **Core Applications:**
    *   `budapp`:  A core application for Bud.
    *   `budsim`: A simulator service.
    *   `budcluster`: Manages cluster resources.
    *   `budmodel`: Manages models.
    *   `budmetrics`: Collects and exposes metrics.
    *   `budproxy`: A proxy service for LiteLLM.
    *   `notify`: A notification service.
*   **Infrastructure Components:**
    *   **Redis Stack:**  A high-performance cache and message broker.
    *   **PostgreSQL:** Both a primary database and a dedicated metrics database.
    *   **MongoDB:** A document database.
    *   **MinIO:** An S3-compatible object storage server.
*   **Observability Tools:**
    *   **Prometheus:**  Monitoring and alerting system.
    *   **Grafana:**  Visualization and dashboarding.
    *   **Alertmanager:**  Alerting and notification system.
*  **Dapr Components:**
    *   Configured for secret management, pub/sub, state store, and actor support.
*   **Ingress:**
    *   Configured to expose various services using Traefik.
    *   Includes ingress for prometheus, grafana and applications.

## Prerequisites

*   Kubernetes cluster (version 1.19 or higher)
*   Helm 3.0+
*   `kubectl` configured to connect to your cluster
*   A persistent volume provisioner (e.g., `local-path`, `hostPath` or a cloud provider's storage solution)

## Chart Dependencies

This chart uses the following sub-charts:

*   `minio` (from `https://charts.min.io/`)
*   `kube-prometheus-stack` (from `https://prometheus-community.github.io/helm-charts`)

## Installing the Chart

1.  **Add the necessary Helm repositories:**

    ```bash
    helm repo add minio https://charts.min.io/
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add dapr https://dapr.github.io/helm-charts/
    helm repo add jetstack https://charts.jetstack.io
    helm repo add altinity https://helm.altinity.com
    helm repo add clickhouse-operator https://docs.altinity.com/clickhouse-operator
    helm repo update
    helm install altinity-clickhouse-operator altinity-clickhouse-operator/altinity-clickhouse-operato
r --namespace clickhouse-operator --create-namespace
    ```
2.  **Update your Helm dependencies:**

    ```bash
    helm repo update
    helm dependency update
    ```

    * This step is **crucial** as it ensures you have the latest versions of the sub-charts referenced in `Chart.yaml`.

3.  **Install the chart using Helm:**

    ```bash
    helm install cert-manager --force jetstack/cert-manager --namespace bud-system --create-namespace --set installCRDs=true
    kubectl get CustomResourceDefinition -o name | xargs -I{} kubectl annotate {} meta.helm.sh/release-name=<Stack-Name> --overwrite
    helm install <release-name> chart-bud --namespace <target-namespace> -f values.yaml
    ```

    *   Replace `<release-name>` with your desired release name (e.g., `bud-deployment`).
    *   Replace `<target-namespace>` with the namespace you want to deploy to (e.g., `dapr-system`).
    *   Ensure that `values.yaml` is configured with the specific parameters you need.

## Configuration

The chart's behavior is highly customizable through the `values.yaml` file. Here are some of the key configurable parameters:

*   **`namespace`**: The target namespace for all deployments.
*   **`replicaCount`**: The default replica count for deployments.
*   **`globalEnv`**: Global environment variables shared across all applications. This includes database connection strings, API keys, feature flags, etc.
*   **`Image`**: Configuration for the default application image (repository and tag).
*   **`mongodb`**: Configuration for the MongoDB deployment, including storage and credentials.
*   **`dapr`**: Configuration for Dapr components including secret store, Dapr id and API keys
*   **`apps`**: A list of application configurations (e.g., `notify`, `budsim`, `budapp`, `budcluster`, `budmodel`, `budmetrics`, `budproxy`) specifying images, ports, resources, and Dapr specific settings.
*   **`ingresses`**: A list of ingress configurations to expose the applications.
*   **`services`**: Configuration for additional services such as:
    *   `database`: Enables and configures a primary PostgreSQL instance.
    *   `metrics`: Enables and configures a PostgreSQL instance for metrics.
    *   `cache`: Enables and configures Redis for caching.
*   **`novu`**: Novu specific credentials
*   **`volumes`**: Configuration for persistent volumes.
*   **`minio`**: Configuration for the MinIO object store deployment.
*    **`redisStack`**: Configuration for redis stack database and its connection parameters
*   **`prometheus-node-exporter`**: Configuration for node exporter.
*   **`traefik`**: Configuration for Traefik ingress controller.
*   **`prometheus`**: Configuration for prometheus, including alert rules.
*   **`alertmanager`**: Configuration for alertmanager.
*   **`grafana`**: Configuration for grafana, including datasource configuration.
*   **`thanosRuler`**: Configuration for thanos ruler.
*   **`thanosQueryFrontend`**: Configuration for thanos query frontend.
*   **`thanosStore`**: Configuration for thanos store.
*   **`thanosCompactor`**: Configuration for thanos compactor.
*   **`networkPolicy`**: Configuration for network policy for restricting access between pods
*   Numerous parameters related to resources (memory, cpu), scaling, and service endpoints (ports).

## Configuration

The chart's behavior is highly customizable through the `values.yaml` file. The table below provides an overview of the main configuration options. For full details on each setting, please refer to the `values.yaml` file directly.

| Parameter                     | Description                                                                   | Default Value           |
|------------------------------|-------------------------------------------------------------------------------|------------------------|
| `namespace`                   | The target Kubernetes namespace for all deployments.                         | `dapr-system`          |
| `replicaCount`                | Default replica count for deployments.                                       | `1`                     |
| `globalEnv.data`              | Global environment variables shared across all applications.                    | (See `values.yaml`)     |
| `Image.repository`             | The Docker image repository for applications.                                 | `ghcr.io/novuhq/novu`  |
| `Image.tag`                    | The Docker image tag for applications.                                        | `0.24.0`                |
| `mongodb.initdbRootUsername`    | MongoDB root username.                                                        | `root`                 |
| `mongodb.initdbRootPassword`    | MongoDB root password.                                                        | `secret`               |
| `mongodb.storage.size`         | Storage size for MongoDB.                                                      | `5Gi`                    |
| `mongodb.storage.storageClassName` | Storage class name for MongoDB persistent volume claim.                    | `local-path`          |
| `mongodb.storage.hostPath`    | Host path for MongoDB persistent volume.                                     | `/datadisk/pvc/mongodb-data`|
| `apps`                       | Configuration for individual applications (e.g., `notify`, `budsim`, etc.), including images, ports, resources, Dapr settings and more. | (See `values.yaml`) |
| `ingresses`                 | Ingress configurations for exposing services, including hostnames, service names, and ports.                                 | (See `values.yaml`) |
| `services.database.enabled`   | Enables the primary PostgreSQL database.                                    | `true`                  |
| `services.database.postgres`  | PostgreSQL connection details for the primary database.                                               | (See `values.yaml`)     |
| `services.database.storage`   | PostgreSQL storage settings for the primary database.                                                 | (See `values.yaml`) |
| `services.metrics.enabled`    | Enables the PostgreSQL metrics database.                                      | `true`                  |
| `services.metrics.postgres`   | PostgreSQL connection details for the metrics database.                              | (See `values.yaml`)     |
| `services.metrics.storage`    | PostgreSQL metrics database storage settings.                               | (See `values.yaml`) |
| `services.cache.enabled`      | Enables the Redis cache.                                                       | `true`                  |
| `services.cache.redis`        | Redis connection details.                                                     | (See `values.yaml`) |
| `novu.credentials.email`    | Email for Novu credentials.                                                   | `admin@bud.studio` |
| `novu.credentials.password`    | Password for Novu credentials.                                                   | `Admin@1234` |
| `volumes`                   | Configuration for persistent volumes, including size and storage class.                                         | (See `values.yaml`)    |
| `minio`                   | Configuration for MinIO object store deployment, including replicas and bucket policies.                                         | (See `values.yaml`)    |
| `redisStack`                   | Configuration for Redis Stack database, including image, port, persistence and resources.                                        | (See `values.yaml`)    |
| `prometheus-node-exporter`   | Configuration for the prometheus node exporter service.                           | (See `values.yaml`)  |
| `traefik`                    | Configuration for the traefik ingress controller, including middleware.                             | (See `values.yaml`)  |
| `prometheus`                   | Configuration for prometheus, including alert rules, resources and storage.                              | (See `values.yaml`)     |
| `alertmanager`                   | Configuration for alertmanager, including resources.                                           | (See `values.yaml`)     |
| `grafana`                    | Configuration for Grafana dashboard, including admin credentials and persistence settings.                                          | (See `values.yaml`)  |
| `thanosRuler`                    | Configuration for thanos ruler service, including resources.                                        | (See `values.yaml`)  |
| `thanosQueryFrontend`                    | Configuration for thanos query frontend service, including resources.                                        | (See `values.yaml`)  |
|  `thanosStore`                 | Configuration for thanos store service, including resources.                                        | (See `values.yaml`)  |
| `thanosCompactor`                   | Configuration for thanos compactor service, including resources and retention policy.                                       | (See `values.yaml`)  |
| `networkPolicy`                   | Configuration for network policy, including enable.                                          | (See `values.yaml`)  |


## Values Overrides

Modify `values.yaml` to configure your deployment. Here are a few common overrides:

*   **Changing the container image tag**: Set the `Image.tag` value.
*   **Setting custom environment variables**: Add new key/value pairs under `globalEnv.data`
*   **Adjusting resource limits**: Modify the `resources.limits` and `resources.requests` sections for individual apps
*   **Customising Dapr settings**: Modify the `dapr` section for settings like logging level, component names, etc.
*  **Configuring ingress**: Update ingress domain names and service ports under the `ingresses` section