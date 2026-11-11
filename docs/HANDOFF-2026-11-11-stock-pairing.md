# Finish 3D: stock pairing + unit fixes, found on the Spacewalker LNA board (2026-11-11)

Branch: `fix/stock-pairing` (off `main` @ 732e165). Not merged, no PR opened.

## Why

Running `python -m finish3d SWL434_1v4.kicad_pcb --write-back` on a Windows box
(HP ProBook G7, KiCad 10 with the stock 3D library, plain PowerShell, no KiCad
GUI) produced 46/53 "resolved" with verify passing, yet the render was one big
grey block. Every footprint had fallen through to the box generator. The board
is an Eagle import, so footprint names are Eagle/IPC style (`CAP_0402`,
`RESC1005X40_0402`, `SON50P200X200X95-9N`, `BMI-S-202-F_43799422`).

## Root causes and what this branch changes

1. **Stock library not found on Windows** (`sources/stock.py`).
   `KICADn_3DMODEL_DIR` only exists inside a running KiCad, and the default
   root was `C:/Program Files/KiCad/share/...` while real installs are
   versioned (`.../KiCad/10.0/share/kicad/3dmodels`). Added glob roots, sorted
   by numeric version (plain string sort puts 9.0 above 10.0).

2. **Exact `Lib:Name` matching only** (`sources/stock.py`).
   Added `alias_candidates()`: normalises non-KiCad names to stock names.
   - chip parts: kind from the name (RESC/CAP/IND/LQW/WE-KI/BEAD/LED/DIO...),
     size from an IPC metric code (`RESC1005X40` -> `0402_1005Metric`) or an
     imperial 4-digit token
   - IPC no-lead packages: `SON50P200X200X95-9N` ->
     `DFN-8-1EP_2x2mm_P0.5mm*` (glob, first hit)
   Also: a `footprint_models.csv` row with `source=stock` and a
   `Lib.3dshapes/Name` locator now pins a pairing explicitly.

3. **WRL unit convention** (`model_io.py`).
   KiCad renders one VRML unit as 0.1 inch. `wrl_vertex_bbox` returned raw
   numbers as if they were mm, so real stock WRL models measured 2.54x too
   small and failed `xy_extent` (0402 caps scraped through at cover 0.35,
   resistors/inductors/ICs were rejected). `write_box_wrl` wrote mm, so
   generated boxes rendered 2.54x too large. Both now convert; the module
   speaks mm everywhere.

4. **Y axis sign** (`sources/generators/box.py`, `verify.py`).
   Footprint-local Y points down, model Y points up. Boxes for footprints whose
   origin is not at the centre (e.g. the shield frame, origin at a corner) were
   mirrored to the wrong side. Box centre and the verify centre check now use
   `-y`.

5. **Extension order** (`sources/stock.py`). KiCad 10 ships STEP only; without
   CadQuery a STEP cannot be measured and verify fails. The search now prefers
   a `.wrl` from any installed KiCad version before a `.step`.

`python -m finish3d selftest` is 100% on the branch. `pytest` was NOT run
(not installed on that machine) - please run the suite and the corpus
round-trip before merging. The WRL unit change will shift numbers in any test
that reads raw WRL coordinates.

## Result on SWL434_1v4

30 of 53 footprints now get the stock model (16 C, 6 R, 6 L, 2 DFN ICs).

## Still open (not in this branch)

- **LED-0603**: stock model found, rejected by verify because the Eagle
  footprint is drawn along Y (needs rotate z=90). The seat step never tries
  90-degree rotations.
- **BEADC4532X350N**: `L_1812_4532Metric` found, rejected at `cover_y` 1.64 vs
  the 1.6 limit. No courtyard on the footprint, so the pad span is the
  reference and it is tight.
- **Graphics-only footprints** (CE / UKCA / Pb / recycle logos, REF marks,
  solder jumpers, test points) get placeholder or generated boxes. A footprint
  with no pads, or only a bare pad, should get no model at all.
- **Edge SMA / USB-C**: the name gives no exact part. On this board
  `SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount` (rotate z=-90) and
  `USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal` (rotate 0) seat
  correctly; candidates for table rows.
- **No model exists in KiCad** for the Laird BMI-S-202 shield frame/cover or a
  3x3 mm 6-pad SAW package (there is no `RF_Shielding.3dshapes`). The online
  sources need an LCSC number or a vendor row; this board has neither. For the
  campaign render these three were modelled by hand in CadQuery.
- **Generated box for a shield frame is a solid block** hiding everything
  inside. Frames/cans need a hollow generator, or should be skipped.
- **verify passes boxes by construction**: a generated box always "fits" the
  footprint it was derived from, so 46/53 "resolved" said nothing about the
  result being usable. The summary line should count generated boxes
  separately from real models.
- `--render` reports "kicad-cli not found" on Windows for the same reason as
  (1): it is not on PATH; look under `C:/Program Files/KiCad/*/bin/`.
