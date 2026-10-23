cmake_minimum_required(VERSION 3.20)

set(CMAKE_TOOLCHAIN_FILE ${CMAKE_CURRENT_SOURCE_DIR}/cmake/arm-none-eabi.cmake)
project(am24_converter C ASM)

set(TP ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
set(DEV ${TP}/cmsis_device_g4)

add_executable(am24.elf
    src/main.c src/board.c src/uart.c src/ad7124.c src/outputs.c
    src/config.c src/app.c src/cli.c
    ${DEV}/Source/Templates/system_stm32g4xx.c
    ${DEV}/Source/Templates/gcc/startup_stm32g474xx.s
)

target_include_directories(am24.elf PRIVATE src ${DEV}/Include ${TP}/cmsis_core/CMSIS/Core/Include)
target_compile_definitions(am24.elf PRIVATE STM32G474xx USE_TCXO=$<IF:$<BOOL:${USE_HSI}>,0,1>)

set(CPU -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard)
target_compile_options(am24.elf PRIVATE ${CPU} -O2 -g3 -Wall -Wextra -Wno-unused-parameter
    -ffunction-sections -fdata-sections $<$<COMPILE_LANGUAGE:ASM>:-x assembler-with-cpp>)
target_link_options(am24.elf PRIVATE ${CPU} -T${CMAKE_CURRENT_SOURCE_DIR}/STM32G474RETX_FLASH.ld
    --specs=nano.specs --specs=nosys.specs -u _printf_float -Wl,--gc-sections
    -Wl,-Map=am24.map -Wl,--print-memory-usage -Wl,--no-warn-rwx-segments)
target_link_libraries(am24.elf PRIVATE m)

add_custom_command(TARGET am24.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex am24.elf am24.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary am24.elf am24.bin)
