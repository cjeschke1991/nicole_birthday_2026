#!/usr/bin/env python3
"""Convert raw Figma scatter pull (pt) → figma-scatter-export.json (stage %).

Slot tuple (11 values):
  left%, top%, width%, height%, rot°, clipart_left%, clipart_top%,
  caption_left%, caption_top%, caption_width%, caption_height%
  (9-value slots without caption box size still supported)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import common
from stage_coords import figma_pt_to_stage_pct

ROOT = common.ROOT
RAW = ROOT / "scripts" / "figma-scatter-export-raw.json"
OUT = ROOT / "scripts" / "figma-scatter-export.json"

PAGE_W_PT = 792.0
PAGE_H_PT = 612.0
STAGE_LEFT_PT = 36.0
STAGE_TOP_PT = 32.4
STAGE_W_PT = PAGE_W_PT - 72.0
STAGE_H_PT = PAGE_H_PT - 64.8


def _size_pct(w_pt: float, h_pt: float) -> tuple[float, float]:
    return round(w_pt / STAGE_W_PT * 100.0, 1), round(h_pt / STAGE_H_PT * 100.0, 1)


def convert(raw: dict) -> dict[str, list[list[float]]]:
    recipes_in = raw.get("recipes", raw)
    recipes_out: dict[str, list[list[float]]] = {}
    for name, slots in recipes_in.items():
        if not name.startswith("scatter-"):
            continue
        out_slots: list[list[float]] = []
        for slot in slots:
            p = slot["photo"]
            left, top = figma_pt_to_stage_pct(p["x"], p["y"])
            w_pct, h_pct = _size_pct(p["w"], p["h"])
            rot = round(p["rot"], 1)
            if slot.get("clip"):
                cil, cit = figma_pt_to_stage_pct(slot["clip"]["x"], slot["clip"]["y"])
            else:
                cil, cit = left + w_pct * 0.5, top
            if slot.get("caption"):
                cap = slot["caption"]
                cap_l, cap_t = figma_pt_to_stage_pct(cap["x"], cap["y"])
                cap_w, cap_h = _size_pct(cap.get("w", 0), cap.get("h", 0))
                if cap_w <= 0:
                    cap_w, cap_h = 22.0, 12.0
            else:
                cap_l, cap_t, cap_w, cap_h = 50.0, 70.0, 22.0, 12.0
            out_slots.append(
                [left, top, w_pct, h_pct, rot, cil, cit, cap_l, cap_t, cap_w, cap_h],
            )
        recipes_out[name] = out_slots
    return recipes_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="src", type=Path, default=RAW)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    raw = json.loads(args.src.read_text())
    recipes = convert(raw)
    export = {
        "source": "figma://scatter-recipes",
        "recipes": recipes,
    }
    args.out.write_text(json.dumps(export, indent=2) + "\n")
    for name in sorted(recipes):
        print(f"  {name}: {len(recipes[name])} slots (with captions)")
    print(f"Wrote {args.out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
