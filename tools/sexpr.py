"""Tiny S-expression reader/writer for KiCad files and symbol-library access."""
import math
import os
import re

KICAD_SYMBOLS = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"

_tok = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Q(str):
    """A quoted string atom."""


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif m.group(3):
            cur.append(Q(m.group(3)[1:-1].replace('\\"', '"').replace('\\\\', '\\')))
        elif m.group(4):
            cur.append(m.group(4))
    return cur[0] if len(cur) == 1 else cur


def dump(x):
    if isinstance(x, list):
        return "(" + " ".join(dump(e) for e in x) + ")"
    if isinstance(x, Q):
        return '"' + x.replace('\\', '\\\\').replace('"', '\\"') + '"'
    if isinstance(x, float):
        return f"{x:.4f}".rstrip("0").rstrip(".")
    return str(x)


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


_libcache = {}


def load_lib(lib):
    if lib not in _libcache:
        with open(os.path.join(KICAD_SYMBOLS, lib + ".kicad_sym"), encoding="utf-8") as f:
            tree = parse(f.read())
        _libcache[lib] = {s[1]: s for s in find(tree, "symbol")}
    return _libcache[lib]


def lib_symbol(lib, name):
    """Flattened copy of a library symbol, renamed to 'lib:name' for a schematic's lib_symbols."""
    syms = load_lib(lib)
    s = syms[name]
    ext = first(s, "extends")
    if ext:
        parent = lib_symbol(lib, ext[1])
        props = find(s, "property")
        body = [e for e in parent[2:] if not (isinstance(e, list) and e[0] == "property")]
        # rename parent units to the child name
        out = [ "symbol", Q(f"{lib}:{name}")]
        for e in body:
            if isinstance(e, list) and e[0] == "symbol":
                e = list(e)
                e[1] = Q(e[1].replace(ext[1], name, 1))
            out.append(e)
        out[2:2] = props
        return out
    out = list(s)
    out[1] = Q(f"{lib}:{name}")
    return out


def pins_of(sym):
    """{number: (x, y, angle, name)} of unit 1 / common unit, body style 1."""
    pins = {}
    for sub in find(sym, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        unit, style = (int(m.group(1)), int(m.group(2))) if m else (1, 1)
        if unit not in (0, 1) or style not in (0, 1):
            continue
        for p in find(sub, "pin"):
            at = first(p, "at")
            num = first(p, "number")[1]
            nm = first(p, "name")[1]
            pins[str(num)] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, str(nm))
    return pins


def place_pin(px, py, x, y, rot):
    """Library pin point -> sheet point for a symbol at (x, y) rotated by rot degrees (no mirror)."""
    a = math.radians(rot)
    rx = px * math.cos(a) - py * math.sin(a)
    ry = px * math.sin(a) + py * math.cos(a)
    return round(x + rx, 4), round(y - ry, 4)
