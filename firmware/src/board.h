/*
 * Board definitions: NUCLEO-G474RE + converter shield.
 *
 * Pin map (Arduino header names in brackets):
 *   PA5  SPI1_SCK   [D13]  -> ISO7741 -> AD7124 SCLK   (LD2 on Nucleo blinks with SCK)
 *   PA6  SPI1_MISO  [D12]  <- ISO7741 <- AD7124 DOUT/RDY
 *   PA7  SPI1_MOSI  [D11]  -> ISO7741 -> AD7124 DIN
 *   PB6  GPIO       [D10]  -> ISO7741 -> AD7124 CS
 *   PA0  TIM2_CH1   [A0]   frequency output (to output stage, channel F)
 *   PA1  GPIO       [A1]   pulse output (to output stage, channel P)
 *   PA4  GPIO       [A2]   alarm LED (HL2), active high
 *   PA2/PA3 LPUART1        ST-LINK virtual COM port (USB), 115200 8N1
 *   PF0  OSC_IN            10 MHz TCXO in HSE bypass mode (solder bridges on Nucleo!)
 */
#ifndef BOARD_H
#define BOARD_H

#include "stm32g4xx.h"

/* Clock source. 1 = external 10 MHz TCXO on OSC_IN (HSE bypass), 0 = internal HSI16 (bench tests only). */
#ifndef USE_TCXO
#define USE_TCXO 1
#endif

#define SYSCLK_HZ        170000000UL
#define TIMER_CLK_HZ     SYSCLK_HZ     /* APB1 prescaler = 1 -> timers run at SYSCLK */

#define CS_PORT          GPIOB
#define CS_PIN           6U
#define MISO_PORT        GPIOA
#define MISO_PIN         6U
#define FOUT_PIN         0U            /* PA0, TIM2_CH1, AF1 */
#define POUT_PIN         1U            /* PA1 */
#define ALARM_PIN        4U            /* PA4 */

static inline void gpio_set(GPIO_TypeDef *p, uint32_t pin)   { p->BSRR = 1UL << pin; }
static inline void gpio_clr(GPIO_TypeDef *p, uint32_t pin)   { p->BRR  = 1UL << pin; }
static inline int  gpio_read(GPIO_TypeDef *p, uint32_t pin)  { return (p->IDR >> pin) & 1U; }

/* Configure a pin: mode 0=input 1=output 2=AF 3=analog, af = alternate function number. */
void gpio_config(GPIO_TypeDef *p, uint32_t pin, uint32_t mode, uint32_t af);

void clock_init(void);
void systick_init(void);
uint32_t millis(void);
void delay_ms(uint32_t ms);

#endif
