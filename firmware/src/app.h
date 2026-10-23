#ifndef APP_H
#define APP_H

#include <stdint.h>

#define FW_VERSION "0.2.0"

enum {
    ALM_LOW   = 1u << 0,    /* current below NE43 limit (wire break) */
    ALM_HIGH  = 1u << 1,    /* current above NE43 limit (short / transmitter fault) */
    ALM_ADC   = 1u << 2,    /* ADC error flag or no data through the isolator */
    ALM_PULSE = 1u << 3,    /* pulse buffer overflow (rate above 1 / (2 x width)) */
    ALM_TEMP  = 1u << 4,    /* NTC open/short or front end outside the calibration temperature window:
                               LED only, the outputs keep working */
};

enum { CLK_STORED = 0, CLK_GPS = 1 };

typedef struct {
    double   raw_u_ma;      /* chopped pair, before temperature correction and calibration */
    double   raw_ma;        /* temperature-corrected, before calibration */
    double   avg_raw_ma;    /* mean of the last AVG_N raw values (for calibration without a window) */
    uint32_t avg_n;
    double   cur_ma;        /* calibrated and damped */
    double   freq_hz;       /* frequency set on the output */
    double   flow;          /* engineering units per hour */
    double   temp_c;        /* front-end temperature (NTC), smoothed */
    int      temp_ok;
    double   clock_ppm;     /* clock correction in use, + = fast */
    int      clock_src;     /* CLK_STORED (tcxo_ppm) or CLK_GPS */
    uint32_t alarms;
    uint32_t samples;       /* chopped pairs since start */
    uint32_t last_sample_ms;
    double   ftest_hz;      /* < 0: normal operation; >= 0: forced frequency for clock calibration */
} app_state_t;

typedef struct {
    uint32_t n;
    double   raw_ma;        /* mean temperature-corrected raw */
    double   raw_u_ma;      /* mean uncorrected raw */
    double   cal_ma;        /* mean calibrated current (before damping) */
    double   temp_c;
    double   seconds;
} app_window_t;

#define AVG_N    20         /* 3 s at ~6.7 pairs/s */
#define WIN_MIN  10         /* pairs a window needs before CAL ADD uses it */

extern app_state_t app;

void   app_init(void);
void   app_apply_config(void);
void   app_adc(uint8_t channel, int32_t code, int adc_error);
void   app_poll(void);                     /* timeouts, LED */
void   app_gps_ppm(double ppm);            /* new clock measurement from the GPS window */
double app_calibrate(double raw_ma);
int    app_cal_add(double ref_ma);         /* adds a point at the window mean (or the 3 s average) */
void   app_cal_clear(void);
void   app_window_start(void);
void   app_window_get(app_window_t *w);

#endif
