#!/usr/bin/env python3
"""Convert raw Figma caption pull (pt coords) → figma-caption-export.json.

Agent workflow after user drags captions in Figma:
  1. use_figma read script (see figma_pull_captions.js) returns { pages: { "2015-01": { "caption-1": {x,y}, ... } } } }
  2. Save to scripts/figma-caption-export-raw.json
  3. python scripts/pull_figma_captions.py
  4. python scripts/figma_to_captions.py --version v2
  5. python scripts/render.py --version v2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import common
from stage_coords import figma_pt_to_stage_pct

ROOT = common.ROOT
RAW = ROOT / "scripts" / "figma-caption-export-raw.json"
OUT = ROOT / "scripts" / "figma-caption-export.json"


def convert(raw: dict) -> dict:
    pages_in = raw.get("pages", raw)
    pages_out: dict[str, dict[str, dict[str, float]]] = {}
    for page_id, caps in pages_in.items():
        pages_out[page_id] = {}
        for cap_name, pos in caps.items():
            if not cap_name.startswith("caption-"):
                continue
            x = float(pos["x"])
            y = float(pos["y"])
            left, top = figma_pt_to_stage_pct(x, y)
            pages_out[page_id][cap_name] = {"left": left, "top": top}
    return {"pages": pages_out}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="src", type=Path, default=RAW)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    raw = json.loads(args.src.read_text())
    export = convert(raw)
    args.out.write_text(json.dumps(export, indent=2) + "\n")
    n = sum(len(v) for v in export["pages"].values())
    print(f"Wrote {args.out.relative_to(ROOT)} ({len(export['pages'])} pages, {n} captions)")


if __name__ == "__main__":
    main()
