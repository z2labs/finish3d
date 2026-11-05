# Becoming an official KiCad PCM plugin

Finish 3D is already **PCM-compatible**: it installs from the release zip
("Install from File…") and from the self-hosted repository (below). Getting it into
the **official** KiCad Plugin and Content Manager list is a separate, one-time
submission to the KiCad addons metadata repository.

## 0. Prerequisites (done by the release)

- A published GitHub Release with the installer zip as an asset, so the package has
  a stable `download_url`.
- A schema-valid `metadata.json` whose `versions[]` entry carries `download_url`,
  `download_sha256`, `download_size` and `install_size`. `packaging/make_repo.py`
  emits exactly this as `dist/pcm-repo/metadata-submission.json`.
- `status` should be `stable` (or `testing`) for the official list — `development`
  packages are hidden unless the user opts in. Bump it when the GUI has been
  hand-tested on the machine.

## 1. Self-hosted repository (works today, no KiCad approval needed)

Users add this URL in KiCad → **Plugin and Content Manager → Manage… → add**:

```
https://github.com/z2labs/finish3d/releases/download/v0.1.0/repository.json
```

That `repository.json` points at `packages.json` + `resources.zip` (both release
assets). This is the fastest path and is fully under our control.

## 2. Official repository submission

1. Fork **https://gitlab.com/kicad/addons/metadata**.
2. Add the package metadata at:
   ```
   packages/com.github.z2labs.finish3d/metadata.json
   ```
   Use `dist/pcm-repo/metadata-submission.json` (the per-package object with the
   download fields filled in). Keep the `identifier` = `com.github.z2labs.finish3d`.
3. Make sure the release asset `download_url` is public and the `download_sha256` /
   sizes match the uploaded zip exactly (regenerate with `make_repo.py` if the zip
   is rebuilt — the sha changes every build).
4. Open a merge request. KiCad CI validates the metadata against the schema and the
   download hash. Address any CI feedback.
5. Once merged, Finish 3D appears in every KiCad user's PCM list under the default
   repository — no "Add repository" step needed.

## Re-releasing a new version

1. Bump `version` in `metadata.json` (and `status` when appropriate).
2. `python3 packaging/make_pcm.py` then `python3 packaging/make_repo.py`.
3. Tag `vX.Y.Z`, push, create the GitHub release, upload the four assets
   (`finish3d-X.Y.Z-pcm.zip`, `packages.json`, `resources.zip`, `repository.json`).
4. For the official repo: add a new entry to the `versions[]` array in the submitted
   `metadata.json` via a new merge request (keep old versions listed).
