from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobState(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    # Reserved for a future transient "failed but retryable" state if needed.
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class Job:
    id: str
    command: str

    state: JobState = JobState.PENDING

    attempts: int = 0
    max_retries: int = 3

    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    # Earliest time this job is eligible to run.
    next_run_at: datetime = field(default_factory=utc_now)