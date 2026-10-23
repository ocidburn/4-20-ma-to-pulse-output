#include "board.h"

static volatile uint32_t ms_ticks;

void gpio_config(GPIO_TypeDef *p, uint32_t pin, uint32_t mode, uint32_t af)
{
    p->MODER   = (p->MODER & ~(3UL << (pin * 2))) | (mode << (pin * 2));
    p->OSPEEDR |= 3UL << (pin * 2);                       /* very high speed: clean edges */
    if (pin < 8)
        p->AFR[0] = (p->AFR[0] & ~(0xFUL << (pin * 4))) | (af << (pin * 4));
    else
        p->AFR[1] = (p->AFR[1] & ~(0xFUL << ((pin - 8) * 4))) | (af << ((pin - 8) * 4));
}

/* 170 MHz from PLL in boost mode (RM0440, "Range 1 boost mode"). */
void clock_init(void)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_PWREN;
    (void)RCC->APB1ENR1;
    PWR->CR5 &= ~PWR_CR5_R1MODE;                          /* Range 1 boost, required above 150 MHz */

    FLASH->ACR = FLASH_ACR_LATENCY_4WS | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN | FLASH_ACR_DCEN;
    while ((FLASH->ACR & FLASH_ACR_LATENCY) != FLASH_ACR_LATENCY_4WS) { }

    uint32_t pllcfgr;
#if USE_TCXO
    RCC->CR |= RCC_CR_HSEBYP;
    RCC->CR |= RCC_CR_HSEON;
    uint32_t t = 1000000;
    while (!(RCC->CR & RCC_CR_HSERDY) && --t) { }
    if (t) {
        /* 10 MHz / M2 = 5 MHz, x N68 = 340 MHz VCO, / R2 = 170 MHz */
        pllcfgr = RCC_PLLCFGR_PLLSRC_HSE | (1UL << RCC_PLLCFGR_PLLM_Pos) | (68UL << RCC_PLLCFGR_PLLN_Pos);
    } else
#endif
    {
        /* No TCXO: HSI16 / M4 = 4 MHz, x N85 = 340 MHz VCO, / R2 = 170 MHz. Frequency accuracy ~1 %! */
        RCC->CR |= RCC_CR_HSION;
        while (!(RCC->CR & RCC_CR_HSIRDY)) { }
        pllcfgr = RCC_PLLCFGR_PLLSRC_HSI | (3UL << RCC_PLLCFGR_PLLM_Pos) | (85UL << RCC_PLLCFGR_PLLN_Pos);
    }
    RCC->PLLCFGR = pllcfgr | (0UL << RCC_PLLCFGR_PLLR_Pos) | RCC_PLLCFGR_PLLREN;
    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY)) { }

    /* Step through AHB/2 when switching to >80 MHz, then go to full speed after >= 1 us. */
    RCC->CFGR = (RCC->CFGR & ~(RCC_CFGR_HPRE | RCC_CFGR_SW)) | RCC_CFGR_HPRE_DIV2 | RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) { }
    for (volatile int i = 0; i < 200; i++) { }
    RCC->CFGR &= ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2);   /* AHB, APB1, APB2 = /1 */

    SystemCoreClock = SYSCLK_HZ;

    RCC->AHB2ENR |= RCC_AHB2ENR_GPIOAEN | RCC_AHB2ENR_GPIOBEN;
    (void)RCC->AHB2ENR;
}

void systick_init(void)
{
    SysTick_Config(SYSCLK_HZ / 1000U);
    NVIC_SetPriority(SysTick_IRQn, 3);
}

void SysTick_Handler(void) { ms_ticks++; }

uint32_t millis(void) { return ms_ticks; }

void delay_ms(uint32_t ms)
{
    uint32_t t0 = ms_ticks;
    while ((ms_ticks - t0) < ms) { }
}
