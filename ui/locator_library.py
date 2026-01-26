import os
import json

def _lib_path() -> str:
    d = os.path.join(os.getcwd(), "state")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "locators.json")

def load_locators() -> dict:
    p = _lib_path()
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_locator(name: str, selector: str) -> None:
    lib = load_locators()
    lib[name] = selector
    with open(_lib_path(), "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)

def list_locators() -> dict:
    return load_locators()

def delete_locator(name: str) -> None:
    lib = load_locators()
    if name in lib:
        del lib[name]
        with open(_lib_path(), "w", encoding="utf-8") as f:
            json.dump(lib, f, ensure_ascii=False, indent=2)

