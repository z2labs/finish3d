"""Run configuration for Finish 3D.

Defaults are **offline-first**: ``offline=True`` so a plain run never touches the
network. Networked sources (EasyEDA/LCSC, GitHub vendor libs) are opt-in per run
via ``--online`` / ``offline=False`` in the API request. This matches the
recommendation in the handoff §9 (resolve freely offline; only reach out when
asked) and the standing "mostly offline" goal -- stock + cache + generation need
no network at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_cache() -> str:
    return os.environ.get("FINISH3D_CACHE", str(Path.home() / ".finish3d" / "cache"))


def _tables_dir() -> str:
    return str(Path(__file__).resolve().parent / "tables")


@dataclass
class Config:
    # network
    offline: bool = True

    # outputs
    render: bool = False
    write_back: bool = False
    out_dir: str = "out"
    cache_dir: str = field(default_factory=_default_cache)
    tables_dir: str = field(default_factory=_tables_dir)

    # verify tolerances (mm / ratios)
    xy_tol_mm: float = 1.0
    z_tol_mm: float = 0.05
    cover_lo: float = 0.3
    cover_hi: float = 1.6
    scale_lo: float = 0.2
    scale_hi: float = 5.0

    # tooling
    kicad_cli: str = field(
        default_factory=lambda: os.environ.get("FINISH3D_KICAD_CLI", "kicad-cli")
    )

    # licensing: only redistribute/commit models whose license is in this set;
    # everything else stays in the local cache only (handoff §7.1, §9).
    redistributable_licenses: tuple = (
        "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "MIT", "BSD-3-Clause",
        "Apache-2.0", "GPL-3.0-or-later", "own",
    )

    @classmethod
    def from_request(cls, req: dict) -> "Config":
        cfg = cls()
        for key in (
            "offline", "render", "write_back", "out_dir", "cache_dir",
            "tables_dir", "xy_tol_mm", "z_tol_mm", "kicad_cli",
        ):
            if key in req and req[key] is not None:
                setattr(cfg, key, req[key])
        return cfg

    def ensure_dirs(self) -> None:
        Path(self.out_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
