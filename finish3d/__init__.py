"""Finish 3D -- autonomous 3D-model resolution, seating and verification for KiCad.

Core is stdlib-only so headless/offline use never needs pcbnew, requests or a CAD
kernel. Optional extras: ``requests`` (networked sources), ``cadquery`` (STEP
generation + STEP bbox verification).
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
