"""Digital-twin verification with a witness.

Principle (shared with srouter / Eagle Exhumer): *trust a check only if an
injected error trips it.* The model's geometry (read independently from the WRL
/ STEP file) is compared against the footprint courtyard read straight from the
``.kicad_pcb`` -- two independent sources. ``selftest`` then injects known-bad
seats and asserts every one is caught; a check the self-test cannot trip is dead
weight and must be removed.

All extent checks run in the **footprint-local frame**. KiCad applies the
footprint ``at`` rotation and the ``B.Cu`` side flip equally to the model and
the courtyard, so comparing them locally isolates seating correctness from board
placement. The flip logic itself is exercised separately in ``seat`` tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from . import model_io
from .board import BBox


@dataclass
class VerifyResult:
    ok: bool
    checks: dict
    notes: list[str] = field(default_factory=list)


def _rot_matrix(rx: float, ry: float, rz: float):
    ax, ay, az = map(math.radians, (rx, ry, rz))
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    # R = Rz * Ry * Rx
    return (
        (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
        (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
        (-sy,     cy * sx,                cy * cx),
    )


def _place_local(corners, seat):
    """Apply scale -> rotate -> offset to local corners; no fp rot, no mirror."""
    sx, sy, sz = seat.scale
    R = _rot_matrix(*seat.rotate)
    ox, oy, oz = seat.offset
    out = []
    for x, y, z in corners:
        x, y, z = x * sx, y * sy, z * sz
        rx = R[0][0] * x + R[0][1] * y + R[0][2] * z
        ry = R[1][0] * x + R[1][1] * y + R[1][2] * z
        rz = R[2][0] * x + R[2][1] * y + R[2][2] * z
        out.append((rx + ox, ry + oy, rz + oz))
    return out


def _placed_bounds(bounds, seat):
    corners = [
        (bounds.xmin, bounds.ymin, bounds.zmin),
        (bounds.xmax, bounds.ymin, bounds.zmin),
        (bounds.xmax, bounds.ymax, bounds.zmin),
        (bounds.xmin, bounds.ymax, bounds.zmin),
        (bounds.xmin, bounds.ymin, bounds.zmax),
        (bounds.xmax, bounds.ymin, bounds.zmax),
        (bounds.xmax, bounds.ymax, bounds.zmax),
        (bounds.xmin, bounds.ymax, bounds.zmax),
    ]
    placed = _place_local(corners, seat)
    xs = [p[0] for p in placed]
    ys = [p[1] for p in placed]
    zs = [p[2] for p in placed]
    return model_io.Bounds3D(
        min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)
    )


def verify(fp, hit, seat, cfg) -> VerifyResult:
    xy_tol = getattr(cfg, "xy_tol_mm", 1.0)
    z_tol = getattr(cfg, "z_tol_mm", 0.05)
    cover_lo = getattr(cfg, "cover_lo", 0.3)
    cover_hi = getattr(cfg, "cover_hi", 1.6)
    scale_lo = getattr(cfg, "scale_lo", 0.2)
    scale_hi = getattr(cfg, "scale_hi", 5.0)

    notes: list[str] = []
    raw = model_io.model_bbox(hit.path) if hit.path else None
    cy = fp.courtyard_bbox()

    checks: dict = {}

    if raw is None:
        # Can't read geometry (e.g. STEP without a CAD kernel). Record an
        # honest "unknown" rather than a false pass.
        notes.append("model geometry unreadable (no WRL verts / no CAD kernel)")
        checks["geometry_readable"] = False
        return VerifyResult(ok=False, checks=checks, notes=notes)

    if not cy.valid or cy.max_dim <= 0:
        notes.append("no courtyard/pad extent on footprint; extent checks skipped")
        checks["has_reference_extent"] = False
        # we can still sanity-check upside-down
        placed = _placed_bounds(raw, seat)
        checks["upright"] = placed.zmin >= -z_tol and placed.zmax > z_tol
        return VerifyResult(ok=all(checks.values()), checks=checks, notes=notes)

    placed = _placed_bounds(raw, seat)

    # 1) XY coverage: model should occupy a sane fraction of the courtyard and
    #    be roughly centred on it. Catches rot90 (non-square flips coverage),
    #    offset (centre drifts), swap_model (wrong size).
    cover_x = placed.dx / cy.width if cy.width else math.inf
    cover_y = placed.dy / cy.height if cy.height else math.inf
    model_cx = (placed.xmin + placed.xmax) / 2
    model_cy = (placed.ymin + placed.ymax) / 2
    court_cx = (cy.xmin + cy.xmax) / 2
    court_cy = (cy.ymin + cy.ymax) / 2
    centre_shift = math.hypot(model_cx - court_cx, model_cy - court_cy)
    checks["xy_extent"] = (
        cover_lo <= cover_x <= cover_hi
        and cover_lo <= cover_y <= cover_hi
        and centre_shift <= xy_tol
    )
    notes.append(
        f"cover_x={cover_x:.2f} cover_y={cover_y:.2f} "
        f"centre_shift={centre_shift:.3f}mm (tol {xy_tol})"
    )

    # 2) Scale sanity: catches the mm / 0.1mm / inch unit mistakes (25.4x etc.)
    ratio = placed.max_dim / cy.max_dim if cy.max_dim else math.inf
    checks["scale_sane"] = scale_lo < ratio < scale_hi
    notes.append(f"max_dim ratio={ratio:.3f}")

    # 3) Upright / correct Z half: body sits on the component side of its own
    #    origin plane (local z >= ~0 and grows positive). Catches an
    #    upside-down / wrong-side seat.
    checks["upright"] = placed.zmin >= -z_tol and placed.zmax > z_tol
    notes.append(f"z=[{placed.zmin:.3f}, {placed.zmax:.3f}]")

    return VerifyResult(ok=all(checks.values()), checks=checks, notes=notes)


# --------------------------------------------------------------------------- #
# Witness self-test: build a known-good seat, inject each error, require a trip.
# --------------------------------------------------------------------------- #
@dataclass
class SelftestReport:
    ok: bool
    cases: list                      # list of (name, expected, tripped, detail)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "cases": [
                {"name": n, "expected": e, "result": r, "detail": d}
                for (n, e, r, d) in self.cases
            ],
        }


def run_selftest(cfg=None) -> SelftestReport:
    """Return a report; ``ok`` only if the good seat passes AND every injected
    error is caught."""
    import copy
    import os
    import tempfile

    from .config import Config
    from .seat import SeatTransform
    from .sources.base import ModelHit

    cfg = cfg or Config()

    # --- build a known-good part: a 10 x 4 x 3 mm body on a 10 x 4 courtyard ---
    tmp = tempfile.mkdtemp(prefix="finish3d_selftest_")
    good_path = os.path.join(tmp, "good.wrl")
    model_io.write_box_wrl(good_path, dx=10.0, dy=4.0, dz=3.0,
                           center_xy=(0.0, 0.0), z0=0.0, label="selftest-good")
    swap_path = os.path.join(tmp, "swap.wrl")
    model_io.write_box_wrl(swap_path, dx=2.0, dy=2.0, dz=2.0, label="selftest-swap")

    class _FP:
        name = "Selftest:BODY_10x4"
        ref = "U1"
        at = (100.0, 100.0)
        rotation_deg = 0.0
        side = "F.Cu"

        def courtyard_bbox(self):
            bb = BBox()
            bb.add(-5.0, -2.0)
            bb.add(5.0, 2.0)
            return bb

    fp = _FP()
    good_hit = ModelHit(path=good_path, source="selftest",
                        base_offset=(0.0, 0.0, 0.0), base_rotate=(0.0, 0.0, 0.0),
                        unit_scale=1.0, license="n/a")
    good_seat = SeatTransform(offset=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0),
                              rotate=(0.0, 0.0, 0.0))

    cases: list = []

    # baseline must PASS
    base = verify(fp, good_hit, good_seat, cfg)
    cases.append(("baseline_good", True, base.ok,
                  "checks=" + str(base.checks)))

    # injected errors -- each must make verify FAIL (i.e. be "tripped")
    def seat_of(**kw) -> SeatTransform:
        s = copy.deepcopy(good_seat)
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    injections = {
        "rot90": (good_hit, seat_of(rotate=(0.0, 0.0, 90.0))),
        "wrong_side": (good_hit, seat_of(rotate=(180.0, 0.0, 0.0))),  # flips body under plane
        "scale_254": (good_hit, seat_of(scale=(25.4, 25.4, 25.4))),
        "offset_1mm": (good_hit, seat_of(offset=(1.0, 1.0, 0.0))),
        "swap_model": (
            ModelHit(path=swap_path, source="selftest",
                     base_offset=(0.0, 0.0, 0.0), base_rotate=(0.0, 0.0, 0.0),
                     unit_scale=1.0, license="n/a"),
            good_seat,
        ),
    }
    for name, (hit, seat) in injections.items():
        vr = verify(fp, hit, seat, cfg)
        tripped = not vr.ok
        cases.append((name, True, tripped, "checks=" + str(vr.checks)))

    ok = base.ok and all(tripped for (_, _, tripped, _) in cases[1:])
    return SelftestReport(ok=ok, cases=cases)
