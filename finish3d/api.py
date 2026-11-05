"""JSON API for other plugins (srouter, Eagle Exhumer) and AI agents.

Two ways in, same contract -- one request dict in, one report dict out, no hidden
state:

* in-process:  ``finish3d.api.handle(request) -> report``
* stdin/stdout: ``python -m finish3d.api``  (reads one JSON request, writes one
  JSON report). Language- and process-agnostic, MCP-style, matching srouter's
  MCP server pattern.

Request::

    {
      "op": "resolve_board" | "resolve_footprint" | "selftest",
      "board": "/path/board.kicad_pcb",      # resolve_board
      "footprint": { "name": "...", "mpn": "", "lcsc": "C123",
                     "courtyard": [[x,y],...], "pads": [...],
                     "side": "F.Cu", "at": [x,y,rot] },   # resolve_footprint
      "offline": true, "render": false, "write_back": false,
      "cache_dir": "~/.finish3d/cache", "out_dir": "out/"
    }

Report::

    { "ok": bool, "footprints": [...], "renders": [...], "summary": {...},
      "warnings": [...] }
"""

from __future__ import annotations

import json
import sys
from typing import Optional

from .board import BBox, Footprint, ModelRef
from .config import Config


def _footprint_from_request(spec: dict) -> Footprint:
    cy = BBox()
    for pt in spec.get("courtyard", []) or []:
        if len(pt) >= 2:
            cy.add(float(pt[0]), float(pt[1]))
    pad = BBox()
    for p in spec.get("pads", []) or []:
        # accept [x,y,w,h] or {"at":[x,y],"size":[w,h]}
        if isinstance(p, dict):
            at = p.get("at", [0, 0]); sz = p.get("size", [0, 0])
            x, y = float(at[0]), float(at[1])
            w, h = float(sz[0]), float(sz[1])
        else:
            x, y = float(p[0]), float(p[1])
            w = float(p[2]) if len(p) > 2 else 0.0
            h = float(p[3]) if len(p) > 3 else 0.0
        pad.add(x - w / 2, y - h / 2)
        pad.add(x + w / 2, y + h / 2)
    at = spec.get("at", [0.0, 0.0, 0.0])
    model = None
    if spec.get("model"):
        model = ModelRef(path=spec["model"])
    fields = dict(spec.get("fields", {}) or {})
    if spec.get("mpn"):
        fields.setdefault("MPN", spec["mpn"])
    if spec.get("lcsc"):
        fields.setdefault("LCSC", spec["lcsc"])
    return Footprint(
        name=spec.get("name", ""),
        ref=spec.get("ref", spec.get("name", "FP")),
        at=(float(at[0]), float(at[1]) if len(at) > 1 else 0.0),
        rotation_deg=float(at[2]) if len(at) > 2 else 0.0,
        side=spec.get("side", "F.Cu"),
        courtyard=cy,
        pad_span=pad,
        fields=fields,
        model=model,
    )


def handle(request: dict) -> dict:
    """Process one request, return one report dict. Never raises for op errors."""
    op = request.get("op", "resolve_board")
    cfg = Config.from_request(request)

    try:
        if op == "selftest":
            from .verify import run_selftest
            return run_selftest(cfg).as_dict()

        if op == "resolve_footprint":
            from .core import resolve_footprint
            spec = request.get("footprint") or {}
            fp = _footprint_from_request(spec)
            cfg.ensure_dirs()
            cfg._board_path = None
            outcome = resolve_footprint(fp, cfg)
            return {"ok": bool(outcome.hit), "footprints": [outcome.to_report()],
                    "renders": [], "summary": {"total": 1,
                    "source": outcome.source}, "warnings": []}

        if op == "resolve_board":
            from .core import resolve_board
            board = request.get("board")
            if not board:
                return {"ok": False, "error": "resolve_board requires 'board'"}
            return resolve_board(board, cfg).to_dict()

        return {"ok": False, "error": f"unknown op: {op!r}"}
    except Exception as exc:  # noqa: BLE001 - API must always answer
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main(argv: Optional[list] = None) -> int:
    raw = sys.stdin.read()
    try:
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        json.dump({"ok": False, "error": f"invalid JSON: {exc}"}, sys.stdout)
        sys.stdout.write("\n")
        return 2
    report = handle(request)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
