#!/usr/bin/env python3
"""
Render versions/{v}/story.json into print-ready PDFs (warm editorial, 11x8.5 landscape).

Produces, from the SAME source:
  versions/{v}/build/Story_of_Us_home.pdf   (borderless-friendly, no bleed)
  versions/{v}/build/Story_of_Us_shop.pdf   (0.125in bleed + crop marks)

Usage:
    python scripts/render.py                      # default version (v1), both profiles
    python scripts/render.py --version v2
    python scripts/render.py --profile home
    python scripts/render.py --html-only

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
    ASSETS_DIR, DEFAULT_VERSION, PLAYWRIGHT_DIR, VersionPaths,
    list_versions, resolve_cover, resolve_photo, set_version,
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

_missing_photos: list[str] = []


def to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def photo_uri(rel: str, vp: VersionPaths) -> str:
    path = resolve_photo(rel, vp)
    if not path.exists():
        _missing_photos.append(rel)
    return to_uri(path)


def cover_uri(rel: str, vp: VersionPaths) -> str:
    path = resolve_cover(rel, vp)
    if not path.exists():
        _missing_photos.append(rel)
    return to_uri(path)


def fmt_date(iso: str) -> str:
    try:
        from datetime import datetime
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %Y")
    except Exception:
        return iso or ""


def build_pages(story: dict, vp: VersionPaths) -> list[dict]:
    pages: list[dict] = []
    book = story.get("book", {})

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
            "bg": photo_uri(cover_rel, vp),
        })

    if book.get("dedication"):
        ded = book["dedication"]
        body, signoff = ded, ""
        if "—" in ded:
            parts = ded.rsplit("—", 1)
            body, signoff = parts[0].strip(), "— " + parts[1].strip()
        pages.append({"type": "dedication", "body": body, "signoff": signoff})

    cast = book.get("cast", [])
    if cast:
        members = []
        for m in cast:
            members.append({
                "name": m["name"],
                "role": m.get("role", ROLE_HINTS.get(m["name"], "")),
                "img": cover_uri(m["cover"], vp),
            })
        pages.append({
            "type": "cast",
            "title": book.get("cast_title", "Our Little Family"),
            "lede": book.get("cast_lede", "The people (and pups) who make up our story."),
            "members": members,
        })

    for yr in story.get("years", []):
        photos = yr.get("photos", [])
        pages.append({
            "type": "year-divider",
            "year": yr["year"],
            "title": yr.get("title", ""),
            "intro": yr.get("intro", ""),
            "accent_img": photo_uri(photos[0]["file"], vp) if photos else None,
        })
        pages.extend(layout_year(yr, photos, vp))

    return pages


def layout_year(yr: dict, photos: list[dict], vp: VersionPaths) -> list[dict]:
    out: list[dict] = []
    i = 0
    n = len(photos)
    while i < n:
        p = photos[i]
        layout = p.get("layout", "hero")

        if layout == "hero":
            out.append({"type": "content", "layout": "hero",
                        "img": photo_uri(p["file"], vp),
                        "caption": p.get("caption", ""), "date": fmt_date(p.get("date", ""))})
            i += 1

        elif layout == "full":
            out.append({"type": "content", "layout": "full",
                        "img": photo_uri(p["file"], vp),
                        "caption": p.get("caption", ""), "date": fmt_date(p.get("date", ""))})
            i += 1

        elif layout == "pair":
            group = []
            while i < n and photos[i].get("layout") == "pair" and len(group) < 2:
                group.append(photos[i]); i += 1
            cells = [{"img": photo_uri(g["file"], vp), "caption": g.get("caption", "")}
                     for g in group]
            out.append({"type": "content", "layout": "pair", "cells": cells})

        elif layout == "collage":
            group = []
            while i < n and photos[i].get("layout") == "collage" and len(group) < 5:
                group.append(photos[i]); i += 1
            out.append(make_collage(yr, group, vp))

        else:
            out.append({"type": "content", "layout": "hero",
                        "img": photo_uri(p["file"], vp),
                        "caption": p.get("caption", ""), "date": fmt_date(p.get("date", ""))})
            i += 1
    return out


def make_collage(yr: dict, group: list[dict], vp: VersionPaths) -> dict:
    count = max(3, min(5, len(group)))
    slots = COLLAGE_SLOTS[count]
    shots = []
    for idx, g in enumerate(group[:count]):
        left, top, w, h, rot = slots[idx]
        shots.append({
            "img": photo_uri(g["file"], vp),
            "caption": g.get("caption", ""),
            "left": f"{left}%", "top": f"{top}%",
            "width": f"{w}%", "height": f"{h}%",
            "rot": rot, "z": idx + 1,
        })
    return {"type": "content", "layout": "collage",
            "year_tag": str(yr.get("year", "")), "shots": shots}


def template_dirs(vp: VersionPaths) -> list[str]:
    dirs = []
    if vp.templates.is_dir():
        dirs.append(str(vp.templates))
    dirs.append(str(common.TEMPLATES_DIR))
    return dirs


def render_html(story: dict, profile: dict, vp: VersionPaths) -> str:
    env = Environment(
        loader=FileSystemLoader(template_dirs(vp)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template("book.html.j2")
    css_path = vp.css if vp.css.exists() else ASSETS_DIR / "css" / "book.css"
    book_css = css_path.read_text()
    flourish = (ASSETS_DIR / "svg" / "flourish.svg").read_text()
    pages = build_pages(story, vp)
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


def load_story(vp: VersionPaths) -> dict:
    if not vp.story_json.exists():
        print(f"No {vp.story_json.relative_to(common.ROOT)} found.")
        sys.exit(1)
    return json.loads(vp.story_json.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DEFAULT_VERSION,
                    help=f"Book version folder (default: {DEFAULT_VERSION})")
    ap.add_argument("--profile", choices=["home", "shop", "both"], default="both")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()

    try:
        vp = set_version(args.version)
    except FileNotFoundError as e:
        print(e)
        if list_versions():
            print(f"Available: {', '.join(list_versions())}")
        sys.exit(1)

    common.ensure_dirs(vp.name)
    story = load_story(vp)
    profiles = ["home", "shop"] if args.profile == "both" else [args.profile]

    global _missing_photos
    _missing_photos = []

    for name in profiles:
        profile = PROFILES[name]
        html = render_html(story, profile, vp)
        html_path = vp.build / f"story_{name}.html"
        html_path.write_text(html)
        print(f"  wrote {html_path.relative_to(common.ROOT)}")
        if not args.html_only:
            pdf_path = vp.build / f"Story_of_Us_{name}.pdf"
            html_to_pdf(html_path, pdf_path)
            print(f"  wrote {pdf_path.relative_to(common.ROOT)}")

    if _missing_photos:
        unique = sorted(set(_missing_photos))
        print(f"\n  WARNING [{vp.name}]: {len(unique)} missing photo(s):")
        for rel in unique:
            print(f"    - {rel}")

    print(f"Done ({vp.name}).")


if __name__ == "__main__":
    main()
