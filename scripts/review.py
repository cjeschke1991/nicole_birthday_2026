#!/usr/bin/env python3
"""DEV: build labeled montages of the photos currently selected in story.json,
one image per year, so the curator (human or AI) can review the actual picks.

    python scripts/review.py            # selected photos, per year
    python scripts/review.py --pool 2019  # ALL tagged candidates for one year
"""
from __future__ import annotations
import argparse, json
from PIL import Image, ImageDraw, ImageFont
import common
from common import THUMBS_DIR, STORY_JSON, MANIFEST_JSON

CELL = 360
COLS = 5
PAD = 14
LABEL = 52


def font(sz):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", sz)
    except Exception:
        return ImageFont.load_default()


def montage(title, entries, out):
    n = max(1, len(entries))
    cols = COLS
    rows = (n + cols - 1) // cols
    W = cols * CELL + PAD * (cols + 1)
    H = rows * (CELL + LABEL) + PAD * (rows + 1) + 56
    img = Image.new("RGB", (W, H), (245, 241, 233))
    d = ImageDraw.Draw(img)
    d.text((PAD, 18), title, fill=(55, 45, 40), font=font(22))
    for i, e in enumerate(entries):
        r, c = divmod(i, cols)
        x = PAD + c * (CELL + PAD)
        y = 56 + PAD + r * (CELL + LABEL + PAD)
        tp = THUMBS_DIR / e["file"]
        try:
            with Image.open(tp) as t:
                t = t.copy(); t.thumbnail((CELL, CELL))
                img.paste(t, (x + (CELL - t.width) // 2, y + (CELL - t.height) // 2))
        except Exception:
            d.rectangle([x, y, x + CELL, y + CELL], outline=(200, 180, 160), width=2)
        ppl = ", ".join(e.get("people", [])) or "—"
        fl = (" [" + ",".join(e.get("flags", [])) + "]") if e.get("flags") else ""
        lay = e.get("layout", "")
        d.text((x, y + CELL + 3), f"#{i} {e.get('date','')}  {lay}", fill=(70, 60, 55), font=font(15))
        d.text((x, y + CELL + 24), f"{ppl}{fl}", fill=(120, 80, 60), font=font(14))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=88)
    print(f"  {out.relative_to(common.ROOT)}  ({len(entries)} photos)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=int, help="show all tagged candidates for a year")
    args = ap.parse_args()
    out_dir = common.BUILD_DIR / "review"

    if args.pool:
        manifest = json.loads(MANIFEST_JSON.read_text())
        items = [e for e in manifest["years"].get(str(args.pool), []) if e.get("people")]
        items.sort(key=lambda e: (len(e["people"]), e["sharpness"]), reverse=True)
        montage(f"{args.pool} — ALL {len(items)} tagged candidates",
                items, out_dir / f"pool_{args.pool}.jpg")
        return

    story = json.loads(STORY_JSON.read_text())
    for yr in story["years"]:
        montage(f"{yr['year']} — {len(yr['photos'])} selected",
                yr["photos"], out_dir / f"{yr['year']}.jpg")


if __name__ == "__main__":
    main()
