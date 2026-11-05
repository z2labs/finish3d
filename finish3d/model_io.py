"""Read/write 3D model geometry without a CAD kernel (stdlib only).

* ``wrl_vertex_bbox`` scans a VRML2 (.wrl) file for ``Coordinate { point [...] }``
  blocks and returns the raw vertex bounding box. KiCad WRL models are in
  0.1 inch "KiCad units" historically, but modern exports are in mm; we return
  the raw numbers and let the caller apply the model's scale.
* ``write_box_wrl`` emits a labelled rectangular box. This lets the offline
  ``Generate`` source and the ``Placeholder`` source produce a real, viewable
  model with zero dependencies -- no CadQuery, no OCP.
* ``step_bbox`` tries OCP/CadQuery if installed, else returns ``None`` so the
  verifier degrades gracefully instead of crashing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Bounds3D:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @property
    def dx(self) -> float:
        return self.xmax - self.xmin

    @property
    def dy(self) -> float:
        return self.ymax - self.ymin

    @property
    def dz(self) -> float:
        return self.zmax - self.zmin

    @property
    def max_dim(self) -> float:
        return max(self.dx, self.dy, self.dz)

    def center(self) -> tuple[float, float, float]:
        return (
            (self.xmin + self.xmax) / 2,
            (self.ymin + self.ymax) / 2,
            (self.zmin + self.zmax) / 2,
        )


_POINT_BLOCK = re.compile(r"point\s*\[(.*?)\]", re.DOTALL)
_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def wrl_vertex_bbox(path: str) -> Optional[Bounds3D]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for block in _POINT_BLOCK.finditer(text):
        nums = [float(m.group()) for m in _NUMBER.finditer(block.group(1))]
        # vertices come in triples
        for i in range(0, len(nums) - 2, 3):
            xs.append(nums[i])
            ys.append(nums[i + 1])
            zs.append(nums[i + 2])
    if not xs:
        return None
    return Bounds3D(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def step_bbox(path: str) -> Optional[Bounds3D]:
    """Bounding box of a STEP file, if a CAD kernel is importable; else None."""
    try:  # pragma: no cover - optional dependency path
        import cadquery as cq  # type: ignore

        shape = cq.importers.importStep(path)
        bb = shape.val().BoundingBox()
        return Bounds3D(bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)
    except Exception:
        return None


def model_bbox(path: str) -> Optional[Bounds3D]:
    """Dispatch on extension: WRL via stdlib, STEP via optional kernel."""
    low = path.lower()
    if low.endswith((".wrl", ".vrml")):
        return wrl_vertex_bbox(path)
    if low.endswith((".step", ".stp")):
        return step_bbox(path)
    # unknown: try WRL parsing anyway
    return wrl_vertex_bbox(path)


def write_box_wrl(
    path: str,
    dx: float,
    dy: float,
    dz: float,
    *,
    center_xy: tuple[float, float] = (0.0, 0.0),
    z0: float = 0.0,
    color: tuple[float, float, float] = (0.4, 0.4, 0.45),
    label: str = "",
) -> str:
    """Write an axis-aligned box as VRML2. Units are millimetres.

    The box spans ``[cx-dx/2, cx+dx/2] x [cy-dy/2, cy+dy/2] x [z0, z0+dz]``.
    """
    cx, cy = center_xy
    x0, x1 = cx - dx / 2, cx + dx / 2
    y0, y1 = cy - dy / 2, cy + dy / 2
    za, zb = z0, z0 + dz

    verts = [
        (x0, y0, za), (x1, y0, za), (x1, y1, za), (x0, y1, za),
        (x0, y0, zb), (x1, y0, zb), (x1, y1, zb), (x0, y1, zb),
    ]
    faces = [
        (0, 1, 2, 3), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5),
        (2, 3, 7, 6), (3, 0, 4, 7),
    ]
    r, g, b = color
    pts = ",\n          ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts)
    idx = ",\n          ".join(f"{a} {b_} {c} {d} -1" for a, b_, c, d in faces)
    comment = f"# Finish 3D generated box: {label}\n" if label else ""
    body = f"""#VRML V2.0 utf8
{comment}Shape {{
  appearance Appearance {{
    material Material {{
      diffuseColor {r:.3f} {g:.3f} {b:.3f}
    }}
  }}
  geometry IndexedFaceSet {{
    coord Coordinate {{
      point [
          {pts}
      ]
    }}
    coordIndex [
          {idx}
    ]
  }}
}}
"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path
