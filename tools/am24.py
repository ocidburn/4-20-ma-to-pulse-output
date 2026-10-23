#!/usr/bin/env python3
"""
AM24 converter utility: settings, step-by-step calibration, verification, logging.

Needs pyserial:  pip install pyserial
Examples:
  python am24.py ports
  python am24.py -p COM5 meas --watch
  python am24.py -p COM5 conf
  python am24.py -p COM5 set fmax 10000 --save
  python am24.py -p COM5 cal            (calibration wizard with reference resistor + voltmeter)
  python am24.py -p COM5 verify         (check points, error in % of span, CSV report)
  python am24.py -p COM5 tcxo           (clock correction from a frequency counter)
  python am24.py -p COM5 log --interval 1 --file log.csv
  python am24.py --sim cal              (dry run against a built-in simulator, no hardware)
"""
import argparse
import csv
import datetime as dt
import random
import statistics
import sys
import time

SPAN_MA = 16.0
CAL_POINTS = [4.0, 8.0, 12.0, 16.0, 20.0]
VERIFY_POINTS = [3.8, 4.0, 8.0, 12.0, 16.0, 20.0, 20.5]


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
    """Simulated converter: gain/offset error on the raw reading, 5-point piecewise calibration."""

    def __init__(self):
        self.true_ma = 12.0
        self.conf = {"fmin": 0.0, "fmax": 10000.0, "cutoff": 0.0, "damp": 0.0, "qmax": 100.0,
                     "pval": 0.01, "pwidth": 2, "ppol": 1, "alarm_mode": 0, "alarm_freq": 0.0,
                     "alarm_lo": 3.6, "alarm_hi": 21.0, "tcxo_ppm": 0.0, "vref": 3.0, "rshunt": 50.0}
        self.cal = []

    def _raw(self):
        return self.true_ma * 1.0004 - 0.0021 + random.gauss(0, 0.00005)

    def _calibrated(self, raw):
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

    def cmd(self, text):
        t = text.strip()
        u = t.upper()
        if u == "*IDN?":
            return ["AM24,4-20mA to frequency/pulse,fw sim,adc_id 0x04"]
        if u == "RAW?":
            raw = self._raw()
            return [f"RAW={raw:.6f} AVG={raw:.6f} AVG_N=40"]
        if u == "MEAS?":
            i = self._calibrated(self._raw())
            f = self.conf["fmin"] + (i - 4) / 16 * (self.conf["fmax"] - self.conf["fmin"])
            return [f"I={i:.6f} RAW={self._raw():.6f} F={max(f, 0):.4f} Q=0 TOT=0 PULSES=0 OWED=0 ALM=0x00 N=1"]
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
            return []
        if u.startswith("CAL ADD "):
            self.cal.append((self._raw(), float(t.split()[2])))
            return []
        if u == "CAL?":
            return [f"P{n} RAW={r:.6f} REF={f:.6f}" for n, (r, f) in enumerate(sorted(self.cal))]
        if u in ("SAVE", "DEFAULTS", "TOTAL RESET", "FTEST OFF") or u.startswith("FTEST "):
            return []
        raise DeviceError(f"{t}: ERR unknown command")

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


def reference_current(args, nominal, sim):
    """Reference current from the standard resistor and voltmeter, in mA."""
    if args.direct:
        return ask_float(f"  Ток по эталону, мА [{nominal}]: ", nominal if sim else None)
    u = ask_float(f"  Напряжение на эталонном резисторе {args.rref} Ом, В: ",
                  round(nominal * args.rref / 1000.0, 7) if sim else None)
    return u / args.rref * 1000.0


def wait_stable(dev, tol_ma=0.0002, n=5, max_s=60):
    """Wait until the 2 s average stops moving (n readings within tol). Returns the mean raw mA."""
    vals = []
    t0 = time.time()
    while time.time() - t0 < max_s:
        vals.append(float(kv(dev.cmd("RAW?")[0])["AVG"]))
        vals = vals[-n:]
        if len(vals) == n and max(vals) - min(vals) <= tol_ma:
            return statistics.mean(vals)
        time.sleep(0 if isinstance(dev, SimDevice) else 0.5)
    print("  Внимание: показания не установились, точка всё равно записывается.")
    return statistics.mean(vals)


def cmd_cal(dev, args, sim):
    print("Калибровка тока. Схема: источник -> эталонный резистор -> вход X1 -> источник.")
    print("Вольтметр на потенциальных выводах эталонного резистора. Прогрев не менее 1 ч.\n")
    dev.cmd("CAL CLEAR")
    for p in CAL_POINTS:
        if not sim:
            input(f"Установите ток ≈ {p} мА и нажмите Enter...")
        else:
            dev.true_ma = p
        wait_stable(dev)
        ref = reference_current(args, p, sim)
        dev.cmd(f"CAL ADD {ref:.6f}")
        print(f"  Точка {p} мА записана: эталон {ref:.6f} мА")
    print("\nТаблица калибровки:")
    for ln in dev.cmd("CAL?"):
        print("  " + ln)
    if sim or input("Сохранить во flash? [y/N]: ").strip().lower() == "y":
        dev.cmd("SAVE")
        print("Сохранено.")


def cmd_verify(dev, args, sim):
    name = args.file or f"verify_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    rows = []
    fmin, fmax = None, None
    for ln in dev.cmd("CONF?"):
        k, v = ln.split("=", 1)
        if k == "fmin":
            fmin = float(v)
        if k == "fmax":
            fmax = float(v)
    print(f"Проверка, допуск ±{args.limit} % диапазона. Отчёт: {name}")
    for p in VERIFY_POINTS:
        if not sim:
            input(f"Установите ток ≈ {p} мА и нажмите Enter...")
        else:
            dev.true_ma = p
        wait_stable(dev)
        ref = reference_current(args, p, sim)
        readings = [kv(dev.cmd("MEAS?")[0]) for _ in range(5)]
        i_dev = statistics.mean(float(r["I"]) for r in readings)
        f_dev = statistics.mean(float(r["F"]) for r in readings)
        err = (i_dev - ref) / SPAN_MA * 100.0
        f_exp = max(fmin + (ref - 4.0) / 16.0 * (fmax - fmin), 0.0)
        ok = abs(err) <= args.limit
        rows.append([p, f"{ref:.6f}", f"{i_dev:.6f}", f"{err:+.4f}", f"{f_exp:.3f}", f"{f_dev:.3f}",
                     "OK" if ok else "FAIL"])
        print(f"  {p:5.1f} мА: эталон {ref:.6f}, прибор {i_dev:.6f}, ошибка {err:+.4f} % -> {'OK' if ok else 'НЕ ГОДЕН'}")
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["point_mA", "ref_mA", "device_mA", "error_pct_span", "f_expected_Hz", "f_device_Hz", "result"])
        w.writerows(rows)
    bad = sum(r[-1] != "OK" for r in rows)
    print("Итог: годен." if bad == 0 else f"Итог: {bad} точек вне допуска.")


def cmd_tcxo(dev, args, sim):
    f_set = 10000.0
    dev.cmd(f"FTEST {f_set}")
    print(f"На частотном выходе {f_set} Гц. Измерьте частотомером со временем счёта 10 с.")
    conf = {k: v for k, v in (ln.split("=", 1) for ln in dev.cmd("CONF?"))}
    old = float(conf["tcxo_ppm"])
    f_meas = ask_float("Показание частотомера, Гц: ", f_set * (1 + 1.7e-6) if sim else None)
    # output frequency scales with the real clock: f_meas/f_set - 1 = (clock error) - (correction in use)
    ppm = old + (f_meas / f_set - 1.0) * 1e6
    dev.cmd(f"SET tcxo_ppm {ppm:.3f}")
    dev.cmd("FTEST OFF")
    print(f"Поправка генератора: {ppm:+.3f} ppm (было {old:+.3f}).")
    if sim or input("Сохранить во flash? [y/N]: ").strip().lower() == "y":
        dev.cmd("SAVE")
        print("Сохранено.")


def cmd_log(dev, args, sim):
    name = args.file or f"log_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    print(f"Запись в {name}, Ctrl+C для остановки.")
    keys = ["I", "RAW", "F", "Q", "TOT", "PULSES", "ALM"]
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
                if sim and n >= 3:
                    break
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
    print(f"Записано строк: {n}")


def main():
    ap = argparse.ArgumentParser(description="AM24 4-20 mA converter utility")
    ap.add_argument("-p", "--port", help="COM port, e.g. COM5")
    ap.add_argument("--sim", action="store_true", help="use the built-in simulator instead of hardware")
    ap.add_argument("--rref", type=float, default=100.0, help="reference resistor, ohm (from its certificate)")
    ap.add_argument("--direct", action="store_true", help="enter reference current in mA instead of voltage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ports")
    m = sub.add_parser("meas")
    m.add_argument("--watch", action="store_true")
    sub.add_parser("conf")
    s = sub.add_parser("set")
    s.add_argument("key")
    s.add_argument("value")
    s.add_argument("--save", action="store_true")
    sub.add_parser("cal")
    v = sub.add_parser("verify")
    v.add_argument("--limit", type=float, default=0.01, help="tolerance, %% of span (default 0.01)")
    v.add_argument("--file")
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

    if args.sim:
        dev = SimDevice()
    elif args.port:
        dev = Device(args.port)
    else:
        ap.error("укажите -p COMx или --sim")

    try:
        print(dev.cmd("*IDN?")[0])
        if args.cmd == "meas":
            while True:
                print(dev.cmd("MEAS?")[0])
                if not args.watch:
                    break
                time.sleep(0.5)
        elif args.cmd == "conf":
            print("\n".join(dev.cmd("CONF?")))
        elif args.cmd == "set":
            dev.cmd(f"SET {args.key} {args.value}")
            if args.save:
                dev.cmd("SAVE")
            print("OK")
        elif args.cmd == "cal":
            cmd_cal(dev, args, args.sim)
        elif args.cmd == "verify":
            cmd_verify(dev, args, args.sim)
        elif args.cmd == "tcxo":
            cmd_tcxo(dev, args, args.sim)
        elif args.cmd == "log":
            cmd_log(dev, args, args.sim)
    except DeviceError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()


if __name__ == "__main__":
    main()
