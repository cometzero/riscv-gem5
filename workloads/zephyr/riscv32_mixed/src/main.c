#include <stdint.h>
#include <string.h>

#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#define OMX_ROLE DT_PROP(DT_PATH(zephyr_user), omx_role)
#define OMX_UART_POLICY DT_PROP(DT_PATH(zephyr_user), omx_uart_policy)

LOG_MODULE_REGISTER(riscv32_mixed, LOG_LEVEL_INF);

#define MIXED_SYNC_BASE ((uintptr_t)0x90000000U)
#define MIXED_SYNC_SLOT_AMP0 (MIXED_SYNC_BASE + 0x0U)
#define MIXED_SYNC_SLOT_AMP1 (MIXED_SYNC_BASE + 0x4U)
#define MIXED_SYNC_SLOT_SMP (MIXED_SYNC_BASE + 0x8U)
#define MIXED_SYNC_SIG_AMP0 UINT32_C(0x41504330)
#define MIXED_SYNC_SIG_AMP1 UINT32_C(0x41504331)
#define MIXED_SYNC_SIG_SMP UINT32_C(0x534d5032)
#define MIXED_SYNC_READY_MASK (BIT(0) | BIT(1) | BIT(2))

struct workload_profile {
	const char *dt_role;
	const char *marker_role;
	uint32_t phases;
	uint32_t loops_per_phase;
};

static const struct workload_profile profiles[] = {
	{
		.dt_role = "cluster0-amp-cpu0",
		.marker_role = "AMP CPU0",
		.phases = 4U,
		.loops_per_phase = 1600U,
	},
	{
		.dt_role = "cluster0-amp-cpu1",
		.marker_role = "AMP CPU1",
		.phases = 4U,
		.loops_per_phase = 1700U,
	},
	{
		.dt_role = "cluster1-smp",
		.marker_role = "CLUSTER1 SMP",
		.phases = 5U,
		.loops_per_phase = 2400U,
	},
};

static const struct workload_profile *resolve_profile(const char *dt_role)
{
	for (size_t i = 0; i < ARRAY_SIZE(profiles); ++i) {
		if (strcmp(dt_role, profiles[i].dt_role) == 0) {
			return &profiles[i];
		}
	}

	return NULL;
}

static volatile uint32_t *sync_slot(const char *dt_role)
{
	if (strcmp(dt_role, "cluster0-amp-cpu0") == 0) {
		return (volatile uint32_t *)MIXED_SYNC_SLOT_AMP0;
	}

	if (strcmp(dt_role, "cluster0-amp-cpu1") == 0) {
		return (volatile uint32_t *)MIXED_SYNC_SLOT_AMP1;
	}

	if (strcmp(dt_role, "cluster1-smp") == 0) {
		return (volatile uint32_t *)MIXED_SYNC_SLOT_SMP;
	}

	return NULL;
}

static uint32_t sync_signature(const char *dt_role)
{
	if (strcmp(dt_role, "cluster0-amp-cpu0") == 0) {
		return MIXED_SYNC_SIG_AMP0;
	}

	if (strcmp(dt_role, "cluster0-amp-cpu1") == 0) {
		return MIXED_SYNC_SIG_AMP1;
	}

	if (strcmp(dt_role, "cluster1-smp") == 0) {
		return MIXED_SYNC_SIG_SMP;
	}

	return 0U;
}

static void mark_role_ready(const char *dt_role)
{
	volatile uint32_t *slot = sync_slot(dt_role);
	uint32_t signature = sync_signature(dt_role);

	if (slot == NULL || signature == 0U) {
		return;
	}

	__atomic_store_n(slot, signature, __ATOMIC_RELEASE);
}

static uint32_t role_ready_mask(void)
{
	uint32_t mask = 0U;

	if (__atomic_load_n((volatile uint32_t *)MIXED_SYNC_SLOT_AMP0,
			    __ATOMIC_ACQUIRE) == MIXED_SYNC_SIG_AMP0) {
		mask |= BIT(0);
	}

	if (__atomic_load_n((volatile uint32_t *)MIXED_SYNC_SLOT_AMP1,
			    __ATOMIC_ACQUIRE) == MIXED_SYNC_SIG_AMP1) {
		mask |= BIT(1);
	}

	if (__atomic_load_n((volatile uint32_t *)MIXED_SYNC_SLOT_SMP,
			    __ATOMIC_ACQUIRE) == MIXED_SYNC_SIG_SMP) {
		mask |= BIT(2);
	}

	return mask;
}

int main(void)
{
	const char *dt_role = OMX_ROLE;
	const char *uart_policy = OMX_UART_POLICY;
	const struct workload_profile *profile = resolve_profile(dt_role);
	const char *marker_role = profile ? profile->marker_role : "UNKNOWN";
	uint32_t phases = profile ? profile->phases : 3U;
	uint32_t loops_per_phase = profile ? profile->loops_per_phase : 1200U;
	uint32_t total = 0U;

	printk("RISCV32 MIXED %s WORKLOAD START role=%s uart=%s\n", marker_role, dt_role,
	       uart_policy);
	printk("RISCV32 MIXED ROLE_UART role=%s uart=%s\n", dt_role, uart_policy);
	LOG_INF("mixed workload role=%s marker=%s uart=%s", dt_role, marker_role, uart_policy);
	LOG_INF("mixed workload verbose=%s",
		IS_ENABLED(CONFIG_RISCV32_MIXED_VERBOSE) ? "enabled" : "disabled");

	for (uint32_t phase = 0U; phase < phases; ++phase) {
		uint32_t phase_acc = 0U;

		for (uint32_t i = 0U; i < loops_per_phase; ++i) {
			phase_acc += (i + (phase * 3U) + marker_role[0]) & 0x1FU;
		}

		total += phase_acc;

		if (IS_ENABLED(CONFIG_RISCV32_MIXED_VERBOSE)) {
			LOG_INF("phase=%u phase_acc=%u total=%u", phase, phase_acc, total);
		}
	}

	printk("RISCV32 MIXED %s WORKLOAD DONE total=%u\n", marker_role, total);
	LOG_INF("mixed workload completed marker=%s total=%u", marker_role, total);
	mark_role_ready(dt_role);

	if (strcmp(dt_role, "cluster1-smp") == 0) {
		uint32_t ready_mask = 0U;

		for (uint32_t attempt = 0U; attempt < 300U; ++attempt) {
			ready_mask = role_ready_mask();
			if (ready_mask == MIXED_SYNC_READY_MASK) {
				break;
			}
			k_sleep(K_MSEC(10));
		}

		printk("RISCV32 MIXED ROLE_SYNC mask=0x%x status=%s\n", ready_mask,
		       ready_mask == MIXED_SYNC_READY_MASK ? "READY" : "TIMEOUT");
		LOG_INF("mixed role sync mask=0x%x status=%s", ready_mask,
			ready_mask == MIXED_SYNC_READY_MASK ? "READY" : "TIMEOUT");
	}

	for (uint32_t heartbeat = 0U;; ++heartbeat) {
		if (IS_ENABLED(CONFIG_RISCV32_MIXED_VERBOSE) && (heartbeat % 5U) == 0U) {
			LOG_INF("heartbeat=%u total=%u role=%s", heartbeat, total, marker_role);
		}
		k_sleep(K_MSEC(200));
	}

	return 0;
}
