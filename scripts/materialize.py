#!/usr/bin/env python3
"""
Materialize full-resolution print JPEGs for ONLY the photos used in story.json.

Reads story/story.json + build/manifest.json, finds each chosen photo's original
source file, and writes a high-quality, EXIF-rotated, sRGB JPEG to
photos_processed/<year>/<name>.jpg (the path render.py expects).

This keeps the project small: thousands of photos are indexed as thumbnails, but
only the ~dozens that make the book are converted to full resolution.

Usage:
    python scripts/materialize.py
"""
from __future__ import annotations

import json

from PIL import Image, ImageOps

import common
from common import MANIFEST_JSON, PHOTOS_PROCESSED, STORY_JSON

# Long-edge cap: 11.25in (shop, with bleed) * 300 DPI = 3375 px.
MAX_LONG_EDGE = 3400
JPEG_QUALITY = 88


def used_files(story: dict) -> set:
    files = set()
    cover = story.get("book", {}).get("cover")
    if cover:
        files.add(cover)
    for yr in story.get("years", []):
        for p in yr.get("photos", []):
            if p.get("file"):
                files.add(p["file"])
    return files


def main() -> None:
    common.register_heif()
    if not STORY_JSON.exists():
        print("No story/story.json. Run scripts/draft_story.py first.")
        return
    if not MANIFEST_JSON.exists():
        print("No build/manifest.json. Run scripts/ingest.py first.")
        return

    story = json.loads(STORY_JSON.read_text())
    manifest = json.loads(MANIFEST_JSON.read_text())

    src_by_file = {}
    for items in manifest.get("years", {}).values():
        for e in items:
            src_by_file[e["file"]] = e["src"]

    # Clear stale processed output (fully derived from story.json).
    import shutil
    if PHOTOS_PROCESSED.exists():
        for y in PHOTOS_PROCESSED.iterdir():
            if y.is_dir():
                shutil.rmtree(y)

    wanted = used_files(story)
    print(f"Materializing {len(wanted)} photo(s) at print resolution...")

    done, missing = 0, []
    for rel in sorted(wanted):
        src = src_by_file.get(rel)
        if not src:
            missing.append(rel)
            continue
        out = PHOTOS_PROCESSED / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                if max(im.size) > MAX_LONG_EDGE:
                    im.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE))
                im.save(out, "JPEG", quality=JPEG_QUALITY)
            done += 1
        except Exception as e:
            missing.append(f"{rel} ({e})")

    print(f"  wrote {done} file(s) to photos_processed/")
    if missing:
        print(f"  WARNING: {len(missing)} not materialized:")
        for m in missing[:20]:
            print(f"    - {m}")


if __name__ == "__main__":
    main()
