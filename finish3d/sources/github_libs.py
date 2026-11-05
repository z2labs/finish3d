"""Source 5: GitHub / vendor 3D libraries (networked, opt-in).

Driven by the curated ``tables/vendor_repos.csv`` table (knowledge as data). Each
row maps a package pattern to a repo + path template. Matched by MPN/package; the
resolved file is downloaded into the cache. Networked, skipped when offline.
"""

from __future__ import annotations

import csv
import fnmatch
import os
from pathlib import Path
from typing import Optional

from .base import ModelHit, Source
from . import cache as cache_mod


def _load_table(cfg) -> list[dict]:
    path = Path(cfg.tables_dir) / "vendor_repos.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh)
                if row.get("vendor") and not row["vendor"].startswith("#")]


def _fill(template: str, fp) -> str:
    return (template
            .replace("{mpn}", fp.mpn)
            .replace("{name}", fp.name.partition(":")[2] or fp.name)
            .replace("{lib}", fp.name.partition(":")[0]))


class GithubLibs(Source):
    name = "github"
    networked = True

    def find(self, fp, cfg) -> Optional[ModelHit]:
        rows = _load_table(cfg)
        if not rows:
            return None
        hay = f"{fp.mpn} {fp.name}".strip()
        if not hay:
            return None

        try:  # pragma: no cover - optional dependency
            import requests  # type: ignore
        except Exception:
            return None

        for row in rows:
            pattern = row.get("package_pattern", "")
            if not pattern:
                continue
            if not (fnmatch.fnmatch(fp.mpn, pattern)
                    or fnmatch.fnmatch(fp.name, pattern)
                    or fnmatch.fnmatch(hay, pattern)):
                continue
            url = _fill(row.get("path_template", ""), fp)
            if not url:
                continue
            try:  # pragma: no cover - network
                r = requests.get(url, timeout=20)
                if r.status_code != 200 or not r.content:
                    continue
                os.makedirs(cfg.cache_dir, exist_ok=True)
                ext = os.path.splitext(url)[1] or ".step"
                tmp = Path(cfg.cache_dir) / f"_dl_{fp.ref or 'x'}{ext}"
                tmp.write_bytes(r.content)
                return cache_mod.put(
                    cfg, fp, str(tmp), source=self.name,
                    license=row.get("license", "vendor (see repo)"),
                    note=f"{row.get('vendor')} {url}",
                )
            except Exception:
                continue
        return None
