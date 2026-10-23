"""Two- and three-terminal parts of the AM24 shield (input protection, outputs, power, LEDs)."""
from kicad_writer import Part

R0805 = "Resistor_SMD:R_0805_2012Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
C1812 = "Capacitor_SMD:C_1812_4532Metric"
SMB = "Diode_SMD:D_SMB"
SMA = "Diode_SMD:D_SMA"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT223 = "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
LED0805 = "LED_SMD:LED_0805_2012Metric"


def r(ref, val, a, b, fp=R0805, mpn=""):
    return Part(ref, val, fp, [("1", "", a, 'L'), ("2", "", b, 'R')], mpn=mpn)


def c(ref, val, a, b, fp=C0805, mpn=""):
    return Part(ref, val, fp, [("1", "", a, 'L'), ("2", "", b, 'R')], mpn=mpn)


def d(ref, val, anode, cathode, fp=SMA, mpn=""):
    return Part(ref, val, fp, [("1", "K", cathode, 'R'), ("2", "A", anode, 'L')], mpn=mpn)


def tvs_bi(ref, a, b, mpn="SMBJ33CA-13-F"):
    return Part(ref, "SMBJ33CA", SMB, [("1", "", a, 'L'), ("2", "", b, 'R')], mpn=mpn)


def output_channel(n, sig):
    """Output stage for one channel: open drain (OC) and push-pull 24 V (PP) from the same MCU pin.
    Both invert the MCU level. Current limit ~60 mA: 10 ohm sense + transistor clamp."""
    s = f"{n}"
    oc, pp, b = f"OC{s}", f"PP{s}", f"PPB{s}"
    return [
        # MCU pin pull-down keeps both stages off while the MCU is in reset
        r(f"R1{s}0", "10k", sig, "GND"),
        # open drain
        r(f"R1{s}1", "1k", sig, f"G{s}"),
        Part(f"VT2{s}", "NTD3055L104T4G", "Package_TO_SOT_SMD:TO-252-2",
             [("1", "G", f"G{s}", 'L'), ("2", "D", oc, 'R'), ("3", "S", f"S{s}", 'R')], mpn="NTD3055L104T4G"),
        r(f"R1{s}2", "10R", f"S{s}", "GND"),
        Part(f"VT6{s}1", "BC847B", SOT23, [("1", "B", f"S{s}", 'L'), ("2", "E", "GND", 'L'), ("3", "C", f"G{s}", 'R')],
             mpn="BC847B,215"),
        d(f"VD7{s}", "SMBJ33A", "GND", oc, fp=SMB, mpn="SMBJ33ATR"),
        # push-pull
        r(f"R1{s}3", "1k", sig, f"B{s}"),
        Part(f"VT3{s}", "BC847B", SOT23, [("1", "B", f"B{s}", 'L'), ("2", "E", "GND", 'L'), ("3", "C", b, 'R')],
             mpn="BC847B,215"),
        r(f"R1{s}4", "4k7 0.25W", "+24V", b, fp="Resistor_SMD:R_1206_3216Metric"),
        Part(f"VT4{s}", "BCP56-16", SOT223, [("1", "B", b, 'L'), ("2", "C", "+24V", 'R'), ("3", "E", f"E1{s}", 'R')],
             mpn="BCP56-16T1G"),
        r(f"R1{s}5", "10R", f"E1{s}", pp),
        Part(f"VT6{s}2", "BC847B", SOT23, [("1", "B", f"E1{s}", 'L'), ("2", "E", pp, 'L'), ("3", "C", b, 'R')],
             mpn="BC847B,215"),
        Part(f"VT5{s}", "BCP53-16", SOT223, [("1", "B", b, 'L'), ("2", "C", "GND", 'R'), ("3", "E", f"E2{s}", 'R')],
             mpn="BCP5316QTA"),
        r(f"R1{s}6", "10R", f"E2{s}", pp),
        Part(f"VT7{s}", "BC857B", SOT23, [("1", "B", f"E2{s}", 'L'), ("2", "E", pp, 'L'), ("3", "C", b, 'R')],
             mpn="BC857B,215"),
        d(f"VD8{s}", "SMBJ33A", "GND", pp, fp=SMB, mpn="SMBJ33ATR"),
        Part(f"X{2 + n}", f"OUT{s} PP/OC/0V", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
             [("1", "PP", pp, 'L'), ("2", "OC", oc, 'L'), ("3", "0V", "GND", 'L')]),
    ]
