# SPDX-License-Identifier: MIT
"""Run the module's route drive policy against independently checked DTBOs."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


ROUTES = {"gpio4": (1, 4), "gpio20": (2, 20)}
ENDPOINT_COMPATIBLE = "wsprrypi,rp1-gpclk-dkms-v1"

# Resolve the candidate's external fixups without using a live device tree.
BASE = """/dts-v1/;
/ {
    rp1: test-rp1 {
        rp1_gpio: gpio { compatible = "raspberrypi,rp1-gpio"; };
        rp1_clocks: clocks {};
        rp1_dma: dma {};
    };
};
"""


def run(args):
    return subprocess.run(args, check=True, capture_output=True, timeout=30).stdout


def properties(blob, node):
    return set(run(["fdtget", "-p", blob, node]).decode().splitlines())


def children(blob, node):
    return run(["fdtget", "-l", blob, node]).decode().splitlines()


def raw(blob, node, prop):
    return bytes(int(cell, 16) for cell in
                 run(["fdtget", "-t", "bx", blob, node, prop]).split())


def strings(blob, node, prop):
    values = raw(blob, node, prop).decode("ascii").split("\0")
    if len(values) < 2 or values[-1] or any(not value for value in values[:-1]):
        raise ValueError(f"invalid string list in {node}:{prop}")
    return values[:-1]


def string(blob, node, prop):
    value, = strings(blob, node, prop)
    return value


def cell(blob, node, prop):
    value = raw(blob, node, prop)
    if len(value) != 4:
        raise ValueError(f"expected one cell in {node}:{prop}")
    return struct.unpack(">I", value)[0]


def available(blob, node, props):
    return "status" not in props or string(blob, node, "status") in ("okay", "ok")


def available_gpio_providers(blob, parent):
    providers = []
    for child in children(blob, parent):
        node = f"{parent}/{child}"
        props = properties(blob, node)
        if ("compatible" in props and "raspberrypi,rp1-gpio" in strings(blob, node, "compatible") and
                available(blob, node, props)):
            providers.append(node)
    return providers


def build_dispatch_probe(source, directory):
    (directory / "linux").mkdir()
    for header in ("fs.h", "ktime.h", "uaccess.h"):
        (directory / "linux" / header).touch()
    probe = directory / "drive-dispatch"
    run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
         "-DRP1_GPCLK_HOST_TEST", "-I" + str(directory),
         "-I" + str(source / "tests/fixtures/linux"), "-I" + str(source / "include"),
         "-I" + str(source / "include/uapi"), "-include", source / "tests/fixtures/drive_dispatch_stubs.h",
         source / "src/rp1_gpclk_uapi_dispatch.c", source / "src/rp1_gpclk_core.c",
         source / "src/rp1_gpclk_compatibility.c",
         source / "src/rp1_gpclk_resource_policy.c",
         source / "tests/fixtures/drive_dispatch.c", "-o", probe])
    return probe


def build_probe(source, directory):
    probe = build_dispatch_probe(source, directory)
    base_source = directory / "base.dts"
    base_source.write_text(BASE, encoding="ascii")
    base = directory / "base.dtb"
    run(["dtc", "-@", "-I", "dts", "-O", "dtb", "-o", base, base_source])
    return probe, base


def validate_overlay(probe, base, overlay, route):
    route_id, pin = ROUTES[route]
    if not 40 < overlay.stat().st_size < 65536:
        raise ValueError(f"{route} overlay exceeds the controller size contract")
    blob = overlay.with_suffix(".dtb")
    run(["fdtoverlay", "-i", base, "-o", blob, overlay])
    endpoint = f"/test-rp1/rp1-gpclk-dkms-{route}"
    endpoint_props = properties(blob, endpoint)
    if (not available(blob, endpoint, endpoint_props) or
            ENDPOINT_COMPATIBLE not in strings(blob, endpoint, "compatible") or
            cell(blob, endpoint, "wsprrypi,route") != route_id or
            cell(blob, endpoint, "wsprrypi,pin") != pin):
        raise ValueError(f"wrong route identity in {route} overlay")
    gpio = "/test-rp1/gpio"
    if available_gpio_providers(blob, "/test-rp1") != [gpio]:
        raise ValueError(f"absent, foreign or ambiguous RP1 pinctrl provider in {route} overlay")
    by_handle = {}
    for child in children(blob, gpio):
        node = f"{gpio}/{child}"
        handle = cell(blob, node, "phandle")
        if not handle or handle in by_handle:
            raise ValueError(f"invalid phandle in {node}")
        by_handle[handle] = node
    args = [probe, str(route_id)]
    flags = {"bias-disable", "input-enable", "output-disable"}
    keys = {"pins", "function", "drive-strength", "phandle", "linux,phandle", "name"}
    names = strings(blob, endpoint, "pinctrl-names")
    state_keys = {"pinctrl-names"} | {f"pinctrl-{index}" for index in range(len(names))}
    if {key for key in endpoint_props if key.startswith("pinctrl-")} != state_keys:
        raise ValueError(f"unexpected pinctrl properties in {route} overlay")
    for index, name in enumerate(names):
        handle = cell(blob, endpoint, f"pinctrl-{index}")
        node = by_handle.get(handle)
        if node is None:
            raise ValueError(f"foreign pinctrl phandle in {route} state {name}")
        props = properties(blob, node)
        if ("bias-disable" not in props or props - keys - flags or children(blob, node) or
                any(raw(blob, node, flag) for flag in flags & props)):
            raise ValueError(f"unexpected pinctrl settings in {node}")
        args.extend([name, string(blob, node, "pins"), string(blob, node, "function"),
                     str(handle), str(cell(blob, node, "drive-strength")),
                     str(int("input-enable" in props)), str(int("output-disable" in props))])
    return int(run(args))


def validate_drives(source, boot_overlays):
    """The caller supplies an independent source reconstruction and package bytes."""
    with tempfile.TemporaryDirectory(prefix="rp1-drive-capability-") as temporary:
        directory = Path(temporary)
        probe, base = build_probe(source, directory)
        run([sys.executable, source / "scripts/build_runtime_controller.py"])
        results = {}
        for route in ROUTES:
            boot = directory / f"boot-{route}.dtbo"
            boot_data = boot_overlays[route]
            boot.write_bytes(boot_data)
            mask = validate_overlay(probe, base, boot, route)

            runtime = source / "build/runtime-controller" / f"{route}.dtbo"
            runtime_data = runtime.read_bytes()
            # Runtime embedding removes symbol exports while retaining all fixups.
            run(["fdtput", "-r", boot, "/__symbols__"])
            if boot.read_bytes() != runtime_data:
                raise ValueError(f"runtime overlay differs from the packaged {route} route")
            results[route] = {
                "supportedDriveMaMask": mask,
                "bootDtboSha256": hashlib.sha256(boot_data).hexdigest(),
                "runtimeDtboSha256": hashlib.sha256(runtime_data).hexdigest(),
            }
        return results


if __name__ == "__main__":
    gpio4, gpio20 = map(Path, sys.argv[1:])
    print(json.dumps(validate_drives(Path(__file__).resolve().parents[1], {
        "gpio4": gpio4.read_bytes(), "gpio20": gpio20.read_bytes(),
    }), sort_keys=True))
