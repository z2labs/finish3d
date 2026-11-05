"""Source protocol + the ModelHit record passed down the resolution chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelHit:
    """A resolved model, found by one source, not yet verified."""
    path: str                                   # local file path (.wrl/.step)
    source: str                                 # source name
    base_offset: tuple = (0.0, 0.0, 0.0)        # mm, model->footprint origin
    base_rotate: tuple = (0.0, 0.0, 0.0)        # degrees
    unit_scale: float = 1.0                     # 1.0 if model already in mm
    license: str = "unknown"
    note: str = ""
    warnings: list = field(default_factory=list)
    is_placeholder: bool = False


class Source:
    """Base class. ``find`` must never raise -- it returns a ModelHit or None."""

    name: str = "base"
    networked: bool = False
    is_placeholder: bool = False

    def find(self, fp, cfg) -> Optional[ModelHit]:  # pragma: no cover - abstract
        raise NotImplementedError

    # safety wrapper used by the orchestrator so a flaky source can't kill a run
    def safe_find(self, fp, cfg) -> Optional[ModelHit]:
        try:
            return self.find(fp, cfg)
        except Exception as exc:  # noqa: BLE001 - sources must be resilient
            return None
