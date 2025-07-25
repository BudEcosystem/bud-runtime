from typing import Union

from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.http_client import AsyncHTTPClient
from pydantic import BaseModel

from ..commons.config import app_settings, secrets_settings
from ..commons.exceptions import DaprJobsException


logger = get_logger(__name__)


class DaprJobs:
    """Ref to https://docs.dapr.io/reference/api/jobs_api/ for more details."""

    def __init__(self):
        """Initialize the DaprJobs class."""
        self.http_client = AsyncHTTPClient()
        self.base_url = f"http://localhost:{app_settings.dapr_http_port}/v1.0-alpha1/jobs"
        self.headers = {"Content-Type": "application/json"}
        if secrets_settings.dapr_api_token:
            self.headers["dapr-api-token"] = secrets_settings.dapr_api_token

    async def create_job(
        self, job_name: str, data: Union[BaseModel, dict, str, None] = None, schedule: str | None = None, **kwargs
    ):
        """Create a job.

        Args:
            job_name: The name of the job.
            data: The data to be passed to the job.
            schedule: The schedule of the job.
                "@every 5s", "@every 1h30m", "@hourly", "@daily", "@weekly", "@monthly", etc.
            kwargs: Additional keyword arguments accepted by the Dapr Jobs API.
        """
        data = data or {}
        serialized_data = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
        request_body = {"data": serialized_data, "schedule": schedule, **kwargs}
        logger.info(f"Creating job {job_name} with request body: {request_body}")
        async with self.http_client as client:
            response = await client.send_request(
                method="POST",
                url=f"{self.base_url}/{job_name}",
                json=request_body,
                headers=self.headers,
            )
            if response.status_code != 204:
                raise DaprJobsException(f"Failed to create job {job_name}: {response.status_code}")
            return response

    async def get_job(self, job_name: str):
        """Get a job."""
        async with self.http_client as client:
            response = await client.send_request(
                method="GET",
                url=f"{self.base_url}/{job_name}",
                headers=self.headers,
            )
            if response.status_code != 200:
                raise DaprJobsException(f"Failed to get job {job_name}: {response.status_code}")
            return response

    async def delete_job(self, job_name: str):
        """Delete a job."""
        async with self.http_client as client:
            response = await client.send_request(
                method="DELETE",
                url=f"{self.base_url}/{job_name}",
                headers=self.headers,
            )
            if response.status_code != 204:
                raise DaprJobsException(f"Failed to delete job {job_name}: {response.status_code}")
            return response
