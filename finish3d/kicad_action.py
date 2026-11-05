"""KiCad 10 action plugin: the "Finish 3D" toolbar button.

Thin GUI wrapper over the ``finish3d`` library -- the library is the single
source of truth; this only gathers the current board path, calls
``core.resolve_board``, and surfaces the result + renders.

NOTE: ``pcbnew`` only exists inside KiCad, and ``pcb render`` needs KiCad 8+.
This module must be HAND-TESTED on the G7/office machine with KiCad 10
(screenshots, develop in a working copy, never edit the live-loaded plugin
mid-session). It is import-guarded so merely importing the package outside KiCad
never fails.
"""

from __future__ import annotations

import os


try:  # pragma: no cover - only importable inside KiCad
    import pcbnew  # type: ignore
    import wx  # type: ignore
    _HAVE_KICAD = True
except Exception:  # noqa: BLE001
    _HAVE_KICAD = False


if _HAVE_KICAD:

    class Finish3DPlugin(pcbnew.ActionPlugin):  # pragma: no cover - GUI
        def defaults(self):
            self.name = "Finish 3D"
            self.category = "Modify PCB"
            self.description = (
                "Resolve, seat and verify 3D models on every footprint "
                "(offline-first), then render."
            )
            self.show_toolbar_button = True
            here = os.path.dirname(__file__)
            icon = os.path.join(here, "icon.png")
            self.icon_file_name = icon if os.path.exists(icon) else ""

        def Run(self):
            from .config import Config
            from .core import resolve_board

            board = pcbnew.GetBoard()
            board_path = board.GetFileName()
            if not board_path:
                wx.MessageBox("Save the board first.", "Finish 3D",
                              wx.OK | wx.ICON_WARNING)
                return

            # GUI runs are online + write-back + render by default; the user
            # sees exactly what changed (standing rule: show the user).
            cfg = Config(
                offline=False,
                render=True,
                write_back=True,
                out_dir=os.path.join(os.path.dirname(board_path),
                                     "finish3d_out"),
            )
            report = resolve_board(board_path, cfg).to_dict()

            # Reload so the freshly written (model) links show in the 3D viewer.
            try:
                reloaded = pcbnew.LoadBoard(board_path)
                pcbnew.GetBoard().__dict__.update(reloaded.__dict__)
            except Exception:
                pass

            s = report.get("summary", {})
            lines = [
                f"Resolved {s.get('resolved', 0)}/{s.get('total', 0)} "
                f"footprints.",
                f"Placeholder: {s.get('placeholder', 0)}   "
                f"Missing: {s.get('missing', 0)}",
                "",
            ]
            for fp in report.get("footprints", []):
                v = fp.get("verify", {})
                mark = "OK" if v.get("pass", True) else "!!"
                warn = (" " + ",".join(fp["warnings"])) if fp.get("warnings") else ""
                lines.append(f"[{mark}] {fp.get('ref')}  {fp.get('name')}  "
                             f"<- {fp.get('source')}{warn}")
            if report.get("renders"):
                lines += ["", "Renders:"] + [f"  {r}" for r in report["renders"]]
            if report.get("warnings"):
                lines += ["", "Notes:"] + [f"  {w}" for w in report["warnings"]]

            wx.MessageBox("\n".join(lines), "Finish 3D",
                          wx.OK | wx.ICON_INFORMATION)

    # KiCad discovers and registers ActionPlugin subclasses via register().
    Finish3DPlugin().register()
