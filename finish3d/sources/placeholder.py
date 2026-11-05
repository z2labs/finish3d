"""Source 7: placeholder (always succeeds, offline).

The last link in the chain. Emits a labelled box sized to the courtyard and
*always* attaches a ``MODEL_MISSING`` warning so a human sees the gap. This is
the old Eagle Exhumer "3D model missing" warning upgraded from a passive notice
into an active, visible resolver -- the board still renders, but the gap is loud.

Because it is a placeholder, the orchestrator accepts it even if verification is
imperfect (it is the floor, not a real model).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import ModelHit, Source
from .generators import box as box_gen


class Placeholder(Source):
    name = "placeholder"
    networked = False
    is_placeholder = True

    def find(self, fp, cfg) -> Optional[ModelHit]:
        out_dir = Path(cfg.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = (fp.ref or fp.name.replace(":", "_") or "model")
        out_path = str(out_dir / f"{stem}_PLACEHOLDER.wrl")
        hit = box_gen.generate_box(fp, cfg, out_path)
        if hit is None:
            # no courtyard at all -- emit a tiny default marker box
            from ..model_io import write_box_wrl
            write_box_wrl(out_path, dx=2.0, dy=2.0, dz=1.0,
                          color=(0.8, 0.2, 0.2), label=f"PLACEHOLDER {fp.name}")
            hit = ModelHit(path=out_path, source=self.name, license="own (placeholder)")
        hit.source = self.name
        hit.is_placeholder = True
        hit.license = "own (placeholder)"
        hit.note = "placeholder box; no real model resolved"
        hit.warnings.append("MODEL_MISSING")
        return hit
