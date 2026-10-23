#ifndef AD7124_H
#define AD7124_H

#include <stdint.h>

#define AD7124_FULL_SCALE  8388608.0      /* 2^23: bipolar code for +VREF */

enum { ADC_CH_SHUNT = 0, ADC_CH_SHUNT_SWAPPED = 1, ADC_CH_NTC = 2 };

int      ad7124_init(uint8_t *id_out);   /* 0 = ok, <0 = no answer / config read-back mismatch */
int      ad7124_ready(void);             /* 1 when a new conversion is available */
int      ad7124_read(int32_t *code, uint8_t *channel);  /* code in -2^23..2^23-1; <0 if ERROR_FLAG */
uint32_t ad7124_error_reg(void);

#endif
