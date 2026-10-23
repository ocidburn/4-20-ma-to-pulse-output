#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

#define CAL_POINTS_MAX 5

enum { ALARM_ZERO = 0, ALARM_FREQ = 1, ALARM_HOLD = 2 };

typedef struct {
    uint32_t magic;
    uint32_t version;
    float    fmin_hz;          /* frequency at 4 mA */
    float    fmax_hz;          /* frequency at 20 mA */
    float    cutoff_pct;       /* low-flow cutoff, % of span */
    float    damp_s;           /* damping time constant */
    float    qmax;             /* engineering units per hour at 20 mA */
    float    pulse_value;      /* engineering units per pulse */
    uint32_t pulse_width_ms;
    uint32_t pulse_active_high;
    uint32_t alarm_mode;       /* ALARM_ZERO / ALARM_FREQ / ALARM_HOLD */
    float    alarm_freq_hz;
    float    alarm_lo_ma;      /* NAMUR NE43: below = alarm */
    float    alarm_hi_ma;      /* NAMUR NE43: above = alarm */
    float    tcxo_ppm;         /* measured clock error, + = fast */
    float    vref_v;           /* nominal reference, used for the raw scale only */
    float    rshunt_ohm;       /* nominal shunt, used for the raw scale only */
    uint32_t cal_n;
    float    cal_raw_ma[CAL_POINTS_MAX];   /* reading before calibration */
    float    cal_ref_ma[CAL_POINTS_MAX];   /* reference current from the standard */
    uint32_t crc;
} config_t;

extern config_t cfg;

void config_defaults(void);
int  config_load(void);        /* 0 = loaded from flash, -1 = defaults used */
int  config_save(void);        /* 0 = ok */

#endif
