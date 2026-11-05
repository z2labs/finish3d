"""Generic edge-mount SMA family generator (CadQuery).

A parametric edge SMA for footprints that don't match a specific vendor part.
Dimensions are scaled from the footprint courtyard where possible so the body
fits the pads. Requires CadQuery/OCP; returns None otherwise.
"""

from __future__ import annotations

from typing import Optional

from ..base import ModelHit

BARREL_D = 6.0
PIN_D = 1.27
PIN_L = 2.5


def generate(fp, cfg, out_path: str) -> Optional[ModelHit]:
    try:  # pragma: no cover - optional dependency
        import cadquery as cq  # type: ignore
    except Exception:
        return None
    try:  # pragma: no cover - requires CAD kernel
        cy = fp.courtyard_bbox()
        barrel_l = max(cy.width, 5.0) if cy.valid else 6.0
        flange = max(cy.height, 5.0) if cy.valid else 6.35
        barrel = cq.Workplane("YZ").circle(BARREL_D / 2).extrude(barrel_l)
        fl = cq.Workplane("YZ").workplane(offset=barrel_l).rect(flange, flange).extrude(1.4)
        pin = cq.Workplane("YZ").workplane(offset=barrel_l + 1.4).circle(PIN_D / 2).extrude(PIN_L)
        part = barrel.union(fl).union(pin)
        step = out_path[:-4] + ".step" if out_path.lower().endswith(".wrl") else out_path + ".step"
        wrl = out_path if out_path.lower().endswith(".wrl") else out_path + ".wrl"
        cq.exporters.export(part, step)
        cq.exporters.export(part, wrl, exportType="VRML")
        return ModelHit(
            path=wrl, source="generate",
            base_offset=(0.0, 0.0, 0.0), base_rotate=(0.0, 0.0, 0.0),
            unit_scale=1.0, license="own (generated)",
            note="CadQuery generic edge-SMA scaled to courtyard",
        )
    except Exception:
        return None
