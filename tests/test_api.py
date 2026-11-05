"""The JSON API contract: one request in, one report out, no raises."""

import os

from finish3d.api import handle

HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(HERE, "data", "sample.kicad_pcb")


def test_selftest_op():
    rep = handle({"op": "selftest"})
    assert rep["ok"] is True


def test_resolve_footprint_op_offline(tmp_path):
    rep = handle({
        "op": "resolve_footprint",
        "offline": True,
        "out_dir": str(tmp_path / "out"),
        "footprint": {
            "name": "Connector_Coaxial:BWSMA-KE-P001",
            "ref": "J9",
            "side": "F.Cu",
            "courtyard": [[-4, -4], [4, -4], [4, 4], [-4, 4]],
            "at": [10, 10, 0],
        },
    })
    assert rep["ok"] is True
    fp = rep["footprints"][0]
    assert fp["source"].startswith("table:") or fp["source"] == "generate"
    assert fp["verify"]["pass"] is True


def test_resolve_board_op(tmp_path):
    rep = handle({
        "op": "resolve_board",
        "board": SAMPLE,
        "offline": True,
        "write_back": False,
        "out_dir": str(tmp_path / "out"),
    })
    assert rep["ok"] is True
    assert rep["summary"]["total"] == 3
    assert rep["summary"]["missing"] == 0


def test_unknown_op_is_soft_error():
    rep = handle({"op": "nope"})
    assert rep["ok"] is False
    assert "unknown op" in rep["error"]


def test_missing_board_is_soft_error():
    rep = handle({"op": "resolve_board"})
    assert rep["ok"] is False
