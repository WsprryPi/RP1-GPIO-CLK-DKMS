/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#ifndef RP1_GPCLK_RESOURCE_POLICY_H
#define RP1_GPCLK_RESOURCE_POLICY_H

#include <linux/types.h>

#ifndef __KERNEL__
#include <stdbool.h>
#endif

#include <linux/rp1_gpclk.h>

#define RP1_GPCLK_PROVIDER_COMPATIBLE "raspberrypi,rp1-clocks"
#define RP1_GPCLK_GPIO_PROVIDER_COMPATIBLE "raspberrypi,rp1-gpio"
#define RP1_GPCLK_CLOCK_ID 33U
#define RP1_GPCLK_PARENT_PROVIDER_COMPATIBLE "raspberrypi,rp1-clocks"
#define RP1_GPCLK_PARENT_CLOCK_ID 3U
#define RP1_GPCLK_PARENT_RATE_HZ 200000000U
#define RP1_GPCLK_DMA_PROVIDER_COMPATIBLE "snps,axi-dma-1.01a"
#define RP1_GPCLK_DMA_REQUEST 0x30U
#define RP1_GPCLK_DIV_FRAC_OFFSET 0x17cU
#define RP1_GPCLK_REGISTER_BYTES 4U
#define RP1_GPCLK_TICK_DMA0_OFFSET 0x174024U
#define RP1_GPCLK_DMA_TICK0_OFFSET 0x158000U
#define RP1_GPCLK_TICK_RESOURCE_BYTES 8U
#define RP1_GPCLK_GPIO4_ENDPOINT_NAME "rp1-gpclk-dkms-gpio4"
#define RP1_GPCLK_GPIO20_ENDPOINT_NAME "rp1-gpclk-dkms-gpio20"

enum rp1_gpclk_pin_state_index {
	RP1_GPCLK_PIN_DEFAULT,
	RP1_GPCLK_PIN_ACTIVE_2,
	RP1_GPCLK_PIN_SAFE,
	RP1_GPCLK_PIN_ACTIVE_4,
	RP1_GPCLK_PIN_ACTIVE_8,
	RP1_GPCLK_PIN_ACTIVE_12,
	RP1_GPCLK_PIN_STATE_COUNT,
};

struct rp1_gpclk_pin_state {
	const char *name;
	const char *pin;
	const char *function;
	__u32 phandle;
	__u32 drive_ma;
	bool input_enabled;
	bool output_disabled;
};

const char *rp1_gpclk_pin_state_name(unsigned int index);
__u32 rp1_gpclk_pin_states_validate(__u32 route,
	const struct rp1_gpclk_pin_state states[RP1_GPCLK_PIN_STATE_COUNT]);
int rp1_gpclk_drive_state(__u32 drive_ma, __u32 supported_mask);
int rp1_gpclk_derive_target(__u64 resource_start, __u64 resource_end,
			    __u64 offset, __u64 bytes, __u64 *target);
int rp1_gpclk_route_pin_validate(__u32 route, __u32 pin);
int rp1_gpclk_route_endpoint_validate(__u32 route, const char *name);

#endif /* RP1_GPCLK_RESOURCE_POLICY_H */
