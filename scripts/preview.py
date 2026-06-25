#!/usr/bin/env python3
"""DEV: screenshot each .page of build/story_home.html into build/preview/."""
from __future__ import annotations
import os
from pathlib import Path
import common
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(common.PLAYWRIGHT_DIR))
from playwright.sync_api import sync_playwright

OUT = common.BUILD_DIR / "preview"
OUT.mkdir(parents=True, exist_ok=True)
html = (common.BUILD_DIR / "story_home.html").resolve().as_uri()

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1056, "height": 816}, device_scale_factor=2)
    pg.goto(html)
    n = pg.locator("section.page").count()
    for i in range(n):
        el = pg.locator("section.page").nth(i)
        el.screenshot(path=str(OUT / f"page_{i+1:02d}.png"))
    print(f"wrote {n} page previews to {OUT.relative_to(common.ROOT)}")
    b.close()
