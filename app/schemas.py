import os
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "500"))


class RecipientInput(BaseModel):
    # Keep per-recipient data permissive so one bad row can fail independently.
    name: str = Field(max_length=200)
    email: str | None = Field(default=None, max_length=320)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class JobCreate(BaseModel):
    certificate_title: str = Field(min_length=1, max_length=200)
    event_name: str = Field(min_length=1, max_length=200)
    issuer_name: str = Field(min_length=1, max_length=200)
    issue_date: date
    recipients: list[RecipientInput] = Field(min_length=1, max_length=MAX_BATCH_SIZE)

    @field_validator("certificate_title", "event_name", "issuer_name")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class RecipientResult(BaseModel):
    id: str
    name: str
    email: str | None
    status: str
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class JobAccepted(BaseModel):
    job_id: str
    status: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    total_count: int
    successful_count: int
    failed_count: int
    pending_count: int
    created_at: datetime
    completed_at: datetime | None
    recipients: list[RecipientResult]
