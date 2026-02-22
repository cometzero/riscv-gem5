#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

int main(void)
{
	volatile uint32_t acc = 0U;

	printk("RISCV32 SIMPLE WORKLOAD START\n");
	for (uint32_t i = 0; i < 5000U; ++i) {
		acc += (i & 0x7U);
	}
	printk("RISCV32 SIMPLE WORKLOAD DONE acc=%u\n", acc);

	for (;;) {
		k_sleep(K_MSEC(1000));
	}

	return 0;
}
