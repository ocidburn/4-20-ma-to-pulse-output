/*
 * 4-20 mA -> frequency / pulse converter, NUCLEO-G474RE + isolated AD7124-4 front end.
 */
#include "board.h"
#include "uart.h"
#include "ad7124.h"
#include "outputs.h"
#include "config.h"
#include "app.h"
#include "cli.h"

int main(void)
{
    clock_init();
    systick_init();
    uart_init(115200);
    alarm_led_init();
    outputs_init();

    int loaded = config_load();
    app_init();

    uint8_t id = 0;
    int adc_rc = ad7124_init(&id);
    cli_set_adc_id(id);

    uart_printf("\nAM24 converter fw 0.1.0, clock %s, settings %s, AD7124 id 0x%02X %s\n",
                (RCC->PLLCFGR & RCC_PLLCFGR_PLLSRC) == RCC_PLLCFGR_PLLSRC_HSE ? "TCXO" : "HSI (inaccurate!)",
                loaded == 0 ? "from flash" : "defaults", id, adc_rc == 0 ? "ok" : "NOT FOUND");

    uint32_t retry_ms = millis();
    for (;;) {
        if (adc_rc == 0) {
            if (ad7124_ready()) {
                int32_t code;
                uint8_t status;
                int err = ad7124_read(&code, &status);
                app_sample(code, err != 0);
            }
        } else if ((millis() - retry_ms) > 1000U) {          /* isolator side not powered yet: retry */
            retry_ms = millis();
            adc_rc = ad7124_init(&id);
            cli_set_adc_id(id);
        }
        app_poll();
        cli_poll();
    }
}
