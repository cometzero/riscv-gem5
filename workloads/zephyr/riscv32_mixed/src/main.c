#include <stdint.h>
#include <string.h>

#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#define OMX_ROLE DT_PROP(DT_PATH(zephyr_user), omx_role)

LOG_MODULE_REGISTER(riscv32_mixed, LOG_LEVEL_INF);

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

int main(void)
{
	const char *dt_role = OMX_ROLE;
	const struct workload_profile *profile = resolve_profile(dt_role);
	const char *marker_role = profile ? profile->marker_role : "UNKNOWN";
	uint32_t phases = profile ? profile->phases : 3U;
	uint32_t loops_per_phase = profile ? profile->loops_per_phase : 1200U;
	uint32_t total = 0U;

	printk("RISCV32 MIXED %s WORKLOAD START role=%s\n", marker_role, dt_role);
	LOG_INF("mixed workload role=%s marker=%s", dt_role, marker_role);
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

	for (uint32_t heartbeat = 0U;; ++heartbeat) {
		if (IS_ENABLED(CONFIG_RISCV32_MIXED_VERBOSE) && (heartbeat % 5U) == 0U) {
			LOG_INF("heartbeat=%u total=%u role=%s", heartbeat, total, marker_role);
		}
		k_sleep(K_MSEC(200));
	}

	return 0;
}
