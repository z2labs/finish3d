"""Command-line entry point: ``python -m finish3d``.

    python -m finish3d board.kicad_pcb [--offline/--online] [--render]
                       [--write-back] [--out DIR] [--cache DIR] [--json]
    python -m finish3d selftest
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import Config


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="finish3d",
        description="Resolve, seat and verify 3D models on KiCad footprints "
                    "(offline-first).",
    )
    p.add_argument("target", help="path to a .kicad_pcb, or 'selftest'")
    net = p.add_mutually_exclusive_group()
    net.add_argument("--offline", dest="offline", action="store_true",
                     help="never touch the network (default)")
    net.add_argument("--online", dest="offline", action="store_false",
                     help="allow EasyEDA/LCSC + GitHub vendor sources")
    p.set_defaults(offline=True)
    p.add_argument("--render", action="store_true",
                   help="run kicad-cli pcb render (KiCad 8+ / G7 machine)")
    p.add_argument("--write-back", action="store_true",
                   help="write resolved (model) links back into the board")
    p.add_argument("--out", default="out", help="output directory (default: out)")
    p.add_argument("--cache", default=None, help="cache directory override")
    p.add_argument("--json", action="store_true", help="print the full report JSON")
    return p


def _print_human(report: dict) -> None:
    s = report.get("summary", {})
    print(f"Finish 3D: {s.get('resolved', 0)}/{s.get('total', 0)} resolved, "
          f"{s.get('placeholder', 0)} placeholder, {s.get('missing', 0)} missing "
          f"(net_used={s.get('net_used')})")
    for fp in report.get("footprints", []):
        v = fp.get("verify", {})
        mark = "OK " if v.get("pass", True) else "!! "
        warn = (" [" + ", ".join(fp["warnings"]) + "]") if fp.get("warnings") else ""
        print(f"  {mark}{fp.get('ref',''):<6} {fp.get('name','')}"
              f"  <- {fp.get('source')}{warn}")
    for w in report.get("warnings", []):
        print(f"  * {w}")
    if report.get("renders"):
        print("  renders:")
        for r in report["renders"]:
            print(f"    {r}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "selftest":
        from .verify import run_selftest
        rep = run_selftest()
        for name, _exp, res, detail in rep.cases:
            print(f"  [{'PASS' if res else 'FAIL'}] {name}: {detail}")
        print(f"\nselftest: {'OK (100%)' if rep.ok else 'FAILED'}")
        return 0 if rep.ok else 1

    args = _build_parser().parse_args(argv)
    if args.target == "selftest":
        from .verify import run_selftest
        rep = run_selftest()
        print(json.dumps(rep.as_dict(), indent=2) if args.json
              else f"selftest: {'OK' if rep.ok else 'FAILED'}")
        return 0 if rep.ok else 1

    cfg = Config(offline=args.offline, render=args.render,
                 write_back=args.write_back, out_dir=args.out)
    if args.cache:
        cfg.cache_dir = args.cache

    from .core import resolve_board
    report = resolve_board(args.target, cfg).to_dict()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
