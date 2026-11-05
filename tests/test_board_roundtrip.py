"""Board reader + surgical writeback: parse, edit only (model), stay byte-stable."""

import os
import shutil

from finish3d.board import Board, ModelRef

HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(HERE, "data", "sample.kicad_pcb")


def _strip_model_blocks(text: str) -> str:
    """Remove every (model ...) block (and its own line) from board text."""
    b = Board(text)
    spans = sorted(
        (fp.model.span for fp in b.footprints if fp.model and fp.model.span),
        reverse=True,
    )
    for s, e in spans:
        ls = text.rfind("\n", 0, s) + 1          # start of the (model line
        le = e
        if le < len(text) and text[le] == "\n":  # swallow trailing newline
            le += 1
        text = text[:ls] + text[le:]
    return text


def test_parse_fields_and_sides():
    b = Board.load(SAMPLE)
    by_ref = {fp.ref: fp for fp in b.footprints}
    assert set(by_ref) == {"R1", "J1", "Q1"}
    assert by_ref["R1"].lcsc == "C25804"
    assert by_ref["Q1"].side == "B.Cu"
    assert by_ref["R1"].side == "F.Cu"
    # courtyard extent for 0603 is ~1.6 x 0.95 mm
    cy = by_ref["R1"].courtyard_bbox()
    assert abs(cy.width - 1.6) < 1e-6
    assert abs(cy.height - 0.95) < 1e-6
    # Q1 has an (existing but dead) model link
    assert by_ref["Q1"].model is not None
    assert by_ref["Q1"].model.path.endswith("does_not_exist.wrl")


def test_writeback_only_touches_model_blocks(tmp_path):
    work = tmp_path / "board.kicad_pcb"
    shutil.copy2(SAMPLE, work)
    b = Board.load(str(work))
    for fp in b.footprints:
        b.set_model(fp, ModelRef(path=f"${{KIPRJMOD}}/m/{fp.ref}.wrl"))
    b.save()

    b2 = Board.load(str(work))
    assert len(b2.footprints) == 3
    for fp in b2.footprints:
        assert fp.model is not None
        assert fp.model.path == f"${{KIPRJMOD}}/m/{fp.ref}.wrl"

    # everything except the (model) blocks is byte-identical
    orig = open(SAMPLE).read()
    new = open(work).read()
    assert _strip_model_blocks(orig) == _strip_model_blocks(new)


def test_writeback_is_idempotent(tmp_path):
    work = tmp_path / "board.kicad_pcb"
    shutil.copy2(SAMPLE, work)
    for _ in range(3):
        b = Board.load(str(work))
        for fp in b.footprints:
            b.set_model(fp, ModelRef(path=f"${{KIPRJMOD}}/m/{fp.ref}.wrl"))
        b.save()
    text = open(work).read()
    assert text.count("/m/R1.wrl") == 1
    assert text.count("/m/J1.wrl") == 1
    assert text.count("/m/Q1.wrl") == 1
