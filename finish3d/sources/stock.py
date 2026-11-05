"""Source 2: KiCad stock 3D libraries (offline).

Searches the packages3D trees pointed at by the standard KiCad env vars, matched
by footprint ``Lib:Name``. Also honours the footprint's own ``(model)`` hint path
basename even when that exact file is missing (a different packages3D root may
hold it).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import ModelHit, Source

# KiCad has shuffled the env var name across versions; try them all.
_ENV_VARS = (
    "KICAD9_3DMODEL_DIR",
    "KICAD8_3DMODEL_DIR",
    "KICAD7_3DMODEL_DIR",
    "KICAD6_3DMODEL_DIR",
    "KISYS3DMOD",
    "KICAD10_3DMODEL_DIR",
)

_DEFAULT_ROOTS = (
    "/usr/share/kicad/3dmodels",
    "/usr/local/share/kicad/3dmodels",
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels",
    "C:/Program Files/KiCad/share/kicad/3dmodels",
)

_EXTS = (".wrl", ".step", ".stp")


def _roots(cfg) -> list[str]:
    roots: list[str] = []
    for v in _ENV_VARS:
        val = os.environ.get(v)
        if val and os.path.isdir(val):
            roots.append(val)
    for d in _DEFAULT_ROOTS:
        if os.path.isdir(d):
            roots.append(d)
    extra = getattr(cfg, "stock_roots", None)
    if extra:
        roots.extend(r for r in extra if os.path.isdir(r))
    # de-dup, keep order
    seen, out = set(), []
    for r in roots:
        rp = os.path.realpath(r)
        if rp not in seen:
            seen.add(rp)
            out.append(r)
    return out


class Stock(Source):
    name = "stock"
    networked = False

    def find(self, fp, cfg) -> Optional[ModelHit]:
        roots = _roots(cfg)
        if not roots:
            return None

        # candidate names, best first
        lib, _, name = fp.name.partition(":")
        cands: list[tuple[str, str]] = []  # (library_subdir, basename)
        if lib and name:
            cands.append((f"{lib}.3dshapes", name))
            cands.append((lib, name))
        if name:
            cands.append(("", name))
        # footprint's own model hint basename
        if fp.model and fp.model.path:
            base = Path(fp.model.path).stem
            cands.append(("", base))

        for root in roots:
            for subdir, base in cands:
                for ext in _EXTS:
                    p = Path(root) / subdir / f"{base}{ext}" if subdir \
                        else Path(root) / f"{base}{ext}"
                    if p.exists():
                        return ModelHit(
                            path=str(p), source=self.name,
                            license="KiCad libraries (CC-BY-SA-4.0 w/ exception)",
                            note=f"stock match {subdir}/{base}{ext}",
                        )
        return None
