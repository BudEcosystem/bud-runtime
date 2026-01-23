# GPU/Accelerator Support Guide

---

## Overview

This guide covers GPU and accelerator support in Bud AI Foundry, including NVIDIA GPUs, HAMI time-slicing, and Node Feature Discovery (NFD).

---

## Supported Hardware

### NVIDIA GPUs

| GPU | Memory | Compute | Status |
|-----|--------|---------|--------|
| H100 SXM5 | 80GB HBM3 | Ada | Full Support |
| H100 PCIe | 80GB HBM3 | Ada | Full Support |
| A100 SXM4 | 80GB HBM2e | Ampere | Full Support |
| A100 PCIe | 40GB/80GB | Ampere | Full Support |
| L40S | 48GB GDDR6 | Ada | Full Support |
| A10G | 24GB GDDR6 | Ampere | Full Support |
| T4 | 16GB GDDR6 | Turing | Limited |
| V100 | 16GB/32GB HBM2 | Volta | Limited |

### Intel Accelerators

| Accelerator | Memory | Status |
|-------------|--------|--------|
| Gaudi 2 (HPU) | 96GB HBM2e | Beta |
| Gaudi 3 (HPU) | 128GB HBM2e | Planned |

### AMD GPUs

| GPU | Memory | Status |
|-----|--------|--------|
| MI300X | 192GB HBM3 | Experimental |

---

## Hardware Detection (NFD)

### Node Feature Discovery

NFD automatically detects hardware capabilities:

```yaml
# Detected node labels
feature.node.kubernetes.io/pci-10de.present=true    # NVIDIA device
feature.node.kubernetes.io/cpu-cpuid.AVX512=true   # AVX512 support
nvidia.com/gpu.product=NVIDIA-A100-SXM4-80GB       # GPU model
nvidia.com/gpu.memory=81920                         # GPU memory (MB)
```

### Detection Process

1. NFD DaemonSet runs on all nodes
2. Scans PCI devices, CPU features
3. Updates node labels
4. Labels used for scheduling

### Installation

```bash
# Automatic during cluster onboarding
# Or manual:
kubectl apply -f nfd-master.yaml
kubectl apply -f nfd-worker.yaml
```

---

## GPU Operator

### Components

| Component | Purpose |
|-----------|---------|
| Driver Container | NVIDIA driver installation |
| Device Plugin | GPU device scheduling |
| DCGM Exporter | GPU metrics |
| GPU Feature Discovery | GPU capability labels |
| Container Toolkit | Container GPU access |

### Installation

```bash
# Automatic when GPUs detected during onboarding
# Includes:
# - nvidia-driver-daemonset
# - nvidia-container-toolkit
# - nvidia-device-plugin
# - dcgm-exporter
```

---

## HAMI GPU Time-Slicing

### What is HAMI?

HAMI enables GPU sharing between multiple pods:

```
Without HAMI:           With HAMI:
┌──────────────┐       ┌──────────────┐
│    GPU 0     │       │    GPU 0     │
│              │       │ ┌──────────┐ │
│   Pod A      │       │ │  Pod A   │ │
│   (100%)     │       │ │  (50%)   │ │
│              │       │ ├──────────┤ │
│              │       │ │  Pod B   │ │
│              │       │ │  (50%)   │ │
└──────────────┘       │ └──────────┘ │
                       └──────────────┘
```

### Features

- **Memory Isolation**: Enforce VRAM limits per pod
- **Compute Sharing**: Time-slice GPU compute
- **Scheduling**: Request fractional GPUs

### Configuration

```yaml
# Pod requesting shared GPU
resources:
  limits:
    nvidia.com/gpu: 1
    nvidia.com/gpumem: 8000  # 8GB VRAM limit
    nvidia.com/gpucores: 50  # 50% compute
```

### Installation

```bash
# Automatic when NVIDIA GPUs detected
# After NFD completes hardware detection
```

---

## Multi-GPU Configuration

### Tensor Parallelism (TP)

Split model across GPUs on same node:

```
┌────────────────────────────────────────┐
│              Single Node               │
│  ┌────────┐ ┌────────┐ ┌────────┐    │
│  │ GPU 0  │ │ GPU 1  │ │ GPU 2  │ ...│
│  │Layer 0 │ │Layer 0 │ │Layer 0 │    │
│  │ Part A │ │ Part B │ │ Part C │    │
│  └────────┘ └────────┘ └────────┘    │
└────────────────────────────────────────┘
```

- **Best for**: Large models that don't fit on single GPU
- **Requirement**: NVLink/NVSwitch for efficient communication
- **Typical TP values**: 2, 4, 8

### Pipeline Parallelism (PP)

Split model layers across nodes:

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Node 0  │───►│ Node 1  │───►│ Node 2  │
│Layer 0-9│    │Layer10-19   │Layer20-29│
└─────────┘    └─────────┘    └─────────┘
```

- **Best for**: Very large models (>100B parameters)
- **Requirement**: Fast network between nodes
- **Typical PP values**: 1, 2, 4

### Configuration Example

```yaml
# 70B model on 2x A100-80GB
deployment:
  tensor_parallel_size: 2
  pipeline_parallel_size: 1

# 405B model on 8x H100-80GB
deployment:
  tensor_parallel_size: 8
  pipeline_parallel_size: 1

# 405B model on 16x A100-80GB (2 nodes)
deployment:
  tensor_parallel_size: 8
  pipeline_parallel_size: 2
```

---

## GPU Metrics

### Available Metrics

| Metric | Description |
|--------|-------------|
| `nvidia_gpu_duty_cycle` | GPU utilization % |
| `nvidia_gpu_memory_used_bytes` | VRAM used |
| `nvidia_gpu_memory_total_bytes` | Total VRAM |
| `nvidia_gpu_temperature_celsius` | GPU temp |
| `nvidia_gpu_power_usage_watts` | Power draw |

### Monitoring

- Grafana dashboards for GPU metrics
- Alerts for high utilization, temperature
- Integration with DCGM Exporter

---

## Troubleshooting

### GPU Not Detected

1. Verify driver installation
   ```bash
   nvidia-smi
   ```

2. Check NFD labels
   ```bash
   kubectl get nodes -o yaml | grep nvidia
   ```

3. Verify device plugin
   ```bash
   kubectl get pods -n gpu-operator
   ```

### CUDA Out of Memory

1. Reduce `max_model_len`
2. Reduce `max_num_seqs`
3. Lower `gpu_memory_utilization`
4. Consider quantization

### Scheduling Failures

1. Check node GPU availability
2. Verify resource requests
3. Review node selectors

---

## Related Documents

- [LLM Support Matrix](./llm-support-matrix.md)
- [Resource Optimization Guide](./resource-optimization.md)
- [Cluster Onboarding Runbook](../operations/cluster-onboarding.md)
