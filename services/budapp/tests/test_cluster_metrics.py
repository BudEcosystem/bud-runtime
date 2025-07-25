import asyncio
import json
from uuid import UUID
from budapp.cluster_ops.utils import ClusterMetricsFetcher

TEST_CLUSTER_ID = UUID("1185ae68-6c60-42d0-b3f0-0d67d7a0f279")

async def test_get_cluster_metrics():
    fetcher = ClusterMetricsFetcher("https://metric.bud.studio")
    metrics = await fetcher.get_cluster_metrics(TEST_CLUSTER_ID, "today","network_bandwidth")
    # write metrics to file
    with open("metrics.json", "w") as f:
        json.dump(metrics, f)


if __name__ == "__main__":
    asyncio.run(test_get_cluster_metrics())
