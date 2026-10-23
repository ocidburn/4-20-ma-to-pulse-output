/*
 * Text command interface on the virtual COM port (115200 8N1, lines end with CR or LF).
 * Every reply ends with a line "OK" or "ERR <reason>", so the PC utility can parse it.
 *
 *   *IDN?                 identification
 *   MEAS?                 I, raw, frequency, flow, total, alarms (key=value)
 *   RAW?                  raw current and its 2 s average (for calibration)
 *   CONF?                 all settings, one key=value per line
 *   SET <key> <value>     change a setting (see CONF? for keys); SAVE to keep it
 *   CAL?                  calibration points
 *   CAL CLEAR             remove all points
 *   CAL ADD <mA>          add a point: reference current now applied, from the standard
 *   SAVE | DEFAULTS       write settings to flash | restore factory settings (not saved)
 *   TOTAL? | TOTAL RESET  pulse totalizer
 *   FTEST <Hz> | FTEST OFF   force a frequency on the output (clock calibration)
 */
#include "cli.h"
#include "app.h"
#include "config.h"
#include "outputs.h"
#include "uart.h"
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define FW_VERSION "0.1.0"

static char line[96];
static uint32_t len;
static uint8_t adc_id;

typedef struct {
    const char *key;
    void *ptr;
    char type;            /* 'f' float, 'u' uint32 */
    float min, max;
} param_t;

static const param_t params[] = {
    { "fmin",       &cfg.fmin_hz,           'f', 0.0f,   12000.0f },
    { "fmax",       &cfg.fmax_hz,           'f', 0.1f,   12000.0f },
    { "cutoff",     &cfg.cutoff_pct,        'f', 0.0f,   10.0f },
    { "damp",       &cfg.damp_s,            'f', 0.0f,   30.0f },
    { "qmax",       &cfg.qmax,              'f', 0.0f,   1e9f },
    { "pval",       &cfg.pulse_value,       'f', 1e-9f,  1e9f },
    { "pwidth",     &cfg.pulse_width_ms,    'u', 1.0f,   1000.0f },
    { "ppol",       &cfg.pulse_active_high, 'u', 0.0f,   1.0f },
    { "alarm_mode", &cfg.alarm_mode,        'u', 0.0f,   2.0f },
    { "alarm_freq", &cfg.alarm_freq_hz,     'f', 0.0f,   12000.0f },
    { "alarm_lo",   &cfg.alarm_lo_ma,       'f', 0.0f,   4.0f },
    { "alarm_hi",   &cfg.alarm_hi_ma,       'f', 20.0f,  25.0f },
    { "tcxo_ppm",   &cfg.tcxo_ppm,          'f', -200.0f, 200.0f },
    { "vref",       &cfg.vref_v,            'f', 1.0f,   3.6f },
    { "rshunt",     &cfg.rshunt_ohm,        'f', 1.0f,   1000.0f },
};

void cli_set_adc_id(uint8_t id) { adc_id = id; }

static void print_param(const param_t *p)
{
    if (p->type == 'f')
        uart_printf("%s=%.9g\n", p->key, (double)*(float *)p->ptr);
    else
        uart_printf("%s=%lu\n", p->key, (unsigned long)*(uint32_t *)p->ptr);
}

static void cmd_meas(void)
{
    uint64_t total;
    uint32_t owed;
    int ovf;
    pulse_status(&total, &owed, &ovf);
    uart_printf("I=%.6f RAW=%.6f F=%.4f Q=%.6g TOT=%.9g PULSES=%.0f OWED=%lu ALM=0x%02lX N=%lu\n",
                app.cur_ma, app.raw_ma, app.freq_hz, app.flow, (double)total * cfg.pulse_value,
                (double)total, (unsigned long)owed, (unsigned long)app.alarms,
                (unsigned long)app.samples);
}

static int cmd_set(char *args)
{
    char *key = strtok(args, " \t");
    char *val = strtok(NULL, " \t");
    if (!key || !val)
        return -1;
    char *end;
    float v = strtof(val, &end);
    if (*end)
        return -1;
    for (unsigned i = 0; i < sizeof params / sizeof params[0]; i++) {
        const param_t *p = &params[i];
        if (strcasecmp(key, p->key) == 0) {
            if (v < p->min || v > p->max)
                return -2;
            if (p->type == 'f')
                *(float *)p->ptr = v;
            else
                *(uint32_t *)p->ptr = (uint32_t)(v + 0.5f);
            app_apply_config();
            return 0;
        }
    }
    return -3;
}

static void execute(char *s)
{
    while (*s == ' ')
        s++;
    if (!*s)
        return;

    if (strcasecmp(s, "*IDN?") == 0) {
        uart_printf("AM24,4-20mA to frequency/pulse,fw %s,adc_id 0x%02X\n", FW_VERSION, adc_id);
    } else if (strcasecmp(s, "MEAS?") == 0) {
        cmd_meas();
    } else if (strcasecmp(s, "RAW?") == 0) {
        uart_printf("RAW=%.6f AVG=%.6f AVG_N=%lu\n", app.raw_ma, app.avg_raw_ma, (unsigned long)app.avg_n);
    } else if (strcasecmp(s, "CONF?") == 0) {
        for (unsigned i = 0; i < sizeof params / sizeof params[0]; i++)
            print_param(&params[i]);
    } else if (strncasecmp(s, "SET ", 4) == 0) {
        int rc = cmd_set(s + 4);
        if (rc) {
            uart_puts(rc == -2 ? "ERR out of range\n" : rc == -3 ? "ERR unknown key\n" : "ERR syntax\n");
            return;
        }
    } else if (strcasecmp(s, "CAL?") == 0) {
        for (uint32_t k = 0; k < cfg.cal_n; k++)
            uart_printf("P%lu RAW=%.6f REF=%.6f\n", (unsigned long)k, (double)cfg.cal_raw_ma[k],
                        (double)cfg.cal_ref_ma[k]);
    } else if (strcasecmp(s, "CAL CLEAR") == 0) {
        app_cal_clear();
    } else if (strncasecmp(s, "CAL ADD ", 8) == 0) {
        char *end;
        double ref = strtod(s + 8, &end);
        if (*end || ref < 0.0 || ref > 25.0) {
            uart_puts("ERR syntax\n");
            return;
        }
        if (app_cal_add(ref)) {
            uart_puts("ERR average not ready or table full\n");
            return;
        }
    } else if (strcasecmp(s, "SAVE") == 0) {
        if (config_save()) {
            uart_puts("ERR flash\n");
            return;
        }
    } else if (strcasecmp(s, "DEFAULTS") == 0) {
        config_defaults();
        app_apply_config();
    } else if (strcasecmp(s, "TOTAL?") == 0) {
        uint64_t total;
        uint32_t owed;
        int ovf;
        pulse_status(&total, &owed, &ovf);
        uart_printf("PULSES=%.0f OWED=%lu TOT=%.9g OVF=%d\n", (double)total,
                    (unsigned long)owed, (double)total * cfg.pulse_value, ovf);
    } else if (strcasecmp(s, "TOTAL RESET") == 0) {
        pulse_reset();
        app.alarms &= ~ALM_PULSE;
    } else if (strcasecmp(s, "FTEST OFF") == 0) {
        app.ftest_hz = -1.0;
    } else if (strncasecmp(s, "FTEST ", 6) == 0) {
        char *end;
        double f = strtod(s + 6, &end);
        if (*end || f < 0.0 || f > 12000.0) {
            uart_puts("ERR syntax\n");
            return;
        }
        app.ftest_hz = f;
        freq_set(f);
    } else if (strcasecmp(s, "HELP") == 0) {
        uart_puts("*IDN? MEAS? RAW? CONF? SET <key> <v> CAL? CAL CLEAR CAL ADD <mA> SAVE DEFAULTS "
                  "TOTAL? TOTAL RESET FTEST <Hz>|OFF\n");
    } else {
        uart_puts("ERR unknown command\n");
        return;
    }
    uart_puts("OK\n");
}

void cli_poll(void)
{
    int c;
    while ((c = uart_getc()) >= 0) {
        if (c == '\r' || c == '\n') {
            line[len] = 0;
            if (len)
                execute(line);
            len = 0;
        } else if (len < sizeof line - 1) {
            line[len++] = (char)c;
        }
    }
}
