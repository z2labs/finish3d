# Finish 3D — design notes

Distilled from the handoff `finish3d-3d-model-hero-spec-handoff-2026-11-05.md`. This is
the implementation's own record of *why* it is shaped the way it is.

## One library, three callers + GUI

`finish3d` is the single source of truth. Wrappers:

| Caller | Entry point |
|---|---|
| Engineer in KiCad | `Finish 3D` toolbar button (`kicad_action.py`) |
| Engineer / script, offline | `python -m finish3d <board>` (`cli.py`) |
| Another plugin / AI agent | `finish3d.api.handle(req) -> report`, or `python -m finish3d.api` (JSON stdin/stdout) |

## Module map

```
finish3d/
  board.py        position-aware S-expr reader + surgical (model) writeback
  model_io.py     WRL vertex bbox (stdlib), box writer, STEP bbox (optional OCP)
  seat.py         seat transform + the rotate-then-mirror rule, once
  verify.py       digital-twin checks + witness self-test
  tables.py       footprint_models.csv lookup (short-circuit + known-good seat)
  core.py         resolution orchestrator (the chain), writeback
  render.py       kicad-cli pcb render wrapper (graceful if absent)
  api.py          JSON API (in-process + stdin/stdout)
  cli.py          command line
  kicad_action.py KiCad 10 ActionPlugin (hand-test on the machine)
  sources/        Linked, Stock, Cache, EasyEDA, GithubLibs, Generate, Placeholder
  sources/generators/  box (stdlib) + bwsma / wurth_sma / generic_edge_sma (CadQuery)
  tables/         footprint_models.csv, vendor_repos.csv
```

## Why stdlib-only core

Offline must always work. The board reader/writer parses the `.kicad_pcb` S-expression
directly, so headless use needs no `pcbnew`. `pcbnew`/`kipy` are used *only* in the GUI
action plugin. `requests`/`easyeda2kicad` (net) and `cadquery` (STEP generation) are
optional extras — their absence degrades gracefully, never raises.

## Seat: the rotate-then-mirror trap

Two frames:

- **Local** (persisted): KiCad stores a per-model `(offset)(scale)(rotate)` in the
  footprint frame and applies the footprint `at` rotation + `B.Cu` side flip itself. So
  the transform we write never bakes in the footprint rotation or the flip — the board
  stays a normal board another tool can read.
- **World** (checked): to reproduce what KiCad draws, apply model transform → footprint
  Z-rotation → **then** the mirror for bottom parts. Rotate first, then mirror — never
  the reverse. `seat.place_point` / `seat.mirror_after_rotate` are the only home of that
  rule; `tests/test_seat.py` pins it.

## Verify: trust only what a witness trips

Extent checks run in the footprint-local frame (KiCad applies `at`/side equally to model
and courtyard, so local comparison isolates seating). Three checks, each proven by an
injected error it must catch:

| Check | Catches | Injected witness |
|---|---|---|
| `xy_extent` (coverage + centre) | wrong size, wrong rotation, offset | `rot90`, `offset_1mm`, `swap_model` |
| `scale_sane` (max-dim ratio) | mm/0.1mm/inch unit mistakes | `scale_254` |
| `upright` (Z half) | upside-down / wrong-side seat | `wrong_side` |

`finish3d selftest` must be 100% (baseline passes, all five injections caught) before
anything downstream is trusted. A check the self-test can't trip is dead weight — remove
it.

## Smart tables (knowledge as data)

`tables/footprint_models.csv` maps a footprint glob → source + known-good seat. A hit
short-circuits the chain and carries the verified transform, so repeat parts are instant
and deterministic. `tables/vendor_repos.csv` drives the networked GitHub/vendor source.
The cache `index.json` lets a second board reuse a model with no network.

## Open questions carried from the handoff (§9) — current defaults

- **Network default:** OFF (opt-in per run via `--online` / `offline:false`). Change in
  `config.Config.offline`.
- **Licensing:** resolve freely; only redistribute/commit models with a confirmed
  permissive/own license (`config.redistributable_licenses`); everything else cache-only.
- **Chain priority:** generation before placeholder (a missing part becomes a generated
  body, with placeholder as the loud floor). Flip by reordering `core.SOURCES`.

These are deliberately one-line changes pending Zoltan's confirmation.
