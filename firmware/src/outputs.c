/*
 * Frequency output (TIM2, 32-bit, 170 MHz) and pulse output (TIM6 1 kHz tick).
 *
 * Frequency: the period in timer ticks is a 32.32 fixed-point number. Every period the update
 * interrupt loads the integer part and carries the fraction in an accumulator, so the average
 * frequency is exact (< 1 ppm) and each single period deviates by at most 1 tick (5.9 ns).
 * ARR and CCR1 are preloaded, so a new frequency starts on a period boundary without runt pulses.
 *
 * Pulses: the pulse rate (pulses per ms, 32.32 fixed point) is integrated every 1 ms tick from
 * the same clock; whole pulses go to an "owed" counter that the output drains at the set width.
 */
#include "outputs.h"
#include "board.h"

static volatile uint64_t period_q32;          /* timer ticks per output period, 32.32; 0 = output off */
static volatile uint32_t frac_acc;
static volatile uint64_t periods_out;

static volatile uint64_t rate_q32;            /* pulses per ms, 32.32 */
static volatile uint64_t pulse_acc;           /* fractional pulses, 0.32 */
static volatile uint32_t owed;
static volatile uint64_t pulses_total;        /* pulses generated (sent + owed) */
static volatile uint32_t width_ms = 2, timer_ms;
static volatile uint8_t  pstate, active_high = 1, overflow;
static double timer_clk = (double)TIMER_CLK_HZ;

#define OWED_MAX 100000U

static void pout_write(int on)
{
    if ((on != 0) == (active_high != 0))
        gpio_set(GPIOA, POUT_PIN);
    else
        gpio_clr(GPIOA, POUT_PIN);
}

void outputs_init(void)
{
    /* TIM2 CH1 on PA0, PWM mode 1 */
    RCC->APB1ENR1 |= RCC_APB1ENR1_TIM2EN | RCC_APB1ENR1_TIM6EN;
    (void)RCC->APB1ENR1;
    gpio_config(GPIOA, FOUT_PIN, 2, 1);
    TIM2->CR1 = TIM_CR1_ARPE;
    TIM2->PSC = 0;
    TIM2->ARR = TIMER_CLK_HZ / 1000U - 1U;
    TIM2->CCR1 = 0;
    TIM2->CCMR1 = (6UL << TIM_CCMR1_OC1M_Pos) | TIM_CCMR1_OC1PE;
    TIM2->CCER = TIM_CCER_CC1E;
    TIM2->EGR = TIM_EGR_UG;
    TIM2->SR = 0;
    TIM2->DIER = TIM_DIER_UIE;
    NVIC_SetPriority(TIM2_IRQn, 0);
    NVIC_EnableIRQ(TIM2_IRQn);
    TIM2->CR1 |= TIM_CR1_CEN;

    /* Pulse output on PA1 driven from a 1 kHz tick */
    pout_write(0);
    gpio_config(GPIOA, POUT_PIN, 1, 0);
    TIM6->PSC = TIMER_CLK_HZ / 1000000U - 1U;          /* 1 MHz */
    TIM6->ARR = 999;                                    /* 1 kHz */
    TIM6->EGR = TIM_EGR_UG;
    TIM6->SR = 0;
    TIM6->DIER = TIM_DIER_UIE;
    NVIC_SetPriority(TIM6_DAC_IRQn, 1);
    NVIC_EnableIRQ(TIM6_DAC_IRQn);
    TIM6->CR1 = TIM_CR1_CEN;
}

void TIM2_IRQHandler(void)
{
    TIM2->SR = ~TIM_SR_UIF;
    uint64_t p = period_q32;
    if (p == 0) {
        TIM2->ARR = TIMER_CLK_HZ / 1000U - 1U;          /* idle 1 ms periods, output held low */
        TIM2->CCR1 = 0;
        return;
    }
    uint32_t lo = (uint32_t)p;
    uint32_t prev = frac_acc;
    frac_acc = prev + lo;
    uint32_t ticks = (uint32_t)(p >> 32) + (frac_acc < prev ? 1U : 0U);
    TIM2->ARR = ticks - 1U;
    TIM2->CCR1 = ticks / 2U;                            /* 50 % duty */
    periods_out++;
}

void TIM6_DAC_IRQHandler(void)
{
    TIM6->SR = ~TIM_SR_UIF;

    pulse_acc += rate_q32;
    uint32_t whole = (uint32_t)(pulse_acc >> 32);
    pulse_acc &= 0xFFFFFFFFULL;
    if (whole) {
        pulses_total += whole;
        if (owed + whole > OWED_MAX) {
            owed = OWED_MAX;
            overflow = 1;
        } else {
            owed += whole;
        }
    }

    switch (pstate) {
    case 0:                                             /* idle */
        if (owed) {
            owed--;
            pout_write(1);
            timer_ms = width_ms;
            pstate = 1;
        }
        break;
    case 1:                                             /* pulse on */
        if (--timer_ms == 0) {
            pout_write(0);
            timer_ms = width_ms;                        /* pause = width -> max rate 1/(2*width) */
            pstate = 2;
        }
        break;
    default:                                            /* pause */
        if (--timer_ms == 0)
            pstate = 0;
        break;
    }
}

void freq_set_clock_ppm(double ppm)
{
    timer_clk = (double)TIMER_CLK_HZ * (1.0 + ppm * 1e-6);
}

void freq_set(double hz)
{
    uint64_t p = 0;
    if (hz > 0.05) {                                    /* below 0.05 Hz treat as stopped */
        double ticks = timer_clk / hz;
        if (ticks < 4.0)
            ticks = 4.0;
        p = (uint64_t)(ticks * 4294967296.0);
    }
    __disable_irq();
    period_q32 = p;
    __enable_irq();
}

double freq_get_set_hz(void)
{
    uint64_t p = period_q32;
    return p ? timer_clk / ((double)p / 4294967296.0) : 0.0;
}

uint64_t freq_periods(void)
{
    __disable_irq();
    uint64_t v = periods_out;
    __enable_irq();
    return v;
}

void pulse_set_rate(double pulses_per_ms)
{
    uint64_t r = pulses_per_ms > 0.0 ? (uint64_t)(pulses_per_ms * 4294967296.0) : 0;
    __disable_irq();
    rate_q32 = r;
    __enable_irq();
}

void pulse_config(uint32_t width, int high_active)
{
    if (width < 1)
        width = 1;
    __disable_irq();
    width_ms = width;
    active_high = (uint8_t)(high_active != 0);
    __enable_irq();
}

void pulse_status(uint64_t *total, uint32_t *owed_out, int *ovf)
{
    __disable_irq();
    *total = pulses_total;
    *owed_out = owed;
    *ovf = overflow;
    __enable_irq();
}

void pulse_reset(void)
{
    __disable_irq();
    pulses_total = 0;
    owed = 0;
    pulse_acc = 0;
    overflow = 0;
    __enable_irq();
}

void alarm_led(int on)
{
    if (on)
        gpio_set(GPIOA, ALARM_PIN);
    else
        gpio_clr(GPIOA, ALARM_PIN);
}

void alarm_led_init(void)
{
    gpio_clr(GPIOA, ALARM_PIN);
    gpio_config(GPIOA, ALARM_PIN, 1, 0);
}
