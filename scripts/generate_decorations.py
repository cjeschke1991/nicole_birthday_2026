#!/usr/bin/env python3
"""Generate micro-decoration PNGs for v2 scatter pages via OpenAI Images API.

Usage:
    .venv/bin/python scripts/generate_decorations.py
    .venv/bin/python scripts/generate_decorations.py washi-pink star-burst
    .venv/bin/python scripts/generate_decorations.py --list

Writes PNGs to versions/v2/assets/decor/{name}.png
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "versions" / "v2" / "assets" / "decor"
MCP_JSON = Path.home() / ".cursor" / "mcp.json"

STYLE = (
    "Delicate scrapbook micro-decoration sticker. Hand-painted watercolor and colored "
    "pencil. Soft pastel palette — blush pink, sky blue, cream, golden yellow. "
    "Small scale, meant to tuck into page margins. Isolated on fully transparent "
    "background. No text, no watermark, no canvas border, no drop shadow baked in."
)

DECORATIONS: dict[str, str] = {
    "washi-pink": (
        "a single short strip of pink floral washi tape, slightly wrinkled texture, "
        "soft torn edges, angled diagonally, about 3 inches long if printed"
    ),
    "washi-blue": (
        "a single short strip of soft sky-blue washi tape with tiny white polka dots, "
        "torn edges, angled diagonally, about 3 inches long if printed"
    ),
    "star-burst": (
        "a small golden four-point star burst sparkle doodle, simple and cheerful, "
        "roughly 1 inch across if printed"
    ),
    "heart-tiny": (
        "a tiny glossy pink heart doodle sticker, minimal cute hand-drawn look, "
        "roughly 0.75 inch across if printed"
    ),
    "corner-flourish": (
        "a subtle scrapbook corner flourish ornament for the top-left corner of a page, "
        "delicate watercolor vines and small leaves with soft coral and sage green tones, "
        "designed to sit in the margin, roughly 1.5 inches square if printed"
    ),
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
    parser = argparse.ArgumentParser(description="Generate v2 micro-decoration PNGs")
    parser.add_argument("names", nargs="*", help="Decoration names (default: all)")
    parser.add_argument("--list", action="store_true", help="List available decorations")
    parser.add_argument("--model", default="gpt-image-1", help="OpenAI image model")
    args = parser.parse_args()

    if args.list:
        for name, desc in DECORATIONS.items():
            print(f"  {name:12} — {desc[:72]}…")
        return

    names = args.names or list(DECORATIONS.keys())
    unknown = [n for n in names if n not in DECORATIONS]
    if unknown:
        raise SystemExit(f"Unknown decorations: {', '.join(unknown)}. Use --list.")

    api_key = load_api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name in names:
        out_path = OUT_DIR / f"{name}.png"
        prompt = f"{STYLE} Subject: {DECORATIONS[name]}."
        print(f"Generating {name}...", flush=True)
        img = generate_png(prompt, api_key, model=args.model)
        out_path.write_bytes(img)
        print(f"  wrote {out_path.relative_to(ROOT)} ({len(img) // 1024} KB)")


if __name__ == "__main__":
    main()
