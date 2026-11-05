"""Source 6: parametric generation (offline).

Tries a registered CadQuery datasheet generator for the footprint (BWSMA, Würth,
generic edge-SMA, ...). If none matches or CadQuery is absent, falls back to the
stdlib courtyard-extruded box so generation always yields a real, viewable body
with zero dependencies. Offline -- no network.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import ModelHit, Source
from . import generators


class Generate(Source):
    name = "generate"
    networked = False

    def find(self, fp, cfg) -> Optional[ModelHit]:
        out_dir = Path(cfg.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = (fp.ref or fp.name.replace(":", "_") or "model")
        out_path = str(out_dir / f"{stem}.wrl")

        gen = generators.select(fp)
        if gen is not None:
            hit = gen(fp, cfg, out_path)
            if hit is not None:
                return hit
        # fallback: stdlib courtyard box
        return generators.generate_box(fp, cfg, out_path)
