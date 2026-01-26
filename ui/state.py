import os
import json
import math
import datetime

def _sanitize_json_value(v):
    if v is None:
        return None
    if isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: _sanitize_json_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_sanitize_json_value(x) for x in v]
    if hasattr(v, "item"):
        try:
            return _sanitize_json_value(v.item())
        except Exception:
            return None
    try:
        if v != v:
            return None
    except Exception:
        pass
    return v

def _dedupe_projects(projects: list) -> list:
    by_episode = {}
    order = []
    for pr in projects or []:
        if not isinstance(pr, dict):
            continue
        ep = pr.get("episode")
        if ep is None:
            continue
        ep_key = str(ep)
        if ep_key not in by_episode:
            order.append(ep_key)
            by_episode[ep_key] = {"episode": ep_key}
        merged = by_episode[ep_key]
        if pr.get("created_at") is not None:
            cur = merged.get("created_at")
            inc = pr.get("created_at")
            if cur is None:
                merged["created_at"] = inc
            else:
                try:
                    merged["created_at"] = min(str(cur), str(inc))
                except Exception:
                    merged["created_at"] = cur
        if pr.get("status") is not None:
            merged["status"] = pr.get("status")
        if pr.get("data") is not None:
            incoming = pr.get("data")
            existing = merged.get("data")
            try:
                incoming_len = len(incoming) if isinstance(incoming, list) else 0
            except Exception:
                incoming_len = 0
            try:
                existing_len = len(existing) if isinstance(existing, list) else 0
            except Exception:
                existing_len = 0
            if existing is None or incoming_len > existing_len:
                merged["data"] = incoming
    return [by_episode[k] for k in order]

def _now_iso() -> str:
    try:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _state_dir() -> str:
    d = os.path.join(os.getcwd(), "state")
    os.makedirs(d, exist_ok=True)
    return d

def recent_episodes_path() -> str:
    return os.path.join(_state_dir(), "recent_episodes.json")

def get_recent_episodes() -> list:
    p = recent_episodes_path()
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_recent_episodes(episodes: list) -> None:
    p = recent_episodes_path()
    eps = get_recent_episodes()
    merged = [e for e in episodes if e] + [e for e in eps if e]
    out = []
    for e in merged:
        if e not in out:
            out.append(e)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out[:50], f, ensure_ascii=False, indent=2)

def projects_path() -> str:
    return os.path.join(_state_dir(), "projects.json")

def get_projects() -> list:
    p = projects_path()
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            try:
                loaded = json.load(f)
                cleaned = _sanitize_json_value(loaded)
                cleaned = _dedupe_projects(cleaned) if isinstance(cleaned, list) else []
                if cleaned != loaded:
                    save_projects(cleaned)
                return cleaned
            except Exception:
                return []
    return []

def save_projects(projects: list) -> None:
    p = projects_path()
    with open(p, "w", encoding="utf-8") as f:
        sanitized = _sanitize_json_value(projects)
        sanitized = _dedupe_projects(sanitized) if isinstance(sanitized, list) else []
        json.dump(sanitized, f, ensure_ascii=False, indent=2)

def add_projects(episodes: list) -> list:
    cur = get_projects()
    names = {str(pr.get("episode")) for pr in cur}
    for ep in episodes:
        if str(ep) not in names:
            cur.append({"episode": str(ep), "status": "pending", "created_at": _now_iso()})
    save_projects(cur)
    return cur

def update_project_status(episode: str, status: str) -> None:
    cur = get_projects()
    for pr in cur:
        if str(pr.get("episode")) == str(episode):
            pr["status"] = status
    save_projects(cur)

def add_projects_with_data(df, episodes: list) -> list:
    cur = get_projects()
    names = {str(pr.get("episode")) for pr in cur}
    for ep in episodes:
        ep_str = str(ep)
        if ep_str in names:
            # update existing with data
            for pr in cur:
                if str(pr.get("episode")) == ep_str:
                    try:
                        if 'episode_id' in df.columns:
                            rows = df[df['episode_id'] == ep_str]
                        elif 'episode' in df.columns:
                            rows = df[df['episode'] == ep_str]
                        else:
                            rows = df
                        pr["data"] = _sanitize_json_value(rows.to_dict(orient="records"))
                    except Exception:
                        pr["data"] = []
            continue
        item = {"episode": ep_str, "status": "pending", "created_at": _now_iso()}
        try:
            if 'episode_id' in df.columns:
                rows = df[df['episode_id'] == ep_str]
            elif 'episode' in df.columns:
                rows = df[df['episode'] == ep_str]
            else:
                rows = df
            item["data"] = _sanitize_json_value(rows.to_dict(orient="records"))
        except Exception:
            item["data"] = []
        cur.append(item)
    save_projects(cur)
    return cur

def add_projects_with_records(rows: list, episodes: list | None = None) -> list:
    grouped: dict[str, list] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        ep = r.get("episode") or r.get("episode_id")
        if not ep:
            continue
        ep_str = str(ep)
        grouped.setdefault(ep_str, []).append(r)

    if episodes:
        allow = {str(e) for e in episodes if e}
        grouped = {k: v for k, v in grouped.items() if k in allow}

    cur = get_projects()
    by_episode = {str(pr.get("episode")): pr for pr in cur if isinstance(pr, dict) and pr.get("episode") is not None}
    for ep_str, recs in grouped.items():
        pr = by_episode.get(ep_str)
        if not pr:
            pr = {"episode": ep_str, "status": "pending", "created_at": _now_iso()}
            cur.append(pr)
            by_episode[ep_str] = pr
        if not pr.get("created_at"):
            pr["created_at"] = _now_iso()
        pr["data"] = _sanitize_json_value(recs)
        if not pr.get("status"):
            pr["status"] = "pending"

    save_projects(cur)
    return get_projects()


# Video state management
import uuid

def videos_path() -> str:
    return os.path.join(_state_dir(), "videos.json")


def get_videos() -> dict:
    """Get all videos from state/videos.json"""
    p = videos_path()
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return _sanitize_json_value(data) or {"videos": [], "last_scraped": None}
            except Exception:
                return {"videos": [], "last_scraped": None}
    return {"videos": [], "last_scraped": None}


def save_videos(data: dict) -> None:
    """Save videos to state/videos.json"""
    p = videos_path()
    with open(p, "w", encoding="utf-8") as f:
        sanitized = _sanitize_json_value(data)
        json.dump(sanitized, f, ensure_ascii=False, indent=2)


def get_video_list() -> list:
    """Get just the videos array"""
    return get_videos().get("videos", [])


def add_video(video: dict) -> dict:
    """Add a new video to the list"""
    data = get_videos()
    videos = data.get("videos", [])
    
    # Generate ID if not present
    if not video.get("id"):
        video["id"] = str(uuid.uuid4())
    
    # Check for duplicate by title or download_url
    existing_ids = {v.get("id") for v in videos}
    existing_titles = {v.get("title") for v in videos if v.get("title")}
    
    if video.get("id") in existing_ids:
        # Update existing
        for i, v in enumerate(videos):
            if v.get("id") == video.get("id"):
                videos[i] = {**v, **video}
                break
    elif video.get("title") in existing_titles:
        # Update by title match
        for i, v in enumerate(videos):
            if v.get("title") == video.get("title"):
                videos[i] = {**v, **video}
                video["id"] = v.get("id")
                break
    else:
        videos.append(video)
    
    data["videos"] = videos
    save_videos(data)
    return video


def update_video(video_id: str, updates: dict) -> dict | None:
    """Update a video by ID"""
    data = get_videos()
    videos = data.get("videos", [])
    
    for i, v in enumerate(videos):
        if v.get("id") == video_id:
            videos[i] = {**v, **updates}
            data["videos"] = videos
            save_videos(data)
            return videos[i]
    
    return None


def delete_video(video_id: str) -> bool:
    """Delete a video by ID"""
    data = get_videos()
    videos = data.get("videos", [])
    
    original_len = len(videos)
    videos = [v for v in videos if v.get("id") != video_id]
    
    if len(videos) < original_len:
        data["videos"] = videos
        save_videos(data)
        return True
    
    return False


def clear_videos() -> None:
    """Clear all videos"""
    save_videos({"videos": [], "last_scraped": None})


def set_last_scraped() -> None:
    """Update the last_scraped timestamp"""
    data = get_videos()
    data["last_scraped"] = _now_iso()
    save_videos(data)


def bulk_add_videos(videos: list) -> list:
    """Add multiple videos at once, avoiding duplicates by title"""
    data = get_videos()
    existing = data.get("videos", [])
    existing_titles = {v.get("title") for v in existing if v.get("title")}
    
    added = []
    for video in videos:
        if not video.get("id"):
            video["id"] = str(uuid.uuid4())
        
        if video.get("title") not in existing_titles:
            existing.append(video)
            existing_titles.add(video.get("title"))
            added.append(video)
        else:
            # Update existing video with same title
            for i, v in enumerate(existing):
                if v.get("title") == video.get("title"):
                    existing[i] = {**v, **video, "id": v.get("id")}
                    added.append(existing[i])
                    break
    
    data["videos"] = existing
    data["last_scraped"] = _now_iso()
    save_videos(data)
    return added
