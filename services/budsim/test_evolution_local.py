#!/usr/bin/env python3
"""Local test script for debugging evolution hanging issue.

Run from the budsim directory: python test_evolution_local.py
"""

import json
import logging
import sys
from pathlib import Path


# Add budsim to path
sys.path.insert(0, str(Path(__file__).parent))

from budsim.simulator.evolution import Evolution
from budsim.simulator.services import SimulationService


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_evolution():
    """Test evolution with example cluster data."""
    # Load example cluster data
    with open("examples/cluster_info.json", "r") as f:
        cluster_data = json.load(f)

    # Test with the first cluster that has HPU devices across multiple nodes
    test_cluster = cluster_data[0]

    logger.info(f"Testing with cluster: {test_cluster['name']}")
    logger.info(f"Number of nodes: {len(test_cluster['nodes'])}")

    # Create simulation service instance
    sim_service = SimulationService()

    # Group devices by type across cluster
    device_groups = sim_service._group_devices_by_type_across_cluster([test_cluster], {})

    for device_type, group_info in device_groups.items():
        logger.info(f"\nDevice type: {device_type}")
        logger.info(f"Total devices: {group_info.get('total_devices', 0)}")
        logger.info(f"Node distribution: {group_info.get('node_distribution', {})}")
        logger.info(f"Max devices per node: {group_info.get('max_devices_per_node', 0)}")

    # Test evolution for HPU devices
    if "hpu" in device_groups:
        hpu_group = device_groups["hpu"]

        # Create device config for evolution
        device_config = {
            "name": "HL_225",  # HPU name
            "type": "hpu",
            "available_count": hpu_group.get("total_devices", 0),
            "node_distribution": hpu_group.get("node_distribution", {}),
            "max_devices_per_node": hpu_group.get("max_devices_per_node", 0),
            "cluster_topology": {
                "total_nodes": len(hpu_group.get("node_distribution", {})),
                "total_cluster_devices": hpu_group.get("total_devices", 0),
            },
            "mem_per_GPU_in_GB": 96,
            "peak_fp16_TFLOPS": 432,
            "peak_i8_TFLOPS": 864,
            "peak_i4_TFLOPS": 1728,
            "hbm_bandwidth_in_GB_per_sec": 2450,
            "inter_node_bandwidth_in_GB_per_sec": 200,
            "intra_node_bandwidth_in_GB_per_sec": 300,
            "intra_node_min_message_latency": 0.000008,
        }

        logger.info("\nCreating Evolution with device config:")
        logger.info(json.dumps(device_config, indent=2))

        # Create evolution instance
        evolution = Evolution(
            model="microsoft/phi-2",  # Using non-gated model
            device_config=device_config,
            input_tokens=512,
            output_tokens=512,
            target_ttft=0.5,
            target_e2e_latency=5.0,
            target_throughput_per_user=20,
            max_concurrency=32,
            error_threshold=0.1,
            generation=5,  # Small number for testing
            population_size=10,  # Small population for testing
            elite_ratio=0.2,
            top_k=5,
            dtype=None,
            engine_name="vllm",
            benchmark_predictor_models_dir=None,
            use_heuristic=True,  # Use heuristic for faster testing
        )

        logger.info("\nStarting evolution...")
        try:
            results = evolution.evolve()
            logger.info(f"\nEvolution completed! Found {len(results)} configurations")

            for i, result in enumerate(results[:3]):  # Show top 3
                logger.info(f"\nConfiguration {i + 1}:")
                logger.info(f"  Config: {result.config}")
                logger.info(f"  Fitness: {result.fitness}")
                logger.info(f"  TTFT: {result.ttft}")
                logger.info(f"  E2E Latency: {result.e2e_latency}")
                logger.info(f"  Throughput: {result.throughput_per_user}")

        except Exception as e:
            logger.error(f"Evolution failed: {e}", exc_info=True)
    else:
        logger.error("No HPU devices found in cluster")


if __name__ == "__main__":
    test_evolution()
    sys.exit(0)
