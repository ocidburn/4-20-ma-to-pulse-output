#!/usr/bin/env python3
"""
AM24 shield PCB: outline, placement, isolation barrier, net classes, ground pours and the
hand-routed analog tracks. The remaining nets are routed by Freerouting (route_pcb.py).

Run with KiCad's Python (it has the pcbnew module):
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/gen_pcb.py --layers 4
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/gen_pcb.py --layers 2

Coordinates below are in the Nucleo-64 frame, mm: x to the right from the Nucleo's left edge,
y UP from its bottom edge (ST-LINK end at the top). In this frame the Arduino rows are at
x = 10.87 (power, A0-A5) and x = 59.13 (D0-D15), Morpho CN7/CN10 at x = 3.25/5.79 and
64.21/66.75 for y = 5.04...50.76. Over the Nucleo (0 < x < 70, y > 0) only SMD parts are used,
so no leads reach the Nucleo below; through-hole parts sit on the overhang.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcb_netlist import HW, footprint_dir, read_netlist  # noqa: E402

OX, OY = 30.0, 80.0                  # Nucleo frame -> KiCad sheet: X = x + OX, Y = OY - y
BOARD = (-15.0, -34.0, 85.0, 56.0)   # x0, y0, x1, y1 in the Nucleo frame
CORNER = 2.0

# Isolated (loop) side: left band and bottom-left band. 4 mm copper-free barrier around it.
ISO = [(-15, 56), (5, 56), (5, -2), (44, -2), (44, -34), (-15, -34)]
BARRIER = [  # (x0, y0, x1, y1) strips
    (5, -2, 9, 56),
    (5, -2, 48, 2),
    (44, -34, 48, 2),
]
SLOTS = [(2.0, 12.5, 8.0, 18.0), (2.0, 43.0, 8.0, 48.5)]   # jumper wires to CN7 pin 29 (PF0), pin 6 (E5V)
HOLES = [(-11.5, -30.5), (81.5, -30.5), (-11.5, 52.5), (81.5, 52.5)]
COVER = (-1.0, -33.0, 27.5, -2.5)    # analog core under one cover

# ref: (x, y, rotation in degrees counter-clockwise). Position is the footprint anchor:
# pad 1 for headers, terminals, TO-220, R-78 and the PTC fuses; the body centre for SMD parts.
PLACE = {
    # --- Arduino headers (fixed by the Nucleo) ---
    "XS1": (10.87, 40.60, 0), "XS2": (10.87, 17.74, 0),
    "XS3": (59.13, 26.88, 180), "XS4": (59.13, 5.04, 180),

    # --- isolated input: terminal, fuse, TVS, current limiter ---
    "X1": (-10.4, -16.0, 270), "F1": (-11.5, -7.0, 90), "VD1": (-2.2, -1.5, 90),
    "VT1": (-6.0, 6.0, 90), "R1": (-2.5, 13.5, 0),

    # --- isolated analog core (under the cover): shunt, Kelvin resistors, filter, ADC, reference ---
    "R2": (2.5, -5.0, 270), "VD2": (2.5, -10.5, 90),
    "R4": (7.0, -4.5, 270), "R3": (12.0, -4.5, 270), "C1": (9.5, -8.7, 180),
    "VD3": (8.0, -14.0, 90), "C2": (12.0, -14.5, 90), "VD4": (8.0, -18.5, 90), "C3": (12.0, -18.5, 90),
    "DD1": (19.0, -14.0, 270),
    "C13": (20.2, -8.0, 90), "C11": (24.5, -9.5, 90), "C12": (19.2, -20.5, 270), "C10": (21.5, -20.5, 270),
    "DA1": (15.0, -24.0, 90), "C16": (11.5, -24.0, 90),
    "RK1": (18.5, -24.0, 90), "R9": (21.5, -24.0, 90), "C33": (24.0, -24.0, 90),
    "R5": (14.5, -30.0, 0), "C14": (19.0, -29.0, 90), "C15": (21.5, -29.0, 90),

    # --- isolation crossing: digital isolator and DC/DC on the horizontal barrier ---
    "DD2": (20.0, 0.0, 270), "C21": (26.5, -7.5, 90), "C20": (24.5, 9.5, 90),
    "U1": (33.0, 0.0, 0), "C22": (30.0, 10.0, 0),
    # isolated 5 V / 3.3 V column
    "R6": (41.5, -7.0, 90), "C23": (38.0, -8.0, 90), "L1": (41.5, -11.5, 90),
    "C24": (38.0, -13.0, 90), "DA2": (40.0, -19.0, 90), "C25": (38.0, -25.0, 90),

    # --- 24 V input and 5 V (bottom-right overhang: through-hole allowed) ---
    "X2": (80.4, -12.0, 90), "VD5": (70.0, -12.0, 0), "F2": (57.0, -12.0, 0),
    "VD6": (52.0, -18.0, 0), "C30": (54.0, -23.5, 0),
    "DA3": (60.0, -22.0, 0), "C31": (72.0, -22.0, 0), "R7": (72.0, -26.5, 0), "HL1": (72.0, -29.5, 180),
    "J7": (60.0, -31.5, 90), "R10": (55.5, 31.0, 90),

    # --- MCU side helpers over the Nucleo (SMD) ---
    "J5": (15.5, 46.0, 0), "J6": (16.5, 14.5, 0), "G1": (23.0, 15.5, 0), "C32": (23.0, 19.5, 0),
    "R8": (17.0, 8.5, 0), "HL2": (21.0, 8.5, 180),

    # --- output channel 1 (FOUT -> X3: OC, PP, 0 V) ---
    "X3": (80.4, 34.0, 90),
    # left of the D-header: OC MOSFET and drivers
    "VT21": (52.0, 52.0, 0), "VT611": (43.0, 52.5, 0), "R112": (43.0, 48.5, 0), "R111": (49.5, 46.0, 0),
    "VT31": (52.0, 42.0, 0), "R113": (47.0, 42.0, 0), "R110": (43.0, 42.0, 0), "R114": (52.0, 37.5, 0),
    # right of the D-header: push-pull stage, current limit, TVS
    "VT612": (64.0, 53.5, 0), "VD81": (71.0, 53.0, 0), "VT41": (67.5, 47.0, 0),
    "R115": (65.0, 41.5, 0), "R116": (70.0, 41.5, 0), "VT51": (67.5, 36.0, 0),
    "VT71": (64.0, 29.9, 0), "VD71": (70.5, 29.8, 0),

    # --- output channel 2 (POUT -> X4), same layout 28 mm lower ---
    "X4": (80.4, 6.0, 90),
    "VT22": (52.0, 24.0, 0), "VT621": (43.0, 24.5, 0), "R122": (43.0, 20.5, 0), "R121": (49.5, 18.0, 0),
    "VT32": (52.0, 14.0, 0), "R123": (47.0, 14.0, 0), "R120": (43.0, 14.0, 0), "R124": (52.0, 9.5, 0),
    "VT622": (64.0, 25.5, 0), "VD82": (71.0, 25.0, 0), "VT42": (67.5, 19.0, 0),
    "R125": (65.0, 13.5, 0), "R126": (70.0, 13.5, 0), "VT52": (67.5, 8.0, 0),
    "VT72": (64.0, 1.9, 0), "VD72": (70.5, 1.4, 0),
}

BOTTOM = {"XS1", "XS2", "XS3", "XS4"}

# Copper around the DPAK drains of the OC outputs (heat during a short on the output):
# (net, polygon, via positions), on the outer layers and In2
DRAIN = [
    ("Net-(VD71-K)", [(48.5, 47.4), (57.6, 47.4), (57.6, 55.4), (48.5, 55.4)], [(57.1, 49.5), (57.1, 52.0), (57.1, 54.5)]),
    ("Net-(VD72-K)", [(48.5, 19.4), (57.6, 19.4), (57.6, 27.4), (48.5, 27.4)], [(57.1, 21.5), (57.1, 24.0), (57.1, 26.5)]),
]

# Net classes: (track, clearance, via diameter, via drill) in mm
NETCLASSES = {     # narrow enough to reach the 0.65 mm pitch pins of DD1; currents here are < 0.3 A
    "Default": (0.2, 0.2, 0.6, 0.3),
    "Power": (0.3, 0.2, 0.6, 0.3),
    "Loop": (0.3, 0.25, 0.6, 0.3),
}
POWER_NETS = ["+24V", "+5V", "+3V3", "GND", "AGND", "+5V_ISO", "+3V3_ISO", "Net-(VD5-A)", "Net-(VD5-K)",
              "Net-(U1-+VOUT)"]
LOOP_NETS = ["Net-(X1-Pin_1)", "Net-(VD1-A2)", "Net-(VT1-S)", "Net-(VT1-G)", "Net-(VD2-A)"]


def V(x, y):
    return pcbnew.VECTOR2I_MM(x + OX, OY - y)


def mm(v):
    return pcbnew.FromMM(v)


def add_segment(board, layer, a, b, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(layer)
    s.SetStart(V(*a))
    s.SetEnd(V(*b))
    s.SetWidth(mm(width))
    board.Add(s)


def add_arc(board, layer, center, start, end, width=0.1):
    """Quarter arc from start to end around center, through the 45 degree point."""
    cx, cy = center
    mx, my = (start[0] + end[0]) / 2 - cx, (start[1] + end[1]) / 2 - cy
    k = ((start[0] - cx) ** 2 + (start[1] - cy) ** 2) ** 0.5 / (mx * mx + my * my) ** 0.5
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetLayer(layer)
    s.SetArcGeometry(V(*start), V(cx + mx * k, cy + my * k), V(*end))
    s.SetWidth(mm(width))
    board.Add(s)


def add_rect(board, layer, x0, y0, x1, y1, width=0.1):
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        add_segment(board, layer, a, b, width)


def add_text(board, layer, text, x, y, size=1.0, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetPosition(V(x, y))
    t.SetTextSize(pcbnew.VECTOR2I_MM(size, size))
    t.SetTextThickness(mm(size * 0.15))
    t.SetTextAngleDegrees(angle)
    board.Add(t)


def outline(board):
    x0, y0, x1, y1 = BOARD
    r = CORNER
    add_segment(board, pcbnew.Edge_Cuts, (x0 + r, y0), (x1 - r, y0))
    add_segment(board, pcbnew.Edge_Cuts, (x1, y0 + r), (x1, y1 - r))
    add_segment(board, pcbnew.Edge_Cuts, (x1 - r, y1), (x0 + r, y1))
    add_segment(board, pcbnew.Edge_Cuts, (x0, y1 - r), (x0, y0 + r))
    add_arc(board, pcbnew.Edge_Cuts, (x0 + r, y0 + r), (x0, y0 + r), (x0 + r, y0))
    add_arc(board, pcbnew.Edge_Cuts, (x1 - r, y0 + r), (x1 - r, y0), (x1, y0 + r))
    add_arc(board, pcbnew.Edge_Cuts, (x1 - r, y1 - r), (x1, y1 - r), (x1 - r, y1))
    add_arc(board, pcbnew.Edge_Cuts, (x0 + r, y1 - r), (x0 + r, y1), (x0, y1 - r))
    for sx0, sy0, sx1, sy1 in SLOTS:
        add_rect(board, pcbnew.Edge_Cuts, sx0, sy0, sx1, sy1)


def polygon_zone(board, pts, layers, net=None, rule=False, priority=0, name=""):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    z.SetLayerSet(ls)
    if name:
        z.SetZoneName(name)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        p = V(x, y)
        o.Append(p.x, p.y)
    if rule:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(net)
        z.SetAssignedPriority(priority)
        z.SetMinThickness(mm(0.25))
        z.SetLocalClearance(mm(0.3))
        z.SetThermalReliefGap(mm(0.4))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z


def setup_rules(board):
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.5)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.4)
    ds.m_HoleClearance = mm(0.25)
    ns = ds.m_NetSettings
    for name, (tw, cl, vd, vdr) in NETCLASSES.items():
        nc = ns.GetDefaultNetclass() if name == "Default" else pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(tw))
        nc.SetClearance(mm(cl))
        nc.SetViaDiameter(mm(vd))
        nc.SetViaDrill(mm(vdr))
        if name != "Default":
            ns.SetNetclass(name, nc)
    for n in POWER_NETS:
        ns.SetNetclassPatternAssignment(n, "Power")
    for n in LOOP_NETS:
        ns.SetNetclassPatternAssignment(n, "Loop")


def add_pours(board, layers):
    """AGND pour on the isolated side, GND on the rest; the barrier strips stay empty."""
    bx0, by0, bx1, by1 = BOARD
    nonisol = [(9, by1), (bx1, by1), (bx1, by0), (48, by0), (48, 2), (9, 2)]
    for layer in layers:
        name = board.GetLayerName(layer)
        polygon_zone(board, ISO, [layer], board.FindNet("AGND"), priority=1, name="AGND_" + name)
        polygon_zone(board, nonisol, [layer], board.FindNet("GND"), priority=1, name="GND_" + name)


def via(board, net, at, size=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(*at))
    v.SetWidth(mm(size))
    v.SetDrill(mm(drill))
    v.SetNet(board.FindNet(net))
    v.SetLocked(True)
    board.Add(v)


def add_drains(board):
    layers = [pcbnew.F_Cu, pcbnew.B_Cu] + ([pcbnew.In2_Cu] if board.GetCopperLayerCount() == 4 else [])
    for net, poly, _ in DRAIN:
        for layer in layers:
            polygon_zone(board, poly, [layer], board.FindNet(net), priority=2, name="drain")


def track(board, net, pts, width, layer=pcbnew.F_Cu):
    n = board.FindNet(net)
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(*a))
        t.SetEnd(V(*b))
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(n)
        t.SetLocked(True)
        board.Add(t)


def kelvin_tracks(board):
    """Sense lines straight from the shunt pads (R2) to the 1 kOhm filter resistors, away from the
    loop current, which enters R2.1 from the left and leaves R2.2 downwards to VD2."""
    r21, r22 = (2.5, -4.09), (2.5, -5.91)      # R2 at (2.5, -5.0), 270 deg
    r31, r41 = (12.0, -3.59), (7.0, -3.59)     # R3.1, R4.1
    track(board, "Net-(VT1-G)", [r21, (2.5, -2.6), (12.0, -2.6), r31], 0.25)       # S+
    track(board, "Net-(VD2-A)", [r22, (5.5, -5.91), (5.5, -3.59), r41], 0.25)       # S-
    # loop current into R2.1 from the left, on In2 from R1.2 / VT1 gate (the gate draws no current)
    g = "Net-(VT1-G)"
    track(board, g, [r21, (0.8, -4.09)], 0.3)
    via(board, g, (0.8, -4.09))
    inner = pcbnew.In2_Cu if board.GetCopperLayerCount() == 4 else pcbnew.B_Cu
    track(board, g, [(0.8, -4.09), (0.8, 6.0), (-6.0, 6.0)], 0.3, inner)           # to VT1.1 (THT)
    track(board, g, [(0.8, 6.0), (0.8, 10.0), (-1.59, 11.8)], 0.3, inner)
    via(board, g, (-1.59, 11.8))
    track(board, g, [(-1.59, 11.8), (-1.59, 13.5)], 0.3)                            # R1.2


def build(layers, out):
    comps, nets = read_netlist()
    board = pcbnew.NewBoard(out)     # with a project file: net classes are kept there
    board.SetCopperLayerCount(layers)
    setup_rules(board)

    netinfo = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pad_net = {(r, p): name for name, nodes in nets.items() for r, p in nodes}

    missing = [r for r in comps if r not in PLACE]
    if missing:
        raise SystemExit(f"no placement for: {missing}")
    for ref, c in sorted(comps.items()):
        lib_dir, name = footprint_dir(c["footprint"])
        fp = pcbnew.FootprintLoad(lib_dir, name)
        fp.SetFPID(pcbnew.LIB_ID(c["footprint"].split(":")[0], name))
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        if c["tstamp"]:
            fp.SetPath(pcbnew.KIID_PATH("/" + c["tstamp"]))
        board.Add(fp)
        x, y, rot = PLACE[ref]
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        if ref in BOTTOM:      # pins pointing down into the Nucleo: header body under the board
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        t = fp.Reference()
        t.SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
        t.SetTextThickness(mm(0.12))
        for pad in fp.Pads():
            n = pad_net.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(netinfo[n])

    for hx, hy in HOLES:
        h = pcbnew.FootprintLoad(os.path.join(os.path.dirname(footprint_dir("MountingHole:x")[0]),
                                              "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        h.SetReference(f"H{HOLES.index((hx, hy)) + 1}")
        h.Reference().SetVisible(False)
        h.SetPosition(V(hx, hy))
        board.Add(h)

    outline(board)

    # isolation barrier: no copper of any kind in the strips
    for x0, y0, x1, y1 in BARRIER:
        polygon_zone(board, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [pcbnew.F_Cu, pcbnew.B_Cu]
                     + ([pcbnew.In1_Cu, pcbnew.In2_Cu] if layers == 4 else []), rule=True, name="barrier")

    # 4 layers: In1 is the solid AGND / GND plane from the start, so the router drops vias into it
    if layers == 4:
        add_pours(board, [pcbnew.In1_Cu])
    kelvin_tracks(board)
    for net, poly, vias in DRAIN:     # the pours themselves are added after routing (add_drains)
        for at in vias:
            via(board, net, at)

    # silkscreen: cover, heatsink, terminal labels, title
    cx0, cy0, cx1, cy1 = COVER
    add_rect(board, pcbnew.F_SilkS, cx0, cy0, cx1, cy1, 0.15)
    add_text(board, pcbnew.F_SilkS, "COVER", cx0 + 2.5, cy0 + 1.2, 0.8)
    add_rect(board, pcbnew.F_Fab, -14.5, 1.5, -9.6, 15.5, 0.1)
    add_text(board, pcbnew.F_Fab, "HEATSINK", -12.0, 8.5, 0.8, 90)
    add_text(board, pcbnew.F_SilkS, "1.5 kV", 7.0, 30.0, 1.0, 90)
    add_text(board, pcbnew.F_SilkS, "IN+", -13.0, -12.0, 0.8)
    add_text(board, pcbnew.F_SilkS, "IN-", -13.0, -24.5, 0.8)
    add_text(board, pcbnew.F_SilkS, "AM24 shield v1", 33.0, 36.0, 1.5)
    add_text(board, pcbnew.F_SilkS, "PF0", 5.0, 19.3, 0.8)
    add_text(board, pcbnew.F_SilkS, "E5V", 5.0, 49.8, 0.8)
    place_refs(board)
    return board


def place_refs(board, size=0.8, gap=0.35):
    """Put each top-side reference just outside its part, on the first side (above, below, right,
    left) that is clear of pads, other parts, other references and the board edge."""
    mmv = pcbnew.ToMM
    bx0, by0, bx1, by1 = BOARD
    lim = (bx0 + OX + 0.5, OY - by1 + 0.5, bx1 + OX - 0.5, OY - by0 - 0.5)   # sheet coordinates
    holes = [(x0 + OX, OY - y1, x1 + OX, OY - y0) for x0, y0, x1, y1 in SLOTS]

    def box_of(fp):
        xs, ys = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_CrtYd:
                bb = g.GetBoundingBox()
                xs += [mmv(bb.GetLeft()), mmv(bb.GetRight())]
                ys += [mmv(bb.GetTop()), mmv(bb.GetBottom())]
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            xs += [mmv(bb.GetLeft()), mmv(bb.GetRight())]
            ys += [mmv(bb.GetTop()), mmv(bb.GetBottom())]
        return (min(xs), min(ys), max(xs), max(ys))

    fps = [fp for fp in board.GetFootprints() if not fp.IsFlipped() and fp.Pads()]
    bodies = {fp.GetReference(): box_of(fp) for fp in fps}
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            pads.append((mmv(bb.GetLeft()) - 0.15, mmv(bb.GetTop()) - 0.15, mmv(bb.GetRight()) + 0.15, mmv(bb.GetBottom()) + 0.15))
    texts = []

    def hit(r, rects):
        return any(r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3] for q in rects)

    for fp in sorted(fps, key=lambda f: -((bodies[f.GetReference()][2] - bodies[f.GetReference()][0]) *
                                          (bodies[f.GetReference()][3] - bodies[f.GetReference()][1]))):
        ref = fp.GetReference()
        x0, y0, x1, y1 = bodies[ref]
        w, h = len(ref) * 0.75 * size + 0.2, size + 0.2
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cands = [(cx, y0 - gap - h / 2), (cx, y1 + gap + h / 2), (x1 + gap + w / 2, cy), (x0 - gap - w / 2, cy)]
        others = [b for r, b in bodies.items() if r != ref]
        best = None
        for strict in (True, False):
            for px, py in cands:
                r = (px - w / 2, py - h / 2, px + w / 2, py + h / 2)
                if r[0] < lim[0] or r[1] < lim[1] or r[2] > lim[2] or r[3] > lim[3]:
                    continue
                if hit(r, pads) or hit(r, texts) or hit(r, holes) or (strict and hit(r, others)):
                    continue
                best = (px, py, r)
                break
            if best:
                break
        t = fp.Reference()
        if best is None:          # nothing free: leave it on the part's own outline centre
            t.SetVisible(True)
            continue
        t.SetPosition(pcbnew.VECTOR2I_MM(best[0], best[1]))
        t.SetTextAngleDegrees(0)
        texts.append(best[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", type=int, choices=(2, 4), default=4)
    ap.add_argument("--out")
    args = ap.parse_args()
    out = args.out or os.path.join(HW, "am24_shield.kicad_pcb" if args.layers == 4 else "am24_shield_2layer.kicad_pcb")
    board = build(args.layers, out)
    pcbnew.SaveBoard(out, board)
    print(f"{len(board.GetFootprints())} footprints, {args.layers} layers -> {out}")


if __name__ == "__main__":
    main()
