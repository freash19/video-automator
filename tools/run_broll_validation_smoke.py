import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from heygen_automation import HeyGenAutomation


async def main() -> None:
    config = {
        "max_scenes": 1,
        "browser": "chrome",
        "force_embedded_browser": True,
        "debug_keep_browser_open_on_error": True,
        "headless": False,
        "enable_generation": False,
        "enable_notifications": False,
        "pre_fill_wait": 1.5,
        "delay_between_scenes": 0.5,
        "post_reload_wait": 5.0,
        "search_results_timeout_ms": 8000,
        "validation_ready_timeout_ms": 10000,
        "save_notification_timeout_ms": 4000,
        "save_fallback_wait_sec": 7.0,
        "orientation_choice": "Landscape",
        "media_source": "getty",
        "close_media_panel_after_broll": True,
        "broll_validation_wait_sec": 4.0,
        "broll_validation_force_empty_once": False,
        "broll_validation_force_needs_set_bg_once": False,
        "csv_columns": {
            "episode_id": "episode_id",
            "part_idx": "part_idx",
            "scene_idx": "scene_idx",
            "speaker": "speaker",
            "text": "text",
            "brolls": "broll_query",
            "title": "title",
            "template_url": "template_url",
        },
        "workflow_steps": [
            {
                "id": "navigate_to_template",
                "type": "navigate_to_template",
                "params": {"timeout_ms": 120000, "wait_until": "domcontentloaded"},
            },
            {
                "id": "wait_editor",
                "type": "wait_for",
                "params": {"selector": "span[data-node-view-content-react]", "timeout_ms": 30000},
            },
            {"id": "fill_scene", "type": "fill_scene", "params": {"handle_broll": True}},
        ],
    }

    a = HeyGenAutomation("state/test_broll_1scene.csv", config)
    a.load_data()
    ok = await a.process_episode_part("ep_test_broll", 1)
    print("TEST RESULT:", ok)


if __name__ == "__main__":
    asyncio.run(main())
