#!/usr/bin/env python3
"""Add /chosen/hakios-ram-banks to the Galaxy M20 ADT (patch 0086: XNU's RAM in several banks).

  m20-adt-ram-banks.py IN.adt OUT.adt [--only N]

The first bank is the boot bank exactly (dram-base/dram-size: 0x880000000 + 1 GiB on the 3 GB M20). The others are
the M20's first two DRAM banks (0x80000000 + 0x3da00000, 0xc0000000 + 0x40000000) minus:
  - the stock BOOT DTBH's /reserved-memory: sec_debug_magic and dram_test (0x80000000), TIMA 0xb8000000 +2 MiB,
    seclog 0xc0000000 +512 KiB, wifibt 0xe9000000 and abox 0xe9400000 (+4 MiB each), the framebuffer 0xec000000
    +20 MiB, modem 0xf5400000, cp_ram_logging 0xfdc00000, gnss 0xffc00000;
  - what S-Boot names on the kernel command line instead (TWRP's /proc/cmdline): ess_setup=0x91200000,
    sec_avc/tsp/summary logs, sec_debug.base and auto_summary_log up to 0x928a2000 (the S7 port saw page-table
    corruption with such areas inside a bank);
  - everything below 0x94000000: S-Boot's load area and the A40 loader, whose secondary-CPU trampoline stays in
    low memory while XNU runs;
  - 0xe9800000-0xec000000, unreserved but next to firmware and the panel: left out to be safe.
EXTRA is ordered far-from-the-logs first, so --only 2 tests the upper bank pieces alone.
"""
import argparse, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

EXTRA = [
    (0xc0200000, 0xe9000000),   # 654 MiB  (seclog below, wifibt/abox above)
    (0xed400000, 0xf5400000),   # 128 MiB  (framebuffer below, modem above)
    (0x94000000, 0xb8000000),   # 576 MiB  (S-Boot logs and the loader below, TIMA above)
    (0xb8200000, 0xbda00000),   #  88 MiB  (TIMA below, end of the bank)
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inp'); ap.add_argument('out')
    ap.add_argument('--only', type=int, default=len(EXTRA), help='use only the first N extra pieces')
    a = ap.parse_args()
    root, _ = adt.parse(open(a.inp, 'rb').read())
    chosen = next(c for c in root.children if c.name == 'chosen')
    base, = struct.unpack('<Q', chosen.prop('dram-base'))
    size, = struct.unpack('<Q', chosen.prop('dram-size'))
    banks = [(base, size)] + [(s, e - s) for s, e in EXTRA[:a.only]]
    for b, n in banks:
        assert b % 0x4000 == 0 and n % 0x4000 == 0, hex(b)
    value = b''.join(struct.pack('<QQ', b, n) for b, n in banks)
    chosen.props = [p for p in chosen.props if p[0] != 'hakios-ram-banks']
    chosen.props.append(('hakios-ram-banks', 0, value))
    open(a.out, 'wb').write(adt.serialize(root))
    extra = sum(n for _, n in banks[1:])
    print(f'{len(banks)} banks: boot {base:#x}+{size >> 20} MiB, extra {extra >> 20} MiB, total {(size + extra) >> 20} MiB')


if __name__ == '__main__':
    main()
