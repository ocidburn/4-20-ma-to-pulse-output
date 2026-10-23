#ifndef GPS_H
#define GPS_H

#include <stdint.h>

typedef struct {
    int      pps_ok;          /* edges arriving now */
    uint32_t pps_count;       /* edges since start */
    uint32_t age_ms;          /* since the last edge */
    uint32_t window_s;        /* seconds collected in the running window */
    uint32_t windows;         /* finished windows since start */
    double   ppm;             /* clock error from the last finished window, + = fast */
    double   pulses_at_pps;   /* exact pulse total latched on the last edge */
} gps_status_t;

void gps_init(void);
int  gps_poll(double *ppm);   /* 1 when a window has just finished and *ppm holds its result */
void gps_status(gps_status_t *st);

#endif
