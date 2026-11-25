#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise drive ioctls and check their handoff to the worker."""

from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from drive_capabilities import build_dispatch_probe

with tempfile.TemporaryDirectory(prefix="rp1-drive-dispatch-") as directory:
    binary = build_dispatch_probe(ROOT, Path(directory))
    subprocess.run([binary], check=True)

execution = (ROOT / "src/rp1_gpclk_execution.c").read_text()
select = execution.split("static int rp1_gpclk_machine_select_active(", 1)[1]
select = select.split("static int rp1_gpclk_machine_readback(", 1)[0]
assert select.index("WRITE_ONCE(device->pin_transition, RP1_GPCLK_PINS_UNCERTAIN)") < select.index(
    "pinctrl_select_state(device->pinctrl,"
)
assert "device->pins[context->plan->drive_state]" in select
descriptor = execution.split("static int rp1_gpclk_run_descriptor(", 1)[1]
descriptor = descriptor.split("static void rp1_gpclk_publish_failure(", 1)[0]
order = [descriptor.index(token) for token in (
    "if (atomic_read(&device->stop_requested))",
    "READ_ONCE(device->pin_transition) != RP1_GPCLK_PINS_ACTIVE",
    "rp1_gpclk_execution_machine_activate(",
    "rp1_gpclk_set_enabled(device, true)",
    "rp1_gpclk_tick_start(device)",
)]
assert order == sorted(order)
gap = execution.split("if (!enabled) {", 1)[1].split("} else {", 1)[0]
assert gap.index("rp1_gpclk_set_enabled(device, false)") < gap.index("rp1_gpclk_machine_select_safe(&context)")
assert execution.count("plan->drive_state =") == 1
print("drive worker source order: PASS (cancel, select, enable, and gap safety)")
