from fastapi import APIRouter
from pydantic import BaseModel


job_router = APIRouter(prefix="/job")


class TestJobRequest(BaseModel):
    message: str


@job_router.post("/test-job")
async def test_job(request: TestJobRequest):
    """Test job."""
    print(request)
    return {"data": request.model_dump()}
