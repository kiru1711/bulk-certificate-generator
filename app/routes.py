import logging
from starlette.background import BackgroundTask

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from .database import get_db
from .models import GenerationJob, RecipientCertificate
from .schemas import JobAccepted, JobCreate, JobStatus
from .services import create_job, process_job
from . import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/jobs", response_model=JobAccepted, status_code=202)
def submit_job(payload: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = create_job(db, payload)
    background_tasks.add_task(process_job, job.id)
    return JobAccepted(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).options(selectinload(GenerationJob.recipients)).filter_by(id=job_id).first()
    if job is None:
        raise HTTPException(404, detail="Job not found")
    pending = sum(rec.status in ("pending", "processing") for rec in job.recipients)
    return JobStatus(job_id=job.id, status=job.status, total_count=job.total_count,
                     successful_count=job.successful_count, failed_count=job.failed_count, pending_count=pending,
                     created_at=job.created_at, completed_at=job.completed_at, recipients=job.recipients)


@router.get("/jobs/{job_id}/certificates/{recipient_id}")
def download_certificate(job_id: str, recipient_id: str, db: Session = Depends(get_db)):
    if db.get(GenerationJob, job_id) is None:
        raise HTTPException(404, detail="Job not found")
    recipient = db.get(RecipientCertificate, recipient_id)
    if recipient is None or recipient.job_id != job_id:
        raise HTTPException(404, detail="Recipient not found for this job")
    if recipient.status in ("pending", "processing"):
        raise HTTPException(409, detail="Certificate generation is not finished")
    if recipient.status != "success" or not recipient.file_name:
        raise HTTPException(404, detail="Certificate was not generated successfully")
    try:
        path = storage.certificate_path(job_id, recipient.file_name)
    except ValueError:
        logger.error("Rejected unsafe stored certificate filename for recipient %s", recipient_id)
        raise HTTPException(404, detail="Certificate file is unavailable")
    if not path.is_file():
        raise HTTPException(404, detail="Certificate file is unavailable")
    return FileResponse(path, media_type="application/pdf", filename=f"certificate-{recipient.id}.pdf")


@router.get("/jobs/{job_id}/certificates")
def download_zip(job_id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).options(selectinload(GenerationJob.recipients)).filter_by(id=job_id).first()
    if job is None:
        raise HTTPException(404, detail="Job not found")
    if any(r.status in ("pending", "processing") for r in job.recipients):
        raise HTTPException(409, detail="Certificate generation is not finished")
    available = []
    for recipient in job.recipients:
        if recipient.status != "success" or not recipient.file_name:
            continue
        try:
            path = storage.certificate_path(job_id, recipient.file_name)
        except ValueError:
            logger.warning("Skipped unsafe stored filename for recipient %s", recipient.id)
            continue
        if path.is_file():
            available.append((path, f"certificate-{recipient.id}.pdf"))
    if not available:
        raise HTTPException(404, detail="No successful certificate files are available")
    try:
        archive = storage.build_zip(available)
    except OSError:
        logger.exception("Could not create certificate ZIP for job %s", job_id)
        raise HTTPException(500, detail="Could not create certificate archive")
    return FileResponse(archive, media_type="application/zip", filename=f"certificates-{job_id}.zip", background=BackgroundTask(archive.unlink, missing_ok=True))
