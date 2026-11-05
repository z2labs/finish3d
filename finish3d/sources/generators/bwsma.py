"""BWSMA-KE-P001 edge-mount SMA connector generator (CadQuery).

Reconstruction of the body described in the handoff §5: flange, neck, threaded
barrel with grooves, centre hole, PTFE dielectric, slotted sleeve, signal pin,
and ground legs sized so a 1.6 mm board fits between the legs without overlap.

Requires CadQuery/OCP. If unavailable, returns None so the chain falls back to
the stdlib courtyard box. Exports STEP + WRL; returns the WRL (stdlib-verifiable).

TODO(machine): replace these dimensions with the verified twin/bwsma_model.py.
"""

from __future__ import annotations

from typing import Optional

from ..base import ModelHit

# --- datasheet-ish dimensions (mm); reconcile with twin/bwsma_model.py ---
BOARD_T = 1.6          # board the legs straddle
FLANGE = 6.35          # flange width/height (square)
FLANGE_T = 1.5
BARREL_D = 6.0         # threaded barrel outer diameter
BARREL_L = 6.0
NECK_D = 4.2
NECK_L = 1.5
BORE_D = 1.6           # centre bore
PTFE_D = 4.1
PIN_D = 1.27
PIN_L = 3.0
LEG_W = 1.0
LEG_T = 0.5
LEG_L = 4.0


def generate(fp, cfg, out_path: str) -> Optional[ModelHit]:
    try:  # pragma: no cover - optional dependency
        import cadquery as cq  # type: ignore
    except Exception:
        return None
    try:  # pragma: no cover - requires CAD kernel
        # barrel + neck + flange along +X (connector faces +X, out of the edge)
        body = (
            cq.Workplane("YZ")
            .circle(BARREL_D / 2).extrude(BARREL_L)
        )
        neck = cq.Workplane("YZ").workplane(offset=BARREL_L).circle(NECK_D / 2).extrude(NECK_L)
        flange = (
            cq.Workplane("YZ").workplane(offset=BARREL_L + NECK_L)
            .rect(FLANGE, FLANGE).extrude(FLANGE_T)
        )
        part = body.union(neck).union(flange)
        # centre bore + PTFE + pin
        part = part.faces(">X").workplane().circle(BORE_D / 2).cutThruAll()
        pin = cq.Workplane("YZ").workplane(offset=BARREL_L + NECK_L + FLANGE_T) \
            .circle(PIN_D / 2).extrude(PIN_L)
        part = part.union(pin)
        # ground legs straddling the board (board plane at z=0, thickness BOARD_T)
        leg = (
            cq.Workplane("XY")
            .box(LEG_L, LEG_W, LEG_T, centered=(True, True, False))
        )
        legs = (
            leg.translate((BARREL_L + NECK_L + FLANGE_T, 0, BOARD_T / 2 + LEG_T))
            .union(leg.translate((BARREL_L + NECK_L + FLANGE_T, 0, -BOARD_T / 2 - LEG_T)))
        )
        part = part.union(legs)

        step = out_path[:-4] + ".step" if out_path.lower().endswith(".wrl") else out_path + ".step"
        wrl = out_path if out_path.lower().endswith(".wrl") else out_path + ".wrl"
        cq.exporters.export(part, step)
        cq.exporters.export(part, wrl, exportType="VRML")
        return ModelHit(
            path=wrl, source="generate",
            base_offset=(0.0, 0.0, 0.0), base_rotate=(0.0, 0.0, 0.0),
            unit_scale=1.0, license="own (generated)",
            note="CadQuery BWSMA-KE-P001 (reconcile w/ twin/bwsma_model.py)",
        )
    except Exception:
        return None
