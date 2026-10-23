/*
 * Measurement processing:
 *   ADC pair (AIN0-AIN1, AIN1-AIN0) -> chopped raw current -> temperature correction (NTC, tc_ppm)
 *   -> calibration -> damping -> NE43 -> frequency and pulse rate.
 */
#include "app.h"
#include "config.h"
#include "outputs.h"
#include "ad7124.h"
#include "board.h"
#include <math.h>

#define ADC_TIMEOUT_MS   500U      /* one pair takes ~150 ms */
#define LIN_LO_MA        3.8       /* NE43 linear range */
#define LIN_HI_MA        20.5
#define TEMP_ALPHA       0.25      /* NTC smoothing per reading (~150 ms) */

app_state_t app;

static double avg_buf[AVG_N];
static uint32_t avg_pos;
static double hold_freq, hold_flow;
static int32_t code_fwd;
static int have_fwd, fwd_error;

static struct {
    uint32_t n, t0_ms;
    double   raw, raw_u, cal, temp;
} win;

void app_init(void)
{
    app.ftest_hz = -1.0;
    app.last_sample_ms = millis();
    app_apply_config();
}

void app_apply_config(void)
{
    if (!cfg.gps_enable || app.clock_src != CLK_GPS) {
        app.clock_ppm = cfg.tcxo_ppm;
        app.clock_src = CLK_STORED;
    }
    freq_set_clock_ppm(app.clock_ppm);
    pulse_config(cfg.pulse_width_ms, (int)cfg.pulse_active_high);
}

void app_gps_ppm(double ppm)
{
    if (!cfg.gps_enable)
        return;
    app.clock_ppm = ppm;
    app.clock_src = CLK_GPS;
    freq_set_clock_ppm(ppm);
}

double app_calibrate(double raw)
{
    uint32_t n = cfg.cal_n;
    if (n == 0)
        return raw;
    if (n == 1)
        return raw + (cfg.cal_ref_ma[0] - cfg.cal_raw_ma[0]);
    /* points are kept sorted by raw value; piecewise linear, end segments extrapolate */
    uint32_t i = 0;
    while (i + 2 < n && raw > cfg.cal_raw_ma[i + 1])
        i++;
    double x0 = cfg.cal_raw_ma[i], x1 = cfg.cal_raw_ma[i + 1];
    double y0 = cfg.cal_ref_ma[i], y1 = cfg.cal_ref_ma[i + 1];
    if (x1 == x0)
        return raw + (y0 - x0);
    return y0 + (raw - x0) * (y1 - y0) / (x1 - x0);
}

void app_cal_clear(void)
{
    cfg.cal_n = 0;
    if (app.temp_ok)
        cfg.cal_t0_c = (float)app.temp_c;     /* temperature correction is referred to this point */
}

int app_cal_add(double ref_ma)
{
    double raw;
    if (win.n >= WIN_MIN)
        raw = win.raw / win.n;
    else if (app.avg_n >= AVG_N)
        raw = app.avg_raw_ma;
    else
        return -1;
    if (cfg.cal_n >= CAL_POINTS_MAX)
        return -1;
    /* replace a point closer than 0.5 mA, otherwise insert sorted */
    for (uint32_t k = 0; k < cfg.cal_n; k++) {
        double d = cfg.cal_raw_ma[k] - raw;
        if (d < 0.5 && d > -0.5) {
            cfg.cal_raw_ma[k] = raw;
            cfg.cal_ref_ma[k] = ref_ma;
            return 0;
        }
    }
    uint32_t k = cfg.cal_n;
    while (k > 0 && cfg.cal_raw_ma[k - 1] > raw) {
        cfg.cal_raw_ma[k] = cfg.cal_raw_ma[k - 1];
        cfg.cal_ref_ma[k] = cfg.cal_ref_ma[k - 1];
        k--;
    }
    cfg.cal_raw_ma[k] = raw;
    cfg.cal_ref_ma[k] = ref_ma;
    cfg.cal_n++;
    return 0;
}

void app_window_start(void)
{
    win.n = 0;
    win.raw = win.raw_u = win.cal = win.temp = 0.0;
    win.t0_ms = millis();
}

void app_window_get(app_window_t *w)
{
    w->n = win.n;
    w->raw_ma = win.n ? win.raw / win.n : 0.0;
    w->raw_u_ma = win.n ? win.raw_u / win.n : 0.0;
    w->cal_ma = win.n ? win.cal / win.n : 0.0;
    w->temp_c = win.n ? win.temp / win.n : 0.0;
    w->seconds = (millis() - win.t0_ms) / 1000.0;
}

static void apply_outputs(void)
{
    double f, flow;
    if (app.alarms & (ALM_LOW | ALM_HIGH | ALM_ADC)) {
        switch (cfg.alarm_mode) {
        case ALARM_FREQ: f = cfg.alarm_freq_hz; flow = 0.0;       break;
        case ALARM_HOLD: f = hold_freq;         flow = hold_flow; break;
        default:         f = 0.0;               flow = 0.0;       break;
        }
    } else {
        double i = app.cur_ma;
        if (i < LIN_LO_MA) i = LIN_LO_MA;
        if (i > LIN_HI_MA) i = LIN_HI_MA;
        double frac = (i - 4.0) / 16.0;
        if (cfg.cutoff_pct > 0.0f && frac * 100.0 < cfg.cutoff_pct)
            frac = 0.0;                                 /* low-flow cutoff (also hides 3.8-4 mA) */
        f = cfg.fmin_hz + frac * (cfg.fmax_hz - cfg.fmin_hz);
        if (f < 0.0)
            f = 0.0;
        flow = frac > 0.0 ? cfg.qmax * frac : 0.0;
        hold_freq = f;
        hold_flow = flow;
    }
    if (app.ftest_hz >= 0.0)
        f = app.ftest_hz;
    app.freq_hz = f;
    app.flow = flow;
    freq_set(f);
    double ppms = (cfg.pulse_value > 0.0) ? flow / 3600000.0 / cfg.pulse_value : 0.0;
    /* the 1 ms integrator tick comes from the TCXO, so a fast clock gives a short tick */
    pulse_set_rate(ppms / (1.0 + app.clock_ppm * 1e-6));
}

static void update_alarms(int adc_error)
{
    uint32_t a = app.alarms & ALM_PULSE;
    if (adc_error)
        a |= ALM_ADC;
    if (app.cur_ma < cfg.alarm_lo_ma)
        a |= ALM_LOW;
    if (app.cur_ma > cfg.alarm_hi_ma)
        a |= ALM_HIGH;
    if (!app.temp_ok || (cfg.cal_n > 0 && fabs(app.temp_c - cfg.cal_t0_c) > cfg.t_window_c))
        a |= ALM_TEMP;
    app.alarms = a;
}

static void current_sample(double raw_u, int adc_error)
{
    uint32_t now = millis();
    double dt = (now - app.last_sample_ms) / 1000.0;
    if (dt < 0.05) dt = 0.05;
    if (dt > 1.0)  dt = 1.0;
    app.last_sample_ms = now;
    app.samples++;

    app.raw_u_ma = raw_u;
    app.raw_ma = raw_u;
    if (app.temp_ok && cfg.tc_ppm != 0.0f)
        app.raw_ma = raw_u * (1.0 - cfg.tc_ppm * 1e-6 * (app.temp_c - cfg.cal_t0_c));

    avg_buf[avg_pos] = app.raw_ma;
    avg_pos = (avg_pos + 1U) % AVG_N;
    if (app.avg_n < AVG_N)
        app.avg_n++;
    double s = 0.0;
    for (uint32_t k = 0; k < app.avg_n; k++)
        s += avg_buf[k];
    app.avg_raw_ma = s / app.avg_n;

    double cal = app_calibrate(app.raw_ma);

    win.n++;
    win.raw += app.raw_ma;
    win.raw_u += raw_u;
    win.cal += cal;
    win.temp += app.temp_c;

    if (cfg.damp_s > 0.0f && app.samples > 1)
        app.cur_ma += (cal - app.cur_ma) * (dt / (cfg.damp_s + dt));
    else
        app.cur_ma = cal;

    update_alarms(adc_error);
    apply_outputs();
}

/* ln(x) = 2 atanh((x-1)/(x+1)); libm's log() sets errno and pulls in newlib stdio */
static double ln(double x)
{
    double y = (x - 1.0) / (x + 1.0), y2 = y * y, term = y, sum = 0.0;
    for (int k = 1; k < 200; k += 2) {
        sum += term / k;
        term *= y2;
        if (term < 1e-17 && term > -1e-17)
            break;
    }
    return 2.0 * sum;
}

static void ntc_sample(int32_t code, int adc_error)
{
    double r = (double)code / AD7124_FULL_SCALE;        /* V(AIN6) / VREF */
    if (adc_error || r < 0.02 || r > 0.98) {
        app.temp_ok = 0;
        return;
    }
    double rntc = cfg.ntc_rfix_ohm * r / (1.0 - r);     /* VREF - Rfix - AIN6 - NTC - AGND */
    double t = 1.0 / (1.0 / 298.15 + ln(rntc / cfg.ntc_r25_ohm) / cfg.ntc_beta_k) - 273.15;
    if (!app.temp_ok)
        app.temp_c = t;
    else
        app.temp_c += (t - app.temp_c) * TEMP_ALPHA;
    app.temp_ok = 1;
}

void app_adc(uint8_t channel, int32_t code, int adc_error)
{
    switch (channel) {
    case ADC_CH_SHUNT:
        code_fwd = code;
        fwd_error = adc_error;
        have_fwd = 1;
        break;
    case ADC_CH_SHUNT_SWAPPED:
        if (have_fwd) {
            /* mean of (+offset + v) and (+offset - v): the offset cancels */
            double diff = 0.5 * ((double)code_fwd - (double)code);
            double raw_u = diff / AD7124_FULL_SCALE * cfg.vref_v / cfg.rshunt_ohm * 1000.0;
            current_sample(raw_u, adc_error || fwd_error);
        }
        have_fwd = 0;
        break;
    case ADC_CH_NTC:
        ntc_sample(code, adc_error);
        break;
    default:
        break;
    }
}

void app_poll(void)
{
    if ((millis() - app.last_sample_ms) > ADC_TIMEOUT_MS && !(app.alarms & ALM_ADC)) {
        app.alarms |= ALM_ADC;
        apply_outputs();
    }
    uint64_t total;
    uint32_t owed;
    int ovf;
    pulse_status(&total, &owed, &ovf);
    if (ovf)
        app.alarms |= ALM_PULSE;
    alarm_led(app.alarms != 0);
}
