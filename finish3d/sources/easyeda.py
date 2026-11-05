"""Source 4: EasyEDA / LCSC (networked, opt-in).

Resolves by LCSC part number ``C######`` taken from a footprint field, following
the easyeda2kicad approach: fetch the component, extract its 3D model, convert to
STEP+WRL and deposit it in the cache. Networked, so it is skipped when
``cfg.offline`` is True (the default).

This module is dependency-tolerant: if neither ``easyeda2kicad`` nor ``requests``
is available, or the network is unreachable, ``find`` returns ``None`` and the
chain falls through to generation -- it never raises.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from .base import ModelHit, Source
from . import cache as cache_mod

_EASYEDA_API = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"


class EasyEDA(Source):
    name = "easyeda"
    networked = True

    def find(self, fp, cfg) -> Optional[ModelHit]:
        lcsc = fp.lcsc.strip().upper()
        if not lcsc or not lcsc.startswith("C") or not lcsc[1:].isdigit():
            return None

        # Preferred path: the maintained easyeda2kicad package does the full
        # component -> STEP/WRL conversion and unit handling for us.
        hit = self._via_easyeda2kicad(fp, cfg, lcsc)
        if hit:
            return hit
        return self._via_api(fp, cfg, lcsc)

    def _via_easyeda2kicad(self, fp, cfg, lcsc) -> Optional[ModelHit]:
        try:  # pragma: no cover - optional dependency + network
            from easyeda2kicad.easyeda.easyeda_api import EasyedaApi  # type: ignore
            from easyeda2kicad.easyeda.easyeda_importer import (  # type: ignore
                Easyeda3dModelImporter,
            )
            from easyeda2kicad.kicad.export_kicad_3d_model import (  # type: ignore
                Exporter3dModelKicad,
            )
        except Exception:
            return None
        try:  # pragma: no cover - network
            data = EasyedaApi().get_cad_data_of_component(lcsc_id=lcsc)
            if not data:
                return None
            model = Easyeda3dModelImporter(
                easyeda_cp_cad_data=data, download_raw_3d_model=True
            ).output
            if model is None:
                return None
            out_base = os.path.join(cfg.cache_dir, lcsc)
            os.makedirs(cfg.cache_dir, exist_ok=True)
            exporter = Exporter3dModelKicad(model=model)
            exporter.export(lib_path=out_base)
            wrl = out_base + ".wrl"
            step = out_base + ".step"
            src_file = wrl if os.path.exists(wrl) else (
                step if os.path.exists(step) else None)
            if not src_file:
                return None
            return cache_mod.put(
                cfg, fp, src_file, source=self.name,
                license="EasyEDA/LCSC (per-part terms; cache-only unless cleared)",
                note=f"easyeda2kicad {lcsc}",
            )
        except Exception:
            return None

    def _via_api(self, fp, cfg, lcsc) -> Optional[ModelHit]:
        """Last-ditch direct fetch if easyeda2kicad is absent. Best effort."""
        try:  # pragma: no cover - optional dependency + network
            import requests  # type: ignore
        except Exception:
            return None
        try:  # pragma: no cover - network
            r = requests.get(_EASYEDA_API.format(lcsc=lcsc), timeout=15)
            if r.status_code != 200:
                return None
            # The raw 3D payload handling (OBJ -> WRL/STEP) is non-trivial and
            # lives properly in easyeda2kicad; without it we only confirm the
            # part exists and defer. Returning None lets generation take over.
            return None
        except Exception:
            return None
