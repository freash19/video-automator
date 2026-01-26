# Core automation modules
"""
Core package containing the refactored HeyGen automation logic.

Modules:
- config: Pydantic Settings for environment/secrets
- types: Shared data models (TaskStatus, AutomationStep, Metrics)
- browser: Browser interaction utilities (safe_click, scroll helpers)
- broll: B-roll search, insert, make_background logic
- scenes: Scene filling, validation, deletion
- workflow: Workflow step execution
- automation: Main HeyGenAutomation coordinator class
"""

from core.config import get_settings, Settings
from core.types import TaskStatus, AutomationStep, Metrics, StepStatus

__all__ = [
    "get_settings",
    "Settings",
    "TaskStatus",
    "AutomationStep",
    "Metrics",
    "StepStatus",
]
