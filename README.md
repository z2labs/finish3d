# Finish 3D

Autonomously resolve, seat and verify 3D models on KiCad footprints — **offline-first**,
callable from the GUI, the CLI, and by other plugins or an AI agent.

> Designed by Z2Labs and Rapid Proto Woerk Kft.

One library (`finish3d`) is the single source of truth; the GUI button, the CLI and
the JSON API are thin wrappers over it.

## What it does

For every footprint on a board, Finish 3D walks an **offline-first resolution chain**
and uses the first source that returns a usable model:

1. **Already linked** — an existing `(model …)` that resolves on disk.
2. **KiCad stock** — the `packages3D` libraries, matched by `Lib:Name`.
3. **Local cache** — `~/.finish3d/cache/`, keyed by MPN / LCSC / footprint hash.
4. **EasyEDA / LCSC** — by `C######` part number *(networked, opt-in)*.
5. **GitHub / vendor libraries** — a curated repo table *(networked, opt-in)*.
6. **Parametric generation** — a CadQuery datasheet body, or a stdlib
   courtyard-extruded box when CadQuery isn't installed.
7. **Placeholder** — a labelled box sized to the courtyard, always emitted with a
   `MODEL_MISSING` warning so the gap is loud.

Only steps 4–5 touch the network. The default is **offline** (`--offline`); add
`--online` to enable the networked sources.

Each resolved model is **seated** (the rotate-then-mirror transform lives in one place)
and **verified** against the footprint courtyard read straight from the `.kicad_pcb`
(an independent source). Verification is only trusted because a **witness self-test**
injects known errors (90° rotation, wrong side, 25.4× scale, 1 mm offset, swapped
model) and requires every one to be caught.

## Install (development)

```bash
pip install -e .            # core, stdlib-only
pip install -e ".[net]"     # + EasyEDA/LCSC + GitHub sources
pip install -e ".[gen]"     # + CadQuery parametric STEP generation
pip install -e ".[dev]"     # + pytest
```

## Use

### CLI

```bash
python -m finish3d board.kicad_pcb --offline --render
python -m finish3d board.kicad_pcb --online --write-back --out out/
python -m finish3d selftest
```

### GUI (KiCad 9 / 10) — PCM installer

Build the installer zip and install it from KiCad:

```bash
python3 packaging/make_pcm.py          # -> dist/finish3d-<ver>-pcm.zip
```

In KiCad: **Tools → Plugin and Content Manager → Install from File…**, pick the zip,
then press the **Finish 3D** toolbar button (the 3D-IC icon). `pcb render` needs
KiCad 8+. See `docs/PACKAGING.md`.

### From another plugin or an AI agent

```python
from finish3d.api import handle
report = handle({"op": "resolve_board", "board": "board.kicad_pcb", "offline": True})
```

Or language-agnostic over stdin/stdout:

```bash
echo '{"op":"resolve_board","board":"board.kicad_pcb"}' | python -m finish3d.api
```

One request in, one report out — no hidden state.

## Self-test

```bash
python -m finish3d selftest      # must be 100% before trusting anything
```

## Status

v0.1.0 — core (board I/O, seat, verify, selftest, resolution chain, tables, CLI, JSON
API) is implemented and tested offline. The CadQuery datasheet generators and the KiCad
10 GUI button need on-machine reconciliation and hand-testing (see
`docs/MACHINE_CHECKLIST.md`).

## License

GPL-3.0-or-later. Downloaded/generated models are redistributed **only** when their
license is confirmed permissive or own; everything else stays in the local cache.
