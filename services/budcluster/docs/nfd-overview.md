# Node Feature Discovery (NFD) Integration

## Overview

BudCluster uses **Node Feature Discovery (NFD)** as the primary method for hardware detection and node information gathering. NFD is a Kubernetes add-on that detects hardware features and system configuration of nodes and advertises them as Kubernetes labels.

## Why NFD?

1. **Industry Standard**: NFD is the Kubernetes standard for hardware discovery
2. **Real-time Updates**: NFD updates labels every 60 seconds automatically
3. **Comprehensive Detection**: Provides 95% of required hardware information
4. **Less Maintenance**: No custom container images to maintain
5. **Better Performance**: No ConfigMap overhead or static data
6. **Cleaner Architecture**: Single source of truth for hardware information

## What NFD Detects

### GPU Information
- ✅ GPU vendor and presence detection
- ✅ GPU product name (e.g., "NVIDIA A100-SXM4-40GB")
- ✅ GPU count per node
- ✅ GPU memory size
- ✅ CUDA version (for NVIDIA)
- ✅ Compute capability
- ✅ GPU family (Ampere, Ada, etc.)
- ❌ PCI device IDs (vendor presence only)

### CPU Information
- ✅ CPU vendor (Intel, AMD)
- ✅ CPU family and model IDs
- ✅ CPU model name (with local source configuration)
- ✅ Instruction sets (AVX512, VNNI, AMX, etc.)
- ✅ Hardware multithreading detection
- ✅ Core count (from node capacity)
- ✅ Architecture (x86_64, aarch64)

### Memory Information
- ✅ Total memory capacity
- ✅ NUMA node detection
- ✅ Persistent memory detection

### System Information
- ✅ Kernel version
- ✅ Operating system and version
- ✅ Storage type (NVMe, SSD)
- ✅ Network capabilities (SR-IOV)

## Architecture Components

### NFDSchedulableResourceDetector (`nfd_handler.py`)
- Core NFD integration handler
- Kubernetes API integration for real-time resource queries
- Device detection (CPU, GPU, HPU) with enhanced metadata

### Enhanced Services (`services.py`)
- `fetch_cluster_info_enhanced()` - NFD-based cluster info fetching
- `update_node_status_enhanced()` - Enhanced node status updates
- `transform_db_nodes_enhanced()` - Enhanced data transformation

### Database Models (`models.py`)
- Extended `ClusterNodeInfo` with NFD fields
- Schedulability metadata storage
- Kernel/driver support information

### Fallback Handler (`fallback_handler.py`)
- Graceful degradation between NFD and ConfigMap methods
- Error handling and recovery mechanisms
- Configuration-driven method selection

## Key Features

### Enhanced Schedulability Detection
- **Real-time availability**: Queries actual Kubernetes allocatable resources
- **Taint awareness**: Detects NoSchedule/NoExecute taints on nodes
- **Pressure conditions**: Monitors MemoryPressure, DiskPressure, PIDPressure
- **Cordon status**: Identifies manually cordoned (unschedulable) nodes
- **Resource allocation**: Calculates available vs. allocated devices per node

### Device Information Enhancement
- **Kernel modules**: NVIDIA driver, CUDA runtime versions
- **CPU features**: AVX-512, VNNI, SSE instruction set support
- **Driver compatibility**: Automatic validation of driver support
- **Memory topology**: NUMA-aware resource information
- **Product identification**: Enhanced device naming and specifications

### Backward Compatibility
- **Same API structure**: Existing consumers (budapp, budadmin) work unchanged
- **Enhanced fields optional**: New fields ignored by existing code
- **Gradual migration**: ConfigMap fallback during NFD deployment
- **Database compatibility**: Minimal schema changes, optional fields

## References

- [NFD Documentation](https://kubernetes-sigs.github.io/node-feature-discovery/)
- [NFD Label Reference](https://kubernetes-sigs.github.io/node-feature-discovery/stable/usage/features.html)
- [GPU Operator Documentation](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/)
