"""データモデル"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TechInfo(BaseModel):
    name: str
    categories: list[str] = []
    confidence: int = 0
    version: str = ""
    icon: str = ""
    website: str = ""


class ScanResult(BaseModel):
    url: str
    status: str = ""  # "success", "error", "timeout"
    technologies: list[TechInfo] = []
    error_message: str | None = None


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.PENDING
    total: int = 0
    completed: int = 0
    results: list[ScanResult] = []
    created_at: datetime = datetime.now()
