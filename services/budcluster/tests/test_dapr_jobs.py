from pydantic import BaseModel

from budcluster.commons.config import app_settings
from budcluster.shared.dapr_jobs import DaprJobs



class TestJob(BaseModel):
    message: str


async def test_create_job():
    dapr_jobs = DaprJobs()
    job_name = "test-job"
    data = TestJob(message="Hello, World!")
    response = await dapr_jobs.create_job(job_name, data, schedule="@every 5s", repeats=5)
    print(dir(response))
    assert response.status_code == 204

async def test_get_job():
    dapr_jobs = DaprJobs()
    job_name = "test-job"
    response = await dapr_jobs.get_job(job_name)
    assert response.status_code == 200

async def test_delete_job():
    dapr_jobs = DaprJobs()
    job_name = "test-job"
    response = await dapr_jobs.delete_job(job_name)
    assert response.status_code == 204

async def test_update_node_status_job():
    dapr_jobs = DaprJobs()
    job_name = "update-node-status"
    data = {"cluster_id": "17b6b7ee-546a-423f-b117-c426c7d521a3"}
    response = await dapr_jobs.create_job(job_name, data, schedule="@every 10s", repeats=2)
    print(dir(response))
    assert response.status_code == 204


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_create_job())
    # asyncio.run(test_delete_job())
    # asyncio.run(test_update_node_status_job())
    # asyncio.run(test_get_job())
