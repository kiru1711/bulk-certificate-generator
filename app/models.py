from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    certificate_title: Mapped[str] = mapped_column(String(200))
    event_name: Mapped[str] = mapped_column(String(200))
    issuer_name: Mapped[str] = mapped_column(String(200))
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_count: Mapped[int] = mapped_column(Integer)
    successful_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipients: Mapped[list["RecipientCertificate"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class RecipientCertificate(Base):
    __tablename__ = "recipient_certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    file_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    job: Mapped[GenerationJob] = relationship(back_populates="recipients")
