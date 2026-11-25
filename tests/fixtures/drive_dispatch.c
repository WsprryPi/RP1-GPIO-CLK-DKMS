// SPDX-License-Identifier: MIT
#include <stdio.h>

#include "rp1_gpclk/execution.h"
#include "rp1_gpclk/uapi_dispatch.h"

static bool inhibited;
static int selected_state;
static unsigned int wake_calls;

bool rp1_gpclk_operationally_ready(const struct rp1_gpclk_device *device)
{
    return device->operational_ready && !inhibited;
}

bool rp1_gpclk_output_inhibited(void) { return inhibited; }

int rp1_gpclk_execution_submit_events(struct rp1_gpclk_device *device, __u64 owner,
    struct rp1_gpclk_submit_events *request, unsigned int drive_state,
    const struct rp1_gpclk_tone *tones, const struct rp1_gpclk_event *events)
{
    selected_state = (int)drive_state;
    return rp1_gpclk_core_submit_events(&device->core, owner, request, tones, events);
}

void rp1_gpclk_execution_activate(struct rp1_gpclk_device *device, __u64 generation)
{
    assert(device->core.value.generation == generation);
    wake_calls++;
}

int rp1_gpclk_execution_stop(struct rp1_gpclk_device *device, __u64 owner,
    __u64 lease, __u64 generation, __u32 reason)
{
    assert(reason == RP1_GPCLK_REASON_STOPPED);
    return rp1_gpclk_core_stop(&device->core, owner, lease, generation);
}

static long ioctl_call(struct file *file, unsigned int op, void *value)
{
    return rp1_gpclk_uapi_dispatch(file, op, (unsigned long)(uintptr_t)value);
}

static void exercise_route(__u32 route, const char *pin)
{
    const struct rp1_gpclk_pin_state states[] = {
        {"default", pin, "gpio", 1, 2, true, true},
        {"active", pin, "gpclk0", 2, 2, false, false},
        {"safe", pin, "gpio", 1, 2, true, true},
        {"active-4ma", pin, "gpclk0", 3, 4, false, false},
        {"active-8ma", pin, "gpclk0", 4, 8, false, false},
        {"active-12ma", pin, "gpclk0", 5, 12, false, false},
    };
    const struct { __u32 drive; int state; } cases[] = {
        {12, RP1_GPCLK_PIN_ACTIVE_12}, {2, RP1_GPCLK_PIN_ACTIVE_2},
        {4, RP1_GPCLK_PIN_ACTIVE_4}, {8, RP1_GPCLK_PIN_ACTIVE_8},
    };
    struct rp1_gpclk_device device = {
        .route = route, .operational_ready = true, .execution_done = true,
        .supported_drive_ma_mask = rp1_gpclk_pin_states_validate(route, states),
    };
    struct rp1_gpclk_file context = {.device = &device, .owner = 1};
    struct file file = {.private_data = &context};
    struct rp1_gpclk_query query = {.header.size = sizeof(query)};
    struct rp1_gpclk_acquire acquire = {.header.size = sizeof(acquire), .expected_route = route};
    struct rp1_gpclk_snapshot snapshot = {.header.size = sizeof(snapshot)};
    const struct rp1_gpclk_tone tone = {
        .lower_divider_q16 = 2U << 16, .upper_divider_q16 = (2U << 16) + 1,
        .lower_count = 1, .upper_count = 1,
    };
    const struct rp1_gpclk_event event = {
        .duration_ns = RP1_GPCLK_EVENT_DURATION_NS_MIN,
        .flags = RP1_GPCLK_EVENT_F_OUTPUT_ENABLED,
    };
    struct rp1_gpclk_submit_events request = {
        .header.size = sizeof(request), .tones_ptr = (__u64)(uintptr_t)&tone,
        .events_ptr = (__u64)(uintptr_t)&event,
        .fractional_bits = RP1_GPCLK_FRACTIONAL_BITS, .tick_divider = RP1_GPCLK_TICK_DIVIDER,
        .tone_count = 1, .event_count = 1, .total_duration_ns = event.duration_ns,
    };
    unsigned int index;

    wake_calls = 0;
    selected_state = -1;
    rp1_gpclk_core_init(&device.core);
    assert(ioctl_call(&file, RP1_GPCLK_IOC_QUERY, &query) == 0);
    assert(query.route == route && query.supported_drive_ma_mask == 15);
    assert(ioctl_call(&file, RP1_GPCLK_IOC_ACQUIRE, &acquire) == 0);
    request.lease_id = acquire.lease_id;
    request.drive_ma = 6;
    assert(ioctl_call(&file, RP1_GPCLK_IOC_SUBMIT_EVENTS, &request) == -EINVAL);
    request.drive_ma = 4;
    device.supported_drive_ma_mask = RP1_GPCLK_DRIVE_SUPPORT_2_MA;
    assert(ioctl_call(&file, RP1_GPCLK_IOC_QUERY, &query) == 0);
    assert(query.supported_drive_ma_mask == RP1_GPCLK_DRIVE_SUPPORT_2_MA);
    assert(ioctl_call(&file, RP1_GPCLK_IOC_SUBMIT_EVENTS, &request) == -EINVAL);
    device.supported_drive_ma_mask = rp1_gpclk_pin_states_validate(route, states);
    inhibited = true;
    assert(ioctl_call(&file, RP1_GPCLK_IOC_QUERY, &query) == 0);
    assert(query.supported_drive_ma_mask == 15);
    assert(ioctl_call(&file, RP1_GPCLK_IOC_SUBMIT_EVENTS, &request) == -EACCES);
    assert(wake_calls == 0 && selected_state == -1);
    inhibited = false;

    for (index = 0; index < sizeof(cases) / sizeof(cases[0]); index++) {
        request.drive_ma = cases[index].drive;
        request.generation = 0;
        assert(ioctl_call(&file, RP1_GPCLK_IOC_SUBMIT_EVENTS, &request) == 0);
        assert(wake_calls == index + 1 && request.generation == index + 1);
        assert(selected_state == cases[index].state);
        if (request.drive_ma == 4) {
            struct rp1_gpclk_stop stop = {
                .header.size = sizeof(stop), .lease_id = request.lease_id,
                .generation = request.generation,
            };

            assert(ioctl_call(&file, RP1_GPCLK_IOC_STOP, &stop) == 0);
        }
        if (request.drive_ma == 8) {
            device.pin_transition = RP1_GPCLK_PINS_UNCERTAIN;
            assert(rp1_gpclk_core_cleanup_failed(&device.core, context.owner,
                request.lease_id, request.generation) == RP1_GPCLK_CORE_OK);
            assert(ioctl_call(&file, RP1_GPCLK_IOC_GET_SNAPSHOT, &snapshot) == 0);
            assert(snapshot.gpio_safe == RP1_GPCLK_OBSERVATION_UNKNOWN);
            assert(snapshot.cleanup_fault == RP1_GPCLK_OBSERVATION_TRUE);
            assert(snapshot.stable == RP1_GPCLK_OBSERVATION_FALSE);
        } else {
            assert(rp1_gpclk_core_progress(&device.core, context.owner,
                request.lease_id, request.generation) == RP1_GPCLK_CORE_OK);
        }
    }
    request.generation = 0;
    assert(ioctl_call(&file, RP1_GPCLK_IOC_SUBMIT_EVENTS, &request) == -EUCLEAN);
    assert(wake_calls == 4);
}

static int report_overlay(int argc, char **argv)
{
    struct rp1_gpclk_pin_state states[RP1_GPCLK_PIN_STATE_COUNT] = {0};
    struct rp1_gpclk_device device = {.operational_ready = true};
    struct rp1_gpclk_file context = {.device = &device};
    struct file file = {.private_data = &context};
    struct rp1_gpclk_query query = {.header.size = sizeof(query)};
    unsigned int index;

    if (argc != 2 + RP1_GPCLK_PIN_STATE_COUNT * 7)
        return 2;
    /* The offline reader supplies bounded, normalized FDT fields. */
    for (index = 0; index < RP1_GPCLK_PIN_STATE_COUNT; index++) {
        char **state = &argv[2 + index * 7];

        states[index].name = state[0];
        states[index].pin = state[1];
        states[index].function = state[2];
        states[index].phandle = strtoul(state[3], NULL, 10);
        states[index].drive_ma = strtoul(state[4], NULL, 10);
        states[index].input_enabled = strtoul(state[5], NULL, 10) != 0;
        states[index].output_disabled = strtoul(state[6], NULL, 10) != 0;
    }
    device.route = strtoul(argv[1], NULL, 10);
    device.supported_drive_ma_mask = rp1_gpclk_pin_states_validate(device.route, states);
    if (!device.supported_drive_ma_mask ||
        ioctl_call(&file, RP1_GPCLK_IOC_QUERY, &query) ||
        query.route != device.route ||
        query.supported_drive_ma_mask != device.supported_drive_ma_mask)
        return 1;
    printf("%u\n", (unsigned int)query.supported_drive_ma_mask);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc > 1)
        return report_overlay(argc, argv);
    exercise_route(RP1_GPCLK_ROUTE_GPIO4, "gpio4");
    exercise_route(RP1_GPCLK_ROUTE_GPIO20, "gpio20");
    puts("production drive ioctl dispatch: PASS (both routes, four levels, refusal, cleanup latch)");
    return 0;
}
