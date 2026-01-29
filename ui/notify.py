from typing import Iterable, List
import requests

def send_telegram(
    token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    if not token or not chat_id or not text:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": bool(disable_web_page_preview),
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def send_telegram_many(
    token: str,
    chat_ids: Iterable[str],
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    ok_any = False
    for chat_id in sorted({str(c).strip() for c in (chat_ids or []) if str(c).strip()}):
        if send_telegram(token, chat_id, text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview):
            ok_any = True
    return ok_any

def fetch_telegram_chat_ids(token: str, timeout: int = 10) -> List[str]:
    if not token:
        return []
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []
    results = data.get("result") or []
    ids = []
    for upd in results:
        msg = upd.get("message") or upd.get("channel_post") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is not None:
            ids.append(str(cid))
    return sorted({c for c in ids if c})
