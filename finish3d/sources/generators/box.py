"""Stdlib parametric fallback: a courtyard-sized box, no CAD kernel needed.

This keeps "parametric generation" available in the pure-offline, no-dependency
core. It extrudes the footprint courtyard (or pad span) to a heuristic height and
writes a VRML2 body that is viewable in KiCad and passes verification (it is
derived from the footprint, so it fits by construction). For a geometrically
*independent* body use the CadQuery datasheet generators instead.
"""

from __future__ import annotations

import os
from typing import Optional

from ... import model_io
from ..base import ModelHit


def _height_for(fp) -> float:
    cy = fp.courtyard_bbox()
    base = min(cy.width, cy.height) if cy.valid else 2.0
    # modest default profile; clamped to a sane range
    return max(0.6, min(base * 0.6, 8.0))


def generate_box(fp, cfg, out_path: str) -> Optional[ModelHit]:
    cy = fp.courtyard_bbox()
    if not cy.valid or cy.max_dim <= 0:
        return None
    dx = max(cy.width, 0.5)
    dy = max(cy.height, 0.5)
    dz = _height_for(fp)
    cx = (cy.xmin + cy.xmax) / 2
    cy_ = (cy.ymin + cy.ymax) / 2
    model_io.write_box_wrl(
        out_path, dx=dx, dy=dy, dz=dz, center_xy=(cx, -cy_), z0=0.0,  # footprint Y is down, model Y is up
        color=(0.35, 0.45, 0.5), label=f"generated-box {fp.name}",
    )
    return ModelHit(
        path=out_path, source="generate",
        base_offset=(0.0, 0.0, 0.0), base_rotate=(0.0, 0.0, 0.0),
        unit_scale=1.0, license="own (generated)",
        note="stdlib courtyard-extruded box",
    )
