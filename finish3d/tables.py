"""The "smart table" layer (handoff §4): knowledge as data, not code.

``footprint_models.csv`` maps a footprint name/glob to a model source and a
known-good seat transform. A table hit short-circuits the resolution chain and
carries that verified seat, so repeat parts are instant and deterministic (same
philosophy as the CSXCAD FabStackups table).
"""

from __future__ import annotations

import csv
import fnmatch
from pathlib import Path
from typing import Optional


def _triple(s: str, default) -> tuple:
    s = (s or "").strip()
    if not s:
        return default
    parts = [p for p in s.replace(",", ";").split(";") if p != ""]
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return default
    if len(vals) >= 3:
        return (vals[0], vals[1], vals[2])
    return default


def load_footprint_table(cfg) -> list[dict]:
    path = Path(cfg.tables_dir) / "footprint_models.csv"
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            glob = (row.get("footprint_glob") or "").strip()
            if not glob or glob.startswith("#"):
                continue
            rows.append(row)
    return rows


def lookup(fp, cfg) -> Optional[dict]:
    """Return a parsed table entry for ``fp`` or None.

    Keys: source, locator, offset, rotate, scale, license, note.
    """
    hay_candidates = [fp.name, fp.mpn, f"{fp.name} {fp.mpn}".strip()]
    for row in load_footprint_table(cfg):
        glob = row["footprint_glob"].strip()
        if any(h and fnmatch.fnmatch(h, glob) for h in hay_candidates):
            return {
                "source": (row.get("source") or "").strip(),
                "locator": (row.get("locator") or "").strip(),
                "offset": _triple(row.get("offset"), (0.0, 0.0, 0.0)),
                "rotate": _triple(row.get("rotate"), (0.0, 0.0, 0.0)),
                "scale": _triple(row.get("scale"), (1.0, 1.0, 1.0)),
                "license": (row.get("license") or "unknown").strip(),
                "note": (row.get("note") or "").strip(),
                "glob": glob,
            }
    return None
