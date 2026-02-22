OUTPUT_ARCH(riscv)
ENTRY(_start)

SECTIONS
{
  . = BOOT_START;

  .text : ALIGN(4)
  {
    *(.text*)
    *(.rodata*)
  }

  .data : ALIGN(4)
  {
    *(.data*)
  }

  .bss (NOLOAD) : ALIGN(4)
  {
    *(.bss*)
    *(COMMON)
  }
}
