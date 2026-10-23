#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

#define CAL_POINTS_MAX 11

enum { ALARM_ZERO = 0, ALARM_FREQ = 1, ALARM_HOLD = 2 };

typedef struct {
    uint32_t magic;
    uint32_t version;
    float    fmin_hz;          /* frequency at 4 mA */
    float    fmax_hz;          /* frequency at 20 mA */
    float    cutoff_pct;       /* low-flow cutoff, % of span */
    float    damp_s;           /* damping time constant */
    double   qmax;             /* engineering units per hour at 20 mA */
    double   pulse_value;      /* engineering units per pulse */
    uint32_t pulse_width_ms;
    uint32_t pulse_active_high;
    uint32_t alarm_mode;       /* ALARM_ZERO / ALARM_FREQ / ALARM_HOLD */
    float    alarm_freq_hz;
    float    alarm_lo_ma;      /* NAMUR NE43: below = alarm */
    float    alarm_hi_ma;      /* NAMUR NE43: above = alarm */
    float    tcxo_ppm;         /* measured clock error, + = fast (used while GPS gives none) */
    uint32_t gps_enable;       /* 1 = correct the clock from the GPS PPS input */
    uint32_t gps_window_s;     /* PPS seconds per clock measurement */
    float    vref_v;           /* nominal reference, used for the raw scale only */
    float    rshunt_ohm;       /* nominal shunt, used for the raw scale only */
    float    ntc_r25_ohm;      /* NTC at 25 C */
    float    ntc_beta_k;       /* NTC beta (25/50) */
    float    ntc_rfix_ohm;     /* divider resistor from VREF to the NTC */
    float    tc_ppm;           /* gain temperature coefficient of the front end, ppm/C */
    float    t_window_c;       /* warning when |T - cal_t0| exceeds this */
    float    cal_t0_c;         /* front-end temperature at calibration (reference for tc_ppm) */
    uint32_t cal_n;
    double   cal_raw_ma[CAL_POINTS_MAX];   /* reading before calibration, temperature-corrected */
    double   cal_ref_ma[CAL_POINTS_MAX];   /* reference current from the standard */
    uint32_t crc;
} config_t;

extern config_t cfg;

void config_defaults(void);
int  config_load(void);        /* 0 = loaded from flash, -1 = defaults used */
int  config_save(void);        /* 0 = ok */

#endif
