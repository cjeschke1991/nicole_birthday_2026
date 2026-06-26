#!/usr/bin/env python3
"""Write scatter_page_manifest.json and optionally seed caption_positions.json."""
from __future__ import annotations

import argparse
import json

import common
from common import set_version
from render import make_scatter
from scatter_pages import (
    iter_scatter_pages,
    load_caption_positions,
    write_caption_positions,
    write_manifest,
)

ROOT = common.ROOT


def _parse_cap_pct(value: str) -> float:
    return float(value.rstrip("%"))


def seed_caption_positions(story: dict, version: str) -> int:
    vp = set_version(version)
    positions = load_caption_positions(version)
    count = 0
    for page in iter_scatter_pages(story):
        yr = next(y for y in story["years"] if int(y["year"]) == page.year)
        group = []
        for rel in page.photos:
            group.append(next(p for p in yr["photos"] if p["file"] == rel))
        scatter = make_scatter(yr, group, page.recipe, vp, page_id=page.id)
        for item, rel in zip(scatter["cells"], page.photos):
            if not item.get("caption"):
                continue
            positions[rel] = {
                "left": _parse_cap_pct(item["cap_left"]),
                "top": _parse_cap_pct(item["cap_top"]),
            }
            count += 1
    write_caption_positions(positions, version)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2")
    parser.add_argument("--seed-captions", action="store_true",
                        help="Also write caption_positions.json from auto layout")
    args = parser.parse_args()

    vp = set_version(args.version)
    story = json.loads(vp.story_json.read_text())
    path = write_manifest(story, args.version)
    pages = iter_scatter_pages(story)
    print(f"Wrote {path.relative_to(ROOT)} ({len(pages)} scatter pages)")

    if args.seed_captions:
        n = seed_caption_positions(story, args.version)
        print(f"Seeded caption_positions.json ({n} captions)")


if __name__ == "__main__":
    main()
