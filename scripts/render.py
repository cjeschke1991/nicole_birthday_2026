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
import math
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
import common
from common import (
    ASSETS_DIR, DEFAULT_VERSION, PLAYWRIGHT_DIR, VersionPaths,
    list_versions, resolve_cover, resolve_photo, set_version,
)
from scatter_pages import load_caption_positions

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

# Scatter slot: left%, top%, width%, height%, rot°, clipart%, clipart%
# Loaded from scripts/scatter_recipes.json (synced from Figma via figma_to_scatter.py).
_SCATTER_RECIPES_DEFAULT: dict[str, list[tuple]] = {
    "scatter-a": [
        (5, 6, 18, 24, -6, 22, 4),
        (55, 4, 17, 24, 4, 68, 2),
        (8, 32, 19, 24, 3, 26, 30),
    ],
    "scatter-b": [
        (62, 6, 17, 24, 5, 76, 4),
        (36, 14, 18, 24, -3, 52, 10),
        (10, 32, 19, 24, 4, 28, 28),
    ],
    "scatter-c": [
        (66, 6, 17, 23, -4, 82, 4),
        (8, 10, 18, 24, 5, 24, 6),
        (40, 24, 18, 24, -2, 56, 18),
    ],
    "scatter-d": [
        (12, 6, 18, 24, 3, 28, 4),
        (48, 4, 17, 23, -5, 64, 2),
        (72, 16, 17, 23, 6, 86, 12),
    ],
}


def _load_scatter_recipes() -> dict[str, list[tuple]]:
    path = Path(__file__).parent / "scatter_recipes.json"
    if not path.is_file():
        return _SCATTER_RECIPES_DEFAULT
    raw = json.loads(path.read_text())
    return {name: [tuple(slot) for slot in slots] for name, slots in raw.items()}


SCATTER_RECIPES: dict[str, list[tuple]] = _load_scatter_recipes()

DECOR_POOL = ("washi-pink", "washi-blue", "star-burst", "heart-tiny")


def _load_scatter_decorations() -> dict:
    path = Path(__file__).parent / "scatter_decorations.json"
    if not path.is_file():
        return {"recipes": {}, "two_photo_extra": {}}
    raw = json.loads(path.read_text())
    return {
        "recipes": {k: v for k, v in raw.items() if k.startswith("scatter-")},
        "two_photo_extra": raw.get("two_photo_extra", {}),
    }


SCATTER_DECORATIONS = _load_scatter_decorations()


def _load_special_page_decorations() -> dict:
    path = Path(__file__).parent / "special_page_decorations.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


SPECIAL_PAGE_DECORATIONS = _load_special_page_decorations()

# Slot index of the leftmost photo per recipe (needs axis-aligned shadow matte).
LEFTMOST_SHADOW_SLOT: dict[str, int] = {"scatter-a": 0, "scatter-c": 1}

CAPTION_GAP = 8.0
CAPTION_MAX_W = 22.0  # percent of scatter-stage width
POLAROID_PAD = 4.5   # polaroid frame + shadow slack in stage %
OVERLAP_MARGIN = 3.0
CAPTION_BAND_TOP = 68.0  # captions prefer y at/above this line


def _estimate_caption_box(caption: str) -> tuple[float, float]:
    """Conservative caption bounding box in stage % — errs on the large side."""
    lines = max(1, (len(caption) + 13) // 14)
    width = CAPTION_MAX_W
    height = lines * 9.0 + 5.0
    return width, height


def _rect(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float, float, float]:
    return x1, y1, x2, y2


def _overlaps(a: tuple, b: tuple, margin: float = OVERLAP_MARGIN) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 + margin <= bx1 or bx2 + margin <= ax1 or
                ay2 + margin <= by1 or by2 + margin <= ay1)


def _rotated_photo_rect(
    left: float, top: float, w: float, h: float, rot_deg: float,
    pad: float = POLAROID_PAD,
) -> tuple[float, float, float, float]:
    """Axis-aligned bbox for a rotated polaroid frame."""
    cx, cy = left + w / 2, top + h / 2
    rad = math.radians(abs(rot_deg))
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    hw, hh = w / 2 + pad, h / 2 + pad
    xs: list[float] = []
    ys: list[float] = []
    for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        xs.append(cx + dx * cos_a - dy * sin_a)
        ys.append(cy + dx * sin_a + dy * cos_a)
    return _rect(min(xs), min(ys), max(xs), max(ys))


def _caption_fits(
    cl: float, ct: float, cap_w: float, cap_h: float,
    photo_rects: list[tuple], placed_captions: list[tuple],
) -> bool:
    if not _in_stage(cl, ct, cap_w, cap_h):
        return False
    cr = _rect(cl, ct, cl + cap_w, ct + cap_h)
    if any(_overlaps(cr, pr) for pr in photo_rects):
        return False
    if any(_overlaps(cr, c) for c in placed_captions):
        return False
    return True


def _caption_candidates(
    left: float, top: float, w: float, h: float, cap_w: float, cap_h: float,
) -> list[tuple[float, float]]:
    g = CAPTION_GAP
    return [
        (left, top + h + g),                         # below, left-aligned
        (left + w - cap_w, top + h + g),             # below, right-aligned
        (left + w + g, top),                         # right, top-aligned
        (left + w + g, top + h - cap_h),             # right, bottom-aligned
        (left - cap_w - g, top),                     # left, top-aligned
        (left - cap_w - g, top + h - cap_h),         # left, bottom-aligned
        (left, top - cap_h - g),                     # above, left-aligned
        (left + w - cap_w, top - cap_h - g),         # above, right-aligned
    ]


def _in_stage(x: float, y: float, w: float, h: float) -> bool:
    margin = 1.5
    return x >= margin and y >= margin and x + w <= 100 - margin and y + h <= 100 - margin


def _min_dist_to_photos(cr: tuple, photo_rects: list[tuple]) -> float:
    """Minimum edge distance from caption rect to nearest photo rect."""
    cx1, cy1, cx2, cy2 = cr
    best = 999.0
    for px1, py1, px2, py2 in photo_rects:
        dx = max(px1 - cx2, cx1 - px2, 0)
        dy = max(py1 - cy2, cy1 - py2, 0)
        best = min(best, (dx ** 2 + dy ** 2) ** 0.5)
    return best


def _perimeter_anchors(cap_w: float, cap_h: float) -> list[tuple[float, float]]:
    """Caption origins along page margins (top-left corner of each box)."""
    m = 2.0
    bottom = max(CAPTION_BAND_TOP, 96.0 - cap_h)
    right = max(m, 98.0 - cap_w)
    anchors: list[tuple[float, float]] = []
    for x in (m, 26.0, 50.0, 74.0):
        anchors.append((x, m))
        anchors.append((x, bottom))
    for y in (16.0, 38.0, 56.0):
        anchors.append((m, y))
        anchors.append((right, y))
    return anchors


def _grid_caption_pos(
    cap_w: float, cap_h: float,
    photo_rects: list[tuple], placed_captions: list[tuple],
) -> tuple[float, float] | None:
    """Scan caption band and side margins for open whitespace."""
    best: tuple[float, float] | None = None
    best_dist = -1.0
    y_start = int(CAPTION_BAND_TOP)
    for y in list(range(y_start, int(96 - cap_h), 2)) + list(range(2, y_start, 2)):
        for x in range(2, int(98 - cap_w), 2):
            if not _caption_fits(x, y, cap_w, cap_h, photo_rects, placed_captions):
                continue
            cr = _rect(x, y, x + cap_w, y + cap_h)
            dist = _min_dist_to_photos(cr, photo_rects)
            if dist > best_dist:
                best_dist = dist
                best = (x, y)
    return best


def _stack_caption_pos(
    cap_w: float, cap_h: float,
    photo_rects: list[tuple], placed_captions: list[tuple],
) -> tuple[float, float]:
    """Last resort: stack in left margin, guaranteed collision-checked."""
    for x in (2.0, 26.0, 50.0, 74.0):
        for y in range(int(CAPTION_BAND_TOP), int(96 - cap_h), 2):
            if _caption_fits(x, y, cap_w, cap_h, photo_rects, placed_captions):
                return x, y
    for x in (2.0, 74.0):
        for y in range(2, int(CAPTION_BAND_TOP), 2):
            if _caption_fits(x, y, cap_w, cap_h, photo_rects, placed_captions):
                return x, y
    return 2.0, CAPTION_BAND_TOP


def scatter_caption_pos(
    left: float, top: float, w: float, h: float,
    caption: str,
    photo_rects: list[tuple],
    placed_captions: list[tuple],
) -> tuple[float, float]:
    """Pick caption position that clears every photo on the page."""
    cap_w, cap_h = _estimate_caption_box(caption)
    px, py = left + w / 2, top + h / 2

    for cl, ct in _caption_candidates(left, top, w, h, cap_w, cap_h):
        if _caption_fits(cl, ct, cap_w, cap_h, photo_rects, placed_captions):
            return cl, ct

    anchors = _perimeter_anchors(cap_w, cap_h)
    anchors.sort(key=lambda a: (a[0] - px) ** 2 + (a[1] - py) ** 2)
    for cl, ct in anchors:
        if _caption_fits(cl, ct, cap_w, cap_h, photo_rects, placed_captions):
            return cl, ct

    pos = _grid_caption_pos(cap_w, cap_h, photo_rects, placed_captions)
    if pos:
        return pos
    return _stack_caption_pos(cap_w, cap_h, photo_rects, placed_captions)


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


def clipart_uri(theme: str, vp: VersionPaths) -> str | None:
    clip_dir = vp.root / "assets" / "clipart"
    for ext in (".png", ".svg"):
        path = clip_dir / f"{theme}{ext}"
        if path.exists():
            return to_uri(path)
    fallback = clip_dir / "heart.png"
    if not fallback.exists():
        fallback = clip_dir / "heart.svg"
    if fallback.exists():
        return to_uri(fallback)
    return None


def decor_uri(kind: str, vp: VersionPaths) -> str | None:
    path = vp.root / "assets" / "decor" / f"{kind}.png"
    if path.exists():
        return to_uri(path)
    return None


def decor_kind_for(page_id: str, slot_idx: int, hint: str = "auto") -> str:
    if hint and hint != "auto" and hint in DECOR_POOL:
        return hint
    seed = sum(ord(c) for c in page_id) + slot_idx * 7
    return DECOR_POOL[seed % len(DECOR_POOL)]


def build_decor_items(
    slots: list[dict], page_id: str, vp: VersionPaths, *, z_base: int = 3,
) -> list[dict]:
    out: list[dict] = []
    for idx, slot in enumerate(slots):
        kind = decor_kind_for(page_id, idx, slot.get("kind", "auto"))
        uri = decor_uri(kind, vp)
        if not uri:
            continue
        out.append({
            "img": uri,
            "kind": kind,
            "left": f"{slot['left']}%",
            "top": f"{slot['top']}%",
            "rot": slot.get("rot", 0),
            "z": z_base + idx,
        })
    return out


def scatter_decorations(recipe: str, page_id: str, photo_count: int, vp: VersionPaths) -> list[dict]:
    slots = list(SCATTER_DECORATIONS["recipes"].get(recipe, []))
    if photo_count < 3:
        slots.extend(SCATTER_DECORATIONS["two_photo_extra"].get(recipe, []))
    return build_decor_items(slots, page_id, vp)


def special_page_embellishments(page_key: str, page_id: str, vp: VersionPaths) -> dict | None:
    cfg = SPECIAL_PAGE_DECORATIONS.get(page_key)
    if not cfg:
        return None
    corner = decor_uri("corner-flourish", vp) if cfg.get("corners") else None
    decorations = build_decor_items(cfg.get("slots", []), page_id, vp)
    if not corner and not decorations:
        return None
    return {"corner_flourish": corner, "decorations": decorations}


def maybe_embellishments(
    page_key: str, page_id: str, story: dict, vp: VersionPaths,
) -> dict | None:
    if story.get("book", {}).get("edition") != "scrapbook":
        return None
    return special_page_embellishments(page_key, page_id, vp)


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
            "embellishments": maybe_embellishments("cover", "cover", story, vp),
        })

    if book.get("dedication"):
        ded = book["dedication"]
        body, signoff = ded, ""
        if "—" in ded:
            parts = ded.rsplit("—", 1)
            body, signoff = parts[0].strip(), "— " + parts[1].strip()
        pages.append({
            "type": "dedication",
            "body": body,
            "signoff": signoff,
            "embellishments": maybe_embellishments("dedication", "dedication", story, vp),
        })

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
            "embellishments": maybe_embellishments("cast", "cast", story, vp),
        })

    for yr in story.get("years", []):
        photos = yr.get("photos", [])
        year = yr["year"]
        pages.append({
            "type": "year-divider",
            "year": year,
            "title": yr.get("title", ""),
            "intro": yr.get("intro", ""),
            "accent_img": photo_uri(photos[0]["file"], vp) if photos else None,
            "embellishments": maybe_embellishments(
                "year-divider", f"year-{year}", story, vp,
            ),
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

        elif layout.startswith("scatter"):
            recipe = layout
            group = []
            while i < n and photos[i].get("layout") == recipe and len(group) < 3:
                group.append(photos[i]); i += 1
            if group:
                year = int(yr["year"])
                seq = sum(1 for pg in out if pg.get("layout", "").startswith("scatter")) + 1
                page_id = f"{year}-{seq:02d}"
                out.append(make_scatter(yr, group, recipe, vp, page_id=page_id))

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


def make_scatter(yr: dict, group: list[dict], recipe: str, vp: VersionPaths,
                 page_id: str = "") -> dict:
    slots = SCATTER_RECIPES.get(recipe, SCATTER_RECIPES["scatter-a"])
    photo_rects = [_rotated_photo_rect(*slots[i][:5]) for i in range(len(group))]
    placed_captions: list[tuple] = []
    cap_overrides = load_caption_positions(vp.name)
    items = []
    for idx, g in enumerate(group):
        slot = slots[idx]
        left, top, w, h, rot, cil, cit = slot[:7]
        recipe_cap = slot[7:9] if len(slot) >= 9 else None
        caption = g.get("caption", "")
        rel = g["file"]
        if caption and recipe_cap:
            cl, ct = recipe_cap[0], recipe_cap[1]
            cap_w, cap_h = _estimate_caption_box(caption)
            placed_captions.append(_rect(cl, ct, cl + cap_w, ct + cap_h))
        elif caption and rel in cap_overrides:
            cl = cap_overrides[rel]["left"]
            ct = cap_overrides[rel]["top"]
            cap_w, cap_h = _estimate_caption_box(caption)
            placed_captions.append(_rect(cl, ct, cl + cap_w, ct + cap_h))
        elif caption:
            cl, ct = scatter_caption_pos(
                left, top, w, h, caption, photo_rects, placed_captions,
            )
            cap_w, cap_h = _estimate_caption_box(caption)
            placed_captions.append(_rect(cl, ct, cl + cap_w, ct + cap_h))
        else:
            cl, ct = 0.0, 0.0
        theme = g.get("theme", "heart")
        items.append({
            "img": photo_uri(g["file"], vp),
            "caption": g.get("caption", ""),
            "date": fmt_date(g.get("date", "")),
            "left": f"{left}%", "top": f"{top}%",
            "width": f"{w}%", "height": f"{h}%",
            "rot": rot,
            "cap_left": f"{cl}%", "cap_top": f"{ct}%",
            "clip_left": f"{cil}%", "clip_top": f"{cit}%",
            "clipart": clipart_uri(theme, vp),
            "z": idx + 10,
            "edge_shadow": recipe in LEFTMOST_SHADOW_SLOT and idx == LEFTMOST_SHADOW_SLOT[recipe],
        })
    return {
        "type": "content",
        "layout": recipe,
        "page_id": page_id,
        "year_tag": str(yr.get("year", "")),
        "cells": items,
        "decorations": scatter_decorations(recipe, page_id, len(group), vp),
    }


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
        page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.evaluate("() => document.fonts.ready")
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
