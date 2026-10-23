#ifndef APP_H
#define APP_H

#include <stdint.h>

enum {
    ALM_LOW   = 1u << 0,    /* current below NE43 limit (wire break) */
    ALM_HIGH  = 1u << 1,    /* current above NE43 limit (short / transmitter fault) */
    ALM_ADC   = 1u << 2,    /* ADC error flag or no data through the isolator */
    ALM_PULSE = 1u << 3,    /* pulse buffer overflow (rate above 1 / (2 x width)) */
};

typedef struct {
    double   raw_ma;        /* before calibration */
    double   avg_raw_ma;    /* mean of the last AVG_N raw samples (for calibration) */
    uint32_t avg_n;
    double   cur_ma;        /* calibrated and damped */
    double   freq_hz;       /* frequency set on the output */
    double   flow;          /* engineering units per hour */
    uint32_t alarms;
    uint32_t samples;
    uint32_t last_sample_ms;
    double   ftest_hz;      /* < 0: normal operation; >= 0: forced frequency for clock calibration */
} app_state_t;

#define AVG_N 40            /* 2 s at 20 samples/s */

extern app_state_t app;

void   app_init(void);
void   app_apply_config(void);
void   app_sample(int32_t code, int adc_error);
void   app_poll(void);                     /* timeouts, LED */
double app_calibrate(double raw_ma);
int    app_cal_add(double ref_ma);         /* adds a point at the current averaged raw reading */
void   app_cal_clear(void);

#endif
