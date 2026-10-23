/* LPUART1 on PA2/PA3: ST-LINK virtual COM port. RX by interrupt into a ring buffer, TX blocking. */
#include "uart.h"
#include "board.h"
#include <stdarg.h>
#include <stdio.h>

#define RX_SIZE 256U

static volatile uint8_t  rx_buf[RX_SIZE];
static volatile uint32_t rx_head, rx_tail;

void uart_init(uint32_t baud)
{
    RCC->APB1ENR2 |= RCC_APB1ENR2_LPUART1EN;
    (void)RCC->APB1ENR2;
    gpio_config(GPIOA, 2, 2, 12);                       /* LPUART1_TX, AF12 */
    gpio_config(GPIOA, 3, 2, 12);                       /* LPUART1_RX, AF12 */

    LPUART1->CR1 = 0;
    LPUART1->BRR = (uint32_t)(((uint64_t)SYSCLK_HZ * 256U + baud / 2) / baud);
    LPUART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_RXNEIE_RXFNEIE | USART_CR1_UE;
    NVIC_SetPriority(LPUART1_IRQn, 2);
    NVIC_EnableIRQ(LPUART1_IRQn);
}

void LPUART1_IRQHandler(void)
{
    uint32_t isr = LPUART1->ISR;
    if (isr & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE))
        LPUART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF;
    if (isr & USART_ISR_RXNE_RXFNE) {
        uint8_t c = (uint8_t)LPUART1->RDR;
        uint32_t next = (rx_head + 1U) % RX_SIZE;
        if (next != rx_tail) {
            rx_buf[rx_head] = c;
            rx_head = next;
        }
    }
}

int uart_getc(void)
{
    if (rx_tail == rx_head)
        return -1;
    int c = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1U) % RX_SIZE;
    return c;
}

void uart_putc(char c)
{
    while (!(LPUART1->ISR & USART_ISR_TXE_TXFNF)) { }
    LPUART1->TDR = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n')
            uart_putc('\r');
        uart_putc(*s++);
    }
}

void uart_printf(const char *fmt, ...)
{
    char buf[256];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    uart_puts(buf);
}
