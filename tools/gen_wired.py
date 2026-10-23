#!/usr/bin/env python3
"""
AM24 shield schematic with visible wiring: real KiCad library symbols, wires between parts,
power symbols for supply rails, net labels only for the few signals that cross blocks.
Writes hardware/am24_shield.kicad_sch (the previous label-only version is kept as am24_shield_labels.kicad_sch).
"""
import os
import sys
from sexpr import lib_symbol
from wired_sheet import Sheet, box_symbol, renumber

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "hardware")

R0805 = "Resistor_SMD:R_0805_2012Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SMA, SMB = "Diode_SMD:D_SMA", "Diode_SMD:D_SMB"
SOT23, SOT223 = "Package_TO_SOT_SMD:SOT-23", "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
TERM2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
TERM3 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal"
PH = "Connector_PinHeader_2.54mm:PinHeader_1x{:02d}_P2.54mm_Vertical"

R = lib_symbol("Device", "R")
C = lib_symbol("Device", "C")
D = lib_symbol("Device", "D")
DZ = lib_symbol("Device", "D_Zener")
TVS = lib_symbol("Device", "D_TVS")
LED = lib_symbol("Device", "LED")
PTC = lib_symbol("Device", "Polyfuse")
FB = lib_symbol("Device", "FerriteBead")
BAV = lib_symbol("Device", "D_Dual_Series_AKC")
NPN = lib_symbol("Transistor_BJT", "BC847")
PNP = lib_symbol("Transistor_BJT", "BC857")
BCP56 = lib_symbol("Transistor_BJT", "BCP56")
BCP53 = lib_symbol("Transistor_BJT", "BCP53")
SS110 = lib_symbol("Diode", "SS110")
R78 = lib_symbol("Converter_DCDC", "R-78HB5.0-0.5")
OSC = lib_symbol("Oscillator", "ASE-xxxMHz")
T2 = lib_symbol("Connector", "Screw_Terminal_01x02")
T3 = lib_symbol("Connector", "Screw_Terminal_01x03")
NDEP = renumber(lib_symbol("Device", "Q_NMOS_Depletion"), {"G": "1", "D": "2", "S": "3"}, "Q_NMOS_Depletion_GDS")
NMOS = renumber(lib_symbol("Device", "Q_NMOS"), {"G": "1", "D": "2", "S": "3"}, "Q_NMOS_GDS")
CONN = {n: lib_symbol("Connector_Generic", f"Conn_01x{n:02d}") for n in (2, 6, 8, 10)}

ADC = box_symbol("AD7124-4BRUZ", "DD",
                 [("8", "AIN0"), ("9", "AIN1"), ("10", "AIN2"), ("11", "AIN3"), ("14", "AIN4"), ("15", "AIN5"),
                  ("16", "AIN6/REFIN2+"), ("17", "AIN7/REFIN2-"), ("18", "REFOUT"), ("21", "PSW"),
                  ("12", "REFIN1+"), ("13", "REFIN1-")],
                 [("22", "AVDD"), ("6", "IOVDD"), ("23", "~{SYNC}"), ("20", "REGCAPA"), ("3", "CLK"), ("5", "REGCAPD"),
                  ("4", "~{CS}"), ("1", "DIN"), ("24", "DOUT/~{RDY}"), ("2", "SCLK"), ("19", "AVSS"), ("7", "DGND")],
                 width=25.4)
ISO = box_symbol("ISO7741DWR", "DD",
                 [("16", "VCC2"), ("10", "EN2"), ("12", "OUTC"), ("13", "OUTB"), ("11", "IND"), ("14", "OUTA"),
                  ("9", "GND2"), ("15", "GND2")],
                 [("1", "VCC1"), ("7", "EN1"), ("5", "INC"), ("4", "INB"), ("6", "OUTD"), ("3", "INA"),
                  ("2", "GND1"), ("8", "GND1")], width=22.86)
REF = box_symbol("LTC6655BHMS8-3", "DA",
                 [("7", "VOUT_F"), ("6", "VOUT_S")],
                 [("2", "VIN"), ("1", "~{SHDN}"), ("3", "GND"), ("4", "GND"), ("5", "GND"), ("8", "GND")], width=17.78)
DCDC = box_symbol("NXE1S0505MC", "U",
                  [("3", "+VIN"), ("1", "-VIN")], [("8", "+VOUT"), ("7", "-VOUT"), ("14", "NA")], width=17.78)
LDO = box_symbol("ADP7118ARDZ-3.3", "DA",
                 [("7", "VIN"), ("8", "VIN"), ("5", "EN"), ("6", "SS"), ("4", "GND"), ("9", "EP")],
                 [("1", "VOUT"), ("2", "VOUT"), ("3", "SENSE")], width=17.78)

H, V = 90, 0          # resistor/capacitor rotation: horizontal, vertical


def two(s, ref, sym, val, fp, x, y, rot, mpn=""):
    """2-pin part with readable text placement."""
    if rot in (90, 270):
        return s.add(ref, sym, val, fp, x, y, rot, mpn=mpn, ref_at=(x, y - 2.54, None), val_at=(x, y + 2.54, None))
    return s.add(ref, sym, val, fp, x, y, rot, mpn=mpn)


def box(s, ref, sym, fp, x, y, mpn, rows):
    ytop = (rows - 1) / 2 * 2.54
    return s.add(ref, sym, sym[1].split(":")[1], fp, x, y, 0, mpn=mpn,
                 ref_at=(x, y - ytop - 3.81, None), val_at=(x, y + ytop + 3.81, None))


def input_and_adc(s):
    YS, YG = 60.96, 101.6
    s.text("ВХОД 4-20 мА И ЗАЩИТА (изолированная сторона, земля AGND)", 20.32, 30.48)
    s.add("X1", T2, "IN 4-20 mA", TERM2, 25.4, YS, 0, mirror="y", ref_at=(20.32, YS - 3.81, None), val_at=(20.32, YS + 6.35, None))
    two(s, "F1", PTC, "MF-R005-0 50mA", "", 40.64, YS, H, "MF-R005-0")
    s.add("VD1", TVS, "SMBJ33CA", SMB, 50.8, 81.28, 90, mpn="SMBJ33CA-13-F")
    s.add("VT1", NDEP, "DN2540N5-G", "Package_TO_SOT_THT:TO-220-3_Vertical", 63.5, 63.5, 90, mpn="DN2540N5-G",
          ref_at=(60.96, 55.88, None), val_at=(63.5, 53.34, None))
    two(s, "R1", R, "22R (15-33R)", R0805, 76.2, YS, H)
    two(s, "R2", R, "50R Z-foil", R0805, 99.06, YS, H, "Y402250R0000A9R")
    s.add("VD2", D, "S1M", SMA, 111.76, 81.28, 90, mpn="S1M")
    two(s, "R3", R, "1k 0.1%", R0805, 120.65, 45.72, H, "ERA-6AEB102V")
    two(s, "R4", R, "1k 0.1%", R0805, 120.65, 53.34, H, "ERA-6AEB102V")
    s.add("C1", C, "0.47u U2J", "Capacitor_SMD:C_1812_4532Metric", 129.54, 49.53, 0, mpn="C1812C474J5JACTU")
    s.add("C2", C, "10n C0G", C0805, 152.4, 41.91, 0, ref_at=(149.1, 41.91, "right"), hide_val=True)
    s.add("C3", C, "10n C0G", C0805, 152.4, 57.15, 0, ref_at=(149.1, 57.15, "right"), hide_val=True)
    s.add("VD3", BAV, "BAV199", SOT23, 139.7, 35.56, 0, mpn="BAV199,215", ref_at=(137.16, 43.18, "right"), hide_val=True)
    s.add("VD4", BAV, "BAV199", SOT23, 139.7, 63.5, 180, mpn="BAV199,215", ref_at=(137.16, 57.15, "right"), hide_val=True)

    s.dx = 12.7
    box(s, "DD1", ADC, "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", 160.02, 59.69, "AD7124-4BRUZ", 12)
    s.dx = 0
    # loop current path
    s.w("X1.1", "F1.1")
    s.w("F1.2", (50.8, YS), "VT1.2")
    s.w((50.8, YS), "VD1.2")
    s.w("VD1.1", (50.8, YG))
    s.w("VT1.3", "R1.1")
    s.w("R1.2", (86.36, YS), "R2.1")
    s.w("VT1.1", (63.5, 71.12), (86.36, 71.12), (86.36, YS))          # gate to the bottom of R1
    s.w("R2.2", (111.76, YS), "VD2.2")
    s.w("VD2.1", (111.76, YG))
    s.w("X1.2", (33.02, 63.5), (33.02, YG), (111.76, YG))             # IN- / AGND star at VD2 cathode
    s.pwr("AGND", 111.76, YG)
    s.flag(33.02, YG)
    # Kelvin sense and filter
    s.w((91.44, YS), (91.44, 45.72), "R3.1")
    s.w((106.68, YS), (106.68, 53.34), "R4.1")
    s.w("R3.2", "DD1.8")
    s.w("R4.2", (154.94, 53.34), (154.94, 48.26), "DD1.9")
    s.w("VD3.3", (139.7, 45.72))
    s.w("VD4.3", (139.7, 53.34))
    s.text("VD3, VD4: BAV199", 116.84, 76.2, 1.27)
    s.text("C2, C3: 10n C0G", 116.84, 78.74, 1.27)
    s.pwr("AGND", *s.P("C2.1"), rot=180, raw=True)
    s.pwr("AGND", *s.P("C3.2"), raw=True)
    s.pwr("AGND", *s.P("VD3.1"), rot=270, raw=True)
    s.pwr("+3V3_ISO", *s.P("VD3.2"), raw=True)
    s.pwr("AGND", *s.P("VD4.1"), raw=True)
    s.pwr("+3V3_ISO", *s.P("VD4.2"), rot=90, raw=True)

    # ADC (block shifted right)
    s.dx = 12.7
    s.text("АЦП AD7124-4 И ИОН", 147.32, 20.32)
    for p in ("10", "11", "14", "15", "16", "17", "18", "21", "3"):
        s.nc(f"DD1.{p}")
    s.w("DD1.13", (142.24, 73.66))
    s.pwr("AGND", 142.24, 73.66)
    s.w("DD1.22", (177.8, 45.72))
    s.w("DD1.6", (177.8, 48.26))
    s.w("DD1.23", (177.8, 50.8), (177.8, 43.18))
    s.pwr("+3V3_ISO", 177.8, 43.18)
    s.add("C12", C, "100n", C0805, 182.88, 53.34, H, ref_at=(182.88, 50.8, None), hide_val=True)
    s.add("C13", C, "100n", C0805, 182.88, 58.42, H, ref_at=(187.96, 58.42, "left"), hide_val=True)
    s.w("DD1.20", "C12.1")
    s.w("DD1.5", "C13.1")
    s.w("C12.2", "C13.2")
    s.pwr("AGND", 186.69, 55.88, rot=90)
    s.w("DD1.19", (177.8, 71.12))
    s.w("DD1.7", (177.8, 73.66), (177.8, 71.12))
    s.w((177.8, 73.66), (177.8, 76.2))
    s.pwr("AGND", 177.8, 76.2)
    for i, ref in enumerate(("C10", "C11")):
        x = 185.42 + i * 10.16
        s.add(ref, C, "100n", C0805, x, 33.02, 0, hide_val=True)
        s.pwr("+3V3_ISO", *s.P(f"{ref}.1"), raw=True)
        s.pwr("AGND", *s.P(f"{ref}.2"), raw=True)

    # reference
    box(s, "DA1", REF, "Package_SO:MSOP-8_3x3mm_P0.65mm", 165.1, 92.71, "LTC6655BHMS8-3#PBF", 6)
    s.w("DA1.7", (139.7, 86.36), (139.7, 71.12), "DD1.12")
    s.w("DA1.6", (151.13, 88.9), (151.13, 86.36))
    s.add("C16", C, "10u (2.7-100u)", C1206, 134.62, 82.55, 0)
    s.w((139.7, 78.74), "C16.1")
    s.pwr("AGND", *s.P("C16.2"), raw=True)
    s.w("DA1.2", (181.61, 86.36))
    s.w("DA1.1", (181.61, 88.9), (181.61, 83.82))
    s.add("R5", R, "10R", R0805, 181.61, 80.01, 0)
    s.pwr("+5V_ISO", *s.P("R5.1"), raw=True)
    s.add("C14", C, "10u", C1206, 186.69, 87.63, 0)
    s.add("C15", C, "100n", C0805, 196.85, 87.63, 0, hide_val=True)
    s.w("R5.2", "C14.1", "C15.1")
    s.pwr("AGND", *s.P("C14.2"), raw=True)
    s.pwr("AGND", *s.P("C15.2"), raw=True)
    for p in ("3", "4", "5", "8"):
        s.hv(f"DA1.{p}", (179.07, s.P(f"DA1.{p}")[1]))
    s.w((179.07, 91.44), (179.07, 101.6))
    s.pwr("AGND", 179.07, 101.6)
    s.dx = 0


def isolation(s):
    s.dx = 12.7
    s.text("РАЗВЯЗКА SPI", 198.12, 20.32)
    box(s, "DD2", ISO, "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm", 214.63, 64.77, "ISO7741DWR", 8)
    for a, b in (("DD1.4", "DD2.12"), ("DD1.1", "DD2.13"), ("DD1.24", "DD2.11"), ("DD1.2", "DD2.14")):
        s.w(a, b)
    s.w("DD2.16", (198.12, 55.88))
    s.w("DD2.10", (198.12, 58.42), (198.12, 53.34))
    s.pwr("+3V3_ISO", 198.12, 53.34)
    s.w("DD2.9", (198.12, 71.12))
    s.w("DD2.15", (198.12, 73.66), (198.12, 71.12))
    s.w((198.12, 73.66), (198.12, 76.2))
    s.pwr("AGND", 198.12, 76.2)
    s.w("DD2.1", (231.14, 55.88))
    s.w("DD2.7", (231.14, 58.42), (231.14, 53.34))
    s.pwr("+3V3", 231.14, 53.34)
    s.w("DD2.2", (231.14, 71.12))
    s.w("DD2.8", (231.14, 73.66), (231.14, 71.12))
    s.w((231.14, 73.66), (231.14, 76.2))
    s.pwr("GND", 231.14, 76.2)
    s.add("C21", C, "100n", C0805, 210.82, 33.02, 0, hide_val=True)
    s.pwr("+3V3_ISO", *s.P("C21.1"), raw=True)
    s.pwr("AGND", *s.P("C21.2"), raw=True)
    s.add("C20", C, "100n", C0805, 231.14, 33.02, 0, hide_val=True)
    s.pwr("+3V3", *s.P("C20.1"), raw=True)
    s.pwr("GND", *s.P("C20.2"), raw=True)
    # Nucleo Arduino header D8-D15
    s.text("NUCLEO-G474RE", 236.22, 20.32)
    s.add("XS3", CONN[10], "Arduino D8-D15", PH.format(10), 243.84, 66.04, 0,
          ref_at=(241.3, 50.8, None), val_at=(246.38, 83.82, None))
    for a, b in (("DD2.5", "XS3.3"), ("DD2.4", "XS3.4"), ("DD2.6", "XS3.5"), ("DD2.3", "XS3.6")):
        s.w(a, b)
    s.w("XS3.7", (231.14, 71.12))
    for p in ("1", "2", "8", "9", "10"):
        s.nc(f"XS3.{p}")
    s.text("D10=PB6 CS, D11=PA7 MOSI, D12=PA6 MISO, D13=PA5 SCK", 251.46, 63.5, 1.27)
    s.text("C10-C13, C15, C20, C21 = 100n X7R 0805", 147.32, 15.24, 1.27)
    s.dx = 0


def iso_power(s):
    s.dx = 12.7
    s.text("ИЗОЛИРОВАННОЕ ПИТАНИЕ", 200.66, 93.98)
    box(s, "U1", DCDC, "Converter_DCDC:Converter_DCDC_Murata_NXExSxxxxMC_SMD", 223.52, 104.14, "NXE1S0505MC-R7", 3)
    s.w("U1.3", (207.01, 101.6), (207.01, 99.06))
    s.pwr("+5V", 207.01, 99.06)
    s.add("C22", C, "10u", C1206, 203.2, 105.41, 0, ref_at=(199.9, 104.14, "right"), val_at=(199.9, 106.68, "right"))
    s.w((207.01, 101.6), "C22.1")
    s.pwr("GND", *s.P("C22.2"), raw=True)
    s.w("U1.1", (209.55, 104.14), (209.55, 109.22))
    s.pwr("GND", 209.55, 109.22)
    s.nc("U1.14")
    s.add("C23", C, "4.7u", C1206, 240.03, 105.41, 0)
    s.add("R6", R, "270R 0.25W", R1206, 252.73, 105.41, 0)
    s.w("U1.8", (260.35, 101.6))
    s.w("U1.7", (237.49, 104.14), (237.49, 111.76), (252.73, 111.76), "R6.2")
    s.w("C23.2", (240.03, 111.76))
    s.pwr("AGND", 237.49, 111.76)
    s.add("L1", FB, "FB 600R", "Inductor_SMD:L_0603_1608Metric", 264.16, 101.6, H, mpn="BLM18KG601SN1D",
          ref_at=(264.16, 93.98, None), val_at=(264.16, 96.52, None))
    s.w("L1.2", (283.21, 101.6))
    s.add("C24", C, "10u", C1206, 273.05, 105.41, 0)
    s.pwr("AGND", *s.P("C24.2"), raw=True)
    s.w((278.13, 101.6), (278.13, 99.06))
    s.pwr("+5V_ISO", 278.13, 99.06)
    s.flag(270.51, 101.6)
    box(s, "DA2", LDO, "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm", 294.64, 107.95, "ADP7118ARDZ-3.3", 6)
    s.w("DA2.8", (280.67, 104.14))
    s.w("DA2.5", (280.67, 106.68), (280.67, 101.6))
    s.nc("DA2.6")
    s.w("DA2.4", (280.67, 111.76))
    s.w("DA2.9", (280.67, 114.3), (280.67, 111.76))
    s.w((280.67, 114.3), (280.67, 116.84))
    s.pwr("AGND", 280.67, 116.84)
    s.w("DA2.1", (308.61, 101.6))
    s.w("DA2.2", (308.61, 104.14))
    s.w("DA2.3", (308.61, 106.68), (308.61, 99.06))
    s.pwr("+3V3_ISO", 308.61, 99.06)
    s.add("C25", C, "10u", C1206, 313.69, 105.41, 0)
    s.w((308.61, 101.6), "C25.1")
    s.pwr("AGND", *s.P("C25.2"), raw=True)
    s.flag(311.15, 101.6)
    s.dx = 0


def main_power(s):
    y = 139.7
    s.text("ПИТАНИЕ 24 В (общий минус GND)", 20.32, 127.0)
    s.add("X2", T2, "24V DC", TERM2, 25.4, y, 0, mirror="y", ref_at=(20.32, y - 3.81, None), val_at=(20.32, y + 6.35, None))
    s.add("VD5", SS110, "SS110", SMA, 40.64, y, 180, mpn="SS110", ref_at=(40.64, y - 3.81, None), val_at=(40.64, y + 3.81, None))
    two(s, "F2", PTC, "MF-R050 0.5A", "", 53.34, y, H, "MF-R050")
    s.add("VD6", DZ, "SMBJ33A", SMB, 64.77, 143.51, 270, mpn="SMBJ33ATR")
    s.add("C30", C, "10u 50V", "Capacitor_SMD:C_1210_3225Metric", 81.28, 143.51, 0)
    s.add("DA3", R78, "R-78HB5.0-0.5", "Converter_DCDC:Converter_DCDC_RECOM_R-78HB-0.5_THT", 104.14, y, 0, mpn="R-78HB5.0-0.5",
          ref_at=(104.14, y - 6.35, None), val_at=(104.14, y - 3.81, None))
    s.add("C31", C, "10u", C1206, 116.84, 143.51, 0)
    s.add("R7", R, "1k", R0805, 129.54, 143.51, 0)
    s.add("HL1", LED, "LED green", "LED_SMD:LED_0805_2012Metric", 129.54, 151.13, 90)
    s.add("J5", CONN[2], "+5V -> E5V (CN7-6)", PH.format(2), 152.4, y, 0, ref_at=(149.86, y - 3.81, None), val_at=(156.21, y + 1.27, "left"))
    s.w("X2.1", "VD5.2")
    s.w("VD5.1", "F2.1")
    s.w("F2.2", "DA3.1")
    s.w("X2.2", (33.02, 142.24), (33.02, 152.4))
    s.pwr("GND", 33.02, 152.4)
    s.flag(33.02, 147.32)
    s.pwr("GND", *s.P("VD6.2"), raw=True)
    s.pwr("GND", *s.P("C30.2"), raw=True)
    s.w((88.9, y), (88.9, 137.16))
    s.pwr("+24V", 88.9, 137.16)
    s.flag(93.98, y)
    s.pwr("GND", *s.P("DA3.2"), raw=True)
    s.w("DA3.3", "J5.1")
    s.w((124.46, y), (124.46, 137.16))
    s.pwr("+5V", 124.46, 137.16)
    s.pwr("GND", *s.P("C31.2"), raw=True)
    s.w("R7.2", "HL1.2")
    s.pwr("GND", *s.P("HL1.1"), raw=True)
    s.w("J5.2", (147.32, 147.32))
    s.pwr("GND", 147.32, 147.32)


def tcxo_alarm_headers(s):
    s.dx = 25.4
    s.text("TCXO, АВАРИЯ, РАЗЪЁМЫ NUCLEO", 147.32, 127.0)
    s.add("G1", OSC, "TCXO 10MHz", "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm", 167.64, 144.78, 0,
          mpn="ASTX-H11-10.000MHZ-T", ref_at=(172.72, 137.16, "left"), val_at=(157.48, 149.86, "right"))
    s.w("G1.4", (167.64, 134.62))
    s.pwr("+3V3", 167.64, 134.62)
    s.w("G1.1", (157.48, 144.78), (157.48, 134.62), (167.64, 134.62))
    s.add("C32", C, "10n", C0805, 152.4, 138.43, 0)
    s.w((157.48, 134.62), "C32.1")
    s.pwr("GND", *s.P("C32.2"), raw=True)
    s.pwr("GND", *s.P("G1.2"), raw=True)
    s.add("J6", CONN[2], "TCXO -> OSC_IN (PF0)", PH.format(2), 185.42, 144.78, 0, ref_at=(182.88, 140.97, None), val_at=(190.5, 151.13, None))
    s.w("G1.3", "J6.1")
    s.w("J6.2", (177.8, 147.32), (177.8, 152.4))
    s.pwr("GND", 177.8, 152.4)

    two(s, "R8", R, "330R", R0805, 219.71, 139.7, H)
    s.add("HL2", LED, "LED red", "LED_SMD:LED_0805_2012Metric", 231.14, 139.7, 180, ref_at=(231.14, 135.89, None), val_at=(231.14, 143.51, None))
    s.w((210.82, 139.7), "R8.1")
    s.label("ALARM", (210.82, 139.7), 180)
    s.w("R8.2", "HL2.2")
    s.w("HL2.1", (237.49, 139.7), (237.49, 144.78))
    s.pwr("GND", 237.49, 144.78)

    s.add("XS1", CONN[8], "Arduino POWER", PH.format(8), 264.16, 142.24, 0, ref_at=(261.62, 132.08, None), val_at=(266.7, 154.94, None))
    for p in ("1", "2", "3", "5", "8"):
        s.nc(f"XS1.{p}")
    s.w("XS1.4", (254.0, 142.24))
    s.pwr("+3V3", 254.0, 142.24, rot=90)
    s.flag(256.54, 142.24)
    s.w("XS1.6", (256.54, 147.32))
    s.w("XS1.7", (256.54, 149.86), (256.54, 147.32))
    s.w((256.54, 149.86), (256.54, 152.4))
    s.pwr("GND", 256.54, 152.4)
    s.add("XS2", CONN[6], "Arduino A0-A5", PH.format(6), 264.16, 165.1, 0, ref_at=(261.62, 157.48, None), val_at=(266.7, 175.26, None))
    for p, net in (("1", "FOUT"), ("2", "POUT"), ("3", "ALARM")):
        x, y = s.P(f"XS2.{p}")
        s.w(f"XS2.{p}", (x - 5.08 - s.dx, y))
        s.label(net, (x - 5.08 - s.dx, y), 180)
    for p in ("4", "5", "6"):
        s.nc(f"XS2.{p}")
    s.text("A0=PA0 FOUT, A1=PA1 POUT, A2=PA4 ALARM", 269.24, 160.02, 1.27)
    s.add("XS4", CONN[8], "Arduino D0-D7", PH.format(8), 292.1, 142.24, 0, ref_at=(289.56, 132.08, None), val_at=(294.64, 154.94, None))
    for p in range(1, 9):
        s.nc(f"XS4.{p}")
    s.dx = 0


def output_channel(s, n, sig, ox, oy, title):
    """Open-drain (OC) and push-pull 24 V (PP) outputs driven from one MCU pin; both invert; ~60 mA limit."""
    k = str(n)
    s.text(title, ox, oy - 10.16)
    # signal bus
    s.label(sig, (ox + 2.54, oy - 2.54), 180)
    s.w((ox + 2.54, oy - 2.54), (ox + 7.62, oy - 2.54), (ox + 7.62, oy + 63.5))
    s.w((ox + 7.62, oy - 2.54), (ox + 53.34, oy - 2.54), (ox + 53.34, oy + 10.16))
    s.add(f"R1{k}0", R, "10k", R0805, ox + 7.62, oy + 67.31, 0)
    s.pwr("GND", *s.P(f"R1{k}0.2"), raw=True)
    # push-pull driver
    two(s, f"R1{k}3", R, "1k", R0805, ox + 13.97, oy + 60.96, H)
    s.w((ox + 7.62, oy + 60.96), f"R1{k}3.1")
    s.add(f"VT3{k}", NPN, "BC847B", SOT23, ox + 25.4, oy + 60.96, 0, mpn="BC847B,215", ref_at=(ox + 30.48, oy + 60.96, "left"), val_at=(ox + 30.48, oy + 63.5, "left"))
    s.w(f"R1{k}3.2", f"VT3{k}.1")
    s.pwr("GND", *s.P(f"VT3{k}.2"), raw=True)
    s.add(f"R1{k}4", R, "4k7 0.25W", R1206, ox + 27.94, oy + 12.7, 0, ref_at=(ox + 22.86, oy + 11.43, "right"), val_at=(ox + 22.86, oy + 13.97, "right"))
    s.pwr("+24V", *s.P(f"R1{k}4.1"), raw=True)
    xb = ox + 27.94                                     # PPB line
    s.w(f"R1{k}4.2", (xb, oy + 55.88))
    s.add(f"VT4{k}", BCP56, "BCP56-16", SOT223, ox + 35.56, oy + 20.32, 0, mpn="BCP56-16T1G")
    s.w(f"VT4{k}.1", (xb, oy + 20.32))
    s.w(f"VT4{k}.2", (ox + 38.1, oy + 12.7))
    s.w(f"VT4{k}.4", (ox + 40.64, oy + 12.7), (ox + 38.1, oy + 12.7))
    s.pwr("+24V", ox + 38.1, oy + 12.7)
    s.add(f"R1{k}5", R, "10R", R0805, ox + 38.1, oy + 31.75, 0)
    s.w(f"VT4{k}.3", f"R1{k}5.1")
    s.add(f"VT6{k}2", NPN, "BC847B", SOT23, ox + 33.02, oy + 27.94, 0, mirror="y", mpn="BC847B,215",
          ref_at=(ox + 26.67, oy + 27.94, "left"), val_at=(ox + 26.67, oy + 30.48, "left"), hide_val=True)
    s.w(f"VT6{k}2.3", (xb, oy + 22.86))
    s.w(f"VT6{k}2.2", (ox + 30.48, oy + 35.56), f"R1{k}5.2")
    s.add(f"R1{k}6", R, "10R", R0805, ox + 38.1, oy + 39.37, 0)
    s.add(f"VT7{k}", PNP, "BC857B", SOT23, ox + 33.02, oy + 43.18, 180, mpn="BC857B,215",
          ref_at=(ox + 26.67, oy + 43.18, "left"), val_at=(ox + 26.67, oy + 45.72, "left"), hide_val=True)  # rot 180 flips justify
    s.w(f"VT7{k}.2", (ox + 30.48, oy + 35.56))
    s.w(f"VT7{k}.3", (xb, oy + 48.26))
    s.add(f"VT5{k}", BCP53, "BCP53-16", SOT223, ox + 35.56, oy + 50.8, 0, mirror="x", mpn="BCP5316QTA")
    s.w(f"R1{k}6.2", f"VT5{k}.3")
    s.w(f"VT5{k}.1", (xb, oy + 50.8))
    s.w(f"VT5{k}.2", (ox + 38.1, oy + 60.96))
    s.w(f"VT5{k}.4", (ox + 40.64, oy + 58.42), (ox + 38.1, oy + 58.42))
    s.pwr("GND", ox + 38.1, oy + 60.96)
    # open drain
    two(s, f"R1{k}1", R, "1k", R0805, ox + 59.69, oy + 10.16, H)
    s.w((ox + 53.34, oy + 10.16), f"R1{k}1.1")
    s.add(f"VT2{k}", NMOS, "NTD3055L104T4G", "Package_TO_SOT_SMD:TO-252-2", ox + 71.12, oy + 10.16, 0, mpn="NTD3055L104T4G", ref_at=(ox + 66.04, oy + 1.27, "left"), val_at=(ox + 66.04, oy - 1.27, "left"))
    s.w(f"R1{k}1.2", f"VT2{k}.1")
    s.add(f"R1{k}2", R, "10R", R0805, ox + 73.66, oy + 21.59, 0)
    s.w(f"VT2{k}.3", f"R1{k}2.1")
    s.pwr("GND", *s.P(f"R1{k}2.2"), raw=True)
    s.add(f"VT6{k}1", NPN, "BC847B", SOT23, ox + 68.58, oy + 17.78, 0, mirror="y", mpn="BC847B,215",
          ref_at=(ox + 62.23, oy + 17.78, "left"), val_at=(ox + 62.23, oy + 20.32, "left"), hide_val=True)
    s.w(f"VT6{k}1.3", f"VT2{k}.1")
    s.pwr("GND", *s.P(f"VT6{k}1.2"), raw=True)
    # outputs: X pin 1 = OC, 2 = PP, 3 = 0 V
    xt = ox + 99.06
    s.add(f"X{2 + n}", T3, f"OUT {k}: OC/PP/0V", TERM3, xt, oy + 35.56, 0, ref_at=(xt + 2.54, oy + 29.21, "left"), val_at=(xt + 2.54, oy + 43.18, "left"))
    s.w(f"VT2{k}.2", (ox + 88.9, oy + 5.08), (ox + 88.9, oy + 33.02), f"X{2 + n}.1")
    s.w((ox + 38.1, oy + 35.56), f"X{2 + n}.2")
    s.w(f"X{2 + n}.3", (ox + 91.44, oy + 38.1), (ox + 91.44, oy + 40.64))
    s.pwr("GND", ox + 91.44, oy + 40.64)
    s.add(f"VD7{k}", DZ, "SMBJ33A", SMB, ox + 93.98, oy + 16.51, 270, mpn="SMBJ33ATR")
    s.w((ox + 88.9, oy + 12.7), f"VD7{k}.1")
    s.pwr("GND", *s.P(f"VD7{k}.2"), raw=True)
    s.add(f"VD8{k}", DZ, "SMBJ33A", SMB, ox + 81.28, oy + 39.37, 270, mpn="SMBJ33ATR")
    s.pwr("GND", *s.P(f"VD8{k}.2"), raw=True)


def build():
    s = Sheet("am24_shield")
    input_and_adc(s)
    isolation(s)
    iso_power(s)
    main_power(s)
    tcxo_alarm_headers(s)
    output_channel(s, 1, "FOUT", 25.4, 205.74, "ВЫХОД 1 — ЧАСТОТНЫЙ (FOUT)")
    output_channel(s, 2, "POUT", 160.02, 205.74, "ВЫХОД 2 — ИМПУЛЬСНЫЙ (POUT)")
    return s


if __name__ == "__main__":
    s = build()
    path = os.path.join(OUT, "am24_shield.kicad_sch")
    nj, problems = s.save(path, paper="A2", title="AM24 shield: 4-20 mA -> frequency/pulse",
                          comments=["generated by tools/gen_wired.py", "X3/X4: 1 = OC, 2 = PP, 3 = 0 V"])
    print(f"{len(s.parts)} parts, {len(s.wires)} wires, {nj} junctions -> {path}")
    for a, b in problems:
        print("OVERLAP", a, b)
    sys.exit(1 if problems else 0)
