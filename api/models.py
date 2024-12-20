from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    CONVERTING = "converting"
    CONVERTED = "converted"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskCreate(BaseModel):
    file_name: str

class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    file_name: str
    total_pages: Optional[int] = None
    current_page: Optional[int] = None
    error: Optional[str] = None

class PageResult(BaseModel):
    page_number: int
    content: str
    confidence: float

class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    file_name: str
    total_pages: int
    results: List[PageResult]
    created_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str] = None
