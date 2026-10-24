"""Filesystem layout helpers.

Every path is derived from the project root so the CLI works from any cwd.
"""
from __future__ import annotations

import os
from pathlib import Path

# src/stars_forecast/paths.py -> project root is two levels up
ROOT = Path(os.environ.get("STARS_ROOT", Path(__file__).resolve().parents[2]))

DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
CONFIG = ROOT / "config"
DOCS = ROOT / "docs"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"
QA = OUTPUTS / "qa"

for _d in (RAW, PROCESSED, FIGURES, TABLES, QA, DOCS, CONFIG):
    _d.mkdir(parents=True, exist_ok=True)


def rel(path: str | Path) -> str:
    """Path relative to the project root, for reports and manifests."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
