/* SPDX-License-Identifier: MIT */
#ifndef RP1_DRIVE_DISPATCH_STUBS_H
#define RP1_DRIVE_DISPATCH_STUBS_H

#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <linux/errno.h>

#include "rp1_gpclk/core.h"
#include "rp1_gpclk/execution_machine.h"
#include "rp1_gpclk/resource_policy.h"

#define RP1_GPCLK_DEVICE_H
#define RP1_GPCLK_KERNEL_API_H
#define __user
#define READ_ONCE(value) (value)
#define EACCES 13
#define EFAULT 14
#define ENODEV 19
#define EALREADY 114
#define EOPNOTSUPP 95
#define ESTALE 116
#define ETIMEDOUT 110

struct file { void *private_data; };

struct rp1_gpclk_device {
    struct rp1_gpclk_core core;
    enum rp1_gpclk_pin_transition pin_transition;
    __u32 route;
    __u32 supported_drive_ma_mask;
    bool operational_ready;
    bool dead;
    bool dma_submitted;
    bool tick_state_captured;
    bool clock_enabled;
    bool clock_prepared;
    bool execution_done;
    __u64 execution_started_ns;
    __u64 execution_finished_ns;
    __u64 execution_total_ns;
    void *execution_plan;
    void *worker;
    int lock;
};

struct rp1_gpclk_file {
    struct rp1_gpclk_device *device;
    __u64 owner;
};

bool rp1_gpclk_operationally_ready(const struct rp1_gpclk_device *device);
bool rp1_gpclk_output_inhibited(void);

static inline void mutex_lock(int *lock) { assert(!*lock); *lock = 1; }
static inline void mutex_unlock(int *lock) { assert(*lock); *lock = 0; }
static inline bool completion_done(const bool *done) { return *done; }
static inline __u64 ktime_get_boottime_ns(void) { return 0; }
static inline unsigned long msecs_to_jiffies(unsigned long ms) { return ms; }
static inline long wait_for_completion_interruptible_timeout(const bool *done, unsigned long ms)
{
    return *done ? (long)ms : 0;
}

static inline int copy_from_user(void *dest, const void *src, size_t size)
{
    memcpy(dest, src, size);
    return 0;
}

#define copy_to_user copy_from_user
#define kfree free
#define IS_ERR(ptr) ((uintptr_t)(ptr) >= (uintptr_t)-4095)
#define PTR_ERR(ptr) ((long)(intptr_t)(ptr))
#define u64_to_user_ptr(value) ((void *)(uintptr_t)(value))

static inline void *memdup_user(const void *src, size_t size)
{
    void *dest = malloc(size);

    assert(dest);
    return memcpy(dest, src, size);
}

static inline void strscpy(char *dest, const char *src, size_t size)
{
    assert(strlen(src) < size);
    memcpy(dest, src, strlen(src) + 1);
}

#endif
