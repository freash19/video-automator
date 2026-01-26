"""
Clipboard operations for image handling on macOS.

Used for Nano Banano image generation workflow where images
are generated via API and pasted into the HeyGen editor.
"""

import asyncio
import base64
import json
import os
import re
import subprocess
import time
from typing import Tuple, Optional
from urllib import request, error

from core.config import get_settings
from ui.logger import logger


def parse_nano_banano_prompt(query: str) -> Optional[str]:
    """
    Parse a NANO_BANANO: prefix from a broll query.
    
    Args:
        query: B-roll query string (e.g., "NANO_BANANO: a serene forest")
        
    Returns:
        The prompt text after the prefix, or None if not a Nano Banano query
    """
    try:
        m = re.match(r"^\s*NANO_BANANO\s*:\s*(.+)$", str(query or ""), flags=re.I)
        if not m:
            return None
        prompt = str(m.group(1) or "").strip()
        return prompt or None
    except Exception:
        return None


def get_nano_banano_model() -> str:
    """
    Get the Nano Banano model name from settings.
    
    Returns:
        Model name (e.g., "nano-banano-pro" or "imagen-3.0-generate-002")
    """
    settings = get_settings()
    return settings.nano_banano_model or "nano-banano-pro"


def generate_image_sync(prompt: str, model: str, api_key: str) -> Tuple[bytes, str]:
    """
    Generate an image using Google's Generative AI API (synchronous).
    
    Supports both Imagen and Gemini-style models.
    
    Args:
        prompt: Text prompt for image generation
        model: Model name (e.g., "nano-banano-pro", "imagen-3.0-generate-002")
        api_key: Google API key
        
    Returns:
        Tuple of (image_bytes, mime_type)
        
    Raises:
        RuntimeError: If generation fails
    """
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing")
    
    model_name = model.strip()
    if not model_name:
        raise RuntimeError("model name missing")
    
    model_key = model_name.split("/")[-1]
    
    # Imagen-style models use predict endpoint
    if model_key.startswith("imagen-"):
        return _generate_imagen(prompt, model_key, api_key)
    
    # Gemini-style models use generateContent endpoint
    return _generate_gemini(prompt, model_name, api_key)


def _generate_imagen(prompt: str, model_key: str, api_key: str) -> Tuple[bytes, str]:
    """Generate image using Imagen API."""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_key}:predict?key={api_key}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1},
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
    except error.HTTPError as e:
        raw_err = ""
        try:
            raw_err = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"api_error: {e.code} {raw_err}") from e
    except Exception as e:
        raise RuntimeError(f"api_error: {e}") from e
    
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"api_response_parse_error: {e}") from e
    
    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"api_error: {parsed.get('error')}")
    
    preds = parsed.get("predictions") if isinstance(parsed, dict) else None
    if not preds:
        raise RuntimeError("api_no_predictions")
    
    pred = preds[0] if isinstance(preds, list) else preds
    image_b64 = None
    if isinstance(pred, dict):
        image_b64 = pred.get("bytesBase64Encoded") or pred.get("image") or pred.get("bytes")
    
    if not image_b64:
        raise RuntimeError("api_no_image_data")
    
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        raise RuntimeError(f"api_bad_image_data: {e}") from e
    
    return image_bytes, "image/png"


def _generate_gemini(prompt: str, model_name: str, api_key: str) -> Tuple[bytes, str]:
    """Generate image using Gemini-style API."""
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
    
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
    except error.HTTPError as e:
        raw_err = ""
        try:
            raw_err = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"api_error: {e.code} {raw_err}") from e
    except Exception as e:
        raise RuntimeError(f"api_error: {e}") from e
    
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"api_response_parse_error: {e}") from e
    
    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"api_error: {parsed.get('error')}")
    
    candidates = parsed.get("candidates") if isinstance(parsed, dict) else None
    if not candidates:
        raise RuntimeError("api_no_candidates")
    
    parts = None
    try:
        parts = candidates[0].get("content", {}).get("parts")
    except Exception:
        parts = None
    
    if not parts:
        raise RuntimeError("api_no_parts")
    
    image_b64 = None
    mime = "image/png"
    
    for part in parts:
        if not isinstance(part, dict):
            continue
        inline = part.get("inline_data") or part.get("inlineData")
        if isinstance(inline, dict) and inline.get("data"):
            image_b64 = inline.get("data")
            mime = inline.get("mime_type") or inline.get("mimeType") or mime
            break
    
    if not image_b64:
        raise RuntimeError("api_no_image_data")
    
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        raise RuntimeError(f"api_bad_image_data: {e}") from e
    
    return image_bytes, str(mime or "image/png")


async def generate_image(
    prompt: str,
    output_dir: str,
    episode_id: str = "episode",
    part_idx: int = 0,
    scene_idx: int = 0,
) -> Tuple[str, str]:
    """
    Generate an image asynchronously and save it to disk.
    
    Args:
        prompt: Text prompt for generation
        output_dir: Directory to save the image
        episode_id: Episode identifier for filename
        part_idx: Part index for filename
        scene_idx: Scene index for filename
        
    Returns:
        Tuple of (file_path, mime_type)
    """
    settings = get_settings()
    model = get_nano_banano_model()
    api_key = settings.google_api_key
    
    logger.info(f"[nano_banano] generating image for scene {scene_idx}")
    
    image_bytes, mime = await asyncio.to_thread(
        generate_image_sync,
        prompt,
        model,
        api_key,
    )
    
    # Determine file extension
    ext = "png"
    mime_lower = str(mime or "").lower()
    if "jpeg" in mime_lower or "jpg" in mime_lower:
        ext = "jpg"
    
    # Create safe filename
    safe_episode = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(episode_id)).strip("_") or "episode"
    safe_part = str(part_idx)
    stamp = int(time.time())
    filename = f"{safe_episode}_p{safe_part}_s{scene_idx}_{stamp}.{ext}"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    
    # Save image
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    
    logger.info(f"[nano_banano] saved: {out_path}")
    return out_path, mime_lower or "image/png"


def copy_image_to_clipboard(path: str, mime: str) -> None:
    """
    Copy an image file to the macOS clipboard.
    
    Args:
        path: Path to the image file
        mime: MIME type of the image
        
    Raises:
        RuntimeError: If clipboard copy fails
    """
    mime_l = str(mime or "").lower()
    
    # Determine AppleScript picture type
    script_type = "TIFF picture"
    if "jpeg" in mime_l or "jpg" in mime_l:
        script_type = "JPEG picture"
    elif "png" in mime_l:
        script_type = "PNG picture"
    
    script = f'set the clipboard to (read (POSIX file "{path}") as {script_type})'
    
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        logger.info(f"[clipboard] copied: {path}")
        return
    except Exception:
        pass
    
    # Fallback: convert PNG to TIFF for clipboard
    if "png" in mime_l:
        tiff_path = f"{path}.tiff"
        try:
            subprocess.run(
                ["sips", "-s", "format", "tiff", path, "--out", tiff_path],
                check=True,
                capture_output=True,
            )
            script = f'set the clipboard to (read (POSIX file "{tiff_path}") as TIFF picture)'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            logger.info(f"[clipboard] copied (via TIFF): {path}")
            return
        except Exception as e:
            raise RuntimeError(f"clipboard_copy_failed: {e}") from e
    
    raise RuntimeError("clipboard_copy_failed")
