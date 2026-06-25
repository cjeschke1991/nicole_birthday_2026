#!/usr/bin/env python3
"""
Materialize full-resolution print JPEGs for ONLY the photos used in a version's story.json.

Reads versions/{v}/story.json + build/manifest.json, finds each chosen photo's original
source file, and writes a high-quality, EXIF-rotated, sRGB JPEG to
photos_processed/<year>/<name>.jpg (the path render.py expects).

Version-specific swap photos (under versions/{v}/photos/) are skipped — they are
already full resolution and resolved first at render time.

Usage:
    python scripts/materialize.py
    python scripts/materialize.py --version v2
"""
from __future__ import annotations

import argparse
import json
import shutil

from PIL import Image, ImageOps

import common
from common import DEFAULT_VERSION, MANIFEST_JSON, PHOTOS_PROCESSED, set_version

MAX_LONG_EDGE = 3400
JPEG_QUALITY = 88


def used_files(story: dict, version_photos) -> set:
    files = set()
    cover = story.get("book", {}).get("cover")
    if cover:
        files.add(cover)
    for yr in story.get("years", []):
        for p in yr.get("photos", []):
            if p.get("file"):
                files.add(p["file"])
    # Skip paths already provided as version-specific swaps.
    skip = {rel for rel in files if (version_photos / rel).exists()}
    return files - skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DEFAULT_VERSION)
    args = ap.parse_args()

    common.register_heif()
    vp = set_version(args.version)

    if not MANIFEST_JSON.exists():
        print("No build/manifest.json. Run scripts/ingest.py first.")
        return

    story = json.loads(vp.story_json.read_text())
    manifest = json.loads(MANIFEST_JSON.read_text())

    src_by_file = {}
    for items in manifest.get("years", {}).values():
        for e in items:
            src_by_file[e["file"]] = e["src"]

    if PHOTOS_PROCESSED.exists():
        for y in PHOTOS_PROCESSED.iterdir():
            if y.is_dir():
                shutil.rmtree(y)

    wanted = used_files(story, vp.photos)
    print(f"[{vp.name}] Materializing {len(wanted)} photo(s) at print resolution...")

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
        print(f"  WARNING: {len(missing)} not materialized (may be version swap photos):")
        for m in missing[:20]:
            print(f"    - {m}")


if __name__ == "__main__":
    main()
