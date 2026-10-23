"""
Minimal KiCad schematic writer (format 20230121, opens in KiCad 7/8/9).

Every part is drawn as a box with numbered pins; every connected pin gets a short wire stub and a
net label, unconnected pins get a no-connect flag. This gives an electrically complete schematic
(ERC, netlist, BOM, PCB update) without hand-drawn wiring; the drawing is meant to be tidied in KiCad.
"""
import uuid

GRID = 2.54
PIN_LEN = 2.54
STUB = 2.54


def uid():
    return str(uuid.uuid4())


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def snap(v):
    return round(v / 1.27) * 1.27


class Part:
    """pins: list of (number, name, net or None, side) where side is 'L' or 'R'."""

    def __init__(self, ref, value, footprint, pins, sym=None, mpn="", note=""):
        self.ref, self.value, self.footprint = ref, value, footprint
        self.pins = pins
        self.sym = sym or f"BOX_{ref}"
        self.mpn, self.note = mpn, note
        self.x = self.y = 0.0

    def geometry(self):
        left = [p for p in self.pins if p[3] == 'L']
        right = [p for p in self.pins if p[3] == 'R']
        rows = max(len(left), len(right), 1)
        name_len = max([len(p[1]) for p in self.pins] + [1])
        width = max(5.08, snap(1.27 * (name_len * 0.8 + 2)) * 2) if any(p[1] for p in self.pins) else 5.08
        height = rows * GRID + GRID
        return left, right, width, height

    def pin_points(self):
        """{pin number: (x, y, side)} connection points on the sheet."""
        left, right, w, h = self.geometry()
        pts = {}
        top = -h / 2 + GRID
        for i, p in enumerate(left):
            pts[p[0]] = (self.x - w / 2 - PIN_LEN, self.y + top + i * GRID, 'L')
        for i, p in enumerate(right):
            pts[p[0]] = (self.x + w / 2 + PIN_LEN, self.y + top + i * GRID, 'R')
        return pts

    def lib_symbol(self):
        left, right, w, h = self.geometry()
        out = [f'(symbol {q("am24:" + self.sym)} (pin_names (offset 0.762)) (in_bom yes) (on_board yes)',
               f'  (property "Reference" {q(self.ref.rstrip("0123456789") or "U")} (at 0 {h / 2 + 1.27:.2f} 0) (effects (font (size 1.27 1.27))))',
               f'  (property "Value" {q(self.value)} (at 0 {-h / 2 - 1.27:.2f} 0) (effects (font (size 1.27 1.27))))',
               '  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
               '  (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
               f'  (symbol {q(self.sym + "_0_1")} (rectangle (start {-w / 2:.2f} {h / 2:.2f}) (end {w / 2:.2f} {-h / 2:.2f}) '
               '(stroke (width 0.254) (type default)) (fill (type background))))',
               f'  (symbol {q(self.sym + "_1_1")}']
        top = h / 2 - GRID
        for i, p in enumerate(left):
            out.append(f'    (pin passive line (at {-w / 2 - PIN_LEN:.2f} {top - i * GRID:.2f} 0) (length {PIN_LEN}) '
                       f'(name {q(p[1] or "~")} (effects (font (size 1.016 1.016)))) (number {q(p[0])} (effects (font (size 1.016 1.016)))))')
        for i, p in enumerate(right):
            out.append(f'    (pin passive line (at {w / 2 + PIN_LEN:.2f} {top - i * GRID:.2f} 180) (length {PIN_LEN}) '
                       f'(name {q(p[1] or "~")} (effects (font (size 1.016 1.016)))) (number {q(p[0])} (effects (font (size 1.016 1.016)))))')
        out.append('  )')
        out.append(')')
        return "\n".join(out)

    def instance(self, root, project):
        _, _, w, h = self.geometry()
        props = [("Reference", self.ref, h / 2 + 1.27, False), ("Value", self.value, -h / 2 - 1.27, False),
                 ("Footprint", self.footprint, 0, True), ("Datasheet", "", 0, True),
                 ("MPN", self.mpn, 0, True)]
        s = [f'(symbol (lib_id {q("am24:" + self.sym)}) (at {self.x:.2f} {self.y:.2f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid()})']
        for name, val, dy, hide in props:
            s.append(f'  (property {q(name)} {q(val)} (at {self.x:.2f} {self.y - dy:.2f} 0) '
                     f'(effects (font (size 1.27 1.27)){" hide" if hide else ""}))')
        for p in self.pins:
            s.append(f'  (pin {q(p[0])} (uuid {uid()}))')
        s.append(f'  (instances (project {q(project)} (path {q("/" + root)} (reference {q(self.ref)}) (unit 1))))')
        s.append(')')
        return "\n".join(s)


def write_schematic(path, project, parts, texts=(), paper="A2"):
    root = uid()
    body = []
    for p in parts:
        body.append(p.instance(root, project))
        pts = p.pin_points()
        for num, name, net, side in p.pins:
            x, y, sd = pts[num]
            if net is None:
                body.append(f'(no_connect (at {x:.2f} {y:.2f}) (uuid {uid()}))')
                continue
            x2 = x - STUB if sd == 'L' else x + STUB
            body.append(f'(wire (pts (xy {x:.2f} {y:.2f}) (xy {x2:.2f} {y:.2f})) (stroke (width 0) (type default)) (uuid {uid()}))')
            ang, just = (180, "right") if sd == 'L' else (0, "left")
            body.append(f'(label {q(net)} (at {x2:.2f} {y:.2f} {ang}) (fields_autoplaced) '
                        f'(effects (font (size 1.016 1.016)) (justify {just} bottom)) (uuid {uid()}))')
    for x, y, txt, size in texts:
        body.append(f'(text {q(txt)} (at {x:.2f} {y:.2f} 0) (effects (font (size {size} {size}) bold) (justify left bottom)) (uuid {uid()}))')

    seen, libs = set(), []
    for p in parts:
        if p.sym not in seen:
            seen.add(p.sym)
            libs.append(p.lib_symbol())

    with open(path, "w", encoding="utf-8") as f:
        f.write(f'(kicad_sch (version 20230121) (generator eeschema)\n  (uuid {root})\n  (paper {q(paper)})\n')
        f.write('  (title_block (title "AM24 shield: 4-20 mA -> frequency/pulse") (company "") (comment 1 "generated by tools/gen_schematic.py"))\n')
        f.write('  (lib_symbols\n' + "\n".join(libs) + '\n  )\n')
        f.write("\n".join(body) + "\n")
        f.write('  (sheet_instances (path "/" (page "1")))\n)\n')
