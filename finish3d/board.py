"""Offline KiCad board reader/writer (stdlib only).

Reads ``.kicad_pcb`` files as raw S-expressions so that headless callers never
need ``pcbnew``. The writer is deliberately *surgical*: it only re-emits or
replaces the ``(model ...)`` block of a footprint and leaves every other byte of
the file untouched. This is the same discipline used by the srouter / Z2 Stitch
tools -- edit at the text level, never let ``SaveBoard`` rewrite ``.kicad_pro``
or shuffle UUIDs.

The parser keeps source character offsets on every node so writeback can target
exact spans.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional


# --------------------------------------------------------------------------- #
# S-expression parser (position-aware)
# --------------------------------------------------------------------------- #
class Atom:
    __slots__ = ("value", "quoted", "start", "end")

    def __init__(self, value: str, quoted: bool, start: int, end: int):
        self.value = value
        self.quoted = quoted
        self.start = start
        self.end = end

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Atom({self.value!r})"


class SExp:
    __slots__ = ("items", "start", "end")

    def __init__(self, start: int):
        self.items: list = []
        self.start = start
        self.end: Optional[int] = None

    # convenience -----------------------------------------------------------
    @property
    def head(self) -> Optional[str]:
        if self.items and isinstance(self.items[0], Atom):
            return self.items[0].value
        return None

    def children(self, name: str) -> list["SExp"]:
        return [
            it for it in self.items
            if isinstance(it, SExp) and it.head == name
        ]

    def child(self, name: str) -> Optional["SExp"]:
        for it in self.items:
            if isinstance(it, SExp) and it.head == name:
                return it
        return None

    def atoms(self) -> list[Atom]:
        return [it for it in self.items if isinstance(it, Atom)]

    def values(self) -> list[str]:
        """Atom values after the head."""
        return [a.value for a in self.atoms()[1:]]

    def floats(self) -> list[float]:
        out = []
        for v in self.values():
            try:
                out.append(float(v))
            except ValueError:
                pass
        return out


def parse(text: str) -> SExp:
    """Parse the whole file and return the top-level ``(kicad_pcb ...)`` node."""
    stack: list[SExp] = []
    top: Optional[SExp] = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "(":
            node = SExp(i)
            if stack:
                stack[-1].items.append(node)
            stack.append(node)
            i += 1
        elif c == ")":
            if not stack:
                raise ValueError(f"unbalanced ')' at offset {i}")
            node = stack.pop()
            node.end = i + 1
            if not stack:
                top = node
            i += 1
        elif c == '"':
            start = i
            i += 1
            buf = []
            while i < n:
                ch = text[i]
                if ch == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            atom = Atom("".join(buf), True, start, i)
            if stack:
                stack[-1].items.append(atom)
        elif c.isspace():
            i += 1
        else:
            start = i
            while i < n and not text[i].isspace() and text[i] not in '()"':
                i += 1
            atom = Atom(text[start:i], False, start, i)
            if stack:
                stack[-1].items.append(atom)
    if top is None:
        raise ValueError("no top-level S-expression found")
    return top


# --------------------------------------------------------------------------- #
# Domain objects
# --------------------------------------------------------------------------- #
@dataclass
class ModelRef:
    path: str
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotate: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # source span of the whole (model ...) block, for surgical writeback
    span: Optional[tuple[int, int]] = None


@dataclass
class BBox:
    xmin: float = math.inf
    ymin: float = math.inf
    xmax: float = -math.inf
    ymax: float = -math.inf

    def add(self, x: float, y: float) -> None:
        self.xmin = min(self.xmin, x)
        self.ymin = min(self.ymin, y)
        self.xmax = max(self.xmax, x)
        self.ymax = max(self.ymax, y)

    @property
    def valid(self) -> bool:
        return self.xmax >= self.xmin and self.ymax >= self.ymin

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    @property
    def max_dim(self) -> float:
        return max(self.width, self.height)


@dataclass
class Footprint:
    name: str                       # "Lib:Name"
    ref: str                        # reference designator, e.g. "J1"
    at: tuple[float, float]         # board XY, mm
    rotation_deg: float             # Z rotation, degrees
    side: str                       # "F.Cu" or "B.Cu"
    courtyard: BBox                 # footprint-local courtyard extent
    pad_span: BBox                  # footprint-local pad extent (fallback)
    fields: dict[str, str] = field(default_factory=dict)
    model: Optional[ModelRef] = None
    _node: Optional[SExp] = None    # back-reference for writeback

    # convenience lookups ---------------------------------------------------
    @property
    def mpn(self) -> str:
        for key in ("MPN", "mpn", "Manufacturer Part Number", "PartNumber"):
            if self.fields.get(key):
                return self.fields[key]
        return ""

    @property
    def lcsc(self) -> str:
        for key in ("LCSC", "lcsc", "JLCPCB", "LCSC Part #", "LCSC Part"):
            v = self.fields.get(key, "")
            if v:
                return v
        return ""

    def courtyard_bbox(self) -> BBox:
        return self.courtyard if self.courtyard.valid else self.pad_span


def _xyz(node: Optional[SExp], default: tuple[float, float, float]
         ) -> tuple[float, float, float]:
    if node is None:
        return default
    xyz = node.child("xyz")
    vals = xyz.floats() if xyz else node.floats()
    if len(vals) >= 3:
        return (vals[0], vals[1], vals[2])
    return default


def _read_model(fp_node: SExp) -> Optional[ModelRef]:
    m = fp_node.child("model")
    if m is None:
        return None
    atoms = m.atoms()
    path = atoms[1].value if len(atoms) > 1 else ""
    return ModelRef(
        path=path,
        offset=_xyz(m.child("offset"), (0.0, 0.0, 0.0)),
        scale=_xyz(m.child("scale"), (1.0, 1.0, 1.0)),
        rotate=_xyz(m.child("rotate"), (0.0, 0.0, 0.0)),
        span=(m.start, m.end),
    )


def _read_reference(fp_node: SExp) -> str:
    # KiCad 7+: (property "Reference" "J1" ...)
    for p in fp_node.children("property"):
        a = p.atoms()
        if len(a) >= 3 and a[1].value == "Reference":
            return a[2].value
    # legacy: (fp_text reference "J1" ...)
    for t in fp_node.children("fp_text"):
        a = t.atoms()
        if len(a) >= 3 and a[1].value == "reference":
            return a[2].value
    return ""


def _read_fields(fp_node: SExp) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in fp_node.children("property"):
        a = p.atoms()
        if len(a) >= 3:
            out[a[1].value] = a[2].value
    return out


_CRTYD = {"F.CrtYd", "B.CrtYd"}


def _graphic_layer(node: SExp) -> str:
    lyr = node.child("layer")
    if lyr is None:
        return ""
    a = lyr.atoms()
    return a[1].value if len(a) > 1 else ""


def _read_courtyard(fp_node: SExp) -> BBox:
    bb = BBox()
    for ln in fp_node.children("fp_line") + fp_node.children("fp_rect"):
        if _graphic_layer(ln) not in _CRTYD:
            continue
        s = ln.child("start")
        e = ln.child("end")
        if s:
            v = s.floats()
            if len(v) >= 2:
                bb.add(v[0], v[1])
        if e:
            v = e.floats()
            if len(v) >= 2:
                bb.add(v[0], v[1])
    for poly in fp_node.children("fp_poly"):
        if _graphic_layer(poly) not in _CRTYD:
            continue
        pts = poly.child("pts")
        if pts:
            for xy in pts.children("xy"):
                v = xy.floats()
                if len(v) >= 2:
                    bb.add(v[0], v[1])
    for circ in fp_node.children("fp_circle"):
        if _graphic_layer(circ) not in _CRTYD:
            continue
        c = circ.child("center")
        e = circ.child("end")
        if c and e:
            cv, ev = c.floats(), e.floats()
            if len(cv) >= 2 and len(ev) >= 2:
                r = math.hypot(ev[0] - cv[0], ev[1] - cv[1])
                bb.add(cv[0] - r, cv[1] - r)
                bb.add(cv[0] + r, cv[1] + r)
    return bb


def _read_pad_span(fp_node: SExp) -> BBox:
    bb = BBox()
    for pad in fp_node.children("pad"):
        at = pad.child("at")
        size = pad.child("size")
        if not at:
            continue
        av = at.floats()
        sv = size.floats() if size else [0.0, 0.0]
        if len(av) < 2:
            continue
        w = sv[0] if len(sv) > 0 else 0.0
        h = sv[1] if len(sv) > 1 else 0.0
        bb.add(av[0] - w / 2, av[1] - h / 2)
        bb.add(av[0] + w / 2, av[1] + h / 2)
    return bb


def _read_footprint(fp_node: SExp) -> Footprint:
    atoms = fp_node.atoms()
    name = atoms[1].value if len(atoms) > 1 else ""
    at_node = fp_node.child("at")
    av = at_node.floats() if at_node else [0.0, 0.0, 0.0]
    x = av[0] if len(av) > 0 else 0.0
    y = av[1] if len(av) > 1 else 0.0
    rot = av[2] if len(av) > 2 else 0.0
    layer_node = fp_node.child("layer")
    layer = ""
    if layer_node:
        la = layer_node.atoms()
        layer = la[1].value if len(la) > 1 else ""
    side = "B.Cu" if layer.startswith("B") else "F.Cu"
    return Footprint(
        name=name,
        ref=_read_reference(fp_node),
        at=(x, y),
        rotation_deg=rot,
        side=side,
        courtyard=_read_courtyard(fp_node),
        pad_span=_read_pad_span(fp_node),
        fields=_read_fields(fp_node),
        model=_read_model(fp_node),
        _node=fp_node,
    )


class Board:
    """A parsed ``.kicad_pcb`` with surgical model writeback."""

    def __init__(self, text: str, path: Optional[str] = None):
        self.text = text
        self.path = path
        self.root = parse(text)
        self.footprints: list[Footprint] = [
            _read_footprint(n)
            for n in self.root.items
            if isinstance(n, SExp) and n.head in ("footprint", "module")
        ]

    @classmethod
    def load(cls, path: str) -> "Board":
        with open(path, "r", encoding="utf-8") as fh:
            return cls(fh.read(), path=path)

    # ------------------------------------------------------------------ #
    # Writeback: only the (model ...) blocks change.
    # ------------------------------------------------------------------ #
    @staticmethod
    def _format_model(ref: ModelRef, indent: str = "\t\t") -> str:
        ox, oy, oz = ref.offset
        sx, sy, sz = ref.scale
        rx, ry, rz = ref.rotate

        def num(v: float) -> str:
            # KiCad writes plain decimals; keep it tidy.
            if v == int(v):
                return str(int(v))
            return repr(round(v, 6))

        return (
            f'(model "{ref.path}"\n'
            f"{indent}\t(offset (xyz {num(ox)} {num(oy)} {num(oz)}))\n"
            f"{indent}\t(scale (xyz {num(sx)} {num(sy)} {num(sz)}))\n"
            f"{indent}\t(rotate (xyz {num(rx)} {num(ry)} {num(rz)}))\n"
            f"{indent})"
        )

    def set_model(self, fp: Footprint, ref: ModelRef) -> None:
        """Record a new model for ``fp``. Applied to text by :meth:`render`."""
        ref.span = fp.model.span if fp.model else None
        fp.model = ref

    def render(self) -> str:
        """Return new file text with all pending model blocks applied.

        Replacements are applied from the highest offset downward so earlier
        spans stay valid. Footprints with no model are given one inserted just
        before their closing paren.
        """
        edits: list[tuple[int, int, str]] = []  # (start, end, replacement)
        for fp in self.footprints:
            if fp.model is None or fp._node is None:
                continue
            if fp.model.span is not None:
                # replace the existing (model ...) block in place
                s, e = fp.model.span
                indent = self._line_indent(s) or (
                    self._line_indent(fp._node.start) + "\t")
                block = self._format_model(fp.model, indent=indent)
                edits.append((s, e, block))
            else:
                # insert a fresh, properly-indented line just before the
                # footprint's closing ')' line -- touching nothing else.
                close = fp._node.end - 1  # type: ignore[operator]
                line_start = self.text.rfind("\n", 0, close) + 1
                closing_indent = self.text[line_start:close]
                child_indent = closing_indent + "\t"
                block = self._format_model(fp.model, indent=child_indent)
                insertion = f"{child_indent}{block}\n"
                edits.append((line_start, line_start, insertion))
        edits.sort(key=lambda t: t[0], reverse=True)
        text = self.text
        for s, e, rep in edits:
            text = text[:s] + rep + text[e:]
        return text

    def _line_indent(self, offset: int) -> str:
        line_start = self.text.rfind("\n", 0, offset) + 1
        ws = []
        for ch in self.text[line_start:offset]:
            if ch in " \t":
                ws.append(ch)
            else:
                break
        return "".join(ws)

    def save(self, path: Optional[str] = None) -> str:
        target = path or self.path
        if not target:
            raise ValueError("no path to save to")
        out = self.render()
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(out)
        return target


def iter_footprints(board: Board) -> Iterable[Footprint]:
    return iter(board.footprints)
