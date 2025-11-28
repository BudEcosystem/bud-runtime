"""Device Information Extractor for llm-memory-calculator integration.

This module extracts clean, structured device information from cluster data
(NFD labels, node info) that can be used by llm-memory-calculator for matching
against its configuration database.

NOTE: PCI device IDs are not available from NFD or node-info-collector.
Device matching relies on product names, vendor, and specifications.
"""

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


@dataclass
class GPUDevice:
    """Structured GPU device information for llm-memory-calculator.

    Field names aligned with llm-memory-calculator expectations.
    Note: pci_vendor_id and pci_device_id typically not available from cluster.
    """

    raw_name: str  # Full product name from cluster
    vendor: Optional[str] = None  # NVIDIA, AMD, Intel
    model: Optional[str] = None  # A100, H100, MI250X, etc.
    variant: Optional[str] = None  # SXM4, PCIE, etc.
    memory_gb: Optional[int] = None  # Memory in GB
    count: int = 1  # Number of devices
    cuda_version: Optional[str] = None  # CUDA runtime version if NVIDIA
    # PCI IDs - typically not available from NFD/node-info-collector
    pci_vendor_id: Optional[str] = None  # Usually remains None
    pci_device_id: Optional[str] = None  # Usually remains None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CPUDevice:
    """Structured CPU device information for llm-memory-calculator.

    Field names aligned with llm-memory-calculator expectations.
    """

    raw_name: str  # Full CPU model name
    type: str = "cpu"  # Device type: "cpu" or "cpu_high" (with AMX)
    vendor: Optional[str] = None  # Intel, AMD
    family: Optional[str] = None  # Xeon, EPYC, Core
    model: Optional[str] = None  # Gold 6248R, 7742, etc.
    generation: Optional[str] = None  # 3rd Gen (Ice Lake), etc.
    architecture: Optional[str] = None  # x86_64, aarch64
    cores: Optional[int] = None  # Physical core count
    threads: Optional[int] = None  # Thread count (with HT)
    frequency_ghz: Optional[float] = None  # Base frequency
    cache_mb: Optional[int] = None  # L3 cache size
    socket_count: int = 1  # Number of CPU sockets
    memory_gb: Optional[int] = None  # System memory in GB
    instruction_sets: Optional[List[str]] = None  # AVX512, VNNI, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class HPUDevice:
    """Structured HPU (Habana/Intel Gaudi) device information.

    Field names aligned with llm-memory-calculator expectations.
    """

    raw_name: str  # Full product name
    vendor: str = "Intel"  # Always Intel for Gaudi
    model: Optional[str] = None  # Gaudi, Gaudi2, Gaudi3
    generation: Optional[int] = None  # 1, 2, or 3
    memory_gb: Optional[int] = None  # HBM memory in GB
    count: int = 1  # Number of devices
    # PCI IDs - may be available for HPUs from NFD
    pci_vendor_id: Optional[str] = None
    pci_device_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class DeviceExtractor:
    """Extract device information from various cluster data sources."""

    # PCI vendor IDs
    PCI_VENDOR_NVIDIA = "10de"
    PCI_VENDOR_AMD = "1002"
    PCI_VENDOR_INTEL = "8086"

    # Known device PCI IDs
    PCI_DEVICES = {
        # NVIDIA GPUs
        "20b0": "A100-SXM4",
        "20b2": "A100-SXM4-80GB",
        "20f1": "A100-PCIE",
        "20f3": "A100-PCIE-80GB",
        "2330": "H100-SXM5",
        "2331": "H100-PCIE",
        "2322": "H800",
        "1db6": "V100-PCIE-32GB",
        "1db4": "V100-PCIE-16GB",
        "1db1": "V100-SXM2-16GB",
        "1db5": "V100-SXM2-32GB",
        "2230": "RTX A6000",
        "2204": "RTX 3090",
        "2208": "RTX 3080Ti",
        # AMD GPUs
        "740c": "MI250X",
        "740f": "MI250",
        "7408": "MI210",
        "738c": "MI100",
        # Intel Gaudi HPUs
        "1020": "Gaudi",
        "1021": "Gaudi2",
        "1022": "Gaudi3",
    }

    @staticmethod
    def parse_memory_size(memory_str: str, source_label: Optional[str] = None) -> Optional[int]:
        """Parse memory size from various formats to GB.

        Args:
            memory_str: Memory value string to parse (e.g., "40960 MiB", "40 GB", "46068")
            source_label: Optional label name indicating the data source (e.g., "nvidia.com/gpu.memory")
                         Used to determine the correct unit when no unit is specified.

        Examples:
            "40960 MiB" -> 40
            "40 GB" -> 40
            "81920 MB" -> 80
            "43008 MiB" -> 42
            "46068" -> 45 (plain number from NVIDIA GFD label, always MB)
            "128" -> 125 (plain number from NVIDIA GFD label, always MB)
            "96" -> 96 (plain number from other source, heuristic: assume GB if <= 100)
        """
        if not memory_str:
            return None

        memory_str = memory_str.strip()

        # Try to extract number and unit
        match = re.match(r"(\d+(?:\.\d+)?)\s*([KMGT]i?B)?", memory_str, re.IGNORECASE)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2)  # Keep as None if no unit specified

        # Handle plain numbers (no unit specified)
        if unit is None:
            # NVIDIA GFD labels (nvidia.com/gpu.memory) are ALWAYS in MB without unit
            # This is reliable and documented behavior from NVIDIA GPU Feature Discovery
            if source_label and "nvidia.com/gpu.memory" in source_label:
                result_gb = round(value / 1024)
                logger.debug(
                    f"Parsed plain number '{memory_str}' from NVIDIA GFD label '{source_label}' as MB: {result_gb} GB"
                )
                return result_gb

            # For other sources, use heuristic:
            # If the number is large (> 100), assume MB
            # If the number is small (≤ 100), assume GB
            if value > 100:
                # Round to nearest GB instead of truncating
                result_gb = round(value / 1024)
                logger.debug(f"Parsed plain number '{memory_str}' as MB (heuristic): {result_gb} GB")
                return result_gb
            else:
                logger.debug(f"Parsed plain number '{memory_str}' as GB (heuristic): {int(value)} GB")
                return int(value)

        unit = unit.upper()

        # Convert to GB
        if unit in ["B"]:
            return int(value / (1024**3))
        elif unit in ["KB", "KIB"]:
            return int(value / (1024**2))
        elif unit in ["MB", "MIB"]:
            return int(value / 1024)
        elif unit in ["GB", "GIB"]:
            return int(value)
        elif unit in ["TB", "TIB"]:
            return int(value * 1024)

        return None

    @staticmethod
    def parse_gpu_name(gpu_name: str) -> Dict[str, Optional[str]]:
        """Parse GPU name into components.

        Examples:
            "NVIDIA A100-SXM4-40GB" -> {vendor: "NVIDIA", model: "A100", variant: "SXM4", memory: "40"}
            "Tesla V100-PCIE-32GB" -> {vendor: "NVIDIA", model: "V100", variant: "PCIE", memory: "32"}
            "AMD MI250X" -> {vendor: "AMD", model: "MI250X"}
        """
        result = {"vendor": None, "model": None, "variant": None, "memory_gb": None}

        # Clean the name
        gpu_name = gpu_name.strip()

        # Detect vendor
        if any(v in gpu_name.upper() for v in ["NVIDIA", "TESLA", "GEFORCE", "RTX", "GTX", "QUADRO"]):
            result["vendor"] = "NVIDIA"
        elif "AMD" in gpu_name.upper() or gpu_name.upper().startswith("MI"):
            result["vendor"] = "AMD"
        elif any(v in gpu_name.upper() for v in ["INTEL", "GAUDI", "HPU"]):
            result["vendor"] = "Intel"

        # Parse NVIDIA format
        if result["vendor"] == "NVIDIA":
            # Remove vendor prefixes
            clean_name = re.sub(r"^(NVIDIA|Tesla|GeForce|Quadro)\s+", "", gpu_name, flags=re.IGNORECASE)

            # Extract model (A100, V100, H100, etc.)
            model_match = re.search(r"([AHVT]\d{3,4}|RTX\s*[A]?\d{4}|GTX\s*\d{4})", clean_name, re.IGNORECASE)
            if model_match:
                result["model"] = model_match.group(1).upper().replace(" ", "")

            # Extract variant (SXM4, PCIE, etc.)
            variant_match = re.search(r"(SXM[0-9]?|PCIE|PCIe|NVLink)", clean_name, re.IGNORECASE)
            if variant_match:
                result["variant"] = variant_match.group(1).upper()

            # Extract memory
            memory_match = re.search(r"(\d+)\s*GB", clean_name, re.IGNORECASE)
            if memory_match:
                result["memory_gb"] = int(memory_match.group(1))

        # Parse AMD format
        elif result["vendor"] == "AMD":
            # Extract model (MI250X, MI250, MI100, etc.)
            model_match = re.search(r"MI\d{3}X?", gpu_name, re.IGNORECASE)
            if model_match:
                result["model"] = model_match.group(0).upper()

        # Parse Intel/Gaudi format
        elif result["vendor"] == "Intel":
            if "GAUDI3" in gpu_name.upper():
                result["model"] = "Gaudi3"
            elif "GAUDI2" in gpu_name.upper():
                result["model"] = "Gaudi2"
            elif "GAUDI" in gpu_name.upper():
                result["model"] = "Gaudi"

        return result

    @staticmethod
    def parse_cpu_name(cpu_name: str) -> Dict[str, Optional[str]]:
        """Parse CPU name into components.

        Examples:
            "Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz" -> {vendor: "Intel", family: "Xeon", model: "Gold 6248R"}
            "AMD EPYC 7742 64-Core Processor" -> {vendor: "AMD", family: "EPYC", model: "7742"}
        """
        result = {"vendor": None, "family": None, "model": None, "architecture": None}

        # Clean the name
        cpu_name = re.sub(r"\(R\)|\(TM\)", "", cpu_name).strip()
        cpu_name = re.sub(r"CPU\s*@\s*[\d.]+\s*GHz", "", cpu_name).strip()
        cpu_name = re.sub(r"\d+-Core Processor", "", cpu_name).strip()

        # Detect vendor
        if "Intel" in cpu_name:
            result["vendor"] = "Intel"
        elif "AMD" in cpu_name:
            result["vendor"] = "AMD"

        # Parse Intel CPUs
        if result["vendor"] == "Intel":
            if "Xeon" in cpu_name:
                result["family"] = "Xeon"
                # Extract model (Gold 6248R, Silver 4214, etc.)
                model_match = re.search(r"(Platinum|Gold|Silver|Bronze)?\s*\d{4}[A-Z]?", cpu_name)
                if model_match:
                    result["model"] = model_match.group(0).strip()
            elif "Core" in cpu_name:
                result["family"] = "Core"
                # Extract model (i7-12700K, i9-13900K, etc.)
                model_match = re.search(r"i[3579]-\d{4,5}[A-Z]*", cpu_name)
                if model_match:
                    result["model"] = model_match.group(0)

        # Parse AMD CPUs
        elif result["vendor"] == "AMD":
            if "EPYC" in cpu_name:
                result["family"] = "EPYC"
                # Extract model (7742, 7763, etc.)
                model_match = re.search(r"\d{4}[A-Z]?", cpu_name)
                if model_match:
                    result["model"] = model_match.group(0)
            elif "Ryzen" in cpu_name:
                result["family"] = "Ryzen"
                # Extract model
                model_match = re.search(r"\d{4}[A-Z]*", cpu_name)
                if model_match:
                    result["model"] = model_match.group(0)

        return result

    def extract_gpu_from_nfd_labels(self, labels: Dict[str, str]) -> List[GPUDevice]:
        """Extract GPU information from NFD labels."""
        gpus = []

        # Check for NVIDIA GPUs
        if labels.get("nvidia.com/gpu.present") == "true":
            gpu = GPUDevice(
                raw_name=labels.get("nvidia.com/gpu.product", "Unknown NVIDIA GPU"),
                vendor="NVIDIA",
                count=int(labels.get("nvidia.com/gpu.count", "1")),
            )

            # Extract memory
            memory_label_value = labels.get("nvidia.com/gpu.memory", "")
            if memory_label_value:
                gpu.memory_gb = self.parse_memory_size(memory_label_value, source_label="nvidia.com/gpu.memory")
                logger.debug(
                    f"GPU {gpu.raw_name}: Parsed memory from NFD label '{memory_label_value}' -> {gpu.memory_gb} GB"
                )
            else:
                logger.warning(f"GPU {gpu.raw_name}: NFD label 'nvidia.com/gpu.memory' is missing or empty")

            # Extract CUDA version
            cuda_major = labels.get("nvidia.com/cuda.runtime.major", "")
            cuda_minor = labels.get("nvidia.com/cuda.runtime.minor", "")
            if cuda_major and cuda_minor:
                gpu.cuda_version = f"{cuda_major}.{cuda_minor}"

            # Parse the product name for more details
            parsed = self.parse_gpu_name(gpu.raw_name)
            gpu.model = parsed.get("model")
            gpu.variant = parsed.get("variant")
            if not gpu.memory_gb and parsed.get("memory_gb"):
                gpu.memory_gb = parsed["memory_gb"]
                logger.debug(f"GPU {gpu.raw_name}: Extracted memory from product name -> {gpu.memory_gb} GB")

            # Validate final memory value
            if not gpu.memory_gb or gpu.memory_gb == 0:
                logger.warning(
                    f"GPU {gpu.raw_name}: Memory detection resulted in {gpu.memory_gb} GB. "
                    f"NFD label value was '{memory_label_value}'. "
                    f"This will cause simulation failures. Please verify GPU Feature Discovery is running correctly."
                )

            # PCI device IDs not available from NFD for NVIDIA GPUs
            # NFD only provides vendor presence, not specific device IDs
            # Matching will rely on product name instead
            gpu.pci_vendor_id = self.PCI_VENDOR_NVIDIA  # We know vendor from presence
            gpu.pci_device_id = None  # Not available from NFD
            gpus.append(gpu)

        # Check for AMD GPUs (using amd.com labels from AMD GPU operator)
        if (
            labels.get(f"feature.node.kubernetes.io/pci-{self.PCI_VENDOR_AMD}.present") == "true"
            or labels.get("amd.com/gpu.device-id")
            or labels.get("beta.amd.com/gpu.device-id")
        ):
            # Get device info from AMD GPU operator labels
            device_id = labels.get("amd.com/gpu.device-id") or labels.get("beta.amd.com/gpu.device-id", "")
            gpu_family = labels.get("amd.com/gpu.family") or labels.get("beta.amd.com/gpu.family", "")
            vram = labels.get("amd.com/gpu.vram") or labels.get("beta.amd.com/gpu.vram", "")
            # cu_count = labels.get("amd.com/gpu.cu-count") or labels.get("beta.amd.com/gpu.cu-count", "")

            # Map device IDs to model names
            amd_device_map = {
                "74b5": "MI300X",  # AMD Instinct MI300X
                "740c": "MI250X",
                "740f": "MI250",
                "7408": "MI210",
                "738c": "MI100",
            }

            model_name = amd_device_map.get(device_id, f"AMD GPU {device_id}")

            # Parse VRAM (e.g., "191G" -> 191)
            memory_gb = 0
            if vram:
                vram_match = re.match(r"(\d+)G", vram)
                if vram_match:
                    memory_gb = int(vram_match.group(1))

            # Get count from label suffixes (e.g., beta.amd.com/gpu.device-id.74b5=8)
            gpu_count = 1
            for label_key, label_value in labels.items():
                if f"gpu.device-id.{device_id}" in label_key and label_value.isdigit():
                    gpu_count = int(label_value)
                    break

            gpu = GPUDevice(
                raw_name=f"AMD {model_name}" if model_name else f"AMD GPU {gpu_family}",
                vendor="AMD",
                model=model_name if model_name else gpu_family,
                memory_gb=memory_gb,
                count=gpu_count,
                pci_vendor_id=self.PCI_VENDOR_AMD,
                pci_device_id=device_id if device_id else None,
            )

            gpus.append(gpu)

        return gpus

    def extract_hpu_from_nfd_labels(self, labels: Dict[str, str]) -> List[HPUDevice]:
        """Extract HPU (Intel Gaudi) information from NFD labels."""
        hpus = []

        # Check for Intel Gaudi devices
        gaudi_pci_ids = ["1020", "1021", "1022"]
        for pci_id in gaudi_pci_ids:
            if labels.get(f"feature.node.kubernetes.io/pci-{self.PCI_VENDOR_INTEL}.device-{pci_id}") == "true":
                model_name = self.PCI_DEVICES.get(pci_id, "Gaudi")
                hpu = HPUDevice(
                    raw_name=f"Intel {model_name}",
                    vendor="Intel",
                    model=model_name,
                    pci_vendor_id=self.PCI_VENDOR_INTEL,
                    pci_device_id=pci_id,
                    count=1,  # TODO: Extract actual count
                )

                # Set generation based on model
                if "Gaudi3" in model_name:
                    hpu.generation = 3
                elif "Gaudi2" in model_name:
                    hpu.generation = 2
                else:
                    hpu.generation = 1

                hpus.append(hpu)
                break

        return hpus

    def extract_cpu_from_nfd_labels(self, labels: Dict[str, str]) -> List[CPUDevice]:
        """Extract comprehensive CPU information from NFD labels with enhanced fallbacks."""
        cpus = []

        # Try multiple sources for CPU model detection
        cpu_model = ""

        # Primary: Get CPU model from local source (if we configured it)
        cpu_model = labels.get("feature.node.kubernetes.io/local-cpu.model", "")
        if cpu_model:
            logger.debug(f"Found CPU model from local source: {cpu_model}")

        # Fallback 1: System info
        if not cpu_model:
            cpu_model = labels.get("feature.node.kubernetes.io/cpu-model.name", "")
            if cpu_model:
                logger.debug(f"Found CPU model from system info: {cpu_model}")

        # Fallback 2: CPU hardware info
        if not cpu_model:
            cpu_model = labels.get("feature.node.kubernetes.io/cpu-hardware.cpu_model", "")
            if cpu_model:
                logger.debug(f"Found CPU model from hardware info: {cpu_model}")

        # Fallback 3: Try to construct from vendor ID and family - FIXED label names
        if not cpu_model:
            # Use the correct NFD label names that are actually present
            vendor_id = labels.get("feature.node.kubernetes.io/cpu-model.vendor_id", "")
            family = labels.get("feature.node.kubernetes.io/cpu-model.family", "")
            model_id = labels.get("feature.node.kubernetes.io/cpu-model.id", "")

            if vendor_id:
                # Map vendor ID to readable name
                vendor_map = {
                    "GenuineIntel": "Intel",
                    "Intel": "Intel",  # NFD might return just "Intel"
                    "AuthenticAMD": "AMD",
                    "AMD": "AMD",  # NFD might return just "AMD"
                    "CentaurHauls": "Centaur",
                    "HygonGenuine": "Hygon",
                }
                vendor_name = vendor_map.get(vendor_id, vendor_id)

                # Construct CPU model string from available NFD data
                parts = [vendor_name]
                if family:
                    parts.append(f"Family {family}")
                if model_id:
                    parts.append(f"Model {model_id}")
                if parts:
                    cpu_model = " ".join(parts) + " Processor"
                    logger.debug(f"Constructed CPU model from NFD labels: {cpu_model}")

        # Fallback 4: Generic CPU based on architecture
        if not cpu_model:
            arch = labels.get("kubernetes.io/arch", "")
            if arch:
                cpu_model = f"Generic {arch} CPU"
                logger.warning(f"Using generic CPU model based on architecture: {cpu_model}")

        # If we still don't have a CPU model, create a generic one
        if not cpu_model:
            cpu_model = "Unknown CPU"
            logger.warning("Could not determine CPU model from NFD labels, using 'Unknown CPU'")

        # Always create at least one CPU device entry
        if True:  # Always create CPU entry
            cpu = CPUDevice(raw_name=cpu_model)

            # Try to parse the CPU name first (in case it's a full model name from local hook)
            parsed = self.parse_cpu_name(cpu_model)
            cpu.vendor = parsed.get("vendor")
            cpu.family = parsed.get("family")
            cpu.model = parsed.get("model")

            # Override with direct NFD label data if available (more accurate)
            vendor_id = labels.get("feature.node.kubernetes.io/cpu-model.vendor_id", "")
            if vendor_id:
                vendor_map = {
                    "GenuineIntel": "Intel",
                    "Intel": "Intel",
                    "AuthenticAMD": "AMD",
                    "AMD": "AMD",
                    "CentaurHauls": "Centaur",
                    "HygonGenuine": "Hygon",
                }
                cpu.vendor = vendor_map.get(vendor_id, vendor_id)

            # Set family and model from NFD labels
            family_id = labels.get("feature.node.kubernetes.io/cpu-model.family", "")
            model_id = labels.get("feature.node.kubernetes.io/cpu-model.id", "")

            if family_id:
                cpu.family = f"Family {family_id}"
            if model_id:
                cpu.model = f"Model {model_id}"

            # Get architecture
            cpu.architecture = labels.get("kubernetes.io/arch", "")

            # Extract core/thread information
            # Note: NFD doesn't directly provide core count, but we can get it from capacity
            # This would need to be passed from the node capacity info
            if labels.get("feature.node.kubernetes.io/cpu-hardware_multithreading") == "true":
                # If hyperthreading is enabled, we know threads = 2 * cores
                cpu.threads = None  # Would need node capacity info

            # Extract frequency if available (from CPU name)
            freq_match = re.search(r"(\d+\.?\d*)\s*[GM]Hz", cpu_model, re.IGNORECASE)
            if freq_match:
                freq_value = float(freq_match.group(1))
                unit = freq_match.group(0)[-3:].upper()
                if "MHZ" in unit:
                    cpu.frequency_ghz = freq_value / 1000
                else:  # GHz
                    cpu.frequency_ghz = freq_value

            # Determine generation based on vendor and model ID from NFD
            if cpu.vendor == "Intel" and family_id and model_id:
                try:
                    model_int = int(model_id)
                    family_int = int(family_id)
                    if family_int == 6:  # Intel x86-64
                        if model_int == 143:
                            cpu.generation = "Sapphire Rapids"
                        elif model_int in [106, 108]:
                            cpu.generation = "Ice Lake"
                        elif model_int == 85:
                            cpu.generation = "Cascade Lake/Skylake"
                        elif model_int == 79:
                            cpu.generation = "Broadwell"
                        elif model_int == 63:
                            cpu.generation = "Haswell"
                except ValueError:
                    pass
            elif cpu.vendor == "AMD" and family_id and model_id:
                try:
                    family_int = int(family_id)
                    model_int = int(model_id)
                    if family_int == 25:  # Zen 3/4
                        cpu.generation = "Zen 3/4"
                    elif family_int == 23:  # Zen/Zen 2
                        if model_int == 49:
                            cpu.generation = "Zen 2 (Rome)"
                        else:
                            cpu.generation = "Zen/Zen 2"
                except ValueError:
                    pass

            # Extract instruction sets from NFD labels
            instruction_sets = []

            # Check for AVX instructions - using actual NFD label format
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.AVX") == "true":
                instruction_sets.append("AVX")
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.AVX2") == "true":
                instruction_sets.append("AVX2")
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.AVX512F") == "true":
                instruction_sets.append("AVX512")
            # Also check for variations in label format
            if labels.get("feature.node.kubernetes.io/cpu-hardware.avx") == "true":
                instruction_sets.append("AVX")
            if labels.get("feature.node.kubernetes.io/cpu-hardware.avx2") == "true":
                instruction_sets.append("AVX2")
            if labels.get("feature.node.kubernetes.io/cpu-hardware.avx512") == "true":
                instruction_sets.append("AVX512")

            # Check for AI acceleration instructions
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.VNNI") == "true":
                instruction_sets.append("VNNI")
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.AMX") == "true":
                instruction_sets.append("AMX")

            # Check for other important instructions
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.FMA3") == "true":
                instruction_sets.append("FMA3")
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.SSE4.2") == "true":
                instruction_sets.append("SSE4.2")

            if instruction_sets:
                cpu.instruction_sets = instruction_sets

            # Set device type to cpu_high if AMX or AVX2 is supported (Intel CPUs only)
            # This matches the logic in nfd_handler.py for consistency
            # Note: cpu.vendor is already normalized to "Intel" by vendor_map earlier
            if cpu.vendor == "Intel" and ("AMX" in instruction_sets or "AVX2" in instruction_sets):
                cpu.type = "cpu_high"

            cpus.append(cpu)

        return cpus

    def extract_from_node_info(self, node_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract device information from node info using NFD labels.

        Returns a dictionary with 'gpus', 'cpus', and 'hpus' lists.
        Each device dict contains fields compatible with llm-memory-calculator.

        Note: PCI device IDs are typically not available and will be None.
        Device matching should use product names and specifications.

        Requires Node Feature Discovery (NFD) to be installed on the cluster.
        """
        result = {"gpus": [], "cpus": [], "hpus": []}

        # Extract from NFD labels if available
        if "labels" in node_info:
            labels = node_info["labels"]

            # Extract GPUs
            gpus = self.extract_gpu_from_nfd_labels(labels)
            result["gpus"] = [gpu.to_dict() for gpu in gpus]

            # Extract HPUs
            hpus = self.extract_hpu_from_nfd_labels(labels)
            result["hpus"] = [hpu.to_dict() for hpu in hpus]

            # Extract CPUs
            cpus = self.extract_cpu_from_nfd_labels(labels)

            # Enhance CPU info with node capacity if available
            if "capacity" in node_info and cpus:
                cpu_capacity = node_info["capacity"].get("cpu", 0)
                memory_capacity = node_info["capacity"].get("memory", "")
                
                if cpu_capacity:
                    # Distribute cores across CPUs (usually 1 CPU per node)
                    cores_per_cpu = int(cpu_capacity) // len(cpus) if len(cpus) > 0 else int(cpu_capacity)
                    for cpu in cpus:
                        cpu.cores = cores_per_cpu
                        # If hyperthreading is detected, threads = cores * 2
                        if labels.get("feature.node.kubernetes.io/cpu-hardware_multithreading") == "true":
                            cpu.threads = cores_per_cpu * 2
                        else:
                            cpu.threads = cores_per_cpu
                
                # Parse system memory from Kubernetes capacity
                if memory_capacity:
                    memory_gb = self.parse_memory_size(memory_capacity)
                    if memory_gb:
                        # Assign memory to all CPU devices (usually 1 per node)
                        for cpu in cpus:
                            cpu.memory_gb = memory_gb

            result["cpus"] = [cpu.to_dict() for cpu in cpus]

        else:
            # No NFD labels found
            # Return empty result - NFD is required for hardware detection
            pass

        return result
