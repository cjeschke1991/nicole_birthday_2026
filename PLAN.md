# The Story of Us — Implementation Plan

A local, private pipeline that turns iCloud/Photos "People" albums into a print-ready,
warm-editorial photo book PDF (8.5×11" landscape), one chapter per year (~2015→2026).

## Subjects (6)
Clay, Nicole, Connor, Hailey, Cooper (dog), Zoa (dog — merge "zo zo" + "young zo zo" first).

## Key decisions (from brainstorming)
- **Deliverable:** print-it-yourself, print-ready PDF → bound at home into a book/binder.
- **Source:** macOS Photos "People" albums, exported as unmodified originals.
- **Story text:** AI drafts captions + year intros; Clay personalizes in `story.json`.
- **Format:** 8.5×11" **landscape**.
- **Style:** **warm & editorial** (elegant serif, ivory paper tone, single muted accent —
  terracotta or sage, switchable via one CSS variable).
- **Scope:** ~5–10 photos/year (tight & curated).
- **Print targets:** BOTH home (borderless-friendly) AND photo shop (bleed + crop marks).

## Toolchain (adapted to this Mac — Node not installed, Python 3.9 + Homebrew present)
- **Python 3** for the whole pipeline.
- **Pillow** — EXIF dates, thumbnails, contact sheets, resolution checks.
- **ImageHash** (or content hash) — de-duplicate the same photo across people's albums.
- **Jinja2** — templating (`story.json` + templates → HTML).
- **Playwright (Chromium)** — render HTML → pixel-perfect PDF (same engine the design assumes).
- All fonts/SVGs bundled locally → identical, repeatable output, fully offline.

## Directory layout
```
nicole_bday_2026/
├── photos_raw/        # you export here (NEVER modified by scripts)
│   ├── Clay/ Nicole/ Connor/ Hailey/ Cooper/ Zoa/
│   └── covers/        # your People album-cover screenshots
├── photos_processed/  # auto: deduped, date-sorted, bucketed by year
│   └── 2015/ … 2026/
├── story/             # story.json lives here (the editable source of truth)
├── templates/         # HTML/CSS page designs (warm editorial)
├── assets/            # fonts/, svg/ (decorative graphics)
├── build/             # generated HTML + final PDFs + thumbnails/contact sheets
└── scripts/           # ingest.py, render.py, helpers
```

## Pipeline / data flow
1. **Export** (you, ~15 min): merge Zoa's two groups; for each subject
   open the People album → Select All → File ▸ Export ▸ **Export Unmodified Original**
   → drop into `photos_raw/<name>/`. Screenshots of album covers → `photos_raw/covers/`.
2. **Ingest** (`scripts/ingest.py`): read EXIF capture date (fallback file date),
   content-hash de-dupe (record which people each unique photo belongs to),
   bucket into `photos_processed/<year>/`, generate thumbnails + per-year contact sheets,
   flag low-res/blurry/screenshot candidates.
3. **Curate** (AI + you): review contact sheets, pick ~5–10/year, draft `story/story.json`
   (photo picks, captions, year titles/intros, layout hints).
4. **Personalize** (you): edit captions/intros/dedication in `story.json`.
5. **Render** (`scripts/render.py`): Jinja2 → `build/story.html` → Playwright → PDFs.
6. **Print & bind**: print at home and/or hand shop PDF to a photo shop.

## `story.json` schema (single source of truth)
```json
{
  "book": {
    "title": "The Story of Us",
    "subtitle": "Clay & Nicole",
    "dedication": "For Nicole, on your birthday…",
    "accent": "terracotta",
    "cast": [
      {"name": "Clay",   "cover": "covers/clay.jpg"},
      {"name": "Nicole", "cover": "covers/nicole.jpg"},
      {"name": "Connor", "cover": "covers/connor.jpg"},
      {"name": "Hailey", "cover": "covers/hailey.jpg"},
      {"name": "Cooper", "cover": "covers/cooper.jpg"},
      {"name": "Zoa",    "cover": "covers/zoa.jpg"}
    ]
  },
  "years": [
    {
      "year": 2015,
      "title": "Where It Began",
      "intro": "The year everything started…",
      "photos": [
        {"file": "2015/IMG_2031.jpg", "caption": "Our first trip", "people": ["Clay","Nicole"], "layout": "hero", "date": "2015-06-14"}
      ]
    }
  ]
}
```

## Page types / layout kit
- **cover** — title, subtitle, hero photo.
- **dedication** — note to Nicole + flourish.
- **cast** — 6 album-cover portraits in circles with names.
- **year-divider** — big numeral, title, intro paragraph, accent photo.
- **content layouts** (per-photo `layout` hint): `hero`, `pair`, `collage` (3–5, non-uniform
  scatter w/ slight rotation), `full-bleed`.

## Design system
- **Type:** serif display (e.g. Cormorant / Playfair Display) + quiet sans for labels.
- **Palette:** ivory paper, soft charcoal text, one accent (terracotta | sage) via CSS var.
- **Decoration:** subtle SVG botanical line-art, year-connecting timeline thread,
  pawprint icon for dog moments, heart for milestones.

## Print correctness
- Target **300 DPI**; ingest warns when a photo is placed larger than its resolution allows.
- Safe inner margin so faces/captions never trim at the binding edge.
- **Two export profiles** from the same `story.json`:
  - `Story_of_Us_home.pdf` — borderless-friendly, safe margins, single-sided option.
  - `Story_of_Us_shop.pdf` — adds 0.125" bleed + crop marks; full-bleed runs to trim.
- sRGB color; spec note for the shop.

## Build steps (implementation order)
1. Python venv + install deps; `playwright install chromium`.
2. `scripts/ingest.py` (+ resolution/quality flags, contact sheets).
3. `templates/` warm-editorial HTML/CSS + layout kit; bundle fonts/SVGs.
4. `scripts/render.py` with `--profile home|shop`.
5. Generate a sample/proof PDF with placeholder images to validate design.
6. After Clay exports → ingest → AI curates `story.json` → personalize → render.
7. Proof pass + single-page print test (home and shop) → full run.

## Validation
- Low-res guard before printing.
- Proof PDF reviewed per year (spacing, cropping, caption overflow).
- One-page home print test + optional one-page shop test before full run.

## Safety / repeatability
- `photos_raw/` and Photos originals never modified.
- Everything in `build/` regenerable; `story/story.json` is the file to back up.
- Fully offline; no uploads.

## Stretch (optional, later)
- Printed timeline endpaper; QR to a private video montage; hidden "things I love about you" page.
