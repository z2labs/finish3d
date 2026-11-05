#!/usr/bin/env python3
"""Build a self-hostable KiCad PCM repository for Finish 3D.

Given the built installer zip, this emits (into ``dist/pcm-repo/``):

    packages.json     the package list (metadata + versions[] with download_url,
                      download_sha256, download_size, install_size)
    resources.zip     icons for the PCM UI: <identifier>/icon.png
    repository.json    the "Add repository" entry point, pointing at the two above

All three are meant to be uploaded as assets of the GitHub release whose tag is
RELEASE_TAG, so the URLs are stable release-asset URLs. Users then add the
repository.json URL in KiCad: Plugin and Content Manager -> Manage... -> add the
URL. The same metadata (versions[] with download fields) is what the official
KiCad addons repository needs for submission.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

OWNER = "z2labs"
NAME = "finish3d"
RELEASE_TAG = "v0.1.0"
BRANCH = "main"

# Two hosting modes:
#   raw     -> committed under pcm/ on the branch, served via raw.githubusercontent
#              (works immediately, no GitHub release needed)
#   release -> served as assets of the GitHub release RELEASE_TAG (for the official
#              submission; create the release + upload the assets separately)
HOSTS = {
    "raw": (
        os.path.join(REPO, "pcm"),
        f"https://raw.githubusercontent.com/{OWNER}/{NAME}/{BRANCH}/pcm/",
        True,   # copy the installer zip into the output dir
    ),
    "release": (
        os.path.join(REPO, "dist", "pcm-repo"),
        f"https://github.com/{OWNER}/{NAME}/releases/download/{RELEASE_TAG}/",
        False,
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_install_size(zip_path: str) -> int:
    with zipfile.ZipFile(zip_path) as zf:
        return sum(i.file_size for i in zf.infolist())


def build(host: str = "raw") -> dict:
    if host not in HOSTS:
        raise SystemExit(f"host must be one of {list(HOSTS)}")
    out, BASE, copy_zip = HOSTS[host]

    ver_meta = json.load(open(os.path.join(REPO, "metadata.json")))
    version = ver_meta["versions"][0]["version"]
    zip_name = f"{NAME}-{version}-pcm.zip"
    zip_path = os.path.join(REPO, "dist", zip_name)
    if not os.path.exists(zip_path):
        raise SystemExit("build the installer first: python3 packaging/make_pcm.py")

    os.makedirs(out, exist_ok=True)
    if copy_zip:
        shutil.copy2(zip_path, os.path.join(out, zip_name))

    now = int(time.time())
    now_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now))

    # ---- package object = metadata + download fields on the version ----
    zip_bytes = open(zip_path, "rb").read()
    pkg = {
        "$schema": ver_meta["$schema"],
        "name": ver_meta["name"],
        "description": ver_meta["description"],
        "description_full": ver_meta["description_full"],
        "identifier": ver_meta["identifier"],
        "type": ver_meta["type"],
        "author": ver_meta["author"],
        "maintainer": ver_meta["maintainer"],
        "license": ver_meta["license"],
        "resources": ver_meta["resources"],
        "tags": ver_meta["tags"],
        "versions": [{
            **ver_meta["versions"][0],
            "download_url": BASE + zip_name,
            "download_sha256": _sha256(zip_bytes),
            "download_size": len(zip_bytes),
            "install_size": _zip_install_size(zip_path),
        }],
    }
    packages = {"packages": [pkg]}
    packages_bytes = json.dumps(packages, indent=2).encode("utf-8")
    with open(os.path.join(out, "packages.json"), "wb") as fh:
        fh.write(packages_bytes)

    # per-package metadata.json for the OFFICIAL KiCad addons repo submission
    # (gitlab.com/kicad/addons/metadata -> packages/<identifier>/metadata.json)
    with open(os.path.join(out, "metadata-submission.json"), "w",
              encoding="utf-8") as fh:
        json.dump(pkg, fh, indent=2)

    # ---- resources.zip: <identifier>/icon.png ----
    res_path = os.path.join(out, "resources.zip")
    icon = os.path.join(REPO, "resources", "icon.png")
    with zipfile.ZipFile(res_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(icon, f"{ver_meta['identifier']}/icon.png")
    res_bytes = open(res_path, "rb").read()

    # ---- repository.json (the "Add repository" URL target) ----
    repository = {
        "$schema": "https://go.kicad.org/pcm/schemas/v1",
        "name": "Finish 3D (Z2Labs) PCM repository",
        "maintainer": ver_meta["maintainer"],
        "packages": {
            "url": BASE + "packages.json",
            "sha256": _sha256(packages_bytes),
            "update_time_utc": now_utc,
            "update_timestamp": now,
        },
        "resources": {
            "url": BASE + "resources.zip",
            "sha256": _sha256(res_bytes),
            "update_time_utc": now_utc,
            "update_timestamp": now,
        },
    }
    with open(os.path.join(out, "repository.json"), "w", encoding="utf-8") as fh:
        json.dump(repository, fh, indent=2)

    print(f"[host={host}] wrote repo files to {out}")
    print("\nAdd-repository URL:")
    print("  " + BASE + "repository.json")
    return {"zip": zip_path, "out": out, "base": BASE,
            "assets": [zip_path,
                       os.path.join(out, "packages.json"),
                       res_path,
                       os.path.join(out, "repository.json")]}


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "raw"
    build(host)
