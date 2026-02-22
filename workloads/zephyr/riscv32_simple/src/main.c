#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/printk.h>

LOG_MODULE_REGISTER(riscv32_simple, LOG_LEVEL_DBG);

int main(void)
{
	uint32_t acc = 0U;
	uint32_t heartbeat = 0U;

	LOG_INF("UART verbose logging enabled for riscv32_simple");
	LOG_INF("CPU0 workload bootstrap start");

	printk("RISCV32 SIMPLE WORKLOAD START\n");
	for (uint32_t phase = 0U; phase < 5U; ++phase) {
		uint32_t phase_acc = 0U;

		for (uint32_t i = 0U; i < 2000U; ++i) {
			phase_acc += ((i + phase) & 0x7U);
		}

		acc += phase_acc;
		LOG_INF("phase=%u partial=%u total=%u", phase, phase_acc, acc);
		LOG_DBG("phase=%u signature=0x%x", phase, (unsigned int)(acc ^ (phase << 8)));
	}

	printk("RISCV32 SIMPLE WORKLOAD DONE acc=%u\n", acc);
	LOG_INF("CPU0 workload completed");

	for (;;) {
		LOG_DBG("heartbeat=%u acc=%u", heartbeat++, acc);
		k_sleep(K_MSEC(200));
	}

	return 0;
}
