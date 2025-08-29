# Device Extraction for llm-memory-calculator Integration

## Overview

This document describes how device information is extracted from NFD labels and prepared for integration with the llm-memory-calculator service.

## Device Extraction Process

The `DeviceExtractor` class processes NFD labels to extract structured device information:

```python
from budcluster.cluster_ops.device_extractor import DeviceExtractor

extractor = DeviceExtractor()
devices = extractor.extract_from_node_info(node_info)

# Returns:
{
    "gpus": [...],  # List of GPU devices
    "cpus": [...],  # List of CPU devices
    "hpus": [...]   # List of HPU devices
}
```

## Available vs Unavailable Fields

### GPU Devices

#### ✅ Available Fields
- **raw_name**: Full product name (e.g., "NVIDIA A100-SXM4-40GB")
  - Source: `nvidia.com/gpu.product` label from NFD
- **vendor**: GPU vendor (NVIDIA, AMD, Intel)
  - Source: Parsed from product name or vendor presence labels
- **model**: GPU model (A100, H100, MI250X, etc.)
  - Source: Parsed from product name
- **variant**: GPU variant (SXM4, PCIE, etc.)
  - Source: Parsed from product name
- **memory_gb**: GPU memory in GB
  - Source: `nvidia.com/gpu.memory` label (NVIDIA only)
- **count**: Number of GPUs
  - Source: `nvidia.com/gpu.count` label (NVIDIA only)
- **cuda_version**: CUDA runtime version
  - Source: `nvidia.com/cuda.runtime.major/minor` labels (NVIDIA only)

#### ❌ Unavailable Fields
- **pci_vendor_id**: While we know vendor presence, specific vendor ID not in labels
- **pci_device_id**: Device-specific PCI ID not available from NFD
  - NFD provides vendor presence (`pci-10de.present=true`) but not device IDs
  - Would require custom local source with lspci to extract

### CPU Devices

#### ✅ Available Fields
- **raw_name**: Full CPU model name
  - Source: `feature.node.kubernetes.io/local-cpu.model` or constructed from vendor/family
- **vendor**: CPU vendor (Intel, AMD)
  - Source: `feature.node.kubernetes.io/cpu-cpuid.vendor_id`
- **family**: CPU family (Xeon, EPYC, Core)
  - Source: Parsed from model name
- **model**: Specific model (Gold 6248R, 7742, etc.)
  - Source: Parsed from model name
- **generation**: CPU generation (3rd Gen Ice Lake, etc.)
  - Source: Inferred from model number patterns
- **architecture**: CPU architecture (x86_64, aarch64)
  - Source: `kubernetes.io/arch` label
- **cores**: Physical core count
  - Source: Node capacity information
- **threads**: Thread count with hyperthreading
  - Source: Calculated from cores and HT detection
- **frequency_ghz**: Base frequency
  - Source: Parsed from CPU model name if present
- **instruction_sets**: Supported instructions (AVX512, VNNI, etc.)
  - Source: `feature.node.kubernetes.io/cpu-cpuid.*` labels

#### ❌ Unavailable Fields
- **cache_mb**: L3 cache size not provided by NFD
- **cpuid_family/model**: Raw CPUID values not exposed

### HPU Devices (Intel Gaudi)

#### ✅ Available Fields
- **raw_name**: Product name (Intel Gaudi/Gaudi2/Gaudi3)
- **vendor**: Always "Intel" for Gaudi
- **model**: Gaudi model name
- **generation**: 1, 2, or 3
- **count**: Number of HPUs

#### ⚠️ Potentially Available Fields
- **pci_vendor_id**: May be detectable (8086 for Intel)
- **pci_device_id**: May be detectable if specific Gaudi PCI labels present
  - Gaudi: 1020, Gaudi2: 1021, Gaudi3: 1022

#### ❌ Unavailable Fields
- **memory_gb**: HBM memory size not provided by NFD

## Integration Strategy

### Matching Strategy

Since PCI device IDs are typically unavailable, the llm-memory-calculator should use:

1. **Primary matching**: Product name string matching
   - Example: "NVIDIA A100-SXM4-40GB" → A100 configuration

2. **Hierarchical matching**: Vendor → Model → Variant → Memory
   - Vendor: NVIDIA
   - Model: A100
   - Variant: SXM4
   - Memory: 40GB

3. **Fallback matching**: Vendor + partial name match
   - If exact match fails, use fuzzy matching on model names

### Example Device Extraction Output

```python
{
    "gpus": [
        {
            "raw_name": "NVIDIA A100-SXM4-40GB",
            "vendor": "NVIDIA",
            "model": "A100",
            "variant": "SXM4",
            "memory_gb": 40,
            "count": 8,
            "cuda_version": "12.2",
            "pci_vendor_id": "10de",
            "pci_device_id": None  # Not available
        }
    ],
    "cpus": [
        {
            "raw_name": "Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz",
            "vendor": "Intel",
            "family": "Xeon",
            "model": "Gold 6248R",
            "generation": "2nd Gen (Cascade Lake)",
            "architecture": "x86_64",
            "cores": 48,
            "threads": 96,
            "frequency_ghz": 3.0,
            "instruction_sets": ["AVX512", "VNNI"],
            "socket_count": 2
        }
    ],
    "hpus": []
}
```

## API Response Structure

### Enhanced Node Information

```json
{
  "id": "cluster-uuid",
  "name": "cluster-name",
  "nodes": [
    {
      "name": "node-1",
      "id": "node-uuid",
      "status": true,
      "devices": [
        {
          "name": "A100",
          "type": "cuda",
          "available_count": 6,
          "total_count": 8,
          "schedulable": true,
          "mem_per_gpu_in_gb": 40.0,
          "product_name": "NVIDIA-A100-SXM4-40GB",
          "cuda_version": "12.4",
          "compute_capability": "8.0",
          "features": ["AVX512F", "VNNI"],
          "kernel_support": {
            "kernel_version": "5.15.0",
            "os_release": "ubuntu"
          },
          "driver_info": {
            "cuda_driver": "525.147",
            "driver_ready": true
          }
        }
      ],
      "schedulable": true,
      "unschedulable": false,
      "taints": [],
      "conditions": [],
      "pressure": {
        "memory": false,
        "disk": false,
        "pid": false
      },
      "nfd_detected": true,
      "detection_method": "nfd"
    }
  ],
  "enhanced": true,
  "detection_method": "nfd"
}
```

### Backward Compatible Fields

Existing consumers continue to work with these core fields:
- `nodes[].name`
- `nodes[].id`
- `nodes[].status`
- `nodes[].devices[].available_count`
- `nodes[].devices[].type`

## Recommendations

1. **Don't rely on PCI IDs**: Use product names and specifications for matching
2. **Implement fuzzy matching**: Handle variations in product name formats
3. **Use hierarchical matching**: Fall back from specific to general matches
4. **Cache mappings**: Once a device is matched, cache the mapping for future use
5. **Handle unknown devices**: Provide sensible defaults for unmatched devices

## Future Enhancements

If PCI device IDs become critical for matching:

1. Add custom NFD local source that runs `lspci -nn` to extract PCI IDs
2. Parse output to get vendor:device pairs
3. Expose as custom labels `custom-bud.pci-device-id`
4. Requires privileged container access

For now, the available fields provide sufficient information for device matching in most cases.
