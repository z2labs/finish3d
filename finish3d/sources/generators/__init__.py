"""Registry of parametric model generators.

A generator is ``callable(fp, cfg, out_path) -> ModelHit | None``. The registry
maps footprint-name globs to generators; the first glob that matches ``fp.name``
(or its MPN) wins. The CadQuery datasheet generators (``bwsma``, ``wurth_sma``,
``generic_edge_sma``) produce geometrically independent bodies and return STEP+
WRL when CadQuery is importable; otherwise they return ``None`` and the orchestrator
falls back to the stdlib courtyard box.

IMPORTANT (handoff §2, §5): the detailed datasheet geometry for BWSMA-KE-P001 and
the Würth WR-SMA already exists and is verified in ``twin/bwsma_model.py`` and the
project's Würth model on the G7 machine. The bodies here are faithful
reconstructions to make the pipeline runnable; on the machine, reconcile them
against the verified originals (that is step 2 of the live-build checklist) rather
than trusting these dimensions blind.
"""

from __future__ import annotations

import fnmatch
from typing import Callable, Optional

from ..base import ModelHit
from . import box as _box
from . import bwsma as _bwsma
from . import wurth_sma as _wurth
from . import generic_edge_sma as _edge

Generator = Callable[..., Optional[ModelHit]]

# order matters: most specific first
REGISTRY: list[tuple[str, Generator]] = [
    ("*BWSMA*", _bwsma.generate),
    ("*BWSMA-KE-P001*", _bwsma.generate),
    ("*WR-SMA*", _wurth.generate),
    ("*60312202114509*", _wurth.generate),
    ("*Wuerth*SMA*", _wurth.generate),
    ("*SMA*EDGE*", _edge.generate),
    ("*SMA_Edge*", _edge.generate),
    ("*Edge*SMA*", _edge.generate),
]


def select(fp) -> Optional[Generator]:
    hay = f"{fp.name} {fp.mpn}".upper()
    for pattern, gen in REGISTRY:
        if fnmatch.fnmatch(hay, pattern.upper()):
            return gen
    return None


# locator name (from footprint_models.csv) -> generator
BY_LOCATOR: dict[str, Generator] = {
    "bwsma": _bwsma.generate,
    "wurth_sma": _wurth.generate,
    "generic_edge_sma": _edge.generate,
    "box": _box.generate_box,
}


def by_locator(name: str) -> Optional[Generator]:
    return BY_LOCATOR.get((name or "").strip())


# exported so the stdlib fallback is reachable directly
generate_box = _box.generate_box
