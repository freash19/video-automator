import asyncio
import glob
import os
import re
import sys
from typing import Iterable

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from heygen_automation import HeyGenAutomation


class _FakePage:
    async def screenshot(self, path: str, full_page: bool = True):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"")


def _read_new_lines(path: str, start_size: int) -> Iterable[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        handle.seek(start_size)
        return [line.rstrip("\n") for line in handle.readlines()]


def _format_ok(line: str, step_name: str) -> bool:
    pattern = rf"^\[\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}},\d{{3}}\] \[[A-Z]+\] \[{re.escape(step_name)}\] .+"
    return re.match(pattern, line) is not None


async def _run() -> int:
    step_name = "healthcheck_fail"
    log_path = "automation.log"
    start_size = os.path.getsize(log_path) if os.path.exists(log_path) else 0

    automation = HeyGenAutomation(csv_path="healthcheck.csv", config={})
    automation._page = _FakePage()

    async def _fail():
        raise RuntimeError("intentional healthcheck failure")

    try:
        await automation.perform_step(step_name, _fail, critical=True)
    except Exception:
        pass

    screenshot_matches = glob.glob(f"debug/screenshots/{step_name}_*.png")
    screenshot_ok = len(screenshot_matches) > 0

    new_lines = _read_new_lines(log_path, start_size)
    error_lines = [line for line in new_lines if "ERROR" in line and f"[{step_name}]" in line]
    log_ok = any(_format_ok(line, step_name) for line in error_lines)

    if screenshot_ok and log_ok:
        print("SYSTEM READY TO SCALE")
        return 0

    print("VIOLATION: see .cursorrules")
    if not screenshot_ok:
        print(" - missing screenshot in debug/screenshots/")
    if not log_ok:
        print(" - log format or error entry missing in automation.log")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
