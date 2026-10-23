/*
 * Clock correction from a GPS 1 PPS signal on PB10 = Arduino D6 (TIM2_CH3, AF1).
 *
 * TIM2 is a free-running 32-bit counter at the timer clock (TCXO x 17 = 170 MHz). Every PPS edge
 * is captured; consecutive differences are summed over a window of whole seconds, so the result
 * depends only on the first and last edge: with 30 ns PPS jitter a 100 s window resolves 0.001 ppm.
 * An interval more than 50 ppm off (missed or extra pulse) restarts the window.
 *
 * On every edge the exact pulse total is latched as well. The verification utility takes two
 * such snapshots a whole number of GPS seconds apart, so the reference time is GPS, not the
 * converter's own clock.
 */
#include "gps.h"
#include "board.h"
#include "config.h"
#include "outputs.h"

#define PPS_PIN       10U         /* PB10 */
#define NOMINAL       ((double)TIMER_CLK_HZ)
#define TOL_TICKS     (TIMER_CLK_HZ / 20000U)     /* 50 ppm */
#define PPS_LOST_MS   2500U

static volatile uint32_t last_cap;
static volatile uint8_t  have_last;
static volatile uint64_t win_ticks;
static volatile uint32_t win_secs;
static volatile uint32_t pps_count;
static volatile uint32_t last_pps_ms;
static volatile double   pulses_at_pps;
static volatile uint8_t  result_ready;
static volatile double   result_ppm;

static double   ppm_used;
static uint32_t windows_done;

void gps_init(void)
{
    RCC->APB1ENR1 |= RCC_APB1ENR1_TIM2EN;
    (void)RCC->APB1ENR1;
    gpio_config(GPIOB, PPS_PIN, 2, 1);
    GPIOB->PUPDR = (GPIOB->PUPDR & ~(3UL << (PPS_PIN * 2))) | (2UL << (PPS_PIN * 2));   /* pull-down */

    TIM2->CR1 = 0;
    TIM2->PSC = 0;
    TIM2->ARR = 0xFFFFFFFFUL;
    TIM2->CCMR2 = (1UL << TIM_CCMR2_CC3S_Pos) | (3UL << TIM_CCMR2_IC3F_Pos);   /* TI3, filter 8 x fCK */
    TIM2->CCER = TIM_CCER_CC3E;                                                /* rising edge */
    TIM2->EGR = TIM_EGR_UG;
    TIM2->SR = 0;
    TIM2->DIER = TIM_DIER_CC3IE;
    NVIC_SetPriority(TIM2_IRQn, 1);           /* same as the pulse tick: the snapshot is consistent */
    NVIC_EnableIRQ(TIM2_IRQn);
    TIM2->CR1 = TIM_CR1_CEN;
}

void TIM2_IRQHandler(void)
{
    uint32_t cap = TIM2->CCR3;                /* reading CCR3 clears CC3IF */
    TIM2->SR = ~(TIM_SR_CC3OF | TIM_SR_UIF);

    pulses_at_pps = pulse_exact_isr();
    pps_count++;
    last_pps_ms = millis();

    if (have_last) {
        uint32_t d = cap - last_cap;
        if (d > TIMER_CLK_HZ - TOL_TICKS && d < TIMER_CLK_HZ + TOL_TICKS) {
            win_ticks += d;
            win_secs++;
            uint32_t need = cfg.gps_window_s < 10U ? 10U : cfg.gps_window_s;
            if (win_secs >= need) {
                result_ppm = ((double)win_ticks / ((double)win_secs * NOMINAL) - 1.0) * 1e6;
                result_ready = 1;
                win_ticks = 0;
                win_secs = 0;
            }
        } else {
            win_ticks = 0;                    /* missed or spurious edge: start over */
            win_secs = 0;
        }
    }
    last_cap = cap;
    have_last = 1;
}

int gps_poll(double *ppm_out)
{
    int got = 0;
    __disable_irq();
    if (result_ready) {
        result_ready = 0;
        ppm_used = result_ppm;
        windows_done++;
        got = 1;
    }
    if (have_last && (millis() - last_pps_ms) > PPS_LOST_MS) {
        have_last = 0;
        win_ticks = 0;
        win_secs = 0;
    }
    __enable_irq();
    if (got && ppm_out)
        *ppm_out = ppm_used;
    return got;
}

void gps_status(gps_status_t *st)
{
    __disable_irq();
    st->pps_ok = have_last && (millis() - last_pps_ms) <= PPS_LOST_MS;
    st->pps_count = pps_count;
    st->age_ms = pps_count ? millis() - last_pps_ms : 0xFFFFFFFFUL;
    st->window_s = win_secs;
    st->windows = windows_done;
    st->ppm = ppm_used;
    st->pulses_at_pps = pulses_at_pps;
    __enable_irq();
}
