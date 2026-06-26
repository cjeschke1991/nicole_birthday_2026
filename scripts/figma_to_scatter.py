#!/usr/bin/env python3
"""Apply Figma scatter layout export to scripts/scatter_recipes.json.

Workflow (photos + clipart + captions in one step):
  1. Drag photo-N, clipart-N, caption-N on scatter-a … scatter-d in Figma.
  2. Agent runs figma_pull_scatter.js via use_figma → figma-scatter-export-raw.json
  3. python scripts/pull_figma_scatter.py
  4. python scripts/figma_to_scatter.py
  5. python scripts/render.py --version v2

Or say **"sync scatters"** in Cursor.

Slot tuple: left%, top%, width%, height%, rot°, clipart_left%, clipart_top%,
            caption_left%, caption_top%, caption_width%, caption_height%
            (9/11 values; 7-value slots still supported)
Stage insets match .scatter-stage in versions/v2/assets/css/book.css:
  margin 0.5in left/right, 0.45in top/bottom on 11x8.5in page.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORT = ROOT / "scripts" / "figma-scatter-export.json"
RECIPES_JSON = ROOT / "scripts" / "scatter_recipes.json"


def load_export(path: Path) -> dict[str, list[list[float]]]:
    data = json.loads(path.read_text())
    recipes = data.get("recipes", data)
    out: dict[str, list[list[float]]] = {}
    for name, slots in recipes.items():
        if not name.startswith("scatter-"):
            continue
        out[name] = slots
    if not out:
        raise SystemExit(f"No scatter-* recipes found in {path}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Figma scatter layouts to scatter_recipes.json")
    parser.add_argument(
        "--from",
        dest="src",
        type=Path,
        default=DEFAULT_EXPORT,
        help=f"Figma export JSON (default: {DEFAULT_EXPORT.relative_to(ROOT)})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print recipes without writing")
    args = parser.parse_args()

    recipes = load_export(args.src)
    for name in sorted(recipes):
        print(f"  {name}: {len(recipes[name])} slots")

    if args.dry_run:
        print(json.dumps(recipes, indent=2))
        return

    RECIPES_JSON.write_text(json.dumps(recipes, indent=2) + "\n")
    print(f"Wrote {RECIPES_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
