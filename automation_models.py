from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime

class StepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"

class AutomationStep(BaseModel):
    name: str
    status: StepStatus = StepStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None

class Metrics(BaseModel):
    model_config = {"populate_by_name": True}

    scenes_total: int = Field(0, alias="total_scenes")
    scenes_completed: int = Field(0, alias="completed_scenes")
    brolls_total: int = Field(0, alias="total_brolls")
    brolls_inserted: int = Field(0, alias="inserted_brolls")

class TaskStatus(BaseModel):
    task_id: str
    steps: List[AutomationStep] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    global_status: str = "pending" # pending, running, completed, failed

Step = AutomationStep
