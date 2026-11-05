"""The witness self-test must be 100%: baseline passes, every injection trips."""

from finish3d.verify import run_selftest


def test_selftest_all_green():
    rep = run_selftest()
    assert rep.ok, rep.as_dict()


def test_each_injection_is_tripped():
    rep = run_selftest()
    by_name = {name: (exp, res) for (name, exp, res, _d) in rep.cases}
    # baseline good must pass
    assert by_name["baseline_good"][1] is True
    # every injected error must be caught (result == "tripped" == True)
    for name in ("rot90", "wrong_side", "scale_254", "offset_1mm", "swap_model"):
        exp, res = by_name[name]
        assert res is True, f"{name} was not tripped by verify"
