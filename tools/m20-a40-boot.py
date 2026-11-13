#!/usr/bin/env python3
"""Make a Galaxy M20 BOOT image from an A40-port XNU kernel (branch a40m20).

  m20-a40-boot.py KERNEL ADT LOADER16 STOCK_BOOT OUT [--cmdline TEXT]

KERNEL   kernel.development.sweet from the xnu workflow
ADT      the A40 port's ADT adapted to the M20 (dram-size 1 GiB for the
         3 GB M20, the a40-touch node renamed m20-touch)
LOADER16 tlfares/iOS16-on-A40's loader16 Image (the prebuilt boot image's
         kernel slot up to its payload offset)
STOCK_BOOT the M20's own BOOT backup: its header and DTBH are kept

The payload is made by the A40 port's tools/mkpayload.py (on PYTHONPATH
with its adt.py) and appended to loader16 at the offset its Image header
names (0x20 offset, 0x28 size); tools/m20lte-pack-boot.py (branch m20lte)
then packs the kernel slot around the M20 header. Host-only: no device I/O.
"""
import argparse, struct, subprocess, sys, tempfile
from pathlib import Path

CMDLINE = ('debug=0xc keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 '
           'unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 '
           'rootrw=1 launchd_unsecure_cache=1 wdt=-1 cpus=2 sweetusb=0 sweetbattery=0 '
           'sweetfb_hz=30 sweetfb_noconsole=1 ufsroot=USERDATA')

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
for a in ('kernel', 'adt', 'loader16', 'stock', 'out'):
    ap.add_argument(a)
ap.add_argument('--cmdline', default=CMDLINE)
ap.add_argument('--mkpayload', required=True, help="the A40 port's tools/mkpayload.py")
ap.add_argument('--pack', required=True, help='tools/m20lte-pack-boot.py')
a = ap.parse_args()

loader = bytearray(Path(a.loader16).read_bytes())
off = struct.unpack_from('<Q', loader, 0x20)[0]
if loader[0x38:0x3c] != b'ARMd' or off != len(loader):
    sys.exit('LOADER16 must be the Image up to its payload offset')
with tempfile.TemporaryDirectory() as t:
    payload = Path(t) / 'payload.bin'
    subprocess.run([sys.executable, a.mkpayload, a.kernel, a.adt, str(payload),
                    '--cmdline', a.cmdline], check=True)
    blob = payload.read_bytes()
    struct.pack_into('<2Q', loader, 0x20, off, len(blob))
    slot = Path(t) / 'kslot.bin'
    slot.write_bytes(bytes(loader) + blob)
    subprocess.run([sys.executable, a.pack, 'pack', a.stock, str(slot), a.out,
                    '--partition-size', str(32 << 20)], check=True)
