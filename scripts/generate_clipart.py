#!/usr/bin/env python3
"""Generate colored scrapbook clipart PNGs for v2 via OpenAI Images API.

Usage:
    .venv/bin/python scripts/generate_clipart.py              # all themes
    .venv/bin/python scripts/generate_clipart.py baseball boat heart
    .venv/bin/python scripts/generate_clipart.py --list

Reads OPENAI_API_KEY from the environment, or from ~/.cursor/mcp.json.
Writes PNGs to versions/v2/assets/clipart/{theme}.png
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "versions" / "v2" / "assets" / "clipart"
MCP_JSON = Path.home() / ".cursor" / "mcp.json"

STYLE = (
    "Charming detailed scrapbook sticker illustration. Hand-painted mixed media look "
    "with watercolor washes and colored pencil linework. Rich but soft colors — warm "
    "coral, sky blue, sage green, golden yellow, cream highlights. Cute, nostalgic, "
    "gift-book aesthetic. Thick white die-cut sticker border with a subtle drop shadow. "
    "Highly detailed but not photorealistic. Isolated sticker on transparent background. "
    "No text, no watermark, no frame around the canvas."
)

THEMES: dict[str, str] = {
    "baseball": "a baseball with red stitching, small Cubs-style blue accent details",
    "boat": "a cheerful sailboat on gentle blue waves with a small flag",
    "heart": "a glossy red heart sticker with highlight shine and tiny sparkle accents",
    "travel": "a tropical palm tree with coconuts and warm sunset coral sky hints",
    "wedding": "two interlocked golden wedding rings with soft sparkle and ribbon bow",
    "dog": "an adorable golden retriever puppy face, friendly and expressive",
    "baby": "a pastel baby rattle with soft pink and blue details",
    "hockey": "a hockey stick and puck with Chicago Blackhawks red accent stripes",
    "city": "Chicago skyline silhouette with Willis Tower, warm dusk colors",
    "food": "a cozy dinner plate with fork and wine glass, restaurant date-night vibe",
    "home": "a cozy cottage house with chimney smoke and a small heart in the window",
    "music": "a vintage microphone and musical notes, festival concert energy",
    "mountain": "snow-capped mountain peaks with pine trees and a golden sun",
}


def load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    if MCP_JSON.is_file():
        cfg = json.loads(MCP_JSON.read_text())
        key = cfg.get("mcpServers", {}).get("openai-image", {}).get("env", {}).get(
            "OPENAI_API_KEY", ""
        ).strip()
        if key:
            return key
    raise SystemExit(
        "OPENAI_API_KEY not set. Add it to ~/.cursor/mcp.json or export in your shell."
    )


def generate_png(prompt: str, api_key: str, model: str = "gpt-image-1") -> bytes:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "quality": "high",
        "background": "transparent",
        "output_format": "png",
        "n": 1,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise SystemExit(f"OpenAI API error {e.code}: {err[:500]}") from e

    item = data["data"][0]
    if "b64_json" in item:
        return base64.b64decode(item["b64_json"])
    if "url" in item:
        with urllib.request.urlopen(item["url"], timeout=60) as r:
            return r.read()
    raise SystemExit("Unexpected OpenAI response format")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate v2 scrapbook clipart PNGs")
    parser.add_argument("themes", nargs="*", help="Theme names (default: all)")
    parser.add_argument("--list", action="store_true", help="List available themes")
    parser.add_argument("--model", default="gpt-image-1", help="OpenAI image model")
    args = parser.parse_args()

    if args.list:
        for name, desc in THEMES.items():
            print(f"  {name:10} — {desc}")
        return

    themes = args.themes or list(THEMES.keys())
    unknown = [t for t in themes if t not in THEMES]
    if unknown:
        raise SystemExit(f"Unknown themes: {', '.join(unknown)}. Use --list.")

    api_key = load_api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for theme in themes:
        out_path = OUT_DIR / f"{theme}.png"
        prompt = f"{STYLE} Subject: {THEMES[theme]}."
        print(f"Generating {theme}...", flush=True)
        img = generate_png(prompt, api_key, model=args.model)
        out_path.write_bytes(img)
        print(f"  wrote {out_path.relative_to(ROOT)} ({len(img) // 1024} KB)")


if __name__ == "__main__":
    main()
