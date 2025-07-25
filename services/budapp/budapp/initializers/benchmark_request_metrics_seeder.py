import random

from budapp.benchmark_ops.models import BenchmarkCRUD, BenchmarkRequestMetricsCRUD, BenchmarkRequestMetricsSchema
from budapp.benchmark_ops.schemas import BenchmarkRequestMetrics
from budapp.commons import logging
from budapp.dataset_ops.models import DatasetCRUD

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)


class BenchmarkRequestMetricsSeeder(BaseSeeder):
    """Seeder for benchmark request metrics.

    Ref: https://github.com/hiyouga/LLaMA-Factory
    """

    def seed(self) -> None:
        """Seed benchmark request metrics to the database."""
        try:
            self._seed_request_metrics()
        except Exception as e:
            logger.exception(f"Failed to seed metrics: {e}")

    @staticmethod
    def _seed_request_metrics() -> None:
        existing_benchmarks = []
        offset = 0
        limit = 100
        while True:
            with BenchmarkCRUD() as crud:
                db_benchmarks, count = crud.fetch_many(offset=offset, limit=limit)
            if not db_benchmarks:
                break
            existing_benchmarks.extend(db_benchmarks)
            offset += limit

            logger.info(f"Fetched {count} benchmarks. Total metrics found: {len(existing_benchmarks)}")

            if count < limit:
                break

            logger.info(f"Finished fetching benchmarks. Total benchmarks found: {len(existing_benchmarks)}")

        # get one dataset
        with DatasetCRUD() as crud:
            db_datasets, count = crud.fetch_many(offset=0, limit=1)
        dataset_id = db_datasets[0].id

        # delete all metrics
        with BenchmarkRequestMetricsCRUD() as crud:
            deleted_count = crud.delete(conditions={})
            logger.debug(f"Deleted {deleted_count} metrics")

        chosen_benchmark = random.choice(db_benchmarks)

        metrics = []
        for _ in range(100):
            success = random.choice([True, False])
            metrics.append(
                BenchmarkRequestMetrics(
                    benchmark_id=chosen_benchmark.id,
                    dataset_id=dataset_id,
                    latency=random.uniform(0, 1),
                    success=success,
                    error="" if success else "error message",
                    prompt_len=random.randint(1, 1000),
                    output_len=random.randint(1, 1000),
                    req_output_throughput=random.uniform(0, 1),
                    ttft=random.uniform(0, 1),
                    tpot=random.uniform(0, 1),
                    itl=[random.uniform(0, 1) for _ in range(10)],
                )
            )

        metrics_data = [BenchmarkRequestMetricsSchema(**metric.model_dump(mode="json")) for metric in metrics]
        with BenchmarkRequestMetricsCRUD() as crud:
            crud.bulk_insert(metrics_data)


if __name__ == "__main__":
    from sqlalchemy import text

    # BenchmarkRequestMetricsSeeder().seed()
    distribution_type = "prompt_len"
    dataset_id = "0e5362ba-627f-4688-8c9c-3482c4c50424"
    benchmark_id = "91083107-be3c-4386-92c8-da1b845a4e32"
    params = {"dataset_id": dataset_id}
    # calculate distribution bins
    with BenchmarkRequestMetricsCRUD() as crud:
        # Use parameterized query to prevent SQL injection
        if distribution_type == "prompt_len":
            query = "SELECT MAX(prompt_len) FROM benchmark_request_metrics WHERE dataset_id = :dataset_id"
        elif distribution_type == "completion_len":
            query = "SELECT MAX(completion_len) FROM benchmark_request_metrics WHERE dataset_id = :dataset_id"
        elif distribution_type == "ttft":
            query = "SELECT MAX(ttft) FROM benchmark_request_metrics WHERE dataset_id = :dataset_id"
        elif distribution_type == "tpot":
            query = "SELECT MAX(tpot) FROM benchmark_request_metrics WHERE dataset_id = :dataset_id"
        elif distribution_type == "latency":
            query = "SELECT MAX(latency) FROM benchmark_request_metrics WHERE dataset_id = :dataset_id"
        else:
            raise ValueError(f"Invalid distribution_type: {distribution_type}")

        if benchmark_id:
            query += " AND benchmark_id = :benchmark_id"
            params["benchmark_id"] = benchmark_id
        metrics_data = crud.execute_raw_query(
            query=text(query),
            params=params,
        )
        max_value = None
        if metrics_data:
            max_value = metrics_data[0][0]
        print(max_value)
