#!/usr/bin/env python3
"""DEV: screenshot each .page of versions/{v}/build/story_home.html into preview/."""
from __future__ import annotations

import argparse
import os

import common
from common import DEFAULT_VERSION, set_version

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(common.PLAYWRIGHT_DIR))
from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DEFAULT_VERSION)
    args = ap.parse_args()

    vp = set_version(args.version)
    out = vp.build / "preview"
    out.mkdir(parents=True, exist_ok=True)
    html = (vp.build / "story_home.html").resolve().as_uri()

    if not (vp.build / "story_home.html").exists():
        print(f"No {vp.build / 'story_home.html'} — run render.py --version {vp.name} first.")
        return

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1056, "height": 816}, device_scale_factor=2)
        pg.goto(html)
        n = pg.locator("section.page").count()
        for i in range(n):
            el = pg.locator("section.page").nth(i)
            el.screenshot(path=str(out / f"page_{i+1:02d}.png"))
        print(f"wrote {n} page previews to {out.relative_to(common.ROOT)}")
        b.close()


if __name__ == "__main__":
    main()
