import argparse
import asyncio
import os

from utils.clipboard import generate_image


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--prompt",
        required=False,
        default="A photorealistic sushi set on a wooden table, soft studio lighting, shallow depth of field",
    )
    ap.add_argument("--out", required=False, default="debug/nano_banano")
    ap.add_argument("--episode", required=False, default="demo")
    ap.add_argument("--part", required=False, type=int, default=0)
    ap.add_argument("--scene", required=False, type=int, default=1)
    args = ap.parse_args()

    out_dir = str(args.out or "").strip() or "debug/nano_banano"
    os.makedirs(out_dir, exist_ok=True)

    path, mime = await generate_image(
        str(args.prompt),
        out_dir,
        episode_id=str(args.episode),
        part_idx=int(args.part),
        scene_idx=int(args.scene),
    )
    print(path)
    print(mime)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

