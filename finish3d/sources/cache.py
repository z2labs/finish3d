"""Source 3: local cache (offline).

``~/.finish3d/cache/index.json`` maps a key (MPN / LCSC / footprint-name hash)
to a stored file + provenance. Lets a second board reuse a downloaded or
generated model with no network. The cache is also where networked/generated
sources deposit their results (see ``put``).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from .base import ModelHit, Source


def _index_path(cfg) -> Path:
    return Path(cfg.cache_dir) / "index.json"


def _load_index(cfg) -> dict:
    p = _index_path(cfg)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_index(cfg, index: dict) -> None:
    Path(cfg.cache_dir).mkdir(parents=True, exist_ok=True)
    tmp = _index_path(cfg).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_index_path(cfg))


def keys_for(fp) -> list[str]:
    keys = []
    if fp.lcsc:
        keys.append(f"lcsc:{fp.lcsc.upper()}")
    if fp.mpn:
        keys.append(f"mpn:{fp.mpn.upper()}")
    if fp.name:
        h = hashlib.sha1(fp.name.encode("utf-8")).hexdigest()[:12]
        keys.append(f"fp:{fp.name}")
        keys.append(f"fph:{h}")
    return keys


def put(cfg, fp, src_file: str, *, source: str, license: str,
        offset=(0.0, 0.0, 0.0), rotate=(0.0, 0.0, 0.0), unit_scale=1.0,
        note: str = "") -> ModelHit:
    """Copy a resolved model into the cache and index it under all fp keys."""
    Path(cfg.cache_dir).mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(src_file)[1] or ".wrl"
    stem = (fp.lcsc or fp.mpn or fp.name or "model").replace(":", "_").replace("/", "_")
    dst = Path(cfg.cache_dir) / f"{stem}{ext}"
    if os.path.abspath(src_file) != os.path.abspath(dst):
        shutil.copy2(src_file, dst)
    index = _load_index(cfg)
    entry = {
        "file": str(dst), "source": source, "license": license,
        "offset": list(offset), "rotate": list(rotate), "unit_scale": unit_scale,
        "note": note, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    for k in keys_for(fp):
        index[k] = entry
    _save_index(cfg, index)
    return ModelHit(path=str(dst), source=source, base_offset=tuple(offset),
                    base_rotate=tuple(rotate), unit_scale=unit_scale,
                    license=license, note=note or f"cached from {source}")


class Cache(Source):
    name = "cache"
    networked = False

    def find(self, fp, cfg) -> Optional[ModelHit]:
        index = _load_index(cfg)
        for k in keys_for(fp):
            entry = index.get(k)
            if entry and os.path.exists(entry.get("file", "")):
                return ModelHit(
                    path=entry["file"], source=self.name,
                    base_offset=tuple(entry.get("offset", (0, 0, 0))),
                    base_rotate=tuple(entry.get("rotate", (0, 0, 0))),
                    unit_scale=entry.get("unit_scale", 1.0),
                    license=entry.get("license", "unknown"),
                    note=f"cache hit via {k} (orig {entry.get('source')})",
                )
        return None
