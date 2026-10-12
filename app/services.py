import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from . import certificate, storage
from .database import SessionLocal
from .models import GenerationJob, RecipientCertificate

logger = logging.getLogger(__name__)


def create_job(db, payload) -> GenerationJob:
    job_id = str(uuid.uuid4())
    job = GenerationJob(
        id=job_id, certificate_title=payload.certificate_title, event_name=payload.event_name,
        issuer_name=payload.issuer_name, issue_date=payload.issue_date, status="pending",
        total_count=len(payload.recipients),
    )
    for entry in payload.recipients:
        job.recipients.append(RecipientCertificate(id=str(uuid.uuid4()), name=entry.name, email=str(entry.email) if entry.email else None, status="pending"))
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created certificate job %s with %d recipients", job.id, job.total_count)
    return job


def process_job(job_id: str) -> None:
    # Background work owns its session; it never uses the request's session.
    db = SessionLocal()
    logger.info("Started certificate job %s", job_id)
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            logger.error("Background job %s disappeared before processing", job_id)
            return
        job.status = "processing"
        db.commit()
        records = db.scalars(select(RecipientCertificate).where(RecipientCertificate.job_id == job_id).order_by(RecipientCertificate.id)).all()
        for recipient in records:
            email_invalid = recipient.email is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient.email)
            if not recipient.name.strip() or email_invalid:
                recipient.status = "failed"
                recipient.error_message = "Recipient name is required." if not recipient.name.strip() else "Email address is invalid."
                job.failed_count += 1
                db.commit()
                continue
            recipient.status = "processing"
            db.commit()
            file_name = f"{recipient.id}.pdf"
            path = storage.certificate_path(job_id, file_name)
            try:
                certificate.generate_certificate(path, job.certificate_title, recipient.name, job.event_name, job.issuer_name, job.issue_date)
                recipient.status = "success"
                recipient.file_name = file_name
                recipient.error_message = None
            except Exception as exc:
                logger.exception("Certificate generation failed for recipient %s in job %s", recipient.id, job_id)
                recipient.status = "failed"
                recipient.error_message = "Certificate generation failed. Please retry this recipient."
                recipient.file_name = None
                path.unlink(missing_ok=True)
            db.commit()
        db.refresh(job)
        job.successful_count = sum(r.status == "success" for r in records)
        job.failed_count = sum(r.status == "failed" for r in records)
        job.status = "completed" if job.failed_count == 0 else ("completed_with_errors" if job.successful_count else "failed")
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Completed certificate job %s: %d succeeded, %d failed", job_id, job.successful_count, job.failed_count)
    except Exception:
        db.rollback()
        logger.exception("Unexpected error while processing job %s", job_id)
        job = db.get(GenerationJob, job_id)
        if job is not None:
            for recipient in job.recipients:
                if recipient.status in ("pending", "processing"):
                    recipient.status = "failed"
                    recipient.error_message = "Job processing failed unexpectedly."
            job.successful_count = sum(r.status == "success" for r in job.recipients)
            job.failed_count = sum(r.status == "failed" for r in job.recipients)
            job.status = "completed_with_errors" if job.successful_count else "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
