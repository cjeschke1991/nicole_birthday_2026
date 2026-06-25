#!/usr/bin/env python3
"""
Render story/story.json into print-ready PDFs (warm editorial, 11x8.5 landscape).

Produces, from the SAME source:
  build/Story_of_Us_home.pdf   (borderless-friendly, no bleed)   [--profile home]
  build/Story_of_Us_shop.pdf   (0.125in bleed + crop marks)      [--profile shop]

Usage:
    python scripts/render.py                 # both profiles
    python scripts/render.py --profile home  # just one
    python scripts/render.py --html-only     # write build/story_<profile>.html, skip PDF

NOTE: PDF rendering launches headless Chromium and must run OUTSIDE the sandbox.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import common
from common import (
    ASSETS_DIR, BUILD_DIR, COVERS_DIR, MANIFEST_JSON, PHOTOS_PROCESSED,
    PHOTOS_RAW, PLAYWRIGHT_DIR, STORY_JSON, TEMPLATES_DIR, THUMBS_DIR,
)

PROFILES = {
    "home": {
        "name": "home",
        "page_css": (
            "@page { size: 11in 8.5in; margin: 0; }\n"
            ":root { --bleed: 0in; --paper-w: 11in; --paper-h: 8.5in; }"
        ),
    },
    "shop": {
        "name": "shop",
        "page_css": (
            "@page { size: 11.25in 8.75in; margin: 0; }\n"
            ":root { --bleed: 0.125in; --paper-w: 11.25in; --paper-h: 8.75in; }"
        ),
    },
}

# Collage slot presets: (left%, top%, width%, height%, rotationDeg)
COLLAGE_SLOTS = {
    3: [(5, 8, 46, 58, -2.5), (56, 10, 38, 40, 2.5), (50, 54, 44, 40, -1.5)],
    4: [(4, 6, 44, 46, -2.5), (54, 8, 42, 40, 2.0),
        (8, 52, 40, 42, 1.5), (54, 52, 42, 42, -2.0)],
    5: [(3, 5, 40, 44, -3.0), (47, 4, 30, 34, 2.0), (70, 18, 27, 36, -1.0),
        (6, 52, 40, 42, 2.5), (50, 50, 46, 44, -1.5)],
}

ROLE_HINTS = {
    "Clay": "Dad", "Nicole": "Mom", "Connor": "Son", "Hailey": "Daughter",
    "Cooper": "Our Dog", "Zoa": "Our Dog",
}


def to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def resolve_photo(rel: str) -> Path:
    """Prefer the full-res materialized JPEG; fall back to the ingest thumbnail
    (so a proof can render before materialize.py has run)."""
    full = PHOTOS_PROCESSED / rel
    if full.exists():
        return full
    thumb = THUMBS_DIR / rel
    if thumb.exists():
        return thumb
    return full  # report the expected path if neither exists


def resolve_cover(rel: str) -> Path:
    """Cover paths like 'covers/clay.jpg' are relative to photos_raw/."""
    return PHOTOS_RAW / rel


def fmt_date(iso: str) -> str:
    """'2015-06-14' -> 'June 2015'. Pass through anything unexpected."""
    try:
        from datetime import datetime
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %Y")
    except Exception:
        return iso or ""


def build_pages(story: dict) -> list[dict]:
    pages: list[dict] = []
    book = story.get("book", {})

    # Cover background: explicit book.cover, else first photo of first year.
    cover_rel = book.get("cover")
    if not cover_rel:
        for y in story.get("years", []):
            if y.get("photos"):
                cover_rel = y["photos"][0]["file"]
                break
    if cover_rel:
        pages.append({
            "type": "cover",
            "title": book.get("title", "The Story of Us"),
            "subtitle": book.get("subtitle", ""),
            "kicker": book.get("kicker", ""),
            "bg": to_uri(resolve_photo(cover_rel)),
        })

    # Dedication
    if book.get("dedication"):
        ded = book["dedication"]
        body, signoff = ded, ""
        if "—" in ded:  # split trailing "— Clay"
            parts = ded.rsplit("—", 1)
            body, signoff = parts[0].strip(), "— " + parts[1].strip()
        pages.append({"type": "dedication", "body": body, "signoff": signoff})

    # Cast
    cast = book.get("cast", [])
    if cast:
        members = []
        for m in cast:
            members.append({
                "name": m["name"],
                "role": m.get("role", ROLE_HINTS.get(m["name"], "")),
                "img": to_uri(resolve_cover(m["cover"])),
            })
        pages.append({
            "type": "cast",
            "title": book.get("cast_title", "Our Little Family"),
            "lede": book.get("cast_lede", "The people (and pups) who make up our story."),
            "members": members,
        })

    # Years
    for yr in story.get("years", []):
        photos = yr.get("photos", [])
        pages.append({
            "type": "year-divider",
            "year": yr["year"],
            "title": yr.get("title", ""),
            "intro": yr.get("intro", ""),
            "accent_img": to_uri(resolve_photo(photos[0]["file"])) if photos else None,
        })
        pages.extend(layout_year(yr, photos))

    return pages


def layout_year(yr: dict, photos: list[dict]) -> list[dict]:
    """Turn a year's photos into content pages, honoring per-photo 'layout' hints.

    Grouping rules:
      - 'hero'  -> its own page
      - 'full'  -> its own full-bleed page
      - 'pair'  -> consecutive 'pair' photos grouped 2 per page
      - 'collage' -> consecutive 'collage' photos grouped 3-5 per page
    """
    out: list[dict] = []
    i = 0
    n = len(photos)
    while i < n:
        p = photos[i]
        layout = p.get("layout", "hero")

        if layout == "hero":
            out.append({"type": "content", "layout": "hero",
                        "img": to_uri(resolve_photo(p["file"])),
                        "caption": p.get("caption", ""), "date": fmt_date(p.get("date", ""))})
            i += 1

        elif layout == "full":
            out.append({"type": "content", "layout": "full",
                        "img": to_uri(resolve_photo(p["file"])),
                        "caption": p.get("caption", ""), "date": fmt_date(p.get("date", ""))})
            i += 1

        elif layout == "pair":
            group = []
            while i < n and photos[i].get("layout") == "pair" and len(group) < 2:
                group.append(photos[i]); i += 1
            cells = [{"img": to_uri(resolve_photo(g["file"])), "caption": g.get("caption", "")}
                     for g in group]
            out.append({"type": "content", "layout": "pair", "cells": cells})

        elif layout == "collage":
            group = []
            while i < n and photos[i].get("layout") == "collage" and len(group) < 5:
                group.append(photos[i]); i += 1
            out.append(make_collage(yr, group))

        else:
            out.append({"type": "content", "layout": "hero",
                        "img": to_uri(resolve_photo(p["file"])),
                        "caption": p.get("caption", ""), "date": fmt_date(p.get("date", ""))})
            i += 1
    return out


def make_collage(yr: dict, group: list[dict]) -> dict:
    count = max(3, min(5, len(group)))
    slots = COLLAGE_SLOTS[count]
    shots = []
    for idx, g in enumerate(group[:count]):
        left, top, w, h, rot = slots[idx]
        shots.append({
            "img": to_uri(resolve_photo(g["file"])),
            "caption": g.get("caption", ""),
            "left": f"{left}%", "top": f"{top}%",
            "width": f"{w}%", "height": f"{h}%",
            "rot": rot, "z": idx + 1,
        })
    return {"type": "content", "layout": "collage",
            "year_tag": str(yr.get("year", "")), "shots": shots}


def render_html(story: dict, profile: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template("book.html.j2")
    book_css = (ASSETS_DIR / "css" / "book.css").read_text()
    flourish = (ASSETS_DIR / "svg" / "flourish.svg").read_text()
    pages = build_pages(story)
    return tmpl.render(
        book=story.get("book", {}),
        pages=pages,
        profile=profile,
        page_css=profile["page_css"],
        book_css=book_css,
        flourish_svg=flourish,
    )


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    import os
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PLAYWRIGHT_DIR))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.emulate_media(media="print")
        page.pdf(path=str(pdf_path), prefer_css_page_size=True,
                 print_background=True)
        browser.close()


def load_story() -> dict:
    if not STORY_JSON.exists():
        print(f"No {STORY_JSON.relative_to(common.ROOT)} found. Run "
              f"scripts/draft_story.py first (or copy story/story.example.json).")
        sys.exit(1)
    return json.loads(STORY_JSON.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["home", "shop", "both"], default="both")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()

    common.ensure_dirs()
    story = load_story()
    profiles = ["home", "shop"] if args.profile == "both" else [args.profile]

    for name in profiles:
        profile = PROFILES[name]
        html = render_html(story, profile)
        html_path = BUILD_DIR / f"story_{name}.html"
        html_path.write_text(html)
        print(f"  wrote {html_path.relative_to(common.ROOT)}")
        if not args.html_only:
            pdf_path = BUILD_DIR / f"Story_of_Us_{name}.pdf"
            html_to_pdf(html_path, pdf_path)
            print(f"  wrote {pdf_path.relative_to(common.ROOT)}")

    print("Done.")


if __name__ == "__main__":
    main()
