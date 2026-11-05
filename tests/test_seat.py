"""The rotate-then-mirror rule, exercised directly."""

import math

from finish3d.seat import SeatTransform, place_point, mirror_after_rotate


def test_top_side_is_identity_in_xy():
    seat = SeatTransform()
    x, y, z = place_point(2.0, 1.0, 0.5, seat, fp_rotation_deg=0.0, side="F.Cu")
    assert math.isclose(x, 2.0) and math.isclose(y, 1.0) and math.isclose(z, 0.5)


def test_bottom_side_mirrors_after_rotation_not_before():
    """A point at +X on a footprint rotated 90deg must land where rotate-then-
    mirror puts it, which differs from mirror-then-rotate."""
    seat = SeatTransform()
    # rotate-then-mirror (correct): rotate (1,0) by 90 -> (0,1); mirror y -> (0,-1)
    x, y, z = place_point(1.0, 0.0, 0.0, seat, fp_rotation_deg=90.0, side="B.Cu")
    assert math.isclose(x, 0.0, abs_tol=1e-9)
    assert math.isclose(y, -1.0, abs_tol=1e-9)

    # the wrong order (mirror first: (1,0)->(1,0), then rotate 90 -> (0,1))
    # would give y = +1; prove we are NOT doing that.
    assert not math.isclose(y, 1.0, abs_tol=1e-9)


def test_mirror_flips_y_and_z():
    assert mirror_after_rotate(3.0, 2.0, 1.0) == (3.0, -2.0, -1.0)
