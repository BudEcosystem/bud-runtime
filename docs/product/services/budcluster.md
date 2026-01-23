# budcluster Service Documentation

---

## Overview

budcluster manages the lifecycle of Kubernetes clusters across AWS EKS, Azure AKS, and on-premises environments. It handles provisioning, onboarding, model deployment, and cluster monitoring.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budcluster |
| **Port** | 9082 |
| **Database** | budcluster_db (PostgreSQL) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Provision new Kubernetes clusters via Terraform (AWS EKS, Azure AKS)
- Onboard existing clusters via Ansible
- Deploy model runtimes
- Manage cluster credentials with RSA encryption
- Hardware detection via Node Feature Discovery (NFD)
- GPU time-slicing
- Monitor cluster health and resource usage

---

## Module Structure

```
budcluster/
├── cluster/              # Cluster lifecycle
│   ├── routes.py         # Cluster CRUD endpoints
│   ├── services.py       # Cluster operations
│   ├── workflows.py      # Dapr provisioning workflows
│   └── models.py         # Cluster model
│
├── deployment/           # Model deployment
│   ├── routes.py         # Deployment endpoints
│   ├── services.py       # Deployment logic
│   ├── helm_utils.py     # Helm chart operations
│   └── models.py         # Deployment model
│
├── provisioning/         # Infrastructure provisioning
│   ├── terraform/        # Terraform wrappers
│   │   ├── aws_eks.py    # AWS EKS provisioning
│   │   └── azure_aks.py  # Azure AKS provisioning
│   └── ansible/          # Ansible wrappers
│       └── onboard.py    # Cluster onboarding
│
├── credentials/          # Credential management
│   ├── services.py       # Encryption/decryption
│   └── models.py         # Credential storage
│
├── hardware/             # Hardware detection
│   ├── nfd.py            # Node Feature Discovery
│   └── hami.py           # GPU time-slicing
│
├── playbooks/            # Ansible playbooks
│   ├── onboard.yml       # Cluster onboarding
│   ├── deploy_runtime.yml
│   ├── install_nfd.yml
│   └── install_hami.yml
│
└── crypto-keys/          # Encryption keys (gitignored)
    ├── rsa-private-key.pem
    └── symmetric-key-256
```

---

## API Endpoints

### Clusters

| Method | Path | Description |
|--------|------|-------------|
| GET | `/clusters` | List clusters |
| POST | `/clusters` | Create/provision cluster |
| GET | `/clusters/{id}` | Get cluster details |
| DELETE | `/clusters/{id}` | Delete cluster |
| POST | `/clusters/{id}/onboard` | Onboard existing cluster |
| GET | `/clusters/{id}/nodes` | List cluster nodes |
| GET | `/clusters/{id}/hardware` | Get hardware profile |

### Deployments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/deployments` | List deployments |
| POST | `/deployments` | Create deployment |
| GET | `/deployments/{id}` | Get deployment |
| DELETE | `/deployments/{id}` | Delete deployment |
| POST | `/deployments/{id}/scale` | Scale deployment |
| GET | `/deployments/{id}/logs` | Get deployment logs |

### Hardware

| Method | Path | Description |
|--------|------|-------------|
| POST | `/clusters/{id}/detect-hardware` | Run NFD detection |
| GET | `/clusters/{id}/gpus` | List GPUs |
| POST | `/clusters/{id}/install-hami` | Install GPU time-slicing |

---

## Data Models

### Cluster

```python
class Cluster(Base):
    id: UUID
    name: str
    provider: ClusterProvider  # AWS_EKS, AZURE_AKS, ON_PREMISES
    region: str
    status: ClusterStatus  # PROVISIONING, READY, ERROR, DELETING
    kubeconfig_encrypted: bytes  # RSA encrypted
    node_count: int
    gpu_count: int
    hardware_profile: dict
    created_at: datetime
```

### Deployment

```python
class Deployment(Base):
    id: UUID
    cluster_id: UUID
    endpoint_id: UUID
    model_id: UUID
    runtime: RuntimeType  # VLLM, SGLANG, TENSORRT_LLM
    config: dict  # TP, PP, batch size, replicas
    status: DeploymentStatus
    helm_release: str
    created_at: datetime
```

---

## Provisioning Workflows

### AWS EKS Provisioning

```
1. Validate AWS credentials
2. Terraform plan:
   - VPC with public/private subnets
   - EKS cluster
   - Node groups (CPU + GPU)
   - IAM roles
3. Terraform apply
4. Store encrypted kubeconfig
5. Post-provisioning:
   - Install NFD
   - Install GPU Operator (if GPUs detected)
   - Install HAMI
   - Deploy Prometheus stack
```

### Azure AKS Provisioning

```
1. Validate Azure credentials
2. Terraform plan:
   - Resource group
   - AKS cluster
   - Node pools (CPU + GPU)
   - AAD integration
3. Terraform apply
4. Store encrypted kubeconfig
5. Post-provisioning (same as EKS)
```

### On-Premises Onboarding

```
1. Validate kubeconfig access
2. Ansible playbook:
   - Verify connectivity
   - Check Kubernetes version
   - Install required CRDs
3. Hardware detection (NFD)
4. GPU setup (if applicable)
5. Store encrypted kubeconfig
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `RSA_PRIVATE_KEY_PATH` | Path to RSA private key | `crypto-keys/rsa-private-key.pem` |
| `SYMMETRIC_KEY_PATH` | Path to symmetric key | `crypto-keys/symmetric-key-256` |
| `TERRAFORM_WORKSPACE` | Terraform workspace directory | `/tmp/terraform` |
| `ANSIBLE_PLAYBOOKS_PATH` | Ansible playbooks directory | `./playbooks` |
| `NFD_DETECTION_TIMEOUT` | NFD timeout in seconds | `300` |
| `DAPR_HTTP_ENDPOINT` | Dapr sidecar endpoint | `http://localhost:3500` |

### Crypto Keys Setup

```bash
mkdir -p crypto-keys

# Generate RSA key pair (4096-bit)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 \
  -out crypto-keys/rsa-private-key.pem

# Generate symmetric key (256-bit)
openssl rand -out crypto-keys/symmetric-key-256 32

# Set permissions
chmod 644 crypto-keys/rsa-private-key.pem crypto-keys/symmetric-key-256
```

---

## Key Features

### Max Model Length Calculation

The maximum context length for deployed models is calculated dynamically:

```python
max_model_length = (input_tokens + output_tokens) * 1.1
```

### Hardware Detection

NFD (Node Feature Discovery) detects:
- GPU type and count
- CPU architecture
- Memory capacity
- Network capabilities

### HAMI GPU Time-Slicing

When NVIDIA GPUs are detected, HAMI is auto-installed to enable:
- GPU sharing between pods
- Memory isolation
- Compute time allocation

---

## Development

### Running Locally

```bash
cd services/budcluster

# Setup crypto keys
./setup-crypto-keys.sh

# Start with Docker Compose
./deploy/start_dev.sh --build
```

### Running Tests

```bash
pytest
pytest tests/test_provisioning.py
pytest --dapr-http-port 3510 --dapr-api-token TOKEN
```

---

## Related Documents

- [Cluster Onboarding Runbook](../operations/cluster-onboarding.md)
- [High-Level Architecture](../architecture/high-level-architecture.md)
