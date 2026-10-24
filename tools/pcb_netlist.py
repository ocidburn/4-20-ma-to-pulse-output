"""Netlist and footprint access shared by the PCB scripts (plain Python, no pcbnew)."""
import os
from sexpr import parse, find, first

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(HERE, "..", "hardware")
KICAD_FP = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"


def read_netlist(path=os.path.join(HW, "am24_shield.net")):
    """-> comps {ref: {value, footprint, tstamp}}, nets {name: [(ref, pin)]}"""
    t = parse(open(path, encoding="utf-8").read())
    comps = {}
    for c in find(first(t, "components"), "comp"):
        ref = str(first(c, "ref")[1])
        fp = first(c, "footprint")
        ts = first(c, "tstamps")
        comps[ref] = {"value": str(first(c, "value")[1]), "footprint": str(fp[1]) if fp else "",
                      "tstamp": str(ts[1]) if ts else ""}
    nets = {}
    for n in find(first(t, "nets"), "net"):
        name = str(first(n, "name")[1])
        nets[name] = [(str(first(nd, "ref")[1]), str(first(nd, "pin")[1])) for nd in find(n, "node")]
    return comps, nets


def footprint_dir(fp):
    lib, _, name = fp.partition(":")
    if lib == "AM24":
        return os.path.join(HW, "am24.pretty"), name
    return os.path.join(KICAD_FP, lib + ".pretty"), name
