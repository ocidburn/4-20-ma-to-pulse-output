#ifndef UART_H
#define UART_H

#include <stdint.h>

void uart_init(uint32_t baud);
int  uart_getc(void);                 /* -1 if nothing received */
void uart_putc(char c);
void uart_puts(const char *s);        /* converts \n to \r\n */
void uart_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif
