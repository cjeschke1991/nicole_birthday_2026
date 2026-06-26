#!/usr/bin/env python3
"""One-time helper: regroup v2 story.json into scatter pages with theme tags."""
from __future__ import annotations

import json
import re
from pathlib import Path

import common

SCATTER_CYCLE = ["scatter-a", "scatter-b", "scatter-c", "scatter-d"]

THEME_RULES: list[tuple[str, str]] = [
    (r"boat|water|river|cruise|lake|sail", "boat"),
    (r"cubs|wrigley|baseball|ballgame|ballpark", "baseball"),
    (r"blackhawk|hockey", "hockey"),
    (r"cooper|zoa|puppy|pup|good boy|good girl|dog", "dog"),
    (r"connor|hailey|baby|born|newborn|parents|three|four", "baby"),
    (r"married|wedding|mr\.|mrs\.|i do", "wedding"),
    (r"honeymoon|punta|beach|paradise|travel|air", "travel"),
    (r"home|lawn|kitchen|living", "home"),
    (r"concert|festival|music", "music"),
    (r"engaged|kickapoo|yes", "heart"),
    (r"mountain", "mountain"),
    (r"snack|dinner|food|eat", "food"),
    (r"chicago|city|skyline|wrigley", "city"),
    (r"date night|together|us\.", "heart"),
]


def infer_theme(photo: dict) -> str:
    text = f"{photo.get('caption', '')} {photo.get('file', '')}".lower()
    for pattern, theme in THEME_RULES:
        if re.search(pattern, text):
            return theme
    return "heart"


def chunk_photos(photos: list[dict]) -> list[list[dict]]:
    """Split into groups of up to 3 for scatter pages (room for captions)."""
    if not photos:
        return []
    chunks: list[list[dict]] = []
    i = 0
    n = len(photos)
    while i < n:
        remaining = n - i
        if remaining <= 3:
            chunks.append(photos[i:])
            break
        if remaining == 4:
            chunks.extend([photos[i : i + 2], photos[i + 2 : i + 4]])
            break
        if remaining == 5:
            chunks.extend([photos[i : i + 3], photos[i + 3 : i + 5]])
            break
        chunks.append(photos[i : i + 3])
        i += 3
    return chunks


def convert(story: dict) -> dict:
    story = json.loads(json.dumps(story))
    book = story.setdefault("book", {})
    book["edition"] = "scrapbook"
    book["accent"] = "sky"

    recipe_idx = 0
    for yr in story.get("years", []):
        photos = yr.get("photos", [])
        new_photos: list[dict] = []
        for chunk in chunk_photos(photos):
            recipe = SCATTER_CYCLE[recipe_idx % len(SCATTER_CYCLE)]
            recipe_idx += 1
            for p in chunk:
                entry = dict(p)
                entry["layout"] = recipe
                entry["theme"] = p.get("theme") or infer_theme(p)
                new_photos.append(entry)
        yr["photos"] = new_photos
    return story


def main() -> None:
    vp = common.VersionPaths.for_name("v2")
    story = json.loads(vp.story_json.read_text())
    out = convert(story)
    vp.story_json.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    total = sum(len(y["photos"]) for y in out["years"])
    pages = sum(
        len(chunk_photos(y["photos"])) for y in out["years"]
    )
    print(f"Updated {vp.story_json.relative_to(common.ROOT)}")
    print(f"  {total} photos -> {pages} scatter pages")


if __name__ == "__main__":
    main()
