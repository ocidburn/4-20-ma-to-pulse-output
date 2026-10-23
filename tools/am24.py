#!/usr/bin/env python3
"""
AM24 converter utility: settings, calibration, verification, temperature coefficient,
pulse-output test against GPS time, logging.

Needs pyserial. A multimeter on GPIB/USB/LAN/RS-232 also needs pyvisa and a VISA library
(Keysight IO Libraries, NI-VISA, or pyvisa-py):
  pip install pyserial pyvisa pyvisa-py

Examples:
  python am24.py ports
  python am24.py -p COM5 meas --watch
  python am24.py -p COM5 set fmax 10000 --save
  python am24.py -p COM5 --rref 100.000123 --dmm GPIB0::22::INSTR --dmm-type hp3458 tempco --minutes 120
  python am24.py -p COM5 --rref 100.000123 --dmm GPIB0::22::INSTR --dmm-type hp3458 cal
  python am24.py -p COM5 --rref 100.000123 --dmm USB0::0x0F7E::...::INSTR verify
  python am24.py -p COM5 --rref 100.000123 --dmm ... pulses --seconds 1000
  python am24.py -p COM5 gps --store
  python am24.py -p COM5 log --interval 1 --file log.csv
  python am24.py --sim cal              (dry run against a built-in simulator, no hardware)

Without --dmm the multimeter is read by hand: start its averaging (math/statistics) when asked,
and type the mean at the end of the window.
"""
import argparse
import csv
import datetime as dt
import math
import random
import statistics
import sys
import time

SPAN_MA = 16.0
CAL_POINTS = [4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
VERIFY_POINTS = [4.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0, 20.0]


class RealClock:
    def now(self):
        return time.time()

    def sleep(self, s):
        if s > 0:
            time.sleep(s)


class VirtualClock:
    """Simulator time: waiting costs nothing."""

    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.0)


CLK = RealClock()


class DeviceError(Exception):
    pass


class Device:
    """Line protocol: send a command, read lines until 'OK' or 'ERR ...'."""

    def __init__(self, port, baud=115200, timeout=3.0):
        import serial  # imported here so --sim works without pyserial
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def _readline(self):
        raw = self.ser.readline()
        if not raw:
            raise DeviceError("no answer (timeout)")
        return raw.decode("ascii", "replace").strip()

    def cmd(self, text):
        self.ser.write((text + "\r\n").encode("ascii"))
        lines = []
        while True:
            ln = self._readline()
            if ln == "OK":
                return lines
            if ln.startswith("ERR"):
                raise DeviceError(f"{text}: {ln}")
            if ln:
                lines.append(ln)

    def close(self):
        self.ser.close()


class SimDevice:
    """Simulated converter: gain/offset error, ADC bow, 1.8 ppm/C drift, GPS PPS, same protocol."""

    PAIRS_PER_S = 20.0 / 3.0

    def __init__(self):
        self.true_ma = 12.0
        self.conf = {"fmin": 0.0, "fmax": 10000.0, "cutoff": 0.0, "damp": 0.0, "qmax": 100.0,
                     "pval": 0.01, "pwidth": 2, "ppol": 1, "alarm_mode": 0, "alarm_freq": 0.0,
                     "alarm_lo": 3.6, "alarm_hi": 21.0, "tcxo_ppm": 0.0, "gps": 1, "gps_win": 100,
                     "vref": 3.0, "rshunt": 50.0, "tc_ppm": 0.0, "t_window": 2.0, "ntc_r25": 10000.0,
                     "ntc_beta": 3380.0, "ntc_rfix": 10000.0}
        self.cal = []
        self.t0 = 25.0
        self.win_t0 = CLK.now()
        self.tot_t0 = CLK.now()

    @staticmethod
    def temp(t):
        return 23.6 + 0.7 * math.sin(2 * math.pi * t / 5400.0)

    def raw_u(self, t):
        x = self.true_ma
        bow = 1.2e-4 * (1 - ((x - 12.0) / 8.0) ** 2)           # ~6 uV ADC nonlinearity
        return (x * 1.0004 + bow - 0.0021) * (1 + 1.8e-6 * (self.temp(t) - 23.6))

    def corrected(self, ru, temp):
        return ru * (1 - self.conf["tc_ppm"] * 1e-6 * (temp - self.t0))

    def calibrate(self, raw):
        pts = sorted(self.cal)
        if not pts:
            return raw
        if len(pts) == 1:
            return raw + pts[0][1] - pts[0][0]
        i = 0
        while i + 2 < len(pts) and raw > pts[i + 1][0]:
            i += 1
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        return y0 + (raw - x0) * (y1 - y0) / (x1 - x0)

    def window(self):
        t1 = CLK.now()
        n = int((t1 - self.win_t0) * self.PAIRS_PER_S)
        tm = (self.win_t0 + t1) / 2
        temp = self.temp(tm)
        ru = self.raw_u(tm) + random.gauss(0, 3e-5 / math.sqrt(max(n, 1)))
        r = self.corrected(ru, temp)
        return n, r, ru, self.calibrate(r), temp, t1 - self.win_t0

    def current(self):
        t = CLK.now()
        return self.calibrate(self.corrected(self.raw_u(t), self.temp(t)))

    def pulses_at(self, t):
        i = min(max(self.current(), 3.8), 20.5)
        flow = self.conf["qmax"] * max((i - 4.0) / 16.0, 0.0)
        return flow / 3600.0 / self.conf["pval"] * (t - self.tot_t0)

    def cmd(self, text):
        t = text.strip()
        u = t.upper()
        now = CLK.now()
        if u == "*IDN?":
            return ["AM24,4-20mA to frequency/pulse,fw sim,adc_id 0x04"]
        if u == "RAW?":
            temp = self.temp(now)
            ru = self.raw_u(now) + random.gauss(0, 3e-5)
            r = self.corrected(ru, temp)
            return [f"RAW={r:.7f} RAWU={ru:.7f} AVG={r:.7f} AVG_N=20 T={temp:.3f}"]
        if u == "WIN START":
            self.win_t0 = now
            return []
        if u == "WIN?":
            n, r, ru, c, temp, sec = self.window()
            return [f"N={n} RAW={r:.8f} RAWU={ru:.8f} CAL={c:.8f} T={temp:.4f} SEC={sec:.3f}"]
        if u == "MEAS?":
            i = self.current()
            f = self.conf["fmin"] + (i - 4) / 16 * (self.conf["fmax"] - self.conf["fmin"])
            p = self.pulses_at(now)
            return [f"I={i:.7f} RAW={i:.7f} F={max(f, 0):.4f} Q=0 TOT={p * self.conf['pval']:.9g} "
                    f"PULSES={int(p)} OWED=0 T={self.temp(now):.3f} CLK=+1.7032(GPS) ALM=0x00 N=1"]
        if u == "CONF?":
            return [f"{k}={v}" for k, v in self.conf.items()]
        if u.startswith("SET "):
            _, k, v = t.split()
            if k not in self.conf:
                raise DeviceError("ERR unknown key")
            self.conf[k] = float(v)
            return []
        if u == "CAL CLEAR":
            self.cal = []
            self.t0 = self.temp(now)
            return []
        if u.startswith("CAL ADD "):
            n, r, _, _, _, _ = self.window()
            if n < 10:
                r = self.corrected(self.raw_u(now), self.temp(now))
            self.cal = [p for p in self.cal if abs(p[0] - r) >= 0.5] + [(r, float(t.split()[2]))]
            return []
        if u == "CAL?":
            return [f"T0={self.t0:.3f} N={len(self.cal)}"] + \
                   [f"P{n} RAW={r:.8f} REF={f:.8f}" for n, (r, f) in enumerate(sorted(self.cal))]
        if u == "GPS?":
            edges = int(now)
            return [f"PPS=1 EDGES={edges} AGE_MS={int((now - edges) * 1000)} WIN_S={edges % 100} "
                    f"WINDOWS={edges // 100} PPM=+1.7032 PTOT={self.pulses_at(edges):.6f}"]
        if u == "TOTAL?":
            p = self.pulses_at(now)
            return [f"PULSES={int(p)} EXACT={p:.6f} OWED=0 TOT={int(p) * self.conf['pval']:.9g} OVF=0"]
        if u == "TOTAL RESET":
            self.tot_t0 = now
            return []
        if u in ("SAVE", "DEFAULTS", "FTEST OFF", "GPS STORE") or u.startswith("FTEST "):
            return []
        raise DeviceError(f"{t}: ERR unknown command")

    def close(self):
        pass


class VisaMeter:
    """DC voltmeter over VISA. 'scpi': Keysight/Fluke/Keithley SCPI; 'hp3458': HP/Agilent 3458A language.
    Not tested on real instruments: check the first readings against the front panel."""

    def __init__(self, resource, kind, rng, nplc, init=None):
        import pyvisa
        self.kind = kind
        self.inst = pyvisa.ResourceManager().open_resource(resource)
        self.inst.timeout = 30000
        if kind == "hp3458":
            self.inst.read_termination = "\r\n"
            self.inst.write_termination = "\r\n"
            cmds = ["PRESET NORM", "OFORMAT ASCII", "END ALWAYS", f"DCV {rng}", f"NPLC {nplc}",
                    "NDIG 8", "TRIG AUTO", "TARM HOLD"]
        else:
            cmds = ["CONF:VOLT:DC", f"VOLT:DC:RANG {rng}", f"VOLT:DC:NPLC {nplc}"]
        if init:
            cmds = [c.strip() for c in init.split(";") if c.strip()]
        for c in cmds:
            self.inst.write(c)
        print(f"Мультиметр: {resource} ({kind}), диапазон {rng} В, NPLC {nplc}")

    def read(self):
        if self.kind == "hp3458":
            self.inst.write("TARM SGL")
            return float(self.inst.read())
        return float(self.inst.query("READ?"))

    def close(self):
        self.inst.close()


class SimMeter:
    """Simulated voltmeter on the reference resistor: 0.05 ppm noise, 0.2 s per reading."""

    def __init__(self, dev, rref):
        self.dev = dev
        self.rref = rref

    def read(self):
        CLK.sleep(0.2)
        return self.dev.true_ma / 1000.0 * self.rref * (1 + random.gauss(0, 5e-8))

    def close(self):
        pass


def kv(line):
    """'I=1.0 F=2' -> {'I': '1.0', 'F': '2'}"""
    out = {}
    for part in line.split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def ask_float(prompt, sim_value=None):
    if sim_value is not None:
        print(f"{prompt}{sim_value}")
        return sim_value
    while True:
        s = input(prompt).strip().replace(",", ".")
        try:
            return float(s)
        except ValueError:
            print("  Нужно число.")


def read_conf(dev):
    return {k: v for k, v in (ln.split("=", 1) for ln in dev.cmd("CONF?"))}


def parse_points(text, default):
    if not text:
        return default
    return [float(x) for x in text.replace(";", ",").split(",") if x.strip()]


def rref_now(args):
    """Reference resistor value at its present temperature, from the certificate."""
    r = args.rref
    if args.rref_temp is not None and args.rref_tc:
        r *= 1 + args.rref_tc * 1e-6 * (args.rref_temp - args.rref_t0)
    return r


def set_current(dev, ma, args):
    if args.sim:
        dev.true_ma = ma
        return
    input(f"Установите ток ≈ {ma} мА и нажмите Enter...")


def front_end_temp(dev):
    t = float(kv(dev.cmd("RAW?")[0])["T"])
    if t < -100:
        raise DeviceError("датчик температуры (NTC) не отвечает: обрыв или замыкание")
    return t


def measure_window(dev, meter, args, seconds, nominal_ma, need_ref=True):
    """Average the converter (WIN) and the multimeter over the same time. Returns a dict."""
    dev.cmd("WIN START")
    t_end = CLK.now() + seconds
    vals = []
    manual = need_ref and meter is None
    if manual:
        print(f"  Запустите усреднение на мультиметре СЕЙЧАС; через {seconds:.0f} с введите среднее.")
    while CLK.now() < t_end:
        if need_ref and meter is not None:
            vals.append(meter.read())
        else:
            CLK.sleep(min(1.0, t_end - CLK.now()))
    w = kv(dev.cmd("WIN?")[0])
    res = {"n": int(w["N"]), "raw": float(w["RAW"]), "rawu": float(w["RAWU"]), "cal": float(w["CAL"]),
           "t": float(w["T"]), "sec": float(w["SEC"]), "ref": None, "ref_sem_ppm": None}
    if not need_ref:
        return res
    if manual:
        print("\a", end="")
        sim_v = round(nominal_ma * rref_now(args) / 1000.0, 8) if args.sim else None
        if args.direct:
            res["ref"] = ask_float("  Среднее показание тока за окно, мА: ", nominal_ma if args.sim else None)
        else:
            v = ask_float("  Среднее напряжение на эталонном резисторе за окно, В: ", sim_v)
            res["ref"] = v / rref_now(args) * 1000.0
    else:
        v = statistics.mean(vals)
        res["ref"] = v / rref_now(args) * 1000.0
        if len(vals) > 2:
            res["ref_sem_ppm"] = statistics.stdev(vals) / math.sqrt(len(vals)) / abs(v) * 1e6
    return res


def solve(a, b):
    """Gaussian elimination for a small dense system."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


def polyfit(xs, ys, deg):
    a = [[sum(x ** (i + j) for x in xs) for j in range(deg + 1)] for i in range(deg + 1)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(deg + 1)]
    return solve(a, b)


def cmd_cal(dev, meter, args):
    pts = parse_points(args.points, CAL_POINTS)
    t = front_end_temp(dev)
    conf = read_conf(dev)
    print("Калибровка тока. Схема: источник -> эталонный резистор -> вход X1 -> источник.")
    print("Мультиметр на потенциальных выводах эталонного резистора. Прогрев не менее 2 ч, крышка закрыта.")
    print(f"Эталон: {rref_now(args):.7f} Ом. Температура входного узла {t:.2f} °C, "
          f"температурный коэффициент tc_ppm = {conf.get('tc_ppm', '?')} ppm/°C.")
    print(f"Точки: {', '.join(f'{p:g}' for p in pts)} мА, окно {args.window:g} с, выдержка {args.settle:g} с.\n")
    dev.cmd("CAL CLEAR")
    rows = []
    for p in pts:
        set_current(dev, p, args)
        CLK.sleep(args.settle)
        m = measure_window(dev, meter, args, args.window, p)
        dev.cmd(f"CAL ADD {m['ref']:.8f}")
        rows.append(m)
        sem = f", СКО среднего {m['ref_sem_ppm']:.2f} ppm" if m["ref_sem_ppm"] is not None else ""
        print(f"  {p:5.1f} мА: эталон {m['ref']:.8f} мА, прибор до калибровки {m['raw']:.8f} мА, "
              f"T {m['t']:.3f} °C, {m['n']} изм.{sem}")
    print("\nТаблица калибровки:")
    for ln in dev.cmd("CAL?"):
        print("  " + ln)
    if len(rows) >= 5:
        xs = [r["raw"] for r in rows]
        ys = [r["ref"] - r["raw"] for r in rows]
        c = polyfit(xs, ys, 3)
        res = [(y - sum(c[k] * x ** k for k in range(4))) / SPAN_MA * 1e6 for x, y in zip(xs, ys)]
        worst = max(range(len(res)), key=lambda k: abs(res[k]))
        print(f"\nОтклонение точек от гладкой кривой (3-я степень): до {abs(res[worst]):.2f} ppm диапазона "
              f"(точка {pts[worst]:g} мА).")
        if abs(res[worst]) > 2.0:
            print("Внимание: больше 2 ppm — проверьте эту точку (установление, контакты, мультиметр).")
    name = args.file or f"cal_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["point_mA", "ref_mA", "raw_mA", "raw_uncorrected_mA", "temp_C", "pairs", "ref_sem_ppm"])
        for p, r in zip(pts, rows):
            w.writerow([p, f"{r['ref']:.9f}", f"{r['raw']:.9f}", f"{r['rawu']:.9f}", f"{r['t']:.4f}", r["n"],
                        "" if r["ref_sem_ppm"] is None else f"{r['ref_sem_ppm']:.3f}"])
    print(f"Протокол: {name}")
    if args.sim or input("Сохранить калибровку во flash? [y/N]: ").strip().lower() == "y":
        dev.cmd("SAVE")
        print("Сохранено.")


def cmd_verify(dev, meter, args):
    pts = parse_points(args.points, VERIFY_POINTS)
    name = args.file or f"verify_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    t0 = float(kv(dev.cmd("CAL?")[0]).get("T0", "nan"))
    print(f"Проверка, допуск ±{args.limit_ppm:g} ppm диапазона (±{args.limit_ppm * 1e-4:g} %). Отчёт: {name}")
    print(f"Температура калибровки {t0:.2f} °C. Неопределённость эталона в результат не входит.\n")
    rows = []
    for p in pts:
        set_current(dev, p, args)
        CLK.sleep(args.settle)
        m = measure_window(dev, meter, args, args.window, p)
        err = (m["cal"] - m["ref"]) / SPAN_MA * 1e6
        ok = abs(err) <= args.limit_ppm
        rows.append([p, f"{m['ref']:.8f}", f"{m['cal']:.8f}", f"{err:+.2f}", f"{m['t']:.3f}",
                     f"{m['t'] - t0:+.3f}", "OK" if ok else "FAIL"])
        print(f"  {p:5.1f} мА: эталон {m['ref']:.8f}, прибор {m['cal']:.8f}, ошибка {err:+6.2f} ppm, "
              f"T {m['t']:.2f} °C ({m['t'] - t0:+.2f}) -> {'OK' if ok else 'НЕ ГОДЕН'}")
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["point_mA", "ref_mA", "device_mA", "error_ppm_span", "temp_C", "temp_minus_cal_C", "result"])
        w.writerows(rows)
    errs = [abs(float(r[3])) for r in rows]
    bad = sum(r[-1] != "OK" for r in rows)
    print(f"Наибольшая ошибка {max(errs):.2f} ppm диапазона. " +
          ("Итог: годен." if bad == 0 else f"Итог: {bad} точек вне допуска."))


def cmd_tempco(dev, meter, args):
    no_ref = args.no_ref
    if not no_ref and meter is None and not args.sim:
        raise DeviceError("для tempco нужен --dmm (или --no-ref при очень стабильном источнике тока)")
    print(f"Температурный коэффициент: ток ≈ {args.current:g} мА, окна по {args.window:g} с, "
          f"всего {args.minutes:g} мин. Температура должна измениться хотя бы на 0,5 °C:")
    print("включение после остывания, смена режима кондиционера, сквозняк снаружи крышки.\n")
    set_current(dev, args.current, args)
    CLK.sleep(args.settle)
    recs = []
    t_end = CLK.now() + args.minutes * 60
    while CLK.now() < t_end:
        m = measure_window(dev, None if no_ref else meter, args, args.window, args.current, need_ref=not no_ref)
        y = m["rawu"] / m["ref"] if not no_ref else m["rawu"]
        recs.append((m["t"], y))
        print(f"  T {m['t']:.3f} °C  отношение {y:.9f}")
    ts = [r[0] for r in recs]
    ys = [r[1] for r in recs]
    span = max(ts) - min(ts)
    if len(recs) < 4 or span < 0.2:
        raise DeviceError(f"мало данных: {len(recs)} окон, размах температуры {span:.2f} °C")
    b0, b1 = polyfit(ts, ys, 1)
    ym = statistics.mean(ys)
    alpha = b1 / ym * 1e6
    resid = [y - (b0 + b1 * t) for t, y in zip(ts, ys)]
    s = math.sqrt(sum(r * r for r in resid) / (len(recs) - 2))
    tm = statistics.mean(ts)
    se = s / math.sqrt(sum((t - tm) ** 2 for t in ts)) / ym * 1e6
    print(f"\nРазмах температуры {span:.2f} °C, {len(recs)} окон.")
    print(f"tc_ppm = {alpha:+.3f} ± {se:.3f} ppm/°C (одна сигма).")
    if span < 0.5:
        print("Внимание: размах меньше 0,5 °C, оценка ненадёжна.")
    if args.apply:
        dev.cmd(f"SET tc_ppm {alpha:.4f}")
        print("Записано в tc_ppm. После этого выполните калибровку (cal) — она возьмёт новую опорную температуру.")
        if args.sim or input("Сохранить во flash? [y/N]: ").strip().lower() == "y":
            dev.cmd("SAVE")
            print("Сохранено.")


def wait_edge(dev, timeout=5.0):
    """Wait for the next PPS edge; return (edge number, exact pulse total latched on it)."""
    e0 = int(kv(dev.cmd("GPS?")[0])["EDGES"])
    t_end = CLK.now() + timeout
    while CLK.now() < t_end:
        CLK.sleep(0.1)
        g = kv(dev.cmd("GPS?")[0])
        if int(g["EDGES"]) != e0:
            return int(g["EDGES"]), float(g["PTOT"])
    raise DeviceError("нет импульсов PPS от GPS")


def cmd_pulses(dev, meter, args):
    g = kv(dev.cmd("GPS?")[0])
    if g.get("PPS") != "1":
        raise DeviceError("нет PPS от GPS: проверка импульсного выхода идёт по времени GPS")
    conf = read_conf(dev)
    qmax, pval, cutoff = float(conf["qmax"]), float(conf["pval"]), float(conf["cutoff"])
    print(f"Проверка импульсного выхода по времени GPS: ток ≈ {args.current:g} мА, {args.seconds:g} с.")
    print(f"qmax {qmax:g} ед./ч, цена импульса {pval:g} ед. Допуск ±{args.limit_ppm:g} ppm диапазона.\n")
    set_current(dev, args.current, args)
    CLK.sleep(args.settle)
    e0, p0 = wait_edge(dev)
    pc0 = CLK.now()
    m = measure_window(dev, meter, args, args.seconds, args.current)
    e1, p1 = wait_edge(dev)
    n = e1 - e0
    if abs(n - (CLK.now() - pc0)) > 3:
        raise DeviceError(f"пропуски PPS: {n} импульсов за {CLK.now() - pc0:.0f} с")
    i_ref = m["ref"]
    frac = (min(max(i_ref, 3.8), 20.5) - 4.0) / 16.0
    if cutoff > 0 and frac * 100 < cutoff:
        frac = 0.0
    expected = qmax * max(frac, 0.0) * n / 3600.0 / pval
    full = qmax * n / 3600.0 / pval
    got = p1 - p0
    err = (got - expected) / full * 1e6
    ok = abs(err) <= args.limit_ppm
    print(f"  {n} с GPS, эталонный ток {i_ref:.8f} мА")
    print(f"  ожидалось {expected:.4f} импульсов, выдано {got:.4f} (с дробной частью)")
    print(f"  ошибка {err:+.2f} ppm диапазона -> {'OK' if ok else 'НЕ ГОДЕН'}")
    print("  Неопределённость эталона в результат не входит.")


def cmd_gps(dev, args):
    g = kv(dev.cmd("GPS?")[0])
    m = kv(dev.cmd("MEAS?")[0])
    print(f"PPS: {'есть' if g['PPS'] == '1' else 'нет'}, импульсов {g['EDGES']}, "
          f"окон измерения {g['WINDOWS']} (идёт {g['WIN_S']} с)")
    print(f"Ошибка генератора по GPS: {float(g['PPM']):+.4f} ppm; в работе: {m.get('CLK', '?')}")
    if args.store:
        dev.cmd("GPS STORE")
        dev.cmd("SAVE")
        print("Поправка записана в tcxo_ppm и сохранена (будет действовать без GPS).")


def cmd_tcxo(dev, args):
    f_set = 10000.0
    dev.cmd(f"FTEST {f_set}")
    print(f"На частотном выходе {f_set} Гц. Измерьте частотомером со временем счёта 10 с.")
    clk = kv(dev.cmd("MEAS?")[0]).get("CLK", "+0(SET)")
    old = float(clk.split("(")[0])                      # correction in use (GPS or tcxo_ppm)
    # output frequency scales with the real clock: f_meas/f_set - 1 = (clock error) - (correction in use)
    f_meas = ask_float("Показание частотомера, Гц: ", f_set * (1 + (1.7 - old) * 1e-6) if args.sim else None)
    ppm = old + (f_meas / f_set - 1.0) * 1e6
    dev.cmd(f"SET tcxo_ppm {ppm:.3f}")
    dev.cmd("FTEST OFF")
    print(f"Поправка генератора: {ppm:+.3f} ppm (в работе было {clk}). При работающем GPS действует поправка от GPS.")
    if args.sim or input("Сохранить во flash? [y/N]: ").strip().lower() == "y":
        dev.cmd("SAVE")
        print("Сохранено.")


def cmd_log(dev, args):
    name = args.file or f"log_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    print(f"Запись в {name}, Ctrl+C для остановки.")
    keys = ["I", "RAW", "F", "Q", "TOT", "PULSES", "T", "CLK", "ALM"]
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["time"] + keys)
        n = 0
        try:
            while True:
                m = kv(dev.cmd("MEAS?")[0])
                w.writerow([dt.datetime.now().isoformat(timespec="milliseconds")] + [m.get(k, "") for k in keys])
                fh.flush()
                n += 1
                if args.sim and n >= 3:
                    break
                CLK.sleep(args.interval)
        except KeyboardInterrupt:
            pass
    print(f"Записано строк: {n}")


def main():
    global CLK
    ap = argparse.ArgumentParser(description="AM24 4-20 mA converter utility")
    ap.add_argument("-p", "--port", help="COM port, e.g. COM5")
    ap.add_argument("--sim", action="store_true", help="use the built-in simulator instead of hardware")
    ap.add_argument("--rref", type=float, default=100.0, help="reference resistor, ohm (from its certificate)")
    ap.add_argument("--rref-tc", type=float, default=0.0, help="its temperature coefficient, ppm/C")
    ap.add_argument("--rref-temp", type=float, help="its temperature now, C (with --rref-tc)")
    ap.add_argument("--rref-t0", type=float, default=23.0, help="certificate temperature, C (default 23)")
    ap.add_argument("--direct", action="store_true", help="manual entry of current in mA instead of voltage")
    ap.add_argument("--dmm", help="VISA resource of the multimeter, e.g. GPIB0::22::INSTR; none = manual entry")
    ap.add_argument("--dmm-type", choices=["scpi", "hp3458"], default="scpi")
    ap.add_argument("--dmm-range", type=float, default=10.0, help="DC voltage range, V (default 10)")
    ap.add_argument("--dmm-nplc", type=float, default=10.0, help="integration time, power line cycles")
    ap.add_argument("--dmm-init", help="own setup commands separated by ';' instead of the built-in ones")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ports")
    m = sub.add_parser("meas")
    m.add_argument("--watch", action="store_true")
    sub.add_parser("conf")
    s = sub.add_parser("set")
    s.add_argument("key")
    s.add_argument("value")
    s.add_argument("--save", action="store_true")
    for name in ("cal", "verify"):
        c = sub.add_parser(name)
        c.add_argument("--points", help="mA, comma separated")
        c.add_argument("--window", type=float, default=60.0, help="averaging window per point, s")
        c.add_argument("--settle", type=float, default=20.0, help="wait after setting the current, s")
        c.add_argument("--file")
        if name == "verify":
            c.add_argument("--limit-ppm", type=float, default=10.0, help="tolerance, ppm of span (10 = 0.001 %%)")
    tc = sub.add_parser("tempco")
    tc.add_argument("--current", type=float, default=20.0)
    tc.add_argument("--minutes", type=float, default=120.0)
    tc.add_argument("--window", type=float, default=60.0)
    tc.add_argument("--settle", type=float, default=20.0)
    tc.add_argument("--no-ref", action="store_true", help="no multimeter: assume the current source is stable")
    tc.add_argument("--apply", action="store_true", help="write the result to tc_ppm")
    pu = sub.add_parser("pulses")
    pu.add_argument("--current", type=float, default=20.0)
    pu.add_argument("--seconds", type=float, default=1000.0)
    pu.add_argument("--settle", type=float, default=20.0)
    pu.add_argument("--limit-ppm", type=float, default=10.0)
    gp = sub.add_parser("gps")
    gp.add_argument("--store", action="store_true", help="keep the GPS clock correction for work without GPS")
    sub.add_parser("tcxo")
    lg = sub.add_parser("log")
    lg.add_argument("--interval", type=float, default=1.0)
    lg.add_argument("--file")
    args = ap.parse_args()

    if args.cmd == "ports":
        from serial.tools import list_ports
        for p in list_ports.comports():
            print(f"{p.device}\t{p.description}")
        return

    meter = None
    if args.sim:
        CLK = VirtualClock()
        dev = SimDevice()
        if args.dmm or not args.direct:
            meter = SimMeter(dev, rref_now(args))
    elif args.port:
        dev = Device(args.port)
        if args.dmm and args.cmd in ("cal", "verify", "tempco", "pulses"):
            meter = VisaMeter(args.dmm, args.dmm_type, args.dmm_range, args.dmm_nplc, args.dmm_init)
    else:
        ap.error("укажите -p COMx или --sim")

    try:
        print(dev.cmd("*IDN?")[0])
        if args.cmd == "meas":
            while True:
                print(dev.cmd("MEAS?")[0])
                if not args.watch:
                    break
                CLK.sleep(0.5)
        elif args.cmd == "conf":
            print("\n".join(dev.cmd("CONF?")))
        elif args.cmd == "set":
            dev.cmd(f"SET {args.key} {args.value}")
            if args.save:
                dev.cmd("SAVE")
            print("OK")
        elif args.cmd == "cal":
            cmd_cal(dev, meter, args)
        elif args.cmd == "verify":
            cmd_verify(dev, meter, args)
        elif args.cmd == "tempco":
            cmd_tempco(dev, meter, args)
        elif args.cmd == "pulses":
            cmd_pulses(dev, meter, args)
        elif args.cmd == "gps":
            cmd_gps(dev, args)
        elif args.cmd == "tcxo":
            cmd_tcxo(dev, args)
        elif args.cmd == "log":
            cmd_log(dev, args)
    except DeviceError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        if meter:
            meter.close()
        dev.close()


if __name__ == "__main__":
    main()
