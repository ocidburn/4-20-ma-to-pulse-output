"""Schematic builder with real KiCad symbols, wires, auto junctions and power symbols (KiCad 9/10 format)."""
import uuid
import sexpr
from sexpr import Q, find, first, lib_symbol, pins_of, place_pin

EPS = 1e-3


def uid():
    return Q(str(uuid.uuid4()))


def eff(size=1.27, justify=None, hide=False):
    e = ["effects", ["font", ["size", size, size]]]
    if justify:
        e.append(["justify"] + justify.split())
    return e


def prop(name, value, x, y, rot=0, hide=False, justify=None):
    p = ["property", Q(name), Q(value), ["at", round(x, 4), round(y, 4), rot]]
    if hide:
        p.append(["hide", "yes"])
    p.append(eff(justify=justify))
    return p


def box_symbol(name, ref_prefix, left, right, width=20.32, top=None, bottom=None):
    """Custom IC symbol. left/right: lists of (number, name) top->bottom; None = gap row."""
    rows = max(len(left), len(right))
    h = rows * 2.54
    ytop = (rows - 1) / 2 * 2.54
    w2 = width / 2
    pins = []
    for side, lst in (("L", left), ("R", right)):
        for i, p in enumerate(lst):
            if p is None:
                continue
            num, nm = p
            y = round(ytop - i * 2.54, 4)
            x = -w2 - 2.54 if side == "L" else w2 + 2.54
            ang = 0 if side == "L" else 180
            pins.append(["pin", "passive", "line", ["at", round(x, 4), y, ang], ["length", 2.54],
                         ["name", Q(nm), eff()], ["number", Q(num), eff()]])
    sym = ["symbol", Q("am24:" + name), ["pin_names", ["offset", 1.016]],
           ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
           prop("Reference", ref_prefix, 0, ytop + 3.81),
           prop("Value", name, 0, -ytop - 3.81),
           prop("Footprint", "", 0, 0, hide=True), prop("Datasheet", "", 0, 0, hide=True),
           ["symbol", Q(name + "_0_1"), ["rectangle", ["start", -w2, round(ytop + 2.54, 4)], ["end", w2, round(-ytop - 2.54, 4)],
                                         ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]],
           ["symbol", Q(name + "_1_1")] + pins,
           ["embedded_fonts", "no"]]
    return sym


def renumber(sym, mapping, new_name):
    """Copy of a library symbol with pin numbers renamed (e.g. D/G/S -> 2/1/3)."""
    s = sexpr.parse(sexpr.dump(sym))
    old = s[1].split(":", 1)[1]
    s[1] = Q("am24:" + new_name)
    for sub in find(s, "symbol"):
        sub[1] = Q(sub[1].replace(old, new_name, 1))
        for p in find(sub, "pin"):
            num = first(p, "number")
            if num[1] in mapping:
                num[1] = Q(mapping[num[1]])
    return s


def power_symbol(base, net):
    """Power symbol named after its net, built from a library power symbol."""
    s = sexpr.parse(sexpr.dump(lib_symbol("power", base)))
    s[1] = Q("am24:" + net.replace("+", "P"))
    for sub in find(s, "symbol"):
        sub[1] = Q(sub[1].replace(base, net.replace("+", "P"), 1))
    for p in find(s, "property"):
        if p[1] == "Value":
            p[2] = Q(net)
    return s


class Sheet:
    def __init__(self, project):
        self.project = project
        self.root = str(uuid.uuid4())
        self.libs = {}
        self.parts = {}          # ref -> dict
        self.items = []          # placed symbol sexprs
        self.wires = []          # [(x1,y1),(x2,y2)]
        self.labels = []         # (net, x, y, rot)
        self.ncs = []
        self.texts = []
        self.pwr_n = 0
        self.points = []         # pin / label / power points (connection points)
        self.dx = 0.0            # x offset applied to explicit coordinates (shifts a whole block)

    # ---------- symbols ----------
    def _lib(self, sym):
        self.libs[sym[1]] = sym
        return sym

    def add(self, ref, sym, value, fp, x, y, rot=0, mirror=None, mpn="", ref_at=None, val_at=None, hide_val=False):
        self._lib(sym)
        x += self.dx
        if ref_at:
            ref_at = (ref_at[0] + self.dx, ref_at[1], ref_at[2])
        if val_at:
            val_at = (val_at[0] + self.dx, val_at[1], val_at[2])
        pins = {}
        for num, (px, py, ang, nm) in pins_of(sym).items():
            if mirror == "y":
                px = -px
            elif mirror == "x":
                py = -py
            pins[num] = place_pin(px, py, x, y, rot)
            self.points.append(pins[num])
        self.parts[ref] = {"pins": pins, "value": value, "mpn": mpn, "fp": fp}
        rx, ry, rj = ref_at or (x + 3.3, y - 1.27, "left")
        vx, vy, vj = val_at or (x + 3.3, y + 1.27, "left")
        fa = (360 - rot) % 360 if rot in (90, 270) else 0     # keep field text horizontal
        s = ["symbol", ["lib_id", sym[1]], ["at", round(x, 4), round(y, 4), rot]]
        if mirror:
            s.append(["mirror", mirror])
        s += [["unit", 1], ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"],
              ["uuid", uid()],
              prop("Reference", ref, rx, ry, rot=fa, justify=rj), prop("Value", value, vx, vy, rot=fa, justify=vj, hide=hide_val),
              prop("Footprint", fp, x, y, hide=True), prop("Datasheet", "", x, y, hide=True)]
        if mpn:
            s.append(prop("MPN", mpn, x, y, hide=True))
        for num in pins_of(sym):
            s.append(["pin", Q(num), ["uuid", uid()]])
        s.append(["instances", ["project", Q(self.project), ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", 1]]]])
        self.items.append(s)
        return pins

    def P(self, refpin):
        ref, pin = refpin.split(".")
        return self.parts[ref]["pins"][pin]

    def pwr(self, net, x, y, rot=0, base=None, raw=False):
        """Power symbol whose pin is at (x, y). rot: 0 = default (supplies up, grounds down)."""
        if not raw:
            x += self.dx
        if base is None:
            base = "GND" if "GND" in net else "+3V3"
        sym = self._lib(power_symbol(base, net) if net not in ("GND", "+3V3", "+5V", "+24V") else lib_symbol("power", net))
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}"
        gnd = "GND" in net
        d = {0: (0, 3.81), 90: (3.81, 0), 180: (0, -3.81), 270: (-3.81, 0)}[rot]   # direction the symbol points
        if not gnd:
            d = (-d[0], -d[1])
        tx, ty2 = d
        just = "left" if tx > 0 else "right" if tx < 0 else None
        fa = (360 - rot) % 360 if rot in (90, 270) else 0
        s = ["symbol", ["lib_id", sym[1]], ["at", round(x, 4), round(y, 4), rot], ["unit", 1],
             ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["uuid", uid()],
             prop("Reference", ref, x, y, hide=True), prop("Value", net, x + tx, y + ty2, rot=fa, justify=just),
             prop("Footprint", "", x, y, hide=True), prop("Datasheet", "", x, y, hide=True),
             ["pin", Q("1"), ["uuid", uid()]],
             ["instances", ["project", Q(self.project), ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", 1]]]]]
        self.items.append(s)
        self.points.append((round(x, 4), round(y, 4)))

    def flag(self, x, y):
        x += self.dx
        sym = self._lib(lib_symbol("power", "PWR_FLAG"))
        self.pwr_n += 1
        ref = f"#FLG{self.pwr_n:03d}"
        s = ["symbol", ["lib_id", sym[1]], ["at", round(x, 4), round(y, 4), 0], ["unit", 1],
             ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["uuid", uid()],
             prop("Reference", ref, x, y, hide=True), prop("Value", "PWR_FLAG", x, y - 3.81, hide=True),
             prop("Footprint", "", x, y, hide=True), prop("Datasheet", "", x, y, hide=True),
             ["pin", Q("1"), ["uuid", uid()]],
             ["instances", ["project", Q(self.project), ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", 1]]]]]
        self.items.append(s)
        self.points.append((round(x, 4), round(y, 4)))

    # ---------- wiring ----------
    def _pt(self, p):
        return self.P(p) if isinstance(p, str) else (round(p[0] + self.dx, 4), round(p[1], 4))

    def w(self, *pts):
        return self._wire_abs([self._pt(p) for p in pts])

    def _wire_abs(self, pts):
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS:
                raise ValueError(f"diagonal wire {a} -> {b}")
            if abs(a[0] - b[0]) > EPS or abs(a[1] - b[1]) > EPS:
                self.wires.append((a, b))
        return pts[-1]

    def hv(self, a, b):
        """Horizontal then vertical."""
        a, b = self._pt(a), self._pt(b)
        return self._wire_abs([a, (b[0], a[1]), b])

    def vh(self, a, b):
        a, b = self._pt(a), self._pt(b)
        return self._wire_abs([a, (a[0], b[1]), b])

    def label(self, net, p, rot=0):
        x, y = self._pt(p)
        self.labels.append((net, x, y, rot))
        self.points.append((x, y))

    def nc(self, refpin):
        self.ncs.append(self.P(refpin))

    def text(self, s, x, y, size=2.0):
        self.texts.append((s, x + self.dx, y, size))

    # ---------- output ----------
    def _split_and_junctions(self):
        pts = set((round(x, 4), round(y, 4)) for x, y in self.points)
        for a, b in self.wires:
            pts.add(a)
            pts.add(b)

        def inside(p, a, b):
            if abs(a[0] - b[0]) < EPS and abs(p[0] - a[0]) < EPS:
                return min(a[1], b[1]) + EPS < p[1] < max(a[1], b[1]) - EPS
            if abs(a[1] - b[1]) < EPS and abs(p[1] - a[1]) < EPS:
                return min(a[0], b[0]) + EPS < p[0] < max(a[0], b[0]) - EPS
            return False

        segs = list(self.wires)
        out = []
        while segs:
            a, b = segs.pop()
            cut = next((p for p in pts if inside(p, a, b)), None)
            if cut:
                segs += [(a, cut), (cut, b)]
            else:
                out.append((a, b))
        self.wires = out

        # collinear overlaps between distinct segments would merge nets silently: report them
        problems = []
        for i, (a, b) in enumerate(out):
            for c, d in out[i + 1:]:
                if (inside(c, a, b) or inside(d, a, b)) or ((a, b) == (c, d) or (a, b) == (d, c)):
                    problems.append(((a, b), (c, d)))
        count = {}
        for a, b in out:
            for p in (a, b):
                count[p] = count.get(p, 0) + 1
        for p in self.points:
            p = (round(p[0], 4), round(p[1], 4))
            if p in count:
                count[p] += 1
        junctions = [p for p, n in count.items() if n >= 3]
        return junctions, problems

    def save(self, path, paper="A2", title="", comments=()):
        junctions, problems = self._split_and_junctions()
        doc = ["kicad_sch", ["version", 20250114], ["generator", Q("eeschema")], ["generator_version", Q("9.0")],
               ["uuid", Q(self.root)], ["paper", Q(paper)],
               ["title_block", ["title", Q(title)]] + [["comment", i + 1, Q(c)] for i, c in enumerate(comments)],
               ["lib_symbols"] + list(self.libs.values())]
        for x, y in junctions:
            doc.append(["junction", ["at", x, y], ["diameter", 0], ["color", 0, 0, 0, 0], ["uuid", uid()]])
        for x, y in self.ncs:
            doc.append(["no_connect", ["at", x, y], ["uuid", uid()]])
        for a, b in self.wires:
            doc.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                        ["stroke", ["width", 0], ["type", "default"]], ["uuid", uid()]])
        for net, x, y, rot in self.labels:
            just = "left bottom" if rot == 0 else "right bottom" if rot == 180 else "left bottom"
            doc.append(["label", Q(net), ["at", x, y, rot], ["effects", ["font", ["size", 1.27, 1.27]], ["justify"] + just.split()],
                        ["uuid", uid()]])
        for s, x, y, size in self.texts:
            doc.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", x, y, 0],
                        ["effects", ["font", ["size", size, size], ["bold", "yes"]], ["justify", "left", "bottom"]], ["uuid", uid()]])
        doc += self.items
        doc.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        doc.append(["embedded_fonts", "no"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(sexpr.dump(doc) + "\n")
        return len(junctions), problems
