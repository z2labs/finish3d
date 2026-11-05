"""Resolution orchestrator: the offline-first chain, seat, verify, write-back.

Each footprint is resolved by the first source that returns a usable model.
``--offline`` (the default) skips the two networked sources so the chain falls
through to generation; stock + cache + generation need no network.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .board import Board, ModelRef
from .seat import seat_model, SeatTransform
from .verify import verify, VerifyResult
from .sources.base import ModelHit
from .sources.linked import Linked
from .sources.stock import Stock
from .sources.cache import Cache
from .sources.easyeda import EasyEDA
from .sources.github_libs import GithubLibs
from .sources.generate import Generate
from .sources.placeholder import Placeholder

# Chain order = handoff §3.2 resolution chain.
SOURCES = [Linked(), Stock(), Cache(), EasyEDA(), GithubLibs(), Generate(), Placeholder()]


@dataclass
class ResolveOutcome:
    fp: object
    hit: Optional[ModelHit]
    seat: Optional[SeatTransform]
    verify: Optional[VerifyResult]
    source: str
    rejected: list = field(default_factory=list)  # (source, reason)

    def to_report(self) -> dict:
        fp = self.fp
        rep = {
            "ref": getattr(fp, "ref", ""),
            "name": getattr(fp, "name", ""),
            "side": getattr(fp, "side", ""),
            "source": self.source,
        }
        if self.hit:
            rep["model"] = self.hit.path
            rep["license"] = self.hit.license
            rep["warnings"] = list(self.hit.warnings)
        if self.seat:
            rep["seat"] = {
                "offset": list(self.seat.offset),
                "rotate": list(self.seat.rotate),
                "scale": list(self.seat.scale),
            }
        if self.verify:
            rep["verify"] = {"pass": self.verify.ok, "checks": self.verify.checks,
                             "notes": self.verify.notes}
        if self.rejected:
            rep["rejected"] = [{"source": s, "reason": r} for s, r in self.rejected]
        return rep


def _apply_table_seat(hit: ModelHit, table: Optional[dict]) -> ModelHit:
    """Overlay the table's known-good seat transform onto a hit (handoff §4)."""
    if not table:
        return hit
    hit.base_offset = table["offset"]
    hit.base_rotate = table["rotate"]
    if table.get("scale"):
        hit.unit_scale = table["scale"][0]
    if table.get("license") and hit.license in ("unknown", "existing", "own (generated)"):
        hit.license = table["license"]
    if table.get("note"):
        hit.note = (hit.note + "; " if hit.note else "") + f"table:{table['note']}"
    return hit


def resolve_footprint(fp, cfg) -> ResolveOutcome:
    from . import tables
    from .sources import generators

    rejected: list = []
    table = tables.lookup(fp, cfg)

    # Table short-circuit for generated parts: deterministic, carries the seat.
    if table and table.get("source") == "generate" and table.get("locator"):
        gen = generators.by_locator(table["locator"])
        if gen is not None:
            out_dir = Path(cfg.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = fp.ref or fp.name.replace(":", "_") or "model"
            out_path = str(out_dir / f"{stem}.wrl")
            hit = gen(fp, cfg, out_path) or generators.generate_box(fp, cfg, out_path)
            if hit is not None:
                _apply_table_seat(hit, table)
                seat = seat_model(fp, hit)
                vr = verify(fp, hit, seat, cfg)
                if vr.ok:
                    return ResolveOutcome(fp, hit, seat, vr,
                                          source=f"table:{table['locator']}",
                                          rejected=rejected)
                rejected.append((f"table:{table['locator']}",
                                 f"verify failed: {vr.checks}"))

    for src in SOURCES:
        if cfg.offline and src.networked:
            continue
        hit = src.safe_find(fp, cfg)
        if not hit:
            continue
        _apply_table_seat(hit, table)
        seat = seat_model(fp, hit)
        vr = verify(fp, hit, seat, cfg)
        if vr.ok or getattr(src, "is_placeholder", False) or hit.is_placeholder:
            return ResolveOutcome(fp, hit, seat, vr, source=src.name,
                                  rejected=rejected)
        # verified-bad: remember and fall through
        rejected.append((src.name, f"verify failed: {vr.checks}"))
    # Placeholder always returns a hit, so this is unreachable in practice.
    return ResolveOutcome(fp, None, None, None, source="none", rejected=rejected)


@dataclass
class BoardReport:
    ok: bool
    footprints: list
    renders: list
    summary: dict
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "footprints": [o.to_report() for o in self.footprints],
            "renders": self.renders,
            "summary": self.summary,
            "warnings": self.warnings,
        }


def _writeback_model(board: Board, fp, outcome: ResolveOutcome, cfg) -> list[str]:
    """Copy the resolved model next to the board and set the (model) block."""
    warnings: list[str] = []
    if not outcome.hit or not board.path:
        return warnings
    board_dir = Path(board.path).resolve().parent
    models_dir = board_dir / "finish3d_models"
    models_dir.mkdir(parents=True, exist_ok=True)
    src = outcome.hit.path
    dst_name = f"{fp.ref or Path(src).stem}{os.path.splitext(src)[1]}"
    dst = models_dir / dst_name
    try:
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
    except OSError as exc:
        warnings.append(f"{fp.ref}: could not copy model ({exc})")
        return warnings
    seat = outcome.seat or SeatTransform()
    ref = ModelRef(
        path=f"${{KIPRJMOD}}/finish3d_models/{dst_name}",
        offset=seat.offset,
        scale=seat.scale,
        rotate=seat.rotate,
    )
    board.set_model(fp, ref)
    return warnings


def resolve_board(board_path: str, cfg) -> BoardReport:
    cfg.ensure_dirs()
    cfg._board_path = board_path  # for Linked ${KIPRJMOD} resolution
    board = Board.load(board_path)

    outcomes: list[ResolveOutcome] = []
    warnings: list[str] = []
    counts = {"linked": 0, "stock": 0, "cache": 0, "easyeda": 0,
              "github": 0, "generate": 0, "placeholder": 0, "none": 0}
    net_used = False

    for fp in board.footprints:
        outcome = resolve_footprint(fp, cfg)
        outcomes.append(outcome)
        counts[outcome.source] = counts.get(outcome.source, 0) + 1
        if outcome.source in ("easyeda", "github"):
            net_used = True
        if outcome.hit and outcome.hit.warnings:
            for w in outcome.hit.warnings:
                warnings.append(f"{fp.ref} ({fp.name}): {w}")
        if cfg.write_back:
            warnings += _writeback_model(board, fp, outcome, cfg)

    if cfg.write_back and board.path:
        out_board = board.save()
        warnings.append(f"wrote model links into {out_board}")

    renders: list[str] = []
    if cfg.render:
        from .render import render_board
        renders, render_warn = render_board(board_path, cfg)
        warnings += render_warn

    resolved = sum(v for k, v in counts.items()
                   if k not in ("placeholder", "none"))
    summary = {
        "resolved": resolved,
        "placeholder": counts.get("placeholder", 0),
        "missing": counts.get("none", 0),
        "net_used": net_used,
        "by_source": counts,
        "total": len(board.footprints),
    }
    ok = counts.get("none", 0) == 0
    return BoardReport(ok=ok, footprints=outcomes, renders=renders,
                       summary=summary, warnings=warnings)
