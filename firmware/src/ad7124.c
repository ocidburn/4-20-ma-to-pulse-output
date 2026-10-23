/*
 * AD7124-4 driver over SPI1 (through ISO7741).
 * Channel 0 = AIN0(+)/AIN1(-) across the shunt, bipolar, gain 1, input buffers on, REFIN1(+) buffer on,
 * REFIN1(-) buffer OFF: REFIN1(-) sits at AVSS, and a buffered input needs >= AVSS + 0.1 V (datasheet Rev. E),
 * REFIN1 = LTC6655-3 (3.0 V), post filter 20 SPS (simultaneous 50/60 Hz rejection), continuous conversion.
 * CS is held low after init so DOUT/RDY on MISO signals "data ready".
 */
#include "ad7124.h"
#include "board.h"

enum {
    REG_STATUS = 0x00, REG_ADC_CONTROL = 0x01, REG_DATA = 0x02, REG_ID = 0x05, REG_ERROR = 0x06,
    REG_CHANNEL0 = 0x09, REG_CONFIG0 = 0x19, REG_FILTER0 = 0x21,
};

#define COMMS_READ  0x40U
#define CONFIG0_VALUE ((1U << 11) | (1U << 8) | (1U << 6) | (1U << 5))

static uint8_t spi_xfer(uint8_t b)
{
    while (!(SPI1->SR & SPI_SR_TXE)) { }
    *(volatile uint8_t *)&SPI1->DR = b;
    while (!(SPI1->SR & SPI_SR_RXNE)) { }
    return *(volatile uint8_t *)&SPI1->DR;
}

static void spi_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_SPI1EN;
    (void)RCC->APB2ENR;
    gpio_config(GPIOA, 5, 2, 5);                        /* SCK  AF5 */
    gpio_config(GPIOA, 6, 2, 5);                        /* MISO AF5 */
    gpio_config(GPIOA, 7, 2, 5);                        /* MOSI AF5 */
    gpio_set(CS_PORT, CS_PIN);
    gpio_config(CS_PORT, CS_PIN, 1, 0);

    SPI1->CR1 = 0;
    /* Mode 3, master, fPCLK/64 = 2.66 MHz (ISO7741 + cable margin), software NSS */
    SPI1->CR1 = SPI_CR1_MSTR | (5UL << SPI_CR1_BR_Pos) | SPI_CR1_CPOL | SPI_CR1_CPHA | SPI_CR1_SSM | SPI_CR1_SSI;
    SPI1->CR2 = (7UL << SPI_CR2_DS_Pos) | SPI_CR2_FRXTH;   /* 8-bit frames */
    SPI1->CR1 |= SPI_CR1_SPE;
}

static void write_reg(uint8_t addr, uint32_t val, int nbytes)
{
    spi_xfer(addr & 0x3FU);
    for (int i = nbytes - 1; i >= 0; i--)
        spi_xfer((uint8_t)(val >> (8 * i)));
}

static uint32_t read_reg(uint8_t addr, int nbytes)
{
    uint32_t v = 0;
    spi_xfer(COMMS_READ | (addr & 0x3FU));
    for (int i = 0; i < nbytes; i++)
        v = (v << 8) | spi_xfer(0x00);
    return v;
}

int ad7124_init(uint8_t *id_out)
{
    spi_init();
    gpio_clr(CS_PORT, CS_PIN);
    for (int i = 0; i < 8; i++)                          /* 64 x '1' = serial reset */
        spi_xfer(0xFF);
    delay_ms(5);

    uint8_t id = (uint8_t)read_reg(REG_ID, 1);
    if (id_out)
        *id_out = id;
    if (id == 0x00 || id == 0xFF)
        return -1;                                       /* nothing answering through the isolator */

    write_reg(REG_CHANNEL0, 0x8000U | (0U << 12) | (0U << 5) | 1U, 2);   /* enable, setup 0, AIN0-AIN1 */
    /* bipolar | REF_BUFP | AIN_BUFP | AIN_BUFM | REFIN1 | gain 1 (REF_BUFM off, see above) */
    write_reg(REG_CONFIG0, CONFIG0_VALUE, 2);
    /* post filter (111), 20 SPS (101) */
    write_reg(REG_FILTER0, (7UL << 21) | (5UL << 17) | 384U, 3);
    /* DATA_STATUS, full power, continuous conversion, internal 614.4 kHz clock */
    write_reg(REG_ADC_CONTROL, (1U << 10) | (2U << 6), 2);

    uint32_t chk = read_reg(REG_CONFIG0, 2);
    return (chk == CONFIG0_VALUE) ? 0 : -2;
}

int ad7124_ready(void)
{
    return !gpio_read(MISO_PORT, MISO_PIN);              /* DOUT/RDY goes low when a result is waiting */
}

int ad7124_read(int32_t *code, uint8_t *status)
{
    uint32_t v = read_reg(REG_DATA, 4);                  /* 24-bit data + status byte (DATA_STATUS = 1) */
    *code = (int32_t)(v >> 8) - 0x800000;                /* bipolar offset binary -> signed */
    *status = (uint8_t)v;
    return (*status & 0x40U) ? -1 : 0;                   /* ERROR_FLAG */
}

uint32_t ad7124_error_reg(void)
{
    return read_reg(REG_ERROR, 3);
}
