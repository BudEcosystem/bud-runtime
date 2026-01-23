# Bud AI Foundry - Platform Datasheet

---

## Overview

Bud AI Foundry is an enterprise control plane for GenAI deployments that maximizes infrastructure performance through intelligent optimization and unified management across multi-cloud environments.

---

## Key Capabilities

| Capability | Description |
|------------|-------------|
| **Intelligent Deployment** | AI-powered optimization recommends optimal GPU allocation, tensor/pipeline parallelism, and batch sizing |
| **Multi-Cloud Management** | Unified control plane for AWS EKS, Azure AKS, and on-premises Kubernetes clusters |
| **Model Registry** | Centralized catalog with versioning, licensing validation, and security scanning |
| **High-Performance Gateway** | Sub-millisecond routing with OpenAI-compatible API for all inference endpoints |
| **Performance Simulation** | XGBoost + genetic algorithms predict throughput, latency, and resource requirements |
| **Enterprise Observability** | Full LGTM stack (Grafana, Loki, Tempo, Mimir) with inference-specific metrics |

---

## Technical Specifications

### Supported Infrastructure

| Category | Options |
|----------|---------|
| **Cloud Providers** | AWS, Azure, On-premises |
| **Kubernetes** | EKS, AKS, OpenShift, Vanilla K8s 1.26+ |
| **GPU Support** | NVIDIA A100, H100, L40S, A10G, T4 (via HAMI time-slicing) |
| **CPU Inference** | Intel Gaudi (HPU), AMD MI300 |

### Supported AI Frameworks

| Category | Frameworks |
|----------|------------|
| **Inference Runtimes** | vLLM, SGLang, TensorRT-LLM, ONNX Runtime |
| **Model Formats** | Safetensors, GGUF, PyTorch, ONNX |
| **Model Sources** | HuggingFace, Custom S3/MinIO, Direct Upload |

### Performance Characteristics

| Metric | Specification |
|--------|---------------|
| **Gateway Latency** | <1ms P99 (routing overhead) |
| **Optimization Time** | 5-30 seconds per simulation |
| **Cluster Provisioning** | 8-15 minutes (cloud), 2-5 minutes (onboard existing) |
| **Supported Model Scale** | Up to 405B parameters (Llama 3.1 405B validated) |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Bud AI Foundry                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Dashboard  │  │  Core API   │  │  Gateway    │                 │
│  │  (budadmin) │  │  (budapp)   │  │ (budgateway)│                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│         │               │                │                          │
│  ┌──────┴───────────────┴────────────────┴──────┐                  │
│  │              Service Mesh (Dapr)              │                  │
│  └───────────────────────┬──────────────────────┘                  │
│         ┌────────────────┼────────────────┐                         │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐                │
│  │ budcluster  │  │   budsim    │  │  budmodel   │  ...           │
│  │ Cluster Mgmt│  │ Optimizer   │  │  Registry   │                │
│  └─────────────┘  └─────────────┘  └─────────────┘                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
   │   AWS EKS   │      │  Azure AKS  │      │  On-Prem    │
   │   Cluster   │      │   Cluster   │      │  Cluster    │
   └─────────────┘      └─────────────┘      └─────────────┘
```

---

## Security & Compliance

| Feature | Description |
|---------|-------------|
| **Authentication** | Keycloak with SAML 2.0 / OIDC federation |
| **Authorization** | Role-based access control (RBAC) |
| **Encryption** | AES-256 at rest, TLS 1.3 in transit, mTLS service mesh |
| **Secrets** | RSA-4096 key wrapping, K8s Secret Store, Vault integration |
| **Audit Trail** | Tamper-proof hash chain, configurable retention |
| **Compliance Ready** | ISO 27001, SOC 2, GDPR mappings available |

---

## Deployment Options

| Option | Use Case | Infrastructure |
|--------|----------|----------------|
| **SaaS** | Fastest time-to-value | Hosted control plane, customer workload clusters |
| **Dedicated** | Data sovereignty requirements | Single-tenant, customer-managed infrastructure |
| **On-Premises** | Air-gapped environments | Full deployment in customer data center |
| **Hybrid** | Multi-cloud strategies | Control plane + distributed workload clusters |

### Minimum Requirements (Control Plane)

| Resource | Specification |
|----------|---------------|
| **Kubernetes** | 1.26+ with 3+ worker nodes |
| **Compute** | 16 vCPU, 64GB RAM minimum |
| **Storage** | 500GB SSD (databases, artifacts) |
| **Network** | 1Gbps, outbound HTTPS for registries |

---

## Integration Capabilities

| Category | Integrations |
|----------|--------------|
| **Identity** | LDAP, Active Directory, Okta, Azure AD, Keycloak |
| **Storage** | S3, MinIO, Azure Blob, GCS |
| **Monitoring** | Datadog, Splunk, ELK, PagerDuty |
| **CI/CD** | Jenkins, GitLab, GitHub Actions, ArgoCD |
| **AI Providers** | OpenAI, Anthropic, Azure OpenAI, Together, Anyscale |

---

## API & Developer Experience

- **OpenAI-Compatible API** - Drop-in replacement for existing applications
- **RESTful Management API** - Full platform automation via API
- **Python SDK** - Native client library for MLOps workflows
- **CLI Tool** - Command-line interface for scripting
- **Webhook Support** - Event-driven integrations

---

## Support & Services

| Tier | Response Time | Coverage |
|------|---------------|----------|
| **Standard** | 8 business hours | Email, documentation |
| **Professional** | 4 business hours | Email, chat, phone |
| **Enterprise** | 1 hour (critical) | 24/7, dedicated TAM |

---

## Learn More

- **Documentation**: docs.budai.io
- **API Reference**: api.budai.io/docs
- **Contact Sales**: sales@budai.io
