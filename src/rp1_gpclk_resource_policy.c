// SPDX-License-Identifier: GPL-2.0-only OR MIT
#include <linux/string.h>

#include "rp1_gpclk/resource_policy.h"

static const struct {
	const char *name;
	__u32 drive_ma;
	__u32 drive_bit;
} pin_states[RP1_GPCLK_PIN_STATE_COUNT] = {
	[RP1_GPCLK_PIN_DEFAULT] = { "default", RP1_GPCLK_DRIVE_MA_2, 0 },
	[RP1_GPCLK_PIN_ACTIVE_2] = {
		"active", RP1_GPCLK_DRIVE_MA_2, RP1_GPCLK_DRIVE_SUPPORT_2_MA,
	},
	[RP1_GPCLK_PIN_SAFE] = { "safe", RP1_GPCLK_DRIVE_MA_2, 0 },
	[RP1_GPCLK_PIN_ACTIVE_4] = {
		"active-4ma", RP1_GPCLK_DRIVE_MA_4, RP1_GPCLK_DRIVE_SUPPORT_4_MA,
	},
	[RP1_GPCLK_PIN_ACTIVE_8] = {
		"active-8ma", RP1_GPCLK_DRIVE_MA_8, RP1_GPCLK_DRIVE_SUPPORT_8_MA,
	},
	[RP1_GPCLK_PIN_ACTIVE_12] = {
		"active-12ma", RP1_GPCLK_DRIVE_MA_12, RP1_GPCLK_DRIVE_SUPPORT_12_MA,
	},
};

const char *rp1_gpclk_pin_state_name(unsigned int index)
{
	return pin_states[index].name;
}

__u32 rp1_gpclk_pin_states_validate(__u32 route,
	const struct rp1_gpclk_pin_state states[RP1_GPCLK_PIN_STATE_COUNT])
{
	const char *pin;
	unsigned int index;
	__u32 mask = 0;

	switch (route) {
	case RP1_GPCLK_ROUTE_GPIO4:
		pin = "gpio4";
		break;
	case RP1_GPCLK_ROUTE_GPIO20:
		pin = "gpio20";
		break;
	default:
		return 0;
	}
	if (states[RP1_GPCLK_PIN_DEFAULT].phandle !=
	    states[RP1_GPCLK_PIN_SAFE].phandle)
		return 0;
	for (index = 0; index < RP1_GPCLK_PIN_STATE_COUNT; index++) {
		const struct rp1_gpclk_pin_state *state = &states[index];
		bool input = !pin_states[index].drive_bit;

		if (!state->phandle || !state->name || !state->pin ||
		    !state->function || strcmp(state->name, pin_states[index].name) ||
		    strcmp(state->pin, pin) ||
		    strcmp(state->function, input ? "gpio" : "gpclk0") ||
		    state->input_enabled != input || state->output_disabled != input ||
		    state->drive_ma != pin_states[index].drive_ma)
			return 0;
		mask |= pin_states[index].drive_bit;
	}
	return mask;
}

int rp1_gpclk_drive_state(__u32 drive_ma, __u32 supported_mask)
{
	unsigned int index;

	for (index = 0; index < RP1_GPCLK_PIN_STATE_COUNT; index++) {
		if (drive_ma == pin_states[index].drive_ma &&
		    (supported_mask & pin_states[index].drive_bit))
			return index;
	}
	return -1;
}

int rp1_gpclk_route_endpoint_validate(__u32 route, const char *name)
{
	if (!name)
		return -1;
	if (route == RP1_GPCLK_ROUTE_GPIO4 &&
	    !strcmp(name, RP1_GPCLK_GPIO4_ENDPOINT_NAME))
		return 0;
	if (route == RP1_GPCLK_ROUTE_GPIO20 &&
	    !strcmp(name, RP1_GPCLK_GPIO20_ENDPOINT_NAME))
		return 0;
	return -1;
}

int rp1_gpclk_route_pin_validate(__u32 route, __u32 pin)
{
	if (route == RP1_GPCLK_ROUTE_GPIO4 && pin == 4)
		return 0;
	if (route == RP1_GPCLK_ROUTE_GPIO20 && pin == 20)
		return 0;
	return -1;
}

int rp1_gpclk_derive_target(__u64 resource_start, __u64 resource_end,
			    __u64 offset, __u64 bytes, __u64 *target)
{
	__u64 address;
	__u64 last;

	if (!target || resource_end < resource_start || !bytes ||
	    resource_start > ~(__u64)0 - offset)
		return -1;
	address = resource_start + offset;
	if (address > ~(__u64)0 - (bytes - 1))
		return -1;
	last = address + bytes - 1;
	if (address < resource_start || last > resource_end ||
	    address % bytes)
		return -1;
	*target = address;
	return 0;
}
