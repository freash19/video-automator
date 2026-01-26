"""
Shared data types and models for the automation system.

These types are used across all core modules to prevent circular imports.
Import from here, not from individual modules.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Callable, Awaitable, Any, Dict

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Status of an automation step."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class AutomationStep(BaseModel):
    """Record of a single automation step execution."""
    name: str
    status: StepStatus = StepStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None


class Metrics(BaseModel):
    """Metrics tracking for automation tasks."""
    model_config = {"populate_by_name": True}

    scenes_total: int = Field(0, alias="total_scenes")
    scenes_completed: int = Field(0, alias="completed_scenes")
    brolls_total: int = Field(0, alias="total_brolls")
    brolls_inserted: int = Field(0, alias="inserted_brolls")


class TaskStatus(BaseModel):
    """Overall status of an automation task."""
    task_id: str
    steps: List[AutomationStep] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    global_status: str = "pending"  # pending, running, completed, failed


# Type aliases for callback functions (used to avoid circular imports)
BrollHandler = Callable[[int, str], Awaitable[bool]]
NoticeCallback = Callable[[str], None]
StepCallback = Callable[[Dict[str, Any]], None]


# Backward compatibility aliases
Step = AutomationStep


class SceneData(BaseModel):
    """Data structure for a single scene from CSV."""
    scene_idx: int
    text: str
    speaker: Optional[str] = None
    brolls: Optional[str] = None
    title: Optional[str] = None
    template_url: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneData":
        """Create SceneData from a dictionary (CSV row)."""
        return cls(
            scene_idx=int(data.get("scene_idx", 0)),
            text=str(data.get("text", "")),
            speaker=data.get("speaker"),
            brolls=data.get("brolls"),
            title=data.get("title"),
            template_url=data.get("template_url"),
        )


class Report(BaseModel):
    """Automation run report."""
    validation_missing: List[Dict[str, Any]] = Field(default_factory=list)
    broll_skipped: List[Dict[str, Any]] = Field(default_factory=list)
    broll_no_results: List[Dict[str, Any]] = Field(default_factory=list)
    broll_errors: List[Dict[str, Any]] = Field(default_factory=list)
    manual_intervention: List[Dict[str, Any]] = Field(default_factory=list)
