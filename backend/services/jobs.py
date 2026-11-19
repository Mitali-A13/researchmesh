"""Background research jobs.

POST /research creates a job row and returns at once. A small pool of worker threads
runs the pipeline and keeps the row up to date; the app polls GET /research/jobs/{id}.

Limits of this design (on purpose, to keep it simple):
- jobs live in this one server process; if the server restarts, running jobs are lost,
  so at startup they are marked failed (see fail_stale_jobs);
- to run several servers you would move the workers to a real queue (Celery or similar).
"""

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.db.database import SessionLocal
from backend.db.models import ResearchJob
from backend.services.pipeline_service import generate_research
from backend.services.reports import save_report

logger = logging.getLogger("thinkmesh.jobs")

ACTIVE = ("queued", "running")
_executor = ThreadPoolExecutor(
    max_workers=int(os.getenv("JOB_WORKERS", "2")), thread_name_prefix="research-job"
)


class LimitReached(Exception):
    """The user may not start another report right now."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def check_limits(db: Session, user_id: int) -> None:
    """One report at a time per user, and a daily cap (both set in .env)."""
    max_active = int(os.getenv("MAX_ACTIVE_JOBS_PER_USER", "1"))
    daily_limit = int(os.getenv("DAILY_REPORT_LIMIT", "10"))

    active = (
        db.query(ResearchJob)
        .filter(ResearchJob.user_id == user_id, ResearchJob.status.in_(ACTIVE))
        .count()
    )
    if active >= max_active:
        raise LimitReached(
            409, "You already have a report in progress. Please wait for it."
        )

    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = (
        db.query(ResearchJob)
        .filter(
            ResearchJob.user_id == user_id,
            ResearchJob.created_at >= today_start,
            ResearchJob.status != "failed",  # a failed report does not use up the cap
        )
        .count()
    )
    if today >= daily_limit:
        raise LimitReached(
            429, f"Daily limit of {daily_limit} reports reached. Try again tomorrow."
        )


def create_job(db: Session, user_id: int, topic: str) -> ResearchJob:
    job = ResearchJob(
        id=uuid.uuid4().hex,
        user_id=user_id,
        topic=topic,
        status="queued",
        stage="Waiting to start",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def submit_job(job_id: str) -> None:
    _executor.submit(run_job, job_id)


def _fail(db: Session, job: ResearchJob, message: str) -> None:
    job.status = "failed"
    job.stage = "Failed"
    job.error = str(message)[:500]
    job.finished_at = utcnow()
    db.commit()
    logger.warning("job %s failed: %s", job.id, job.error)


def run_job(job_id: str) -> None:
    """Runs in a worker thread, with its own database session."""
    db = SessionLocal()
    try:
        job = db.get(ResearchJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.stage = "Starting"
        job.started_at = utcnow()
        db.commit()
        topic, user_id = job.topic, job.user_id
        logger.info("job %s started", job_id)

        def on_stage(stage: str) -> None:
            job.stage = stage
            db.commit()

        result = generate_research(topic, on_stage=on_stage)
        if result.get("status") == "failed":
            _fail(db, job, result.get("error") or "The research pipeline failed.")
            return

        job.stage = "Saving the report"
        db.commit()
        history = save_report(db, user_id, topic, result)
        job.history_id = history.id
        job.result_json = json.dumps(result, default=str)
        job.status = "completed"
        job.stage = "Done"
        job.finished_at = utcnow()
        db.commit()
        logger.info("job %s completed", job_id)
    except Exception as exc:  # never leave a job stuck on "running"
        db.rollback()
        try:
            job = db.get(ResearchJob, job_id)
            if job is not None:
                _fail(db, job, f"Unexpected error: {exc}")
        except Exception:
            logger.exception("could not record the failure of job %s", job_id)
    finally:
        db.close()


def fail_stale_jobs() -> int:
    """At startup: jobs that were queued or running belonged to a server that is gone."""
    with SessionLocal() as db:
        stale = db.query(ResearchJob).filter(ResearchJob.status.in_(ACTIVE)).all()
        for job in stale:
            job.status = "failed"
            job.stage = "Failed"
            job.error = (
                "The server restarted before this report finished. Please try again."
            )
            job.finished_at = utcnow()
        db.commit()
        return len(stale)


def job_to_dict(job: ResearchJob) -> dict:
    def iso(value):
        return value.isoformat() if value else None

    return {
        "id": job.id,
        "topic": job.topic,
        "status": job.status,
        "stage": job.stage,
        "error": job.error,
        "history_id": job.history_id,
        "created_at": iso(job.created_at),
        "started_at": iso(job.started_at),
        "finished_at": iso(job.finished_at),
    }
