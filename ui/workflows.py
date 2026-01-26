from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError
import json
import os

class WorkflowStep(BaseModel):
    id: str = Field(...)
    type: str = Field(...)
    params: Dict[str, Any] = Field(default_factory=dict)

class Workflow(BaseModel):
    name: str = Field(...)
    steps: List[WorkflowStep] = Field(default_factory=list)
    settings: Dict[str, Any] = Field(default_factory=dict)

BUILTIN_STEPS = [
    "navigate_to_template",
    "fill_scene",
    "handle_broll",
    "delete_empty_scenes",
    "save",
    "reload_and_validate",
    "generate",
    "final_submit",
    "confirm",
    "click",
    "fill",
    "press",
    "wait_for",
    "open_projects",
    "wait_ready",
    "download_video",
    "ffmpeg_concat",
    "schedule"
]

def workflows_dir() -> str:
    d = os.path.join(os.getcwd(), "workflows")
    os.makedirs(d, exist_ok=True)
    return d

def list_workflows() -> List[str]:
    d = workflows_dir()
    return sorted([f for f in os.listdir(d) if f.endswith(".json")])

def load_workflow(path: str) -> Workflow:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Workflow(**data)

def save_workflow(wf: Workflow, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wf.model_dump(), f, ensure_ascii=False, indent=2)

def validate_workflow_dict(data: Dict[str, Any]) -> Workflow:
    return Workflow(**data)
