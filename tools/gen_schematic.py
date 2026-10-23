#!/usr/bin/env python3
"""
Generates hardware/am24_shield.kicad_sch (+ .kicad_pro) for the AM24 shield.

Pinouts checked against datasheets (Oct 2026): AD7124-4 TSSOP-24 (ADI Rev. E), ISO7741 DW (TI SLLSEP4K),
LTC6655 MSOP-8, ADP7118 SOIC-8 (ADI Rev. H), NXE1 (Murata KDC_NXE1.H01), ASTX-H11 (Abracon), R-78HB (RECOM).
Standard pinouts NOT confirmed from a datasheet text (verify against the drawings): DN2540N5 TO-220 G-D-S,
NTD3055L104 DPAK G-D-S, BCP56/BCP53 SOT-223 B-C-E, BAV199 SOT-23 (1 = A1, 2 = K2, 3 = K1/A2).
"""
import json
import os
from kicad_writer import Part, write_schematic, snap
from parts_discrete import r, c, d, tvs_bi, output_channel, R0805, C0805, C1206, C1812, SMA, SMB, SOT23, LED0805

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "hardware")

TSSOP24 = "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"
SOIC16W = "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm"
MSOP8 = "Package_SO:MSOP-8_3x3mm_P0.65mm"
TERM2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"


def input_block():
    return [
        Part("X1", "IN 4-20 mA", TERM2, [("1", "IN+", "LOOP_P", 'R'), ("2", "IN-", "AGND", 'R')]),
        Part("F1", "MF-R005-0 50mA", "", [("1", "", "LOOP_P", 'L'), ("2", "", "LOOP_F", 'R')], mpn="MF-R005-0"),
        tvs_bi("VD1", "LOOP_F", "AGND"),
        Part("VT1", "DN2540N5-G", "Package_TO_SOT_THT:TO-220-3_Vertical",
             [("1", "G", "SH_P", 'L'), ("2", "D", "LOOP_F", 'L'), ("3", "S", "LIM_S", 'R')], mpn="DN2540N5-G"),
        r("R1", "22R (select 15-33R)", "LIM_S", "SH_P"),
        r("R2", "50R Z-foil 0.05%", "SH_P", "SH_N", mpn="Y402250R0000A9R"),
        d("VD2", "S1M", "SH_N", "AGND", fp=SMA, mpn="S1M"),
        r("R3", "1k 0.1% 25ppm", "SH_P", "AIN0", mpn="ERA-6AEB102V"),
        r("R4", "1k 0.1% 25ppm", "SH_N", "AIN1", mpn="ERA-6AEB102V"),
        c("C1", "0.47u 50V U2J", "AIN0", "AIN1", fp=C1812, mpn="C1812C474J5JACTU"),
        c("C2", "10n C0G", "AIN0", "AGND"),
        c("C3", "10n C0G", "AIN1", "AGND"),
        Part("VD3", "BAV199", SOT23, [("1", "A1", "AGND", 'L'), ("2", "K2", "+3V3_ISO", 'R'), ("3", "K1A2", "AIN0", 'R')],
             mpn="BAV199,215"),
        Part("VD4", "BAV199", SOT23, [("1", "A1", "AGND", 'L'), ("2", "K2", "+3V3_ISO", 'R'), ("3", "K1A2", "AIN1", 'R')],
             mpn="BAV199,215"),
    ]


def adc_block():
    adc = Part("DD1", "AD7124-4BRUZ", TSSOP24, [
        ("8", "AIN0", "AIN0", 'L'), ("9", "AIN1", "AIN1", 'L'),
        ("10", "AIN2", None, 'L'), ("11", "AIN3", None, 'L'), ("14", "AIN4", None, 'L'), ("15", "AIN5", None, 'L'),
        ("16", "AIN6/REF2+", None, 'L'), ("17", "AIN7/REF2-", None, 'L'),
        ("12", "REFIN1+", "VREF", 'L'), ("13", "REFIN1-", "AGND", 'L'),
        ("18", "REFOUT", None, 'L'), ("21", "PSW", None, 'L'),
        ("22", "AVDD", "+3V3_ISO", 'R'), ("6", "IOVDD", "+3V3_ISO", 'R'), ("19", "AVSS", "AGND", 'R'),
        ("7", "DGND", "AGND", 'R'), ("20", "REGCAPA", "REGCAPA", 'R'), ("5", "REGCAPD", "REGCAPD", 'R'),
        ("2", "SCLK", "SCLK_ISO", 'R'), ("1", "DIN", "DIN_ISO", 'R'), ("24", "DOUT/RDY", "DOUT_ISO", 'R'),
        ("4", "CS", "CS_ISO", 'R'), ("23", "SYNC", "+3V3_ISO", 'R'), ("3", "CLK", None, 'R'),
    ], mpn="AD7124-4BRUZ")
    ref = Part("DA1", "LTC6655BHMS8-3", MSOP8, [
        ("2", "VIN", "+5V_REF", 'L'), ("1", "SHDN", "+5V_REF", 'L'), ("3", "GND", "AGND", 'L'), ("4", "GND", "AGND", 'L'),
        ("5", "GND", "AGND", 'L'), ("8", "GND", "AGND", 'L'),
        ("7", "VOUT_F", "VREF", 'R'), ("6", "VOUT_S", "VREF", 'R'),
    ], mpn="LTC6655BHMS8-3#PBF")
    return [
        adc,
        c("C10", "100n", "+3V3_ISO", "AGND"), c("C11", "100n", "+3V3_ISO", "AGND"),
        c("C12", "100n", "REGCAPA", "AGND"), c("C13", "100n", "REGCAPD", "AGND"),
        ref,
        r("R5", "10R", "+5V_ISO", "+5V_REF"),
        c("C14", "10u 16V", "+5V_REF", "AGND", fp=C1206), c("C15", "100n", "+5V_REF", "AGND"),
        c("C16", "10u 16V (2.7-100u req.)", "VREF", "AGND", fp=C1206),
    ]


def isolation_block():
    iso = Part("DD2", "ISO7741DWR", SOIC16W, [
        ("1", "VCC1", "+3V3", 'L'), ("2", "GND1", "GND", 'L'), ("8", "GND1", "GND", 'L'), ("7", "EN1", "+3V3", 'L'),
        ("3", "INA", "SCK_MCU", 'L'), ("4", "INB", "MOSI_MCU", 'L'), ("5", "INC", "CS_MCU", 'L'), ("6", "OUTD", "MISO_MCU", 'L'),
        ("16", "VCC2", "+3V3_ISO", 'R'), ("9", "GND2", "AGND", 'R'), ("15", "GND2", "AGND", 'R'), ("10", "EN2", "+3V3_ISO", 'R'),
        ("14", "OUTA", "SCLK_ISO", 'R'), ("13", "OUTB", "DIN_ISO", 'R'), ("12", "OUTC", "CS_ISO", 'R'), ("11", "IND", "DOUT_ISO", 'R'),
    ], mpn="ISO7741DWR")
    dcdc = Part("U1", "NXE1S0505MC-R7", "Converter_DCDC:Converter_DCDC_Murata_NXExSxxxxMC_SMD", [
        ("3", "+VIN", "+5V", 'L'), ("1", "-VIN", "GND", 'L'),
        ("8", "+VOUT", "+5V_ISO_RAW", 'R'), ("7", "-VOUT", "AGND", 'R'), ("14", "NA", None, 'R'),
    ], mpn="NXE1S0505MC-R7")
    ldo = Part("DA2", "ADP7118ARDZ-3.3", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm", [
        ("7", "VIN", "+5V_ISO", 'L'), ("8", "VIN", "+5V_ISO", 'L'), ("5", "EN", "+5V_ISO", 'L'), ("4", "GND", "AGND", 'L'),
        ("9", "EP", "AGND", 'L'), ("6", "SS", None, 'L'),
        ("1", "VOUT", "+3V3_ISO", 'R'), ("2", "VOUT", "+3V3_ISO", 'R'), ("3", "SENSE", "+3V3_ISO", 'R'),
    ], mpn="ADP7118ARDZ-3.3")
    return [
        iso, c("C20", "100n", "+3V3", "GND"), c("C21", "100n", "+3V3_ISO", "AGND"),
        dcdc, c("C22", "10u 16V", "+5V", "GND", fp=C1206), c("C23", "4.7u 16V", "+5V_ISO_RAW", "AGND", fp=C1206),
        # NXE1 needs >= 10 % load (20 mA); the isolated side draws only ~8-10 mA
        r("R6", "270R 0.25W ballast", "+5V_ISO_RAW", "AGND", fp="Resistor_SMD:R_1206_3216Metric"),
        Part("L1", "BLM18KG601SN1D", "Inductor_SMD:L_0603_1608Metric", [("1", "", "+5V_ISO_RAW", 'L'), ("2", "", "+5V_ISO", 'R')],
             mpn="BLM18KG601SN1D"),
        c("C24", "10u 16V", "+5V_ISO", "AGND", fp=C1206),
        ldo, c("C25", "10u 16V", "+3V3_ISO", "AGND", fp=C1206),
    ]


def power_block():
    return [
        Part("X2", "24V DC", TERM2, [("1", "+24V", "+24V_IN", 'R'), ("2", "0V", "GND", 'R')]),
        d("VD5", "SS110", "+24V_IN", "+24V_P", fp=SMA, mpn="SS110"),
        Part("F2", "MF-R050 0.5A", "", [("1", "", "+24V_P", 'L'), ("2", "", "+24V", 'R')], mpn="MF-R050"),
        d("VD6", "SMBJ33A", "GND", "+24V", fp=SMB, mpn="SMBJ33ATR"),
        c("C30", "10u 50V", "+24V", "GND", fp="Capacitor_SMD:C_1210_3225Metric"),
        Part("DA3", "R-78HB5.0-0.5", "Converter_DCDC:Converter_DCDC_RECOM_R-78HB-0.5_THT", [("1", "+VIN", "+24V", 'L'), ("2", "GND", "GND", 'L'), ("3", "+VOUT", "+5V", 'R')],
             mpn="R-78HB5.0-0.5"),
        c("C31", "10u 16V", "+5V", "GND", fp=C1206),
        Part("G1", "ASTX-H11-10.000MHZ-T", "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
             [("4", "VDD", "+3V3", 'L'), ("1", "OE", "+3V3", 'L'), ("2", "GND", "GND", 'L'), ("3", "OUT", "TCXO_OUT", 'R')],
             mpn="ASTX-H11-10.000MHZ-T"),
        c("C32", "10n", "+3V3", "GND"),
        Part("J6", "TCXO -> OSC_IN (PF0)", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
             [("1", "OUT", "TCXO_OUT", 'L'), ("2", "GND", "GND", 'L')]),
        Part("J5", "+5V -> E5V (CN7-6)", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
             [("1", "E5V", "+5V", 'L'), ("2", "GND", "GND", 'L')]),
        r("R7", "1k", "+5V", "LED_PWR"), Part("HL1", "LED green", LED0805, [("2", "A", "LED_PWR", 'L'), ("1", "K", "GND", 'R')]),
        r("R8", "330R", "ALARM", "LED_ALM"), Part("HL2", "LED red", LED0805, [("2", "A", "LED_ALM", 'L'), ("1", "K", "GND", 'R')]),
    ]


def arduino_block():
    ph = "Connector_PinHeader_2.54mm:PinHeader_1x{:02d}_P2.54mm_Vertical"
    return [
        Part("XS1", "Arduino POWER", ph.format(8), [("1", "NC", None, 'R'), ("2", "IOREF", None, 'R'), ("3", "RESET", None, 'R'),
             ("4", "3V3", "+3V3", 'R'), ("5", "5V", None, 'R'), ("6", "GND", "GND", 'R'), ("7", "GND", "GND", 'R'),
             ("8", "VIN", None, 'R')]),
        Part("XS2", "Arduino A0-A5", ph.format(6), [("1", "A0 PA0", "FOUT", 'R'), ("2", "A1 PA1", "POUT", 'R'),
             ("3", "A2 PA4", "ALARM", 'R'), ("4", "A3", None, 'R'), ("5", "A4", None, 'R'), ("6", "A5", None, 'R')]),
        Part("XS3", "Arduino D8-D15", ph.format(10), [("1", "D8", None, 'R'), ("2", "D9", None, 'R'),
             ("3", "D10 PB6", "CS_MCU", 'R'), ("4", "D11 PA7", "MOSI_MCU", 'R'), ("5", "D12 PA6", "MISO_MCU", 'R'),
             ("6", "D13 PA5", "SCK_MCU", 'R'), ("7", "GND", "GND", 'R'), ("8", "AREF", None, 'R'), ("9", "SDA", None, 'R'),
             ("10", "SCL", None, 'R')]),
        Part("XS4", "Arduino D0-D7", ph.format(8), [(str(i + 1), f"D{i}", None, 'R') for i in range(8)]),
    ]


def place(columns, x0=40.0, y0=40.0, col_w=95.0, gap=10.16):
    """columns: list of (title, [parts]); stacks parts top-down in each column."""
    texts, parts = [], []
    for ci, (title, plist) in enumerate(columns):
        x = snap(x0 + ci * col_w)
        y = y0
        texts.append((x - 25.4, y0 - 12.7, title, 2.0))
        for p in plist:
            _, _, w, h = p.geometry()
            p.x, p.y = x, snap(y + h / 2)
            y = p.y + h / 2 + gap
            parts.append(p)
    return parts, texts


def main():
    os.makedirs(OUT, exist_ok=True)
    outs = output_channel(1, "FOUT") + output_channel(2, "POUT")
    columns = [
        ("ВХОД И ЗАЩИТА (изолир.)", input_block()),
        ("АЦП И ИОН (изолир.)", adc_block()),
        ("РАЗВЯЗКА И ПИТАНИЕ ИЗОЛ.", isolation_block()),
        ("ПИТАНИЕ 24 В, TCXO, NUCLEO", power_block() + arduino_block()),
        ("ВЫХОД F (частота)", outs[:17]),
        ("ВЫХОД P (импульсы)", outs[17:]),
    ]
    parts, texts = place(columns)
    sch = os.path.join(OUT, "am24_shield.kicad_sch")
    write_schematic(sch, "am24_shield", parts, texts, paper="A1")
    with open(os.path.join(OUT, "am24_shield.kicad_pro"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"filename": "am24_shield.kicad_pro", "version": 1}}, f)

    # parts list straight from the schematic data
    bom = {}
    for p in parts:
        key = (p.value, p.mpn, p.footprint)
        bom.setdefault(key, []).append(p.ref)
    with open(os.path.join(OUT, "am24_shield_bom.csv"), "w", encoding="utf-8") as f:
        f.write("refs;qty;value;mpn;footprint\n")
        for (val, mpn, fp), refs in sorted(bom.items(), key=lambda kv: kv[1][0]):
            f.write(f"{' '.join(sorted(refs))};{len(refs)};{val};{mpn};{fp or 'TO ASSIGN'}\n")

    nets = {}
    for p in parts:
        for num, name, net, side in p.pins:
            if net:
                nets.setdefault(net, []).append(f"{p.ref}.{num}")
    single = {n: v for n, v in nets.items() if len(v) < 2}
    print(f"{len(parts)} parts, {len(nets)} nets -> {sch}")
    if single:
        print("WARNING single-pin nets:", single)


if __name__ == "__main__":
    main()
