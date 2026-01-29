import asyncio
import json
import os

from heygen_automation import HeyGenAutomation


async def main() -> int:
    config_path = "config.json"
    if not os.path.exists(config_path):
        raise RuntimeError("config.json not found")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["csv_file"] = "test_scroll_scenes.csv"
    config["episodes_to_process"] = ["ep_scroll_demo"]
    config["max_scenes"] = 15

    automation = HeyGenAutomation(config["csv_file"], config)
    automation.load_data()
    await automation.process_many(["ep_scroll_demo"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

