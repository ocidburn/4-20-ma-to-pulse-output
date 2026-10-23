/* Settings and calibration, stored in the last flash page (bank 2 in dual-bank mode). */
#include "config.h"
#include "board.h"
#include <stddef.h>
#include <string.h>

#define CFG_MAGIC   0x34324D41UL     /* "AM24" */
#define CFG_VERSION 1UL

config_t cfg;

static uint32_t crc32(const void *data, uint32_t len)
{
    const uint8_t *p = data;
    uint32_t c = 0xFFFFFFFFUL;
    while (len--) {
        c ^= *p++;
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320UL & (0UL - (c & 1UL)));
    }
    return ~c;
}

void config_defaults(void)
{
    memset(&cfg, 0, sizeof cfg);
    cfg.magic = CFG_MAGIC;
    cfg.version = CFG_VERSION;
    cfg.fmin_hz = 0.0f;
    cfg.fmax_hz = 10000.0f;
    cfg.cutoff_pct = 0.0f;
    cfg.damp_s = 0.0f;
    cfg.qmax = 100.0f;
    cfg.pulse_value = 0.01f;
    cfg.pulse_width_ms = 2;
    cfg.pulse_active_high = 1;
    cfg.alarm_mode = ALARM_ZERO;
    cfg.alarm_freq_hz = 0.0f;
    cfg.alarm_lo_ma = 3.6f;
    cfg.alarm_hi_ma = 21.0f;
    cfg.tcxo_ppm = 0.0f;
    cfg.vref_v = 3.0f;
    cfg.rshunt_ohm = 50.0f;
    cfg.cal_n = 0;
}

/* Last 2 KB page in dual-bank mode (bank 2, page 127), last 4 KB page in single-bank mode. */
static uint32_t page_addr(void)
{
    return (FLASH->OPTR & FLASH_OPTR_DBANK) ? 0x0807F800UL : 0x0807F000UL;
}

int config_load(void)
{
    const config_t *f = (const config_t *)page_addr();
    if (f->magic == CFG_MAGIC && f->version == CFG_VERSION &&
        f->crc == crc32(f, offsetof(config_t, crc))) {
        memcpy(&cfg, f, sizeof cfg);
        return 0;
    }
    config_defaults();
    return -1;
}

static int flash_wait(void)
{
    while (FLASH->SR & FLASH_SR_BSY) { }
    uint32_t err = FLASH->SR & (FLASH_SR_OPERR | FLASH_SR_PROGERR | FLASH_SR_WRPERR | FLASH_SR_PGAERR |
                                FLASH_SR_SIZERR | FLASH_SR_PGSERR | FLASH_SR_MISERR | FLASH_SR_FASTERR);
    FLASH->SR = err | FLASH_SR_EOP;
    return err ? -1 : 0;
}

int config_save(void)
{
    cfg.magic = CFG_MAGIC;
    cfg.version = CFG_VERSION;
    cfg.crc = crc32(&cfg, offsetof(config_t, crc));

    uint32_t addr = page_addr();
    int dbank = (FLASH->OPTR & FLASH_OPTR_DBANK) != 0;
    int rc = 0;

    __disable_irq();
    if (FLASH->CR & FLASH_CR_LOCK) {
        FLASH->KEYR = 0x45670123UL;
        FLASH->KEYR = 0xCDEF89ABUL;
    }
    flash_wait();

    /* erase */
    uint32_t cr = FLASH_CR_PER | (127UL << FLASH_CR_PNB_Pos);
    if (dbank)
        cr |= FLASH_CR_BKER;                             /* bank 2 */
    FLASH->CR = cr;
    FLASH->CR = cr | FLASH_CR_STRT;
    rc |= flash_wait();
    FLASH->CR = 0;

    /* program double words */
    if (!rc) {
        uint32_t words[(sizeof(config_t) + 7) / 8 * 2];
        memset(words, 0xFF, sizeof words);
        memcpy(words, &cfg, sizeof cfg);
        FLASH->CR = FLASH_CR_PG;
        for (uint32_t i = 0; i < sizeof words / 4 && !rc; i += 2) {
            *(volatile uint32_t *)(addr + i * 4) = words[i];
            __ISB();
            *(volatile uint32_t *)(addr + i * 4 + 4) = words[i + 1];
            rc |= flash_wait();
        }
        FLASH->CR = 0;
    }
    FLASH->CR = FLASH_CR_LOCK;
    __enable_irq();

    if (!rc && memcmp((const void *)addr, &cfg, sizeof cfg) != 0)
        rc = -1;
    return rc;
}
