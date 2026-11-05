# Packaging Finish 3D for KiCad (PCM)

## Build the installer zip

```bash
python3 packaging/make_pcm.py
```

This (re)generates the icon and writes `dist/finish3d-<version>-pcm.zip`, then
prints the `download_sha256`, `download_size` and `install_size` you need to
publish it to a PCM repository later.

Archive layout (KiCad PCM spec):

```
finish3d-<ver>-pcm.zip
├── metadata.json          package manifest (archive root)
├── plugins/
│   ├── __init__.py        loader: puts the bundled package on sys.path + registers
│   └── finish3d/          the full library, incl. tables/*.csv and icon.png
└── resources/
    └── icon.png           64×64, shown in the PCM listing
```

## Install in KiCad (9 / 10)

1. **Tools → Plugin and Content Manager**
2. **Install from File…**
3. Pick `finish3d-<version>-pcm.zip`, then **Apply**.
4. In the PCB editor, press the **Finish 3D** toolbar button (3D-IC icon), or find
   it under the external plugins menu.

`kicad-cli pcb render` (for the render step) needs KiCad 8+. The icon is the
isometric 3D IC.

## The icon

`packaging/make_icon.py` draws the isometric 3D IC chip (dark body, gold gull-wing
leads, teal pin-1 dot) at 8× supersample and writes:

- `resources/icon.png` — 64×64, the PCM listing icon
- `finish3d/icon.png` — 64×64, the toolbar-button icon (`kicad_action.py` points at it)
- `resources/icon_256.png` — 256×256, for docs/readme (not committed)

Re-run `make_icon.py` to regenerate after any tweak.

## Publishing to a PCM repository (optional, later)

To let users install via an "Add repository" URL instead of a file, host a
`repository.json` + `packages.json` (with a `versions[].download_url` pointing at a
released zip, plus the `download_sha256` / `download_size` / `install_size` printed
by `make_pcm.py`). A GitHub Release asset is the usual home for the zip.
```
