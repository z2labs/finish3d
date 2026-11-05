"""Seat a 3D model onto a footprint.

Two coordinate frames matter here and they are easy to confuse:

* **Local (what we write into the board).** KiCad stores a per-model
  ``(offset)(scale)(rotate)`` in the footprint, expressed in the footprint's
  own frame. KiCad itself then applies the footprint ``(at x y rot)`` and the
  side flip for ``B.Cu`` at render time. So the transform we *persist* must NOT
  bake in the footprint rotation or the side flip -- otherwise the board stops
  being a normal board another tool can read. ``seat_model`` returns this local
  transform.

* **World (what we check).** To verify a seat we have to reproduce what KiCad
  will actually draw: take the model, apply its local offset/scale/rotate, then
  the footprint Z-rotation, then -- for bottom parts -- the mirror. The order is
  the trap documented for the Eagle pad transform: **rotate first, then
  mirror**, never the reverse. ``place_point`` / ``model_world_bbox`` do this and
  are the single home of that rule.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SeatTransform:
    """Per-model transform written into the footprint (local frame)."""
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)   # mm
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotate: tuple[float, float, float] = (0.0, 0.0, 0.0)   # degrees


def seat_model(fp, hit) -> SeatTransform:
    """Produce the local-frame seat transform for ``fp`` given a resolved ``hit``.

    A well-authored model (KiCad stock, a correctly oriented generated body) is
    already in the footprint frame, so its local offset/rotate are the hit's own
    base values and scale is the unit scale. The footprint ``at`` rotation and
    the ``B.Cu`` side flip are applied by KiCad, not baked here.
    """
    return SeatTransform(
        offset=hit.base_offset,
        scale=(hit.unit_scale, hit.unit_scale, hit.unit_scale)
        if isinstance(hit.unit_scale, (int, float)) else hit.unit_scale,
        rotate=hit.base_rotate,
    )


# --------------------------------------------------------------------------- #
# World placement -- the rotate-then-mirror rule lives here, once.
# --------------------------------------------------------------------------- #
def _rot_z(x: float, y: float, deg: float) -> tuple[float, float]:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (x * c - y * s, x * s + y * c)


def place_point(
    px: float, py: float, pz: float,
    seat: SeatTransform,
    fp_rotation_deg: float,
    side: str,
) -> tuple[float, float, float]:
    """Map a model-local point to world coordinates, KiCad-style.

    Order: model scale -> model rotate (Z) -> model offset -> footprint
    rotation (Z) -> side mirror. The mirror is applied **after** every rotation,
    exactly as KiCad flips a bottom footprint about the X axis once its rotation
    is baked in.
    """
    sx, sy, sz = seat.scale
    x, y, z = px * sx, py * sy, pz * sz

    # model's own rotation (we only use Z here; X/Y handled by generators)
    rx, ry, rz = seat.rotate
    x, y = _rot_z(x, y, rz)

    # model offset (local frame)
    ox, oy, oz = seat.offset
    x, y, z = x + ox, y + oy, z + oz

    # footprint placement rotation about Z
    x, y = _rot_z(x, y, fp_rotation_deg)

    # ---- ROTATE FIRST, THEN MIRROR. Never mirror then rotate. ----
    if side == "B.Cu":
        x, y, z = mirror_after_rotate(x, y, z)
    return (x, y, z)


def mirror_after_rotate(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Mirror a point for a bottom-side part, assuming rotation is already baked.

    KiCad flips the footprint about the X axis (``y -> -y``) and sends the body
    below the board (``z -> -z``). Calling this before applying rotation would
    be the classic bug; by contract it runs last.
    """
    return (x, -y, -z)


def mirror_point_after_rotate(point, fp_rotation_deg):
    """Compatibility helper matching the spec §6.3 signature.

    ``point`` is an already-rotated (x, y, z). Kept so callers that follow the
    handoff pseudo-code read naturally.
    """
    x, y, z = point
    return mirror_after_rotate(x, y, z)
