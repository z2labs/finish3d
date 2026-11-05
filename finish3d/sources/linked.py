"""Source 1: already-linked model that resolves on disk."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import ModelHit, Source


def resolve_model_path(raw: str, board_path: Optional[str]) -> Optional[str]:
    """Resolve a KiCad model path, expanding ${KIPRJMOD} and env vars."""
    if not raw:
        return None
    p = raw
    if "${KIPRJMOD}" in p and board_path:
        p = p.replace("${KIPRJMOD}", str(Path(board_path).resolve().parent))
    p = os.path.expandvars(os.path.expanduser(p))
    if os.path.isabs(p) and os.path.exists(p):
        return p
    # relative to the board
    if board_path:
        cand = Path(board_path).resolve().parent / p
        if cand.exists():
            return str(cand)
    return p if os.path.exists(p) else None


class Linked(Source):
    name = "linked"
    networked = False

    def find(self, fp, cfg) -> Optional[ModelHit]:
        if not fp.model or not fp.model.path:
            return None
        board_path = getattr(cfg, "_board_path", None)
        resolved = resolve_model_path(fp.model.path, board_path)
        if not resolved or not os.path.exists(resolved):
            return None
        return ModelHit(
            path=resolved,
            source=self.name,
            base_offset=fp.model.offset,
            base_rotate=fp.model.rotate,
            unit_scale=fp.model.scale[0] if fp.model.scale else 1.0,
            license="existing",
            note="existing (model) link resolved on disk",
        )
