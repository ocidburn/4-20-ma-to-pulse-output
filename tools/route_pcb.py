#!/usr/bin/env python3
"""
Route a board made by gen_pcb.py with Freerouting, then add the ground pours and fill them.

  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/route_pcb.py hardware/am24_shield.kicad_pcb --jar freerouting-2.5.0.jar

Freerouting (https://github.com/freerouting/freerouting) needs Java 21+. On a 4-layer board In1 is
the AGND / GND plane: the net classes are limited to the other layers, so no tracks go there and
ground pins get vias into it.
"""
import argparse
import os
import re
import subprocess
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import BARRIER, BOARD, ISO, SLOTS, V, add_drains, add_pours  # noqa: E402


def inside(poly, x, y):
    c = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def stitch(board, pitch=5.0, via=0.6, drill=0.3, gap=0.35):
    """Ground vias on a grid wherever nothing else is near, so the pours on all layers form one
    AGND and one GND each. Board units are converted to mm in the sheet frame."""
    mmv = pcbnew.ToMM
    obstacles = []                     # (kind, data)
    for fp in board.GetFootprints():
        # courtyard extents from its drawing (GetCourtyard() can block when called from a script)
        xs, ys = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                bb = g.GetBoundingBox()
                xs += [mmv(bb.GetLeft()), mmv(bb.GetRight())]
                ys += [mmv(bb.GetTop()), mmv(bb.GetBottom())]
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            xs += [mmv(bb.GetLeft()), mmv(bb.GetRight())]
            ys += [mmv(bb.GetTop()), mmv(bb.GetBottom())]
        if xs:
            obstacles.append(("box", (min(xs), min(ys), max(xs), max(ys))))
    for t in board.GetTracks():
        # a via has a width per layer; GetWidth() without one raises an assert dialog and blocks
        w = mmv(t.GetWidth(pcbnew.F_Cu) if t.GetClass() == "PCB_VIA" else t.GetWidth()) / 2
        obstacles.append(("seg", (mmv(t.GetStart().x), mmv(t.GetStart().y), mmv(t.GetEnd().x), mmv(t.GetEnd().y), w)))
    bx0, by0, bx1, by1 = BOARD
    added = 0
    x = bx0 + 2.5
    while x < bx1 - 2:
        y = by0 + 2.5
        while y < by1 - 2:
            ok = not any(x0 - 0.5 <= x <= x1 + 0.5 and y0 - 0.5 <= y <= y1 + 0.5 for x0, y0, x1, y1 in BARRIER + SLOTS)
            if ok:
                p = V(x, y)
                sx, sy = mmv(p.x), mmv(p.y)
                for kind, d in obstacles:
                    if kind == "box":
                        if d[0] - 0.3 <= sx <= d[2] + 0.3 and d[1] - 0.3 <= sy <= d[3] + 0.3:
                            ok = False
                            break
                    elif seg_dist(sx, sy, *d[:4]) < d[4] + via / 2 + gap:
                        ok = False
                        break
            if ok:
                net = "AGND" if inside(ISO, x, y) else "GND"
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(V(x, y))
                v.SetWidth(pcbnew.FromMM(via))
                v.SetDrill(pcbnew.FromMM(drill))
                v.SetNet(board.FindNet(net))
                board.Add(v)
                obstacles.append(("seg", (sx, sy, sx, sy, via / 2)))
                added += 1
            y += pitch
        x += pitch
    return added


def copper_obstacles(board):
    """(x, y, radius-or-None, segment) of every pad and track, sheet mm, for via placement."""
    mmv = pcbnew.ToMM
    obs = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            obs.append((pad.GetNetname(), "box", (mmv(bb.GetLeft()), mmv(bb.GetTop()), mmv(bb.GetRight()), mmv(bb.GetBottom()))))
    for t in board.GetTracks():
        w = mmv(t.GetWidth(pcbnew.F_Cu) if t.GetClass() == "PCB_VIA" else t.GetWidth()) / 2
        obs.append((t.GetNetname(), "seg", (mmv(t.GetStart().x), mmv(t.GetStart().y), mmv(t.GetEnd().x), mmv(t.GetEnd().y), w)))
    return obs


def via_fits(obs, net, sx, sy, r=0.3, gap=0.25):
    for n, kind, d in obs:
        if kind == "box":
            dx = max(d[0] - sx, 0, sx - d[2])
            dy = max(d[1] - sy, 0, sy - d[3])
            if (dx * dx + dy * dy) ** 0.5 < r + gap:
                return False
        elif seg_dist(sx, sy, *d[:4]) < d[4] + r + gap and n != net or seg_dist(sx, sy, *d[:4]) < d[4] + r:
            return False
    return True


def filled(board, net, layer):
    return [z.GetFilledPolysList(layer) for z in board.Zones()
            if not z.GetIsRuleArea() and z.GetNetname() == net and z.IsOnLayer(layer)]


def copper_layers(board):
    return [pcbnew.F_Cu, pcbnew.B_Cu] + ([pcbnew.In1_Cu, pcbnew.In2_Cu] if board.GetCopperLayerCount() == 4 else [])


def prune_ground_vias(board):
    """Remove unlocked GND/AGND vias that reach copper of their net on fewer than two layers."""
    ends = {}
    for t in board.GetTracks():
        t = t.Cast()
        if t.GetClass() == "PCB_TRACK":
            for p in (t.GetStart(), t.GetEnd()):
                ends.setdefault((p.x, p.y), set()).add(t.GetLayer())
    dead = []
    for t in board.GetTracks():
        v = t.Cast()
        if v.GetClass() != "PCB_VIA" or v.IsLocked() or v.GetNetname() not in ("GND", "AGND"):
            continue
        p = v.GetStart()
        n = sum(1 for lay in copper_layers(board)
                if lay in ends.get((p.x, p.y), set()) or any(ps.Contains(p) for ps in filled(board, v.GetNetname(), lay)))
        if n < 2:
            dead.append(v)
    for v in dead:
        board.Delete(v)
    return len(dead)


def join_islands(board):
    """A pour piece with no via or through-hole pad of its net is cut off from the other layers:
    put a via somewhere inside it."""
    added = 0
    obs = copper_obstacles(board)
    links = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            links.setdefault(t.GetNetname(), []).append(t.GetStart())
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                links.setdefault(pad.GetNetname(), []).append(pad.GetPosition())
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in ("GND", "AGND"):
            continue
        layer = z.GetFirstLayer()
        polys = z.GetFilledPolysList(layer)
        for i in range(polys.OutlineCount()):
            chain = polys.Outline(i)
            if any(chain.PointInside(p) for p in links.get(z.GetNetname(), [])):
                continue
            bb = chain.BBox()
            step = pcbnew.FromMM(0.25)
            done = False
            yy = bb.GetTop()
            while yy <= bb.GetBottom() and not done:
                xx = bb.GetLeft()
                while xx <= bb.GetRight() and not done:
                    p = pcbnew.VECTOR2I(int(xx), int(yy))
                    other = [ps for lay in copper_layers(board) if lay != layer
                             for ps in filled(board, z.GetNetname(), lay)]
                    if chain.PointInside(p, pcbnew.FromMM(0.35)) and any(ps.Contains(p) for ps in other) and \
                            via_fits(obs, z.GetNetname(), pcbnew.ToMM(xx), pcbnew.ToMM(yy)):
                        v = pcbnew.PCB_VIA(board)
                        v.SetPosition(p)
                        v.SetWidth(pcbnew.FromMM(0.6))
                        v.SetDrill(pcbnew.FromMM(0.3))
                        v.SetNet(board.FindNet(z.GetNetname()))
                        board.Add(v)
                        links.setdefault(z.GetNetname(), []).append(p)
                        obs.append((z.GetNetname(), "seg", (pcbnew.ToMM(xx), pcbnew.ToMM(yy), pcbnew.ToMM(xx), pcbnew.ToMM(yy), 0.3)))
                        added += 1
                        done = True
                    xx += step
                yy += step
            if not done:
                bb0 = chain.BBox()
                print(f"  no room for a via in a {z.GetNetname()} piece on {board.GetLayerName(layer)} near "
                      f"({pcbnew.ToMM(bb0.GetCenter().x):.1f}, {pcbnew.ToMM(bb0.GetCenter().y):.1f}) mm")
    return added


def remove_dead_ends(board):
    """Drop vias that join tracks on fewer than two layers and track stubs with a free end,
    repeatedly; both are router leftovers that connect nothing."""
    removed = passes = 0
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    while True:
        items = [t.Cast() for t in board.GetTracks()]      # imported items need the cast for GetPosition()
        tracks = [t for t in items if t.GetClass() == "PCB_TRACK"]
        vias = [t for t in items if t.GetClass() == "PCB_VIA"]
        ends = {}
        for t in tracks:
            for p in (t.GetStart(), t.GetEnd()):
                ends.setdefault((p.x, p.y, t.GetNetCode()), []).append((t, t.GetLayer()))

        def pad_at(p, layer, net):
            return any(pd.GetNetCode() == net and pd.IsOnLayer(layer) and pd.HitTest(p) for pd in pads)

        dead = []
        for v in vias:
            if v.IsLocked():
                continue
            p = v.GetStart()          # GetPosition() of an imported via can come back unwrapped
            layers = {l for _, l in ends.get((p.x, p.y, v.GetNetCode()), [])}
            on_pad = any(pd.GetNetCode() == v.GetNetCode() and pd.HitTest(p) for pd in pads)
            if len(layers) < 2 and not on_pad and v.GetNetname() not in ("GND", "AGND"):
                dead.append(v)
        via_pos = {(v.GetStart().x, v.GetStart().y, v.GetNetCode()) for v in vias if v not in dead}
        for t in tracks:
            if t.IsLocked():
                continue
            for p in (t.GetStart(), t.GetEnd()):
                key = (p.x, p.y, t.GetNetCode())
                others = [o for o, l in ends.get(key, []) if o is not t and l == t.GetLayer()]
                if not others and key not in via_pos and not pad_at(p, t.GetLayer(), t.GetNetCode()):
                    dead.append(t)
                    break
        if not dead or passes >= 10:
            return removed
        for item in dead:
            board.Delete(item)        # Remove() leaves the object alive and confuses later proxies
        removed += len(dead)
        passes += 1


def widen_thin(board, min_w=0.15, new_w=0.2):
    n = 0
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < pcbnew.FromMM(min_w):
            t.SetWidth(pcbnew.FromMM(new_w))
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--jar", required=True, help="freerouting-x.y.z.jar")
    ap.add_argument("--passes", type=int, default=100)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    path = os.path.abspath(args.board)
    base = os.path.splitext(path)[0]
    dsn, ses, log = base + ".dsn", base + ".ses", base + "_freerouting.log"

    board = pcbnew.LoadBoard(path)
    layers = board.GetCopperLayerCount()
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise SystemExit("DSN export failed")
    text = open(dsn, encoding="utf-8").read()
    if layers == 4:   # tracks only on F, In2, B; vias still reach the In1 plane
        text = re.sub(r"\(circuit\n", "(circuit\n        (use_layer F.Cu In2.Cu B.Cu)\n", text)
    # 25 um of margin: Freerouting approximates rounded pad corners a little differently from KiCad's DRC
    text = re.sub(r"\(clearance (\d+(?:\.\d+)?)\)", lambda m: "(clearance %g)" % (float(m.group(1)) + 25), text)
    open(dsn, "w", encoding="utf-8").write(text)

    cmd = ["java", "-jar", args.jar, "--gui.enabled=false", "-de", dsn, "-do", ses,
           "--router.autorouter.max_passes=%d" % args.passes, "-mt", str(args.threads)]
    with open(log, "w", encoding="utf-8") as fh:
        subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=True, cwd=os.path.dirname(path))
    summary = [ln for ln in open(log, encoding="utf-8") if "unrouted" in ln or "could not be routed" in ln
               or ln.startswith("  ")]
    print("".join(summary[-12:]))

    board = pcbnew.LoadBoard(path)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("SES import failed")
    pour = [pcbnew.F_Cu, pcbnew.B_Cu] + ([pcbnew.In2_Cu] if layers == 4 else [])
    print(f"tracks widened to 0.2 mm: {widen_thin(board)}")
    print(f"dead-end vias and stubs removed: {remove_dead_ends(board)}")
    add_pours(board, pour)
    add_drains(board)
    print(f"stitching vias: {stitch(board)}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pruned = prune_ground_vias(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    extra = join_islands(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pruned += prune_ground_vias(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"vias for cut-off pour pieces: {extra}, ground vias on one layer removed: {pruned}")
    pcbnew.SaveBoard(path, board)
    for f in (dsn, ses):
        os.remove(f)
    print(f"routed -> {path}")


if __name__ == "__main__":
    main()
