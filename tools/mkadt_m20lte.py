#!/usr/bin/env python3
"""Build the Galaxy M20 (m20lte, SM-M205F, Exynos 7904) ADT for M20LTE XNU.

Derived from mkadt_herolte.py. Addresses come from mainline exynos7885.dtsi
and ztOS's devices/m20lte DTS (see M20LTE_PROGRESS.md). Storage is the
Exynos MSHC eMMC (/a5xelte-emmc, bsd/dev/a5xelte_emmc.c); no touch, key or
GPU nodes yet.
"""
import argparse
import os
from pathlib import Path

import adt
import mkadt

DRAM_BASE = 0xc8000000      # isolated XNU window (shim/m20lte/xnu_boot.c)
DRAM_SIZE = 0x20000000      # 512 MiB, ends below WLBT at 0xe9000000
SOC_BASE = 0x10000000       # arm-io ranges base; child regs are relative
FB_BASE, FB_WIDTH, FB_HEIGHT = 0xec000000, 1080, 2340
EMMC_BASE = 0x13500000      # exynos7885.dtsi mmc@13500000
GICD, GICC = 0x12301000, 0x12302000   # exynos7885.dtsi gic-400
# Logical order: boot A53 cluster first, then the second A53 pair, then
# the two A73s. MPIDR from exynos7885.dtsi; probe 2 booted on 0x100.
CPUS = [(0x100, 'a53'), (0x101, 'a53'), (0x102, 'a53'), (0x103, 'a53'),
        (0x200, 'a53'), (0x201, 'a53'), (0x000, 'a73'), (0x001, 'a73')]


def set_prop(node, name, value):
    for i, (key, flags, _) in enumerate(node.props):
        if key == name:
            node.props[i] = (key, flags, value)
            return
    node.props.append((name, 0, value))


def child(node, name):
    for candidate in node.children:
        if candidate.prop('name') == mkadt.cstr(name):
            return candidate
    raise ValueError(f'missing donor ADT node {name}')


def build(canvas=(FB_WIDTH, FB_HEIGHT), dram=(DRAM_BASE, DRAM_SIZE)):
    root = mkadt.build(seed=os.urandom(64), qemu=True)
    # iPhone X userland (iPhone10,3 / D22AP) like the donor; its 19.5:9
    # screen matches the M20's 1080x2340. 'samsung,a5xelte' keeps the shared
    # SweetPlatformExpert IONameMatch.
    set_prop(root, 'compatible', mkadt.cstr('D22AP') + mkadt.cstr('iPhone10,3') +
             mkadt.cstr('samsung,a5xelte') + mkadt.cstr('samsung,m20lte') +
             mkadt.cstr('samsung,exynos7904') + mkadt.cstr('AppleARM'))
    chosen = child(root, 'chosen')
    set_prop(chosen, 'dram-base', mkadt.u64(dram[0]))
    set_prop(chosen, 'dram-size', mkadt.u64(dram[1]))
    set_prop(chosen, 'firmware-version', mkadt.cstr('m20lte-entry'))
    set_prop(chosen, 'system-firmware-version', mkadt.cstr('m20lte-entry'))
    # Synthetic, locally administered addresses (see mkadt_herolte.py).
    for name, last in (('wifi0', 1), ('bluetooth0', 2), ('ethernet0', 3)):
        set_prop(chosen, f'mac-address-{name}', bytes((0x02, 0x4d, 0x32, 0x30, 0x4c, last)))
    # /product comes from the iPhone X DeviceTree (research/ipsw-x/d22ap.adt,
    # see README); MobileGestalt needs it for userland, the kernel does not.
    products = [n for n in root.children if n.prop('name') == mkadt.cstr('product')]
    if products:
        set_prop(products[0], 'artwork-display-gamut', mkadt.cstr('sRGB'))
    cpus = child(root, 'cpus')
    cpu0 = child(cpus, 'cpu0')
    set_prop(cpu0, 'compatible', mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8'))
    set_prop(cpu0, 'reg', mkadt.u32(CPUS[0][0]))
    set_prop(cpu0, 'timebase-frequency', mkadt.u32(26000000))
    for logical, (mpidr, kind) in enumerate(CPUS[1:], start=1):
        big = kind == 'a73'
        cpus.children.append(mkadt.node(f'cpu{logical}', [
            ('device_type', mkadt.cstr('cpu')),
            # SweetCPU matches IONameMatch 'arm,cortex-a53' (KernelConfigTables).
            ('compatible', (mkadt.cstr('arm,cortex-a73') if big else b'') +
                           mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8')),
            ('reg', mkadt.u32(mpidr)),
            ('cpu-id', mkadt.u32(logical)),
            ('cluster-id', mkadt.u32(0)),
            ('cluster-type', mkadt.u32(0)),
            ('die-cluster-id', mkadt.u32(0)),
            ('cluster-core-id', mkadt.u32(logical)),
            ('l2-cache-id', mkadt.u32(1 if big else 0)),
            ('l3-cache-id', mkadt.u32(0)),
            ('state', mkadt.cstr('stopped')),
            ('timebase-frequency', mkadt.u32(26000000)),
            ('clock-frequency', mkadt.u32(1768000000 if big else 1586000000)),
            ('bus-frequency', mkadt.u32(100000000)),
            ('memory-frequency', mkadt.u32(1794000000)),
            ('peripheral-frequency', mkadt.u32(26000000)),
            ('fixed-frequency', mkadt.u32(26000000)),
        ]))
    arm_io = child(root, 'arm-io')
    set_prop(arm_io, 'device_type', mkadt.cstr('m20lte-io'))
    set_prop(arm_io, 'compatible', mkadt.cstr('samsung,exynos7904-io') +
             mkadt.cstr('arm-io'))
    set_prop(arm_io, 'ranges', mkadt.u64(0, SOC_BASE, 0xf0000000))
    arm_io.children = [n for n in arm_io.children if n.prop('name') == mkadt.cstr('wdt')]
    arm_io.children.append(mkadt.node('gic', [
        ('compatible', mkadt.cstr('arm,cortex-a15-gic')),
        ('interrupt-controller', mkadt.cstr('master')),
        ('virtual-timer-intid', mkadt.u32(27)),
        ('reg', mkadt.u64(GICD - SOC_BASE, 0x1000, GICC - SOC_BASE, 0x1000)),
    ]))
    arm_io.children.append(mkadt.node('disp0', [
        ('device_type', mkadt.cstr('display-subsystem')),
        # AppleCLCD (SweetFramebuffer.cpp) matches 'samsung,a5xelte-display'.
        ('compatible', mkadt.cstr('samsung,a5xelte-display') +
         mkadt.cstr('samsung,m20lte-display')),
        ('canvas-width', mkadt.u32(canvas[0])),
        ('canvas-height', mkadt.u32(canvas[1])),
    ]))
    root.children = [n for n in root.children if n.prop('name') not in
                     (mkadt.cstr('sweet-fbcon'), mkadt.cstr('sweet-ufs'))]
    # Absolute address, read by bsd/dev/a5xelte_emmc.c (A5XELTE_EMMC_PA).
    root.children.append(mkadt.node('a5xelte-emmc', [
        ('reg', mkadt.u64(EMMC_BASE, 0x2000)),
    ]))
    # pe_serial.c looks this node up by name for the kprintf console.
    root.children.append(mkadt.node('a5xelte-fbcon', [
        ('reg', mkadt.u64(FB_BASE, FB_WIDTH * FB_HEIGHT * 4)),
        ('width', mkadt.u32(FB_WIDTH)),
        ('height', mkadt.u32(FB_HEIGHT)),
        ('stride', mkadt.u32(FB_WIDTH * 4)),
    ]))
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--canvas', default=f'{FB_WIDTH}x{FB_HEIGHT}',
                        help='presented display WxH')
    args = parser.parse_args()
    canvas = tuple(int(v) for v in args.canvas.lower().split('x'))
    blob = adt.serialize(build(canvas))
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes')
