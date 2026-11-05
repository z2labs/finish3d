"""Mandatory visual proof: kicad-cli pcb render (top + iso [+ section]).

Standing rule: never trust a result blind -- 3D/section renders are mandatory.
After resolving, this calls ``kicad-cli pcb render`` for top and iso PNGs into the
date-stamped report folder. Degrades gracefully: if ``kicad-cli`` is missing or
too old (``pcb render`` needs KiCad 8+), it returns no paths and a warning rather
than failing the run. On the cloud container (KiCad 7) this always no-ops -- all
KiCad-format rendering must happen on the G7/office machine.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path


def _have_cli(cfg) -> bool:
    return shutil.which(cfg.kicad_cli) is not None


def render_board(board_path: str, cfg) -> tuple[list, list]:
    warnings: list = []
    if not _have_cli(cfg):
        warnings.append(
            f"render skipped: '{cfg.kicad_cli}' not found "
            "(KiCad 8+ required; run renders on the G7/office machine)"
        )
        return [], warnings

    stamp = time.strftime("%Y-%m-%d")
    out_dir = Path(cfg.out_dir) / f"render-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    views = {
        "top": ["--side", "top", "--zoom", "1"],
        "iso": ["--rotate", "-45,0,45"],
    }
    paths: list = []
    for view, args in views.items():
        png = out_dir / f"{Path(board_path).stem}_{view}.png"
        cmd = [cfg.kicad_cli, "pcb", "render", "--output", str(png),
               "--quality", "high", *args, board_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if res.returncode == 0 and png.exists():
                paths.append(str(png))
            else:
                warnings.append(
                    f"render '{view}' failed (rc={res.returncode}): "
                    f"{(res.stderr or res.stdout).strip()[:200]}"
                )
        except (subprocess.SubprocessError, OSError) as exc:
            warnings.append(f"render '{view}' error: {exc}")
    return paths, warnings
