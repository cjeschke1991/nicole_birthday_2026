#!/usr/bin/env python3
"""Apply Figma caption layout export to versions/{v}/caption_positions.json.

LEGACY: Prefer caption-N layers on scatter-a … scatter-d (sync via pull_figma_scatter.py).
This script remains for per-page overrides in caption_positions.json only.
  {
    "pages": {
      "2015-01": {
        "caption-1": {"left": 76.0, "top": 38.0},
        "caption-2": {"left": 50.0, "top": 73.0}
      }
    }
  }

Layer names in Figma: caption-1 … caption-3 (one per photo on the page, same order as photos).
Frame names match manifest ids (2015-01, 2016-02, …).

Workflow:
  1. Drag caption layers on the Caption Layouts page in Figma.
  2. Agent reads frames via Figma MCP → saves figma-caption-export.json.
  3. python scripts/figma_to_captions.py --version v2
  4. python scripts/render.py --version v2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import common
from scatter_pages import (
    load_caption_positions,
    load_manifest,
    write_caption_positions,
)

ROOT = common.ROOT
DEFAULT_EXPORT = ROOT / "scripts" / "figma-caption-export.json"


def apply_export(export: dict, version: str, merge: bool = True) -> dict[str, dict[str, float]]:
    manifest = {p.id: p for p in load_manifest(version)}
    if not manifest:
        raise SystemExit(
            f"No manifest at versions/{version}/scatter_page_manifest.json — "
            f"run: python scripts/export_scatter_manifest.py --version {version}"
        )

    pages = export.get("pages", export)
    positions = load_caption_positions(version) if merge else {}

    for page_id, caps in pages.items():
        page = manifest.get(page_id)
        if not page:
            print(f"  skip unknown page id: {page_id}")
            continue
        for idx, photo in enumerate(page.photos):
            key = f"caption-{idx + 1}"
            if key not in caps:
                continue
            pos = caps[key]
            positions[photo] = {
                "left": float(pos["left"]),
                "top": float(pos["top"]),
            }
            print(f"  {page_id} {key} → {photo} @ {pos['left']}%, {pos['top']}%")

    return positions


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Figma caption positions")
    parser.add_argument("--version", default="v2")
    parser.add_argument("--from", dest="src", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--replace", action="store_true", help="Replace file instead of merging")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.src.is_file():
        raise SystemExit(f"Export not found: {args.src}")

    export = json.loads(args.src.read_text())
    positions = apply_export(export, args.version, merge=not args.replace)

    if args.dry_run:
        print(json.dumps(positions, indent=2))
        return

    path = write_caption_positions(positions, args.version)
    print(f"Wrote {path.relative_to(ROOT)} ({len(positions)} caption(s))")


if __name__ == "__main__":
    main()
