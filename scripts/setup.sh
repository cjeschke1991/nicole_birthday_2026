#!/usr/bin/env bash
# One-time setup: create the Python environment and install dependencies,
# including the local Chromium used to render PDFs.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Creating virtual environment (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python packages"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "==> Installing Chromium (into ./.playwright)"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"
python -m playwright install chromium

echo "==> Done. Next: read README.md, export your photos, then run scripts/build_book.sh"
