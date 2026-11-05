#!/usr/bin/env python3
"""Build the KiCad PCM (Plugin and Content Manager) installer zip.

Archive layout (KiCad PCM spec):

    finish3d-<ver>-pcm.zip
    |- metadata.json            (package manifest, at the archive root)
    |- plugins/
    |   |- __init__.py          (loads + registers the action plugin)
    |   `- finish3d/            (the full library package, incl. tables/*.csv)
    `- resources/
        `- icon.png             (64x64, shown in the PCM listing)

Install in KiCad: Plugin and Content Manager -> Install from File... -> pick the
zip. Then press the "Finish 3D" toolbar button (needs KiCad 9/10).

Also prints download_sha256 / download_size / install_size so the package can
later be published to a PCM repository (packages.json).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", "*.egg-info", ".pytest_cache",
    "icon_256.png",
)

PLUGINS_INIT = '''\
"""KiCad PCM entry point: put the bundled package on the path and register.

KiCad imports this file from the installed plugins directory. We add this folder
to sys.path so ``import finish3d`` resolves to the bundled package, then import
the action plugin, which registers the "Finish 3D" toolbar button on import.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    import finish3d.kicad_action  # noqa: F401  (registers the ActionPlugin)
except Exception:  # pragma: no cover - surface load errors in KiCad's log
    import traceback
    traceback.print_exc()
'''


def _version() -> str:
    meta = json.load(open(os.path.join(REPO, "metadata.json")))
    return meta["versions"][0]["version"]


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def build() -> str:
    # 1) make sure the icon is current
    import subprocess
    subprocess.run([sys.executable, os.path.join(HERE, "make_icon.py")], check=True)

    ver = _version()
    stage = os.path.join(HERE, "_stage")
    if os.path.exists(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    # 2) metadata.json at root
    shutil.copy2(os.path.join(REPO, "metadata.json"),
                 os.path.join(stage, "metadata.json"))

    # 3) plugins/ : loader + the bundled package
    plugins = os.path.join(stage, "plugins")
    os.makedirs(plugins)
    with open(os.path.join(plugins, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write(PLUGINS_INIT)
    shutil.copytree(os.path.join(REPO, "finish3d"),
                    os.path.join(plugins, "finish3d"), ignore=_IGNORE)

    # 4) resources/
    res = os.path.join(stage, "resources")
    os.makedirs(res)
    shutil.copy2(os.path.join(REPO, "resources", "icon.png"),
                 os.path.join(res, "icon.png"))

    install_size = _dir_size(stage)

    # 5) zip it (deterministic order)
    dist = os.path.join(REPO, "dist")
    os.makedirs(dist, exist_ok=True)
    zip_path = os.path.join(dist, f"finish3d-{ver}-pcm.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            for f in sorted(files):
                full = os.path.join(root, f)
                arc = os.path.relpath(full, stage)
                zf.write(full, arc)

    import sys as _sys  # noqa
    data = open(zip_path, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    shutil.rmtree(stage)

    print(f"\nBuilt {zip_path}")
    print(f"  download_size:  {len(data)}")
    print(f"  download_sha256:{sha}")
    print(f"  install_size:   {install_size}")
    return zip_path


if __name__ == "__main__":
    import sys
    build()
