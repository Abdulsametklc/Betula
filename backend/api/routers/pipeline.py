"""Pipeline job status routes."""

from fastapi import APIRouter, HTTPException

from backend.auth.deps import CurrentUser
from backend.schemas import JobOut
from modules.repo_pipeline import get_pipeline_job

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: CurrentUser):
    job = get_pipeline_job(job_id, user_id=user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadi")
    return JobOut(
        id=job["id"],
        document_id=job["document_id"],
        status=job["status"],
        current_step=job.get("current_step"),
        error=job.get("error"),
        created_at=str(job.get("created_at")) if job.get("created_at") else None,
        updated_at=str(job.get("updated_at")) if job.get("updated_at") else None,
    )
