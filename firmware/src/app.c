/* Measurement processing: code -> current -> calibration -> damping -> NE43 -> frequency and pulse rate. */
#include "app.h"
#include "config.h"
#include "outputs.h"
#include "ad7124.h"
#include "board.h"

#define SAMPLE_DT_S      0.05      /* 20 samples/s */
#define ADC_TIMEOUT_MS   300U
#define LIN_LO_MA        3.8       /* NE43 linear range */
#define LIN_HI_MA        20.5

app_state_t app;

static double avg_buf[AVG_N];
static uint32_t avg_pos;
static double hold_freq, hold_flow;

void app_init(void)
{
    app.ftest_hz = -1.0;
    app.last_sample_ms = millis();
    app_apply_config();
}

void app_apply_config(void)
{
    freq_set_clock_ppm(cfg.tcxo_ppm);
    pulse_config(cfg.pulse_width_ms, (int)cfg.pulse_active_high);
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
}

int app_cal_add(double ref_ma)
{
    if (app.avg_n < AVG_N || cfg.cal_n >= CAL_POINTS_MAX)
        return -1;
    double raw = app.avg_raw_ma;
    /* replace a point closer than 0.5 mA, otherwise insert sorted */
    for (uint32_t k = 0; k < cfg.cal_n; k++) {
        double d = cfg.cal_raw_ma[k] - raw;
        if (d < 0.5 && d > -0.5) {
            cfg.cal_raw_ma[k] = (float)raw;
            cfg.cal_ref_ma[k] = (float)ref_ma;
            return 0;
        }
    }
    uint32_t k = cfg.cal_n;
    while (k > 0 && cfg.cal_raw_ma[k - 1] > raw) {
        cfg.cal_raw_ma[k] = cfg.cal_raw_ma[k - 1];
        cfg.cal_ref_ma[k] = cfg.cal_ref_ma[k - 1];
        k--;
    }
    cfg.cal_raw_ma[k] = (float)raw;
    cfg.cal_ref_ma[k] = (float)ref_ma;
    cfg.cal_n++;
    return 0;
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
    double ppms = (cfg.pulse_value > 0.0f) ? flow / 3600000.0 / cfg.pulse_value : 0.0;
    pulse_set_rate(ppms);
}

void app_sample(int32_t code, int adc_error)
{
    app.raw_ma = (double)code / AD7124_FULL_SCALE * cfg.vref_v / cfg.rshunt_ohm * 1000.0;
    app.samples++;
    app.last_sample_ms = millis();

    avg_buf[avg_pos] = app.raw_ma;
    avg_pos = (avg_pos + 1U) % AVG_N;
    if (app.avg_n < AVG_N)
        app.avg_n++;
    double s = 0.0;
    for (uint32_t k = 0; k < app.avg_n; k++)
        s += avg_buf[k];
    app.avg_raw_ma = s / app.avg_n;

    double cal = app_calibrate(app.raw_ma);
    if (cfg.damp_s > 0.0f && app.samples > 1)
        app.cur_ma += (cal - app.cur_ma) * (SAMPLE_DT_S / (cfg.damp_s + SAMPLE_DT_S));
    else
        app.cur_ma = cal;

    uint32_t a = app.alarms & ALM_PULSE;
    if (adc_error)
        a |= ALM_ADC;
    if (app.cur_ma < cfg.alarm_lo_ma)
        a |= ALM_LOW;
    if (app.cur_ma > cfg.alarm_hi_ma)
        a |= ALM_HIGH;
    app.alarms = a;
    apply_outputs();
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
