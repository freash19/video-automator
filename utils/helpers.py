"""
Helper functions for data coercion, text normalization, and speaker mapping.

These are pure functions with no side effects, safe to use anywhere.
"""

import re
from typing import Any, Optional

import pandas as pd


def coerce_scalar(v: Any) -> Any:
    """
    Coerce a pandas Series/DataFrame to a scalar value.
    
    Args:
        v: Value that might be a Series, DataFrame, or scalar
        
    Returns:
        The first value if iterable, otherwise the value itself
    """
    if isinstance(v, pd.Series):
        if len(v) == 0:
            return None
        try:
            return v.iloc[0]
        except Exception:
            return None
    if isinstance(v, pd.DataFrame):
        if v.shape[0] == 0 or v.shape[1] == 0:
            return None
        try:
            return v.iat[0, 0]
        except Exception:
            return None
    return v


def as_clean_str(v: Any) -> str:
    """
    Convert value to a clean string, handling pandas objects and NaN.
    
    Args:
        v: Any value to convert
        
    Returns:
        Stripped string representation, empty string for None/NaN
    """
    v2 = coerce_scalar(v)
    if v2 is None:
        return ""
    try:
        if pd.isna(v2):
            return ""
    except Exception:
        pass
    s = str(v2)
    return s.strip()


def normalize_speaker_key(speaker: Optional[str]) -> Optional[str]:
    """
    Normalize speaker name to a consistent key format.
    
    Maps known speaker names to their canonical forms:
    - "dr peter", "doctor peter", "peter" -> "Dr_Peter"
    - "michael" -> "Michael"
    - "hiroshi" -> "Hiroshi"
    
    Args:
        speaker: Raw speaker name from CSV
        
    Returns:
        Normalized speaker key or None if empty
    """
    if not speaker:
        return None
    s = str(speaker).strip()
    if not s:
        return None
    
    # Normalize to lowercase alphanumeric for matching
    compact = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip().lower()
    
    # Known speaker mappings
    mapping = {
        "dr peter": "Dr_Peter",
        "doctor peter": "Dr_Peter",
        "peter": "Dr_Peter",
        "michael": "Michael",
        "hiroshi": "Hiroshi",
    }
    
    if compact in mapping:
        return mapping[compact]
    
    # Fallback: create safe identifier
    safe = re.sub(r"[^a-zA-Z0-9_\-]+", "_", s).strip("_")
    return safe or None


def normalize_text_for_compare(text: str, strip_annotations: bool = False) -> str:
    """
    Normalize text for comparison purposes.
    
    Args:
        text: Raw text to normalize
        strip_annotations: If True, remove [annotations] in brackets
        
    Returns:
        Normalized text with collapsed whitespace
    """
    try:
        t = str(text or '')
        if strip_annotations:
            t = re.sub(r"\[[^\]]*\]", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t
    except Exception:
        return str(text or '').strip()


def safe_slug(value: str) -> str:
    """
    Create a filesystem-safe slug from a value.
    
    Args:
        value: String to convert to slug
        
    Returns:
        Safe identifier with only alphanumeric, underscore, hyphen
    """
    s = str(value or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", s)
    return s.strip("_") or "item"


def wf_bool(v: Any, default: bool = False) -> bool:
    """
    Parse a workflow parameter as boolean.
    
    Args:
        v: Value to parse (bool, str, int, etc.)
        default: Default value if parsing fails
        
    Returns:
        Boolean value
    """
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def wf_float(v: Any, default: float = 0.0) -> float:
    """
    Parse a workflow parameter as float.
    
    Args:
        v: Value to parse
        default: Default value if parsing fails
        
    Returns:
        Float value
    """
    if v is None:
        return default
    if isinstance(v, (int, float)) and v == v:  # NaN check
        return float(v)
    s = str(v).strip()
    if not s:
        return default
    try:
        return float(s)
    except Exception:
        return default


def wf_int(v: Any, default: int = 0) -> int:
    """
    Parse a workflow parameter as integer.
    
    Args:
        v: Value to parse
        default: Default value if parsing fails
        
    Returns:
        Integer value
    """
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == v:  # NaN check
        return int(v)
    s = str(v).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def wf_render(v: Any, ctx: dict) -> str:
    """
    Render a workflow string template with context variables.
    
    Supports {{variable}} syntax for substitution.
    
    Args:
        v: Template string
        ctx: Context dictionary with variable values
        
    Returns:
        Rendered string with variables substituted
    """
    s = str(v or "")
    if "{{" not in s:
        return s
    try:
        def _repl(m):
            k = str(m.group(1) or "").strip()
            if k in ctx:
                return str(ctx.get(k) or "")
            return m.group(0)
        return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", _repl, s)
    except Exception:
        return s
