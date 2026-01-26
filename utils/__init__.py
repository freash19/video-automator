# Utility modules
"""
Utility package containing helper functions and parsers.

Modules:
- helpers: Data coercion, text normalization, speaker key mapping
- csv_parser: CSV loading, column normalization, validation
- clipboard: Clipboard operations for image copy/paste (Nano Banano)
"""

from utils.helpers import (
    coerce_scalar,
    as_clean_str,
    normalize_speaker_key,
    normalize_text_for_compare,
    safe_slug,
)

__all__ = [
    "coerce_scalar",
    "as_clean_str",
    "normalize_speaker_key",
    "normalize_text_for_compare",
    "safe_slug",
]
