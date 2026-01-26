"""
Workflow execution engine for HeyGen automation.

Handles step-by-step workflow processing based on JSON configuration.
Provides a bridge between workflow definitions and core automation functions.
"""

import asyncio
import re
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Callable, Awaitable

from ui.logger import logger
from utils.helpers import wf_bool, wf_float, wf_int, wf_render

if TYPE_CHECKING:
    from playwright.async_api import Page


# Workflow step types
STEP_NAVIGATE = {"navigate_to_template", "navigate"}
STEP_WAIT = {"wait_for", "wait_for_selector"}
STEP_SLEEP = {"wait", "sleep"}
STEP_CLICK = {"click"}
STEP_FILL = {"fill"}
STEP_PRESS = {"press"}
STEP_SCENE = {"fill_scene"}
STEP_BROLL = {"handle_broll"}
STEP_VALIDATE = {"reload_and_validate", "validate"}
STEP_DELETE = {"delete_empty_scenes"}
STEP_CONFIRM = {"confirm"}
STEP_GENERATE = {"generate"}
STEP_SUBMIT = {"final_submit"}


class WorkflowContext:
    """Context for workflow execution."""
    
    def __init__(
        self,
        episode_id: str = "",
        part_idx: int = 0,
        template_url: str = "",
        scenes: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.episode_id = episode_id
        self.part_idx = part_idx
        self.template_url = template_url
        self.scenes = scenes or []
        self.config = config or {}
        self.variables: Dict[str, Any] = {
            "episode_id": episode_id,
            "part_idx": part_idx,
            "template_url": template_url,
        }
    
    def render(self, template: str) -> str:
        """Render a template string with context variables."""
        return wf_render(template, self.variables)


async def execute_navigate(
    page: "Page",
    params: Dict[str, Any],
    ctx: WorkflowContext,
) -> bool:
    """Execute a navigate step."""
    url = ctx.render(params.get("url") or ctx.template_url).strip()
    wait_until = ctx.render(params.get("wait_until") or "domcontentloaded").strip()
    timeout = wf_int(params.get("timeout_ms"), 120000)
    
    if not url:
        logger.warning("[workflow] navigate: no URL provided")
        return False
    
    logger.info(f"[workflow] navigate: {url}")
    await page.goto(url, wait_until=wait_until, timeout=timeout)
    return True


async def execute_wait_for(
    page: "Page",
    params: Dict[str, Any],
    ctx: WorkflowContext,
) -> bool:
    """Execute a wait_for selector step."""
    selector = ctx.render(params.get("selector") or "").strip()
    if not selector:
        return True
    
    timeout = wf_int(params.get("timeout_ms"), 30000)
    state = ctx.render(params.get("state") or "visible").strip() or "visible"
    
    logger.info(f"[workflow] wait_for: {selector}")
    await page.wait_for_selector(selector, timeout=timeout, state=state)
    return True


async def execute_sleep(
    page: "Page",
    params: Dict[str, Any],
    ctx: WorkflowContext,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """Execute a wait/sleep step."""
    sec = wf_float(params.get("sec"), 1.0)
    
    if gate_callback:
        await gate_callback()
    
    logger.debug(f"[workflow] sleep: {sec}s")
    await asyncio.sleep(sec)
    return True


async def execute_click(
    page: "Page",
    params: Dict[str, Any],
    ctx: WorkflowContext,
) -> bool:
    """Execute a click step."""
    selector = ctx.render(params.get("selector") or "").strip()
    if not selector:
        return True
    
    timeout = wf_int(params.get("timeout_ms"), 8000) or None
    loc = page.locator(selector)
    
    which = ctx.render(params.get("which") or "").strip().lower()
    if which == "last":
        loc = loc.last
    elif which.isdigit():
        loc = loc.nth(int(which))
    
    logger.info(f"[workflow] click: {selector}")
    
    if timeout is None:
        await loc.click()
    else:
        await loc.click(timeout=timeout)
    
    return True


async def execute_fill(
    page: "Page",
    params: Dict[str, Any],
    ctx: WorkflowContext,
) -> bool:
    """Execute a fill step."""
    selector = ctx.render(params.get("selector") or "").strip()
    text = ctx.render(params.get("text") or "").replace("\\n", "\n")
    
    if not selector:
        return True
    
    logger.info(f"[workflow] fill: {selector}")
    await page.locator(selector).fill(text)
    return True


async def execute_press(
    page: "Page",
    params: Dict[str, Any],
    ctx: WorkflowContext,
) -> bool:
    """Execute a key press step."""
    selector = ctx.render(params.get("selector") or "").strip()
    key = ctx.render(params.get("key") or "").strip()
    
    if not selector or not key:
        return True
    
    logger.info(f"[workflow] press: {key} on {selector}")
    await page.press(selector, key)
    return True


def get_step_executor(step_type: str) -> Optional[Callable]:
    """
    Get the executor function for a step type.
    
    Args:
        step_type: Type of the workflow step
        
    Returns:
        Executor function or None if not found
    """
    if step_type in STEP_NAVIGATE:
        return execute_navigate
    if step_type in STEP_WAIT:
        return execute_wait_for
    if step_type in STEP_SLEEP:
        return execute_sleep
    if step_type in STEP_CLICK:
        return execute_click
    if step_type in STEP_FILL:
        return execute_fill
    if step_type in STEP_PRESS:
        return execute_press
    
    # Complex steps are handled by the main automation class
    return None


async def execute_step(
    page: "Page",
    step: Dict[str, Any],
    ctx: WorkflowContext,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Execute a single workflow step.
    
    This function handles basic steps. Complex steps (fill_scene, handle_broll,
    validate, generate) should be handled by the main automation class.
    
    Args:
        page: Playwright Page object
        step: Step definition dictionary
        ctx: Workflow context
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if step executed successfully, None if not handled
    """
    step_type = str(step.get("type") or "").strip()
    params = step.get("params") if isinstance(step.get("params"), dict) else {}
    
    executor = get_step_executor(step_type)
    
    if executor is None:
        # Not a basic step - should be handled elsewhere
        return None
    
    if gate_callback:
        await gate_callback()
    
    try:
        if step_type in STEP_SLEEP:
            return await executor(page, params, ctx, gate_callback)
        else:
            return await executor(page, params, ctx)
    except Exception as e:
        logger.error(f"[workflow] step {step_type} failed: {e}")
        raise


def is_complex_step(step_type: str) -> bool:
    """
    Check if a step type requires complex handling.
    
    Complex steps need access to the full automation class state.
    
    Args:
        step_type: Type of the workflow step
        
    Returns:
        True if step is complex
    """
    complex_types = (
        STEP_SCENE | STEP_BROLL | STEP_VALIDATE | 
        STEP_DELETE | STEP_CONFIRM | STEP_GENERATE | STEP_SUBMIT
    )
    return step_type in complex_types


def validate_workflow(steps: List[Dict[str, Any]]) -> List[str]:
    """
    Validate a workflow definition.
    
    Args:
        steps: List of step definitions
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if not steps:
        errors.append("Workflow has no steps")
        return errors
    
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"Step {i}: not a dictionary")
            continue
        
        step_type = step.get("type")
        if not step_type:
            errors.append(f"Step {i}: missing 'type' field")
        
        params = step.get("params")
        if params is not None and not isinstance(params, dict):
            errors.append(f"Step {i}: 'params' must be a dictionary")
    
    return errors


def has_broll_step(steps: List[Dict[str, Any]]) -> bool:
    """
    Check if workflow has an explicit B-roll handling step.
    
    Args:
        steps: List of step definitions
        
    Returns:
        True if handle_broll step exists
    """
    for step in steps:
        if isinstance(step, dict) and step.get("type") in STEP_BROLL:
            return True
    return False
