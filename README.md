# The Story of Us 📖

A private, offline pipeline that turns your Photos "People" albums into a beautiful,
print-ready photo book — one chapter per year. See `PLAN.md` for the full design.

---

## Step 1 — Export your photos from the Photos app (do this first, ~15 min)

### A. Merge Zoa's two groups
In **Photos ▸ People**, you have two entries for Zoa: **"zo zo"** and **"young zo zo"**.
Select both → right-click → **Merge People** → name the result **Zoa**. (Optional but recommended
so Zoa's whole life is in one album.)

### B. Export each subject's People album
For each of the 6 — **Clay, Nicole, Connor, Hailey, Cooper, Zoa**:
1. Open **Photos ▸ People** and double-click the person/pet.
2. **Edit ▸ Select All** (or ⌘A).
3. **File ▸ Export ▸ Export Unmodified Original…**
   *(Important: "Unmodified Original" keeps the real capture date we need to sort by year.)*
4. Set **Subfolder Format: None**, then export into the matching folder:

```
photos_raw/Clay/
photos_raw/Nicole/
photos_raw/Connor/
photos_raw/Hailey/
photos_raw/Cooper/
photos_raw/Zoa/
```

### C. Add your album-cover screenshots
Drop the 6 People album-cover screenshots you took into:
```
photos_raw/covers/
```
Name them simply: `clay.jpg`, `nicole.jpg`, `connor.jpg`, `hailey.jpg`, `cooper.jpg`, `zoa.jpg`.

> Don't worry about duplicates — the same family photo will live in several albums.
> The ingest step automatically de-duplicates and remembers who's in each photo.

---

## Step 2 — Tell me when the export is done
Once your photos are in `photos_raw/`, let me know and I'll:
1. Run **ingest** (sort by year, de-dupe, build contact sheets, flag low-res shots).
2. **Curate** the best ~5–10 photos per year and draft `story/story.json` with captions
   and year intros.

## Step 3 — You personalize
Edit the version you're working on:
- **v1** (finished gift): `versions/v1/story.json`
- **v2** (redesign): `versions/v2/story.json`

Rewrite captions, year intros, and the dedication. Add the real stories, place names, and inside jokes. See `versions/README.md` for how versions work.

## Step 4 — Render
```bash
python scripts/render.py --version v1    # finished gift edition
python scripts/render.py --version v2    # experimental redesign
```

Each version produces its own PDFs:
- `versions/v1/build/Story_of_Us_home.pdf` — for printing at home
- `versions/v1/build/Story_of_Us_shop.pdf` — for a photo shop (bleed + crop marks)

## Step 5 — Print & bind
Print one test page first to check color/margins, then the full book. Bind into your binder/book.

---

## Running the pipeline (commands)

One-time setup (already done in this project, but to recreate it elsewhere):
```bash
bash scripts/setup.sh
```

Each time you add/replace photos or edit a version's story, rebuild:
```bash
bash scripts/build_book.sh v1    # or v2
```

Or run the steps individually:
```bash
source .venv/bin/activate
python scripts/ingest.py                       # sort, de-dupe, contact sheets, manifest
python scripts/draft_story.py --version v1     # first-draft story (won't overwrite edits)
python scripts/render.py --version v1          # build PDFs for that version
python scripts/render.py --version v1 --profile home   # just one profile
```

> **Starting over with real photos:** the project currently contains *placeholder*
> images so the pipeline could be tested. Before using your real photos, clear the
> placeholders: delete the contents of `photos_raw/<name>/` and `photos_raw/covers/`,
> add your real exports, then run `bash scripts/build_book.sh`. (You can regenerate
> placeholders anytime with `python scripts/make_placeholders.py`.)

### What each script does
- `scripts/ingest.py` — reads EXIF dates, de-duplicates across albums, buckets by
  year into `photos_processed/`, builds thumbnails + `build/contact_sheets/<year>.jpg`,
  and writes `build/manifest.json` with quality flags.
- `scripts/draft_story.py` — turns the manifest into a first-draft `story/story.json`
  (photo picks, layouts, placeholder captions). Safe: won't overwrite your edits
  unless you pass `--force`.
- `scripts/render.py` — merges `story/story.json` + templates into HTML and renders
  `build/Story_of_Us_home.pdf` and `build/Story_of_Us_shop.pdf`.

---

### Folders
- `photos_raw/` — **your exports** (never modified by scripts).
- `photos_processed/` — auto-generated, sorted by year (shared library).
- `versions/v1/`, `versions/v2/` — **independent book editions** (story, design, swap photos, PDFs).
- `story/` — legacy example + milestones; edit `versions/{v}/story.json` instead.
- `build/` — shared ingest output (manifest, thumbnails).
- Everything runs locally on your Mac. Nothing is uploaded.
# nicole_birthday_2026
