#include "riscv32_mixed_boot_addr.h"

    .section .text
    .globl _start

_start:
    csrr a0, mhartid

    li t0, 0
    beq a0, t0, boot_amp_cpu0

    li t0, 1
    beq a0, t0, boot_amp_cpu1

    li t0, 2
    blt a0, t0, park

    li t0, 6
    bge a0, t0, park

boot_cluster1_smp:
    li t0, CLUSTER1_SMP_ENTRY
    jr t0

boot_amp_cpu0:
    li t0, AMP_CPU0_ENTRY
    jr t0

boot_amp_cpu1:
    li t0, AMP_CPU1_ENTRY
    jr t0

park:
    wfi
    j park
