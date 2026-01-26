import requests

def send_telegram(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id or not text:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

