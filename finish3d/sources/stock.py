"""Source 2: KiCad stock 3D libraries (offline).

Searches the packages3D trees pointed at by the standard KiCad env vars, matched
by footprint ``Lib:Name``. Also honours the footprint's own ``(model)`` hint path
basename even when that exact file is missing (a different packages3D root may
hold it).

When the exact ``Lib:Name`` is not a KiCad library name (Eagle / IPC-7351 /
vendor-style footprint names such as ``CAP_0402``, ``RESC1005X40_0402`` or
``SON50P200X200X95-9N``), the name is normalised to the KiCad stock naming and
looked up again ("pairing"). A ``footprint_models.csv`` row with
``source=stock`` and a ``locator`` of ``Lib.3dshapes/Name`` pins the pairing
explicitly and wins over the heuristics.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Optional

from .base import ModelHit, Source

# KiCad has shuffled the env var name across versions; try them all.
_ENV_VARS = (
    "KICAD10_3DMODEL_DIR",
    "KICAD9_3DMODEL_DIR",
    "KICAD8_3DMODEL_DIR",
    "KICAD7_3DMODEL_DIR",
    "KICAD6_3DMODEL_DIR",
    "KISYS3DMOD",
)

_DEFAULT_ROOTS = (
    "/usr/share/kicad/3dmodels",
    "/usr/local/share/kicad/3dmodels",
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels",
    "C:/Program Files/KiCad/share/kicad/3dmodels",
)

# Windows installs are versioned (C:/Program Files/KiCad/10.0/share/...), and the
# KICADn_3DMODEL_DIR variables only exist inside a running KiCad, not in a shell.
_DEFAULT_ROOT_GLOBS = (
    "C:/Program Files/KiCad/*/share/kicad/3dmodels",
    "/Applications/KiCad*/KiCad.app/Contents/SharedSupport/3dmodels",
)

_EXTS = (".wrl", ".step", ".stp")

# imperial chip size -> KiCad "<imperial>_<metric>Metric" suffix
_IMPERIAL = {
    "0201": "0201_0603Metric", "0402": "0402_1005Metric",
    "0603": "0603_1608Metric", "0805": "0805_2012Metric",
    "1206": "1206_3216Metric", "1210": "1210_3225Metric",
    "1812": "1812_4532Metric", "2010": "2010_5025Metric",
    "2512": "2512_6332Metric",
}
_METRIC = {v.split("_")[1][:4]: v for v in _IMPERIAL.values()}

# (regex on the upper-cased name, KiCad library, KiCad name prefix)
_CHIP_KINDS = (
    (r"LED", "LED_SMD", "LED"),
    (r"RESC|^RES|^R[_\-]?\d", "Resistor_SMD", "R"),
    (r"CAPC|^CAP|^C[_\-]?\d", "Capacitor_SMD", "C"),
    (r"INDC|BEADC|INDUCT|FERRITE|BEAD|^IND|^L[_\-]?\d|LQW|LQG|LQP|LQM|WE-KI|WE-MK|BLM",
     "Inductor_SMD", "L"),
    (r"DIOC|^DIO|^D[_\-]?\d", "Diode_SMD", "D"),
)

# IPC-7351 chip names carry the *metric* size: RESC1005X40, CAPC1608X90, BEADC4532X350
_IPC_CHIP = re.compile(r"(?:RESC|CAPC|INDC|BEADC|LEDC|DIOC)(\d{4})X")
# IPC-7351 no-lead packages: SON50P200X200X95-9N  (pitch, body X, body Y, height, pins)
_IPC_NOLEAD = re.compile(r"(SON|DFN|QFN)(\d+)P(\d+)X(\d+)X\d+-(\d+)")


def _mm(hundredths: str) -> str:
    """'200' -> '2', '50' -> '0.5', '165' -> '1.65' (KiCad name formatting)."""
    return f"{int(hundredths) / 100:g}"


def _version_key(path: str) -> tuple:
    """Sort key so that .../KiCad/10.0/... ranks above .../KiCad/9.0/..."""
    return tuple(int(n) for n in re.findall(r"\d+", path))


def _roots(cfg) -> list[str]:
    roots: list[str] = []
    for v in _ENV_VARS:
        val = os.environ.get(v)
        if val and os.path.isdir(val):
            roots.append(val)
    for d in _DEFAULT_ROOTS:
        if os.path.isdir(d):
            roots.append(d)
    for pattern in _DEFAULT_ROOT_GLOBS:
        roots.extend(sorted((d for d in glob.glob(pattern) if os.path.isdir(d)),
                            key=_version_key, reverse=True))  # newest first
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


def alias_candidates(fp_name: str) -> list[tuple[str, str]]:
    """Normalise a non-KiCad footprint name to stock ``(library_subdir, basename)``
    candidates. The basename may contain ``*`` (resolved by glob, first hit wins).
    """
    name = fp_name.partition(":")[2] or fp_name
    up = name.upper()
    out: list[tuple[str, str]] = []

    m = _IPC_NOLEAD.search(up)
    if m:
        _, pitch, bx, by, pins = m.groups()
        n = int(pins)
        body = f"{_mm(bx)}x{_mm(by)}mm_P{_mm(pitch)}mm"
        if n % 2:  # odd count = exposed pad included
            for lib, fam in (("Package_DFN_QFN", "DFN"), ("Package_SON", "WSON"),
                             ("Package_DFN_QFN", "QFN"), ("Package_SON", "*")):
                out.append((f"{lib}.3dshapes", f"{fam}-{n - 1}-1EP_{body}*"))
        else:
            for lib, fam in (("Package_DFN_QFN", "DFN"), ("Package_SON", "*")):
                out.append((f"{lib}.3dshapes", f"{fam}-{n}_{body}*"))
        return out

    size = None
    m = _IPC_CHIP.search(up)
    if m:
        size = _METRIC.get(m.group(1))
    if size is None:
        for tok in re.findall(r"(?<!\d)(\d{4})(?!\d)", up):
            if tok in _IMPERIAL:
                size = _IMPERIAL[tok]
                break
    if size:
        for pattern, lib, prefix in _CHIP_KINDS:
            if re.search(pattern, up):
                out.append((f"{lib}.3dshapes", f"{prefix}_{size}"))
                break
    return out


def _table_candidate(fp, cfg) -> list[tuple[str, str]]:
    """``source=stock`` table row with a ``Lib.3dshapes/Name`` locator."""
    try:
        from .. import tables
        row = tables.lookup(fp, cfg)
    except Exception:  # noqa: BLE001 - table problems must not kill the source
        return []
    if not row or row.get("source") != "stock" or not row.get("locator"):
        return []
    loc = row["locator"].replace("\\", "/")
    subdir, _, base = loc.rpartition("/")
    base = os.path.splitext(base)[0] if base.lower().endswith(_EXTS) else base
    return [(subdir, base)] if base else []


class Stock(Source):
    name = "stock"
    networked = False

    def find(self, fp, cfg) -> Optional[ModelHit]:
        roots = _roots(cfg)
        if not roots:
            return None

        # candidate names, best first: (library_subdir, basename, how)
        lib, _, name = fp.name.partition(":")
        cands: list[tuple[str, str, str]] = []
        cands += [(s, b, "table") for s, b in _table_candidate(fp, cfg)]
        if lib and name:
            cands.append((f"{lib}.3dshapes", name, "exact"))
            cands.append((lib, name, "exact"))
        if name:
            cands.append(("", name, "exact"))
        # footprint's own model hint basename
        if fp.model and fp.model.path:
            base = Path(fp.model.path).stem
            cands.append(("", base, "hint"))
        cands += [(s, b, "paired") for s, b in alias_candidates(fp.name)]

        # Extension outermost: a .wrl in any installed library beats a .step,
        # because WRL geometry can be verified without a CAD kernel.
        for ext in _EXTS:
            for subdir, base, how in cands:
                for root in roots:
                    folder = Path(root) / subdir if subdir else Path(root)
                    if "*" in base:
                        hits = sorted(glob.glob(str(folder / f"{base}{ext}")))
                        p = Path(hits[0]) if hits else None
                    else:
                        p = folder / f"{base}{ext}"
                    if p is not None and p.exists():
                        return ModelHit(
                            path=str(p), source=self.name,
                            license="KiCad libraries (CC-BY-SA-4.0 w/ exception)",
                            note=f"stock {how} match {subdir}/{p.name}",
                        )
        return None
