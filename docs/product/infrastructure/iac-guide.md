# Infrastructure as Code Guide

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Reference Documentation
> **Audience:** DevOps, Platform Engineers

---

## 1. IaC Best Practices

### 1.1 GitOps Principles

| Principle | Implementation |
|-----------|----------------|
| Declarative | All infrastructure defined in code |
| Versioned | Git as single source of truth |
| Automated | Changes applied via CI/CD |
| Auditable | All changes tracked in git history |

### 1.2 Repository Structure

```
infra/
├── tofu/                    # Terraform/OpenTofu modules
│   ├── modules/
│   │   ├── eks/            # AWS EKS cluster
│   │   ├── aks/            # Azure AKS cluster
│   │   ├── networking/     # VPC, subnets
│   │   ├── storage/        # S3, EBS
│   │   └── iam/            # IAM roles
│   ├── environments/
│   │   ├── dev/
│   │   ├── staging/
│   │   └── production/
│   └── backend.tf
├── helm/                    # Helm charts
│   └── bud/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
└── ansible/                 # Ansible playbooks
    ├── playbooks/
    └── inventory/
```

### 1.3 State Management

**Remote State Configuration:**
```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket         = "bud-terraform-state"
    key            = "environments/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

**State Locking:**
```hcl
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

### 1.4 Module Standards

**Module Structure:**
```
modules/eks/
├── main.tf           # Main resources
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── versions.tf       # Provider versions
└── README.md         # Documentation
```

**Variable Naming:**
```hcl
# Use snake_case, descriptive names
variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "node_instance_types" {
  description = "EC2 instance types for worker nodes"
  type        = list(string)
  default     = ["m5.2xlarge"]
}
```

---

## 2. Ansible Playbook Reference

### 2.1 Playbook Structure

```
ansible/
├── playbooks/
│   ├── cluster-provision.yml    # Cluster provisioning
│   ├── cluster-upgrade.yml      # Cluster upgrades
│   ├── app-deploy.yml           # Application deployment
│   └── maintenance.yml          # Maintenance tasks
├── inventory/
│   ├── production/
│   │   ├── hosts.yml
│   │   └── group_vars/
│   └── staging/
├── roles/
│   ├── common/
│   ├── kubernetes/
│   ├── monitoring/
│   └── security/
└── ansible.cfg
```

### 2.2 Cluster Provisioning Playbook

```yaml
# playbooks/cluster-provision.yml
---
- name: Provision Kubernetes cluster
  hosts: localhost
  connection: local
  vars:
    cluster_name: "{{ lookup('env', 'CLUSTER_NAME') }}"
    region: "{{ lookup('env', 'AWS_REGION') | default('us-east-1') }}"

  tasks:
    - name: Create EKS cluster
      community.aws.eks_cluster:
        name: "{{ cluster_name }}"
        version: "1.28"
        region: "{{ region }}"
        role_arn: "{{ eks_role_arn }}"
        resources_vpc_config:
          subnet_ids: "{{ subnet_ids }}"
          security_group_ids: "{{ security_group_ids }}"
        state: present

    - name: Create node group
      community.aws.eks_nodegroup:
        cluster_name: "{{ cluster_name }}"
        nodegroup_name: "{{ cluster_name }}-workers"
        node_role_arn: "{{ node_role_arn }}"
        subnet_ids: "{{ subnet_ids }}"
        scaling_config:
          min_size: 3
          max_size: 10
          desired_size: 5
        instance_types:
          - m5.2xlarge
        state: present

    - name: Update kubeconfig
      shell: |
        aws eks update-kubeconfig --name {{ cluster_name }} --region {{ region }}
```

### 2.3 GPU Node Provisioning

```yaml
# playbooks/gpu-nodes.yml
---
- name: Provision GPU nodes
  hosts: localhost
  connection: local

  tasks:
    - name: Create GPU node group
      community.aws.eks_nodegroup:
        cluster_name: "{{ cluster_name }}"
        nodegroup_name: "{{ cluster_name }}-gpu"
        node_role_arn: "{{ node_role_arn }}"
        subnet_ids: "{{ subnet_ids }}"
        ami_type: AL2_x86_64_GPU
        scaling_config:
          min_size: 0
          max_size: 4
          desired_size: 2
        instance_types:
          - p4d.24xlarge
        labels:
          node.kubernetes.io/gpu: "true"
          nvidia.com/gpu: "true"
        taints:
          - key: nvidia.com/gpu
            value: "true"
            effect: NoSchedule
        state: present

    - name: Install NVIDIA device plugin
      kubernetes.core.k8s:
        state: present
        src: https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/nvidia-device-plugin.yml
```

### 2.4 Maintenance Playbook

```yaml
# playbooks/maintenance.yml
---
- name: Cluster maintenance
  hosts: localhost
  connection: local

  tasks:
    - name: Cordon nodes for maintenance
      kubernetes.core.k8s_drain:
        name: "{{ item }}"
        state: cordon
      loop: "{{ maintenance_nodes }}"

    - name: Drain workloads
      kubernetes.core.k8s_drain:
        name: "{{ item }}"
        state: drain
        delete_emptydir_data: true
        ignore_daemonsets: true
        timeout: 300
      loop: "{{ maintenance_nodes }}"

    - name: Perform maintenance
      include_tasks: maintenance-tasks.yml

    - name: Uncordon nodes
      kubernetes.core.k8s_drain:
        name: "{{ item }}"
        state: uncordon
      loop: "{{ maintenance_nodes }}"
```

---

## 3. Air-Gapped Installation

### 3.1 Prerequisites

| Requirement | Description |
|-------------|-------------|
| Container Registry | Harbor, Nexus, or similar |
| Helm Repository | ChartMuseum or registry |
| Package Mirror | Yum/Apt mirror for OS packages |
| Image Bundle | Pre-pulled container images |

### 3.2 Image Bundling

```bash
# Export images to tarball
IMAGES=(
  "ghcr.io/org/budapp:v1.2.3"
  "ghcr.io/org/budgateway:v1.2.3"
  "ghcr.io/org/budsim:v1.2.3"
  "postgres:15"
  "redis:7"
)

for img in "${IMAGES[@]}"; do
  docker pull $img
done

docker save "${IMAGES[@]}" | gzip > bud-images.tar.gz
```

### 3.3 Air-Gapped Deployment

```bash
# Load images to local registry
gunzip -c bud-images.tar.gz | docker load

# Re-tag for internal registry
docker tag ghcr.io/org/budapp:v1.2.3 registry.internal/bud/budapp:v1.2.3
docker push registry.internal/bud/budapp:v1.2.3

# Deploy with internal registry
helm upgrade --install bud ./infra/helm/bud \
  --set global.imageRegistry=registry.internal \
  --set global.imagePullSecrets[0].name=registry-secret
```

### 3.4 Helm Chart Mirroring

```bash
# Pull chart
helm pull bud/bud --version 1.2.3

# Push to internal repository
helm push bud-1.2.3.tgz oci://registry.internal/charts

# Install from internal repo
helm install bud oci://registry.internal/charts/bud --version 1.2.3
```

---

## 4. Disaster Recovery

### 4.1 DR Tier Classification

| Tier | RTO | RPO | Components |
|------|-----|-----|------------|
| Tier 1 (Critical) | 1 hour | 0 (sync) | API Gateway, Auth |
| Tier 2 (Essential) | 4 hours | 15 min | Databases, Core Services |
| Tier 3 (Important) | 24 hours | 1 hour | Monitoring, Logs |
| Tier 4 (Deferrable) | 72 hours | 24 hours | Analytics, Reports |

### 4.2 Recovery Order

```
1. Infrastructure (VPC, Kubernetes)
2. Databases (PostgreSQL, Redis)
3. Authentication (Keycloak)
4. Core Services (budapp, budcluster)
5. Gateway (budgateway)
6. Frontend (budadmin)
7. Optional Services (monitoring)
```

### 4.3 Partial Failover

**Database Failover:**
```bash
# Promote read replica to primary
aws rds failover-db-cluster --db-cluster-identifier bud-cluster

# Update connection strings
kubectl set env deployment/budapp DATABASE_URL=postgresql://new-primary:5432/budapp
```

**Service Failover:**
```bash
# Route traffic to DR region
kubectl patch service budapp-public -p '{"spec":{"selector":{"region":"dr"}}}'
```

### 4.4 MongoDB Backup/Restore

```bash
# Backup
mongodump --uri="mongodb://mongodb:27017/budnotify" --archive=/backup/budnotify.archive

# Restore
mongorestore --uri="mongodb://mongodb:27017/budnotify" --archive=/backup/budnotify.archive --drop
```

---

## 5. Integration Documentation

### 5.1 On-Premises Integration

**VMware Integration:**
```yaml
# vSphere provider configuration
provider "vsphere" {
  vsphere_server       = var.vsphere_server
  user                 = var.vsphere_user
  password             = var.vsphere_password
  allow_unverified_ssl = false
}

resource "vsphere_virtual_machine" "k8s_node" {
  name             = "k8s-worker-${count.index}"
  resource_pool_id = data.vsphere_resource_pool.pool.id
  datastore_id     = data.vsphere_datastore.datastore.id
  num_cpus         = 8
  memory           = 32768

  network_interface {
    network_id = data.vsphere_network.network.id
  }

  disk {
    label = "disk0"
    size  = 200
  }
}
```

**Bare Metal:**
```yaml
# Ansible inventory for bare metal
all:
  children:
    k8s_masters:
      hosts:
        master-01:
          ansible_host: 10.0.1.10
          ansible_user: admin
    k8s_workers:
      hosts:
        worker-01:
          ansible_host: 10.0.1.20
        worker-02:
          ansible_host: 10.0.1.21
    gpu_nodes:
      hosts:
        gpu-01:
          ansible_host: 10.0.1.30
          gpu_type: nvidia-a100
```

### 5.2 Monitoring Integration

**Datadog:**
```yaml
# Datadog agent configuration
datadog:
  apiKey:
    existingSecret: datadog-secret
  site: datadoghq.com
  logs:
    enabled: true
  apm:
    enabled: true
  processAgent:
    enabled: true
```

**Splunk:**
```yaml
# Splunk forwarder configuration
splunk:
  hec:
    endpoint: https://splunk.example.com:8088
    token:
      existingSecret: splunk-hec-token
    indexName: bud-logs
```

### 5.3 SIEM Integration

```yaml
# Forward security events to SIEM
fluentd:
  sources:
    - type: tail
      path: /var/log/audit/audit.log
      tag: audit
  outputs:
    - type: syslog
      host: siem.example.com
      port: 514
      protocol: tls
      match: audit.**
```

---

## 6. SDK & CLI Reference

### 6.1 Python SDK

```python
from bud import BudClient

# Initialize client
client = BudClient(
    api_key="bud_live_...",
    base_url="https://api.bud.example.com"
)

# List projects
projects = client.projects.list()

# Create endpoint
endpoint = client.endpoints.create(
    project_id="uuid",
    name="my-endpoint",
    model_id="uuid",
    config={
        "max_model_len": 4096,
        "tensor_parallel_size": 2
    }
)

# Deploy endpoint
deployment = client.endpoints.deploy(
    endpoint_id=endpoint.id,
    cluster_id="uuid",
    replicas=1
)

# Inference
response = client.chat.completions.create(
    model="my-endpoint",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=100
)
print(response.choices[0].message.content)
```

### 6.2 CLI Reference

```bash
# Configuration
bud configure --api-key bud_live_...
bud configure --profile production

# Projects
bud projects list
bud projects create --name "My Project"
bud projects get <project-id>

# Endpoints
bud endpoints list --project <project-id>
bud endpoints create --project <project-id> --name "endpoint" --model <model-id>
bud endpoints deploy <endpoint-id> --cluster <cluster-id>
bud endpoints undeploy <endpoint-id>

# Inference
bud chat "Hello!" --endpoint <endpoint-name>
bud chat --endpoint <endpoint-name> --stream

# Clusters
bud clusters list
bud clusters get <cluster-id>
bud clusters refresh <cluster-id>

# Models
bud models list
bud models search --query "llama"
```

### 6.3 Terraform Provider

```hcl
terraform {
  required_providers {
    bud = {
      source  = "bud-ecosystem/bud"
      version = "~> 1.0"
    }
  }
}

provider "bud" {
  api_key = var.bud_api_key
}

resource "bud_project" "example" {
  name        = "terraform-project"
  description = "Managed by Terraform"
}

resource "bud_endpoint" "llama" {
  project_id = bud_project.example.id
  name       = "llama-3-endpoint"
  model_id   = "model-uuid"

  config {
    max_model_len         = 4096
    tensor_parallel_size  = 2
    gpu_memory_utilization = 0.9
  }
}

resource "bud_deployment" "llama" {
  endpoint_id = bud_endpoint.llama.id
  cluster_id  = "cluster-uuid"
  replicas    = 1
}
```
