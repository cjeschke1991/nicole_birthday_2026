#!/usr/bin/env python3
"""
DEV ONLY: generate placeholder photos so the pipeline can be tested before the
real iCloud exports exist. Creates colored images with labels, fake capture
dates (via file mtime), some cross-album duplicates, and sample cover images.

    python scripts/make_placeholders.py

Safe to delete photos_raw contents afterward; this never touches real photos
unless you point it at folders that already contain them (it appends new files).
"""
from __future__ import annotations

import os
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import common
from common import PHOTOS_RAW, COVERS_DIR, SUBJECTS

random.seed(7)
PALETTE = [
    (197, 122, 88), (122, 142, 110), (180, 160, 120), (110, 120, 140),
    (160, 110, 120), (130, 150, 150), (200, 180, 150), (90, 110, 95),
]


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Georgia.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_image(path: Path, label: str, w: int, h: int, color, when: datetime):
    img = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, w - 8, h - 8], outline=(255, 255, 255), width=4)
    f1, f2 = font(int(h * 0.10)), font(int(h * 0.05))
    d.text((w // 2, h // 2 - h * 0.06), label, fill=(255, 255, 255), font=f1, anchor="mm")
    d.text((w // 2, h // 2 + h * 0.07), when.strftime("%b %Y"), fill=(255, 255, 255), font=f2, anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=90)
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def main():
    common.register_heif()
    years = list(range(2015, 2027))
    counter = 0
    for year in years:
        # how many "events" this year
        for _ in range(random.randint(2, 4)):
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            when = datetime(year, month, day, 12, 0, 0)
            # pick a random subset of subjects present in this photo
            present = random.sample(SUBJECTS, random.randint(1, len(SUBJECTS)))
            counter += 1
            # landscape or portrait
            if random.random() < 0.6:
                w, h = 2400, 1600
            else:
                w, h = 1600, 2400
            color = random.choice(PALETTE)
            label = "+".join(p[0] for p in common.sorted_people(present))
            base_name = f"IMG_{year}{month:02d}{day:02d}_{counter:03d}.jpg"
            # identical bytes into every present subject's folder -> tests dedupe
            first_path = PHOTOS_RAW / present[0] / base_name
            make_image(first_path, label, w, h, color, when)
            for p in present[1:]:
                dst = PHOTOS_RAW / p / base_name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(first_path.read_bytes())
                os.utime(dst, (when.timestamp(), when.timestamp()))

    # cover portraits
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(SUBJECTS):
        make_image(COVERS_DIR / f"{s.lower()}.jpg", s, 800, 800,
                   PALETTE[i % len(PALETTE)], datetime(2020, 1, 1))

    print(f"Created placeholder photos for {len(years)} years (~{counter} events) "
          f"+ {len(SUBJECTS)} covers in photos_raw/.")


if __name__ == "__main__":
    main()
