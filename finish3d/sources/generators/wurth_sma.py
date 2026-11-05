"""Würth WR-SMA 60312202114509 edge connector generator (CadQuery).

Handoff §5: vendor STEP exists; the known-good seat rotates the footprint 270°/90°
so the barrel faces outward. This parametric body is a stand-in for the vendor
STEP for offline use; prefer the real vendor STEP via the github/vendor source
when online. Reconcile dimensions with the project's verified Würth model.

Requires CadQuery/OCP; returns None if unavailable.
"""

from __future__ import annotations

from typing import Optional

from ..base import ModelHit

FLANGE = 6.35
FLANGE_T = 1.4
BARREL_D = 5.6
BARREL_L = 5.8
PIN_D = 1.3
PIN_L = 2.5
# barrel points outward; footprint is rotated 270/90 upstream, so the model's
# own rotate stays 0 and the seat/footprint handles orientation.


def generate(fp, cfg, out_path: str) -> Optional[ModelHit]:
    try:  # pragma: no cover - optional dependency
        import cadquery as cq  # type: ignore
    except Exception:
        return None
    try:  # pragma: no cover - requires CAD kernel
        barrel = cq.Workplane("YZ").circle(BARREL_D / 2).extrude(BARREL_L)
        flange = (
            cq.Workplane("YZ").workplane(offset=BARREL_L)
            .rect(FLANGE, FLANGE).extrude(FLANGE_T)
        )
        pin = (
            cq.Workplane("YZ").workplane(offset=BARREL_L + FLANGE_T)
            .circle(PIN_D / 2).extrude(PIN_L)
        )
        part = barrel.union(flange).union(pin)
        step = out_path[:-4] + ".step" if out_path.lower().endswith(".wrl") else out_path + ".step"
        wrl = out_path if out_path.lower().endswith(".wrl") else out_path + ".wrl"
        cq.exporters.export(part, step)
        cq.exporters.export(part, wrl, exportType="VRML")
        return ModelHit(
            path=wrl, source="generate",
            base_offset=(0.0, 0.0, 0.0), base_rotate=(0.0, 0.0, 0.0),
            unit_scale=1.0, license="own (generated); prefer vendor STEP online",
            note="CadQuery Würth WR-SMA stand-in (footprint rotated 270/90 upstream)",
        )
    except Exception:
        return None
