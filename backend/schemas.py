from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ============================================================
# BASE TASK
# ============================================================

class TaskBase(BaseModel):

    title: str

    task_type: str = "task"

    description: Optional[str] = None

    event_date: Optional[str] = None

    event_time: Optional[str] = None

    location: Optional[str] = None

    priority: str = "medium"

    status: str = "pending"

    source_text: Optional[str] = None


# ============================================================
# CREATE TASK
# ============================================================

class TaskCreate(TaskBase):
    pass


# ============================================================
# UPDATE TASK
# ============================================================

class TaskUpdate(BaseModel):

    title: Optional[str] = None

    task_type: Optional[str] = None

    description: Optional[str] = None

    event_date: Optional[str] = None

    event_time: Optional[str] = None

    location: Optional[str] = None

    priority: Optional[str] = None

    status: Optional[str] = None

    source_text: Optional[str] = None


# ============================================================
# OUTPUT TASK
# ============================================================

class TaskOut(TaskBase):

    id: int

    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )