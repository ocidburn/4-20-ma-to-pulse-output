#!/usr/bin/env python3
"""
Fabrication files for JLCPCB / PCBWay: Gerbers, Excellon drill, pick-and-place, one zip per board.

  python tools/export_fab.py hardware/am24_shield.kicad_pcb hardware/am24_shield_2layer.kicad_pcb

Writes hardware/fab/<board>_fab.zip. Uses kicad-cli from KiCad 10.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

KICAD_CLI = os.environ.get("KICAD_CLI", r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hardware")


def run(*args):
    subprocess.run([KICAD_CLI, *args], check=True, stdout=subprocess.DEVNULL)


def export(board):
    name = os.path.splitext(os.path.basename(board))[0]
    text = open(board, encoding="utf-8").read()
    four = re.search(r'\(\d+ "In1\.Cu" (signal|power|mixed)', text) is not None   # layer table of the board
    copper = ["F.Cu"] + (["In1.Cu", "In2.Cu"] if four else []) + ["B.Cu"]
    layers = copper + ["F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen", "F.Mask", "B.Mask", "Edge.Cuts"]
    tmp = tempfile.mkdtemp(prefix=name + "_")
    try:
        run("pcb", "export", "gerbers", "--layers", ",".join(layers), "--subtract-soldermask",
            "--check-zones", "-o", tmp + os.sep, board)
        run("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
            "--generate-map", "--map-format", "pdf", "-o", tmp + os.sep, board)
        run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
            "-o", os.path.join(tmp, name + "_pos.csv"), board)
        out_dir = os.path.join(HW, "fab")
        os.makedirs(out_dir, exist_ok=True)
        zpath = os.path.join(out_dir, name + "_fab.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(tmp)):
                z.write(os.path.join(tmp, f), f)
        print(f"{name}: {len(os.listdir(tmp))} files, {len(copper)} copper layers -> {os.path.normpath(zpath)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for b in sys.argv[1:] or [os.path.join(HW, "am24_shield.kicad_pcb"), os.path.join(HW, "am24_shield_2layer.kicad_pcb")]:
        export(os.path.abspath(b))
