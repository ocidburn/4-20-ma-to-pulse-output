#ifndef OUTPUTS_H
#define OUTPUTS_H

#include <stdint.h>

void     outputs_init(void);
void     freq_set_clock_ppm(double ppm);     /* TCXO correction: +ppm = clock runs fast */
void     freq_set(double hz);                /* 0 = output stopped (held low) */
double   freq_get_set_hz(void);
uint64_t freq_periods(void);                 /* periods generated since start */

void     pulse_set_rate(double pulses_per_ms);
void     pulse_config(uint32_t width_ms, int high_active);
void     pulse_status(uint64_t *total, uint32_t *owed, int *overflow);
void     pulse_reset(void);
double   pulse_exact(void);                  /* pulses generated incl. the fraction not yet whole */
double   pulse_exact_isr(void);              /* same, for an ISR at the pulse tick priority */

void     alarm_led_init(void);
void     alarm_led(int on);

#endif
