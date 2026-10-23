# GNU Arm toolchain. By default the compiler bundled with STM32CubeIDE 2.1.1 is used;
# override with -DARM_TOOLCHAIN_DIR=<path to bin> if it lives elsewhere.
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

if(NOT ARM_TOOLCHAIN_DIR)
    file(GLOB _cube_gcc "C:/ST/STM32CubeIDE_*/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin")
    if(_cube_gcc)
        list(GET _cube_gcc 0 ARM_TOOLCHAIN_DIR)
    endif()
endif()
if(ARM_TOOLCHAIN_DIR)
    set(_p "${ARM_TOOLCHAIN_DIR}/")
endif()

set(CMAKE_C_COMPILER   "${_p}arm-none-eabi-gcc.exe")
set(CMAKE_ASM_COMPILER "${_p}arm-none-eabi-gcc.exe")
set(CMAKE_OBJCOPY      "${_p}arm-none-eabi-objcopy.exe")
set(CMAKE_SIZE         "${_p}arm-none-eabi-size.exe")
set(CMAKE_EXECUTABLE_SUFFIX "")
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
