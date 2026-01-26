"""
CSV parsing and validation for automation scenarios.

Handles loading, column normalization, and validation of scenario CSV files.
"""

import os
from typing import Dict, List, Optional, Any, Tuple

import pandas as pd

from ui.logger import logger


# Default column mappings
DEFAULT_COLUMNS = {
    'episode_id': 'episode_id',
    'part_idx': 'part_idx',
    'scene_idx': 'scene_idx',
    'text': 'text',
    'title': 'title',
    'template_url': 'template_url',
    'speaker': 'speaker',
    'brolls': 'brolls',
}

# Known synonyms for column names
COLUMN_SYNONYMS = {
    'brolls': ['broll_query', 'broll', 'broll_query_ru'],
    'episode_id': ['episode', 'ep_id'],
    'part_idx': ['part', 'part_number'],
    'scene_idx': ['scene', 'scene_number'],
}


def load_csv(
    csv_path: str,
    column_overrides: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Load and normalize a CSV file for automation.
    
    Args:
        csv_path: Path to the CSV file
        column_overrides: Custom column name mappings
        
    Returns:
        Normalized pandas DataFrame
        
    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        KeyError: If required columns are missing
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    logger.info(f"[csv_parser] loading: {csv_path}")
    
    # Try different encodings
    df = None
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1']:
        try:
            df = pd.read_csv(csv_path, encoding=encoding, sep=None, engine='python')
            break
        except Exception:
            continue
    
    if df is None:
        raise ValueError(f"Failed to parse CSV: {csv_path}")
    
    logger.info(f"[csv_parser] loaded {len(df)} rows")
    
    # Normalize column names (remove BOM, trim whitespace)
    df = _normalize_column_names(df)
    
    # Apply synonyms
    df = _apply_column_synonyms(df)
    
    # Apply custom column mappings
    colmap = {**DEFAULT_COLUMNS, **(column_overrides or {})}
    df = _apply_column_mappings(df, colmap)
    
    # Validate required columns
    _validate_required_columns(df)
    
    # Convert numeric columns
    for col in ['part_idx', 'scene_idx']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    logger.info(f"[csv_parser] columns: {list(df.columns)}")
    return df


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Remove BOM and whitespace from column names."""
    norm_map = {}
    for c in df.columns:
        c2 = str(c).replace('\ufeff', '').strip()
        norm_map[c] = c2
    if norm_map:
        df = df.rename(columns=norm_map)
    return df


def _apply_column_synonyms(df: pd.DataFrame) -> pd.DataFrame:
    """Replace synonym column names with standard names."""
    for target, alts in COLUMN_SYNONYMS.items():
        if target not in df.columns:
            for alt in alts:
                if alt in df.columns:
                    df = df.rename(columns={alt: target})
                    break
    return df


def _apply_column_mappings(df: pd.DataFrame, colmap: Dict[str, str]) -> pd.DataFrame:
    """Apply custom column name mappings."""
    ren = {v: k for k, v in colmap.items() if v in df.columns and v != k}
    if ren:
        df = df.rename(columns=ren)
    return df


def _validate_required_columns(df: pd.DataFrame) -> None:
    """Validate that required columns are present."""
    required = ['episode_id', 'part_idx', 'scene_idx', 'text']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")


def get_episode_parts(df: pd.DataFrame, episode_id: str) -> List[int]:
    """
    Get all part indices for an episode.
    
    Args:
        df: DataFrame with scenario data
        episode_id: Episode identifier
        
    Returns:
        Sorted list of part indices
    """
    episode_data = df[df['episode_id'] == episode_id]
    if episode_data.empty:
        return []
    
    vals = pd.to_numeric(episode_data['part_idx'], errors='coerce').dropna().tolist()
    parts = sorted({int(v) for v in vals})
    return parts


def get_episode_data(
    df: pd.DataFrame,
    episode_id: str,
    part_idx: int,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Get template URL and scenes for a specific episode part.
    
    Args:
        df: DataFrame with scenario data
        episode_id: Episode identifier
        part_idx: Part index
        
    Returns:
        Tuple of (template_url, list of scene dictionaries)
    """
    episode_data = df[
        (df['episode_id'] == episode_id) & 
        (df['part_idx'] == part_idx)
    ]
    
    if episode_data.empty:
        return None, []
    
    # Get template URL
    template_url = None
    if 'template_url' in episode_data.columns:
        first_template = episode_data['template_url'].dropna()
        if len(first_template) > 0:
            template_url = str(first_template.iloc[0])
    
    # Build scenes list
    scenes = []
    for _, row in episode_data.iterrows():
        scene = {
            'scene_idx': int(row['scene_idx']),
            'text': str(row['text'] or ''),
        }
        
        # Optional fields
        if 'speaker' in row and pd.notna(row.get('speaker')):
            scene['speaker'] = str(row['speaker'])
        
        if 'brolls' in row and pd.notna(row.get('brolls')):
            scene['brolls'] = str(row['brolls'])
        
        if 'title' in row and pd.notna(row.get('title')):
            scene['title'] = str(row['title'])
        
        if 'template_url' in row and pd.notna(row.get('template_url')):
            scene['template_url'] = str(row['template_url'])
        
        scenes.append(scene)
    
    # Sort by scene index
    scenes.sort(key=lambda s: s['scene_idx'])
    
    return template_url, scenes


def get_all_episodes(df: pd.DataFrame) -> List[str]:
    """
    Get all unique episode IDs from the DataFrame.
    
    Args:
        df: DataFrame with scenario data
        
    Returns:
        Sorted list of episode IDs
    """
    if 'episode_id' not in df.columns:
        return []
    
    return sorted([str(e) for e in df['episode_id'].dropna().unique()])
