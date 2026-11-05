# Finish 3D — on-machine live-build checklist (G7 / office)

The cloud session built and tested the stdlib core offline. These steps need the
G7/office machine with KiCad 10 (the cloud only has KiCad 7, which can't read 9/10
format — all KiCad-format render/DRC runs there). Standing rules apply: hand-tested live
GUI with screenshots, machine-reservation telemetry, feature branches, date-stamped
folders, English docs, push to own/private repos only.

1. **Repo.** Create `z2labs/finish3d`, push this scaffold. (README, `pyproject.toml`,
   PCM `metadata.json`, GPL-3.0 `LICENSE`, module tree — all present.)

2. **Fold in the real generators.** Replace the reconstructed geometry in
   `finish3d/sources/generators/{bwsma,wurth_sma,generic_edge_sma}.py` with the
   verified `twin/bwsma_model.py`, the Würth WR-SMA model, and the generic edge-SMA.
   Keep the `generate(fp, cfg, out_path) -> ModelHit | None` signature. Re-check the
   BWSMA leg gap fits a 1.6 mm board without overlap.

3. **Core** is already implemented (board reader/writer, resolver chain, seat, verify).
   Sanity-run `python -m pytest` on the machine too.

4. **Self-test must be 100%** before anything else:
   ```bash
   python -m finish3d selftest
   ```

5. **Offline run on a real board** (an srouter output or an Eagle Exhumer import):
   ```bash
   python -m finish3d board.kicad_pcb --offline --render --write-back
   ```
   Eyeball the top/iso PNGs on the G7. Confirm the written `(model)` links load in the
   KiCad 3D viewer.

6. **Networked run** on parts stock lacks:
   ```bash
   pip install -e ".[net]"
   python -m finish3d board.kicad_pcb --online --write-back
   ```
   Confirm EasyEDA/LCSC + GitHub sources resolve and that each hit's license is recorded
   in the cache `index.json`.

7. **KiCad 10 GUI button.** Install the PCM package, press **Finish 3D**, resolve the
   current board, place models, show renders. Hand-test with screenshots; develop in a
   working copy; never edit the live-loaded plugin mid-session. (`kicad_action.py` uses
   `pcbnew` + `wx`, import-guarded so the package imports fine off-machine.)

8. **Build-telemetry** text file (machine, what's running, this chat, start/end).

9. **Only then** wire the Eagle Exhumer and srouter hooks (handoff §7), each on its own
   feature branch:
   - Eagle Exhumer `feature/finish3d-models`: after the fix+QC pass, call
     `finish3d.api.handle({"op":"resolve_board", ...})`; add a 3D line to the QC report
     (informational, never a hard FAIL on its own). Private boards (Kraken, morfeus,
     client) → generated/downloaded models go to the local cache only, never uploaded.
   - srouter `tools/finish3d_check.py` (P1): run after placement, before routing; exit
     non-zero on any part with no seatable model or a height collision; feed seated 3D
     into the twin's mandatory human-visual renders and keep-out checks. srouter stays
     private; Finish 3D stays a public dependency, not vendored.

## Open questions for Zoltan (handoff §9) — defaults chosen, confirm or flip

- Name **Finish 3D** + public repo `z2labs/finish3d` — assumed yes.
- Network **off by default**, opt-in per run — implemented. OK, or on by default?
- Licensing: resolve freely, redistribute/commit only confirmed-permissive/own models —
  implemented as `config.redistributable_licenses`.
- Chain priority: **generation before placeholder** — implemented. OK, or keep a missing
  part a visible placeholder until a human picks?
