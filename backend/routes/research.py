import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.models import ResearchJob
from backend.routes.deps import get_current_user, get_db, get_db_user
from backend.schemas.research import ResearchRequest
from backend.services.jobs import (
    LimitReached,
    check_limits,
    create_job,
    job_to_dict,
    submit_job,
)

router = APIRouter(tags=["Research"])


@router.post("/research", status_code=202)
def start_research(
    data: ResearchRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a report in the background and return a job id straight away."""
    user = get_db_user(current_user, db)

    try:
        check_limits(db, user.id)
    except LimitReached as limit:
        raise HTTPException(status_code=limit.status_code, detail=limit.message)

    job = create_job(db, user.id, data.topic)
    submit_job(job.id)
    return {"success": True, "job": job_to_dict(job)}


@router.get("/research/jobs/{job_id}")
def get_research_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Status of one job. Only its owner can see it. When it is completed the
    response also carries the finished result in `data`."""
    user = get_db_user(current_user, db)

    job = (
        db.query(ResearchJob)
        .filter(ResearchJob.id == job_id, ResearchJob.user_id == user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    response = {"success": True, "job": job_to_dict(job)}
    if job.status == "completed" and job.result_json:
        response["data"] = json.loads(job.result_json)
    return response
