# Galaxy M20 (m20lte, SM-M205F, Exynos 7904) progress

Port of this tree (A5XELTE / HEROLTE lineage) to the Galaxy M20. Device
evidence, build results and screen reports are recorded separately.

## Board facts (from ztOS's devices/m20lte and mainline exynos7885.dtsi)

| Item | Value |
| --- | --- |
| CPUs | 6x Cortex-A53 (MPIDR 0x100-0x103, 0x200-0x201), 2x Cortex-A73 (0x0, 0x1); boots on 0x100 |
| GIC | GIC-400 (GICv2): distributor 0x12301000, CPU interface 0x12302000 |
| Timer | 26 MHz; virtual timer PPI 11 (INTID 27) |
| RAM (3 GB) | 0x80000000-0xbd9fffff, 0xc0000000-0xffffffff, 0x880000000-0x8bfffffff |
| Reserved | 0x80000000+0x1000 sec_debug, 0x80002000+0x2000, 0x91200000 ESS, 0x92400000+0x8000 ramoops (TWRP pstore), 0xb8000000+2M TIMA, 0xc0000000+512K seclog, 0xe9000000+8M WLBT/ABOX, 0xec000000+20M framebuffer, 0xf5400000+136M modem, 0xfdc00000+32M CP log, 0xffc00000+4M GNSS |
| XNU window | 0xc8000000-0xe8000000 (512 MiB); log page 0xc7fff000 |
| Display | S-Boot framebuffer 0xec000000, 1080x2340 ARGB8888, stride 4320; DECON_F 0x14860000, HW_SW_TRIG_CONTROL (+0x70) = 0x1281 |
| eMMC | DesignWare MSHC at 0x13500000 |
| PMU | 0x11c80000: INFORM2 +0x808, INFORM3 +0x80c (0x12345674 = TWRP), SWRESET +0x400 |
| Partitions | BOOT p12 (32 MiB), RECOVERY p13 (TWRP), EFS p3, SYSTEM p20, USERDATA p28 |

## Log channel

`shim/m20lte/fbtext.c` mirrors every loader/probe screen line into TWRP's
pstore pmsg zone (0x92404000). After the reset to TWRP:
`adb shell cat /sys/fs/pstore/pmsg-ramoops-0`.

## 2026-11-12: stage-0 probe on the phone

Probe 1 and probe 2 (`shim/m20lte/probe.*`, CI run 43226544191) were written
to BOOT p12 from TWRP; readback hashes matched. Screen photo and pstore
record agree:

    EL 1, SCTLR 0x30C5183E (MMU off), FDT 0x8A000000, IMAGE 0x80080000,
    MIDR 0x410FD034 (Cortex-A53 r0p4), MPIDR 0x80000100,
    ID_AA64MMFR0 0x1122 (no 16 KiB granule), PFR0 0x2222, ISAR0 0x11120,
    CNTFRQ 26 MHz, DECON trigger before 0x1290,
    initrd 0x89000000..0x89000014, 16K PAGES: NO

The PMU recovery request returned the phone to TWRP after 60 s. No other
partition was written.

## 2026-11-12: M20LTE kernel config and ADT (build only)

`xnu/patches/0400-m20lte-board-target.patch` adds `MACHINE_CONFIG=M20LTE`:
the A5XELTE code paths (4 KiB pages, `-mcpu=cortex-a53`, GICv2, MSHC eMMC)
with the M20 values in `pexpert/arm64/A5XELTE.h` (framebuffer
0xec000000 1080x2340, marker 0xc7fff100, boot MPIDR 0x100, eMMC
0x13500000). The Exynos 7580 key and touch probes are compiled out.
`tools/mkadt_m20lte.py` builds the matching ADT (RAM 0xc8000000 + 512 MiB).
The patch was generated against xnu-8796.141.3 with this branch's series
applied (252 of 254 apply with `git apply`; 0031 and 0041 need the HFS
sources that `0026-stage-hfs.sh` stages in CI).

First kernel test plan: BOOT only, `cpus=1`, `emmcprobe=1` (read-only GPT
read), no root device. Expected stop: waiting for the root device.

## 2026-11-12: XNU boot 1 (kernel run 43232759082)

BOOT p12 = xnu_boot loader + 0400 kernel + ADT (RAM 0xc8000000), cmdline
`debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress
emmcprobe=1`; readback hash matched. Phone photo: loader lines
(ENTRY 0xC942C488, BOOTARGS 0xCA4AB000, JUMP TO XNU), then XNU's green
entry block and its small entry text, and nothing after: no blue
"MMU on" block. **XNU executed on the M20**; it stopped at MMU enable.

Cause: `start.s` maps the framebuffer VA=PA with `create_bootstrap_mapping`
into a new L2 table, assuming (its comment) that the framebuffer's 1 GiB
L1 region differs from XNU RAM's. On the M20 both RAM (0xc8000000) and
the framebuffer (0xec000000) were in 0xc0000000-0xffffffff, so the new L2
replaced the kernel's V=P table. Fix: XNU RAM window moved to
0x94000000-0xb4000000 (L1 region 2; free above S-Boot's logs at
0x91200000-0x928a2000 and below TIMA 0xb8000000), log page 0x93fff000.

## 2026-11-12: XNU boot 2 reaches the root-device wait

Kernel run 43237529281 with RAM at 0x94000000 (BOOT readback matched).
Phone photo, in order:

- `A5XELTE CPU: cpu=0 entered initCPU mpidr=0x100 EL1 IRQs=1`, `came alive;
  SGI1 OK`, `1/1 CPUs initialized, SGI1 verified` (GIC-400 and timer work)
- `SWEET FB: AppleCLCD 1080x2340 stride 4320 at 0xec000000 ... presented
  as 1080x2340`, `A5XELTE FB: requested 30 Hz, effective 30 Hz`
- SWEET AMFI, SWEET Sandbox and `SWEET HFS: hfs-627.100.6` registered;
  Skywalk self-tests all PASSED; lo0/gif0/stf0 attached
- `A5XELTE eMMC: ... first=442368 sectors=6963200 read-only` (GPT read on
  the M20's MSHC; the SYSTEM entry, p20) — eMMC reads work
- `Waiting on <dict>...IOMedia...Content...Apple_HFS</dict>` then
  `Failed to write boot-picker-bringup-reason to NVRAM.`

This is the planned stop: no root device was given. Memory map, MMU,
GICv2, timer, framebuffer console and eMMC reads are working on the M20.

## 2026-11-12: Power and volume keys (kernel run 43251997175)

Patch 0400 enables `a5xelte_keys.c` on M20LTE, polling ALIVE 0x11cb0000
GPA1 DAT (+0x64), read only. Phone photo at the root-device wait, each key
pressed several times: idle `gpio=0xe0`; Volume Up `key=1 down=1 gpio=0xc0`
-> HID 0xe9; Volume Down `key=2 down=1 gpio=0xa0` -> HID 0xea; Power
`key=0 down=1 gpio=0x60` -> HID 0x30; every release `down=0`. Keys work.

## 2026-11-12: iOS root image (private repo, run 43252521896)

iOS 16.7.16 (20H392) iPhone X root, 20480 MiB HFSX, built on ubuntu-24.04
with tools/mkiosroot.sh and tools/sweet-root-tweaks.py after freeing
~30 GiB of runner toolkits (the first Linux run ran out of disk). The
fsck and launchd/SpringBoard/dyld cache checks passed; published as a
private release (6.2 GB gzip in 4 parts + d22ap.adt).

## 2026-11-12: iOS root on USERDATA, first iOS boot

`tools/m20lte-flash-root.py` wrote the 20480 MiB root to USERDATA p28 from
TWRP (/data unmounted): 188 data chunks of 64 MiB each read back and
hash-matched, 132 all-zero chunks cleared on the phone; image SHA-256
51cec53c8db42095272444c5f0ddd2c003668c9fd5bdf9d42d66b4b3ea6a2ba9. ztOS is
gone. BOOT: kernel run 43251997175 (keys), ADT with the D22AP /product,
cmdline `debug=0xc serial=3 keepsyms=1 -noprogress -enable_kprintf_spam
cpus=1 rd=emmcroot0 emmcroot=USERDATA emmcwrite=1 rootrw=1
cs_enforcement_disable=1 unentitled_ios_sim_launch=1 ignition_level=1
launchd_unsecure_cache=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin
a5fb_noconsole=1`; readback matched.

First iOS boot, phone photo: **iOS userland runs.** launchd spawns
services through xpcproxy (`exec cloudpaird`, `dasd`, `peakpowermanagerd`,
`seld`, `bluetoothuserd`, `mlsd`, `remindd`, `logd_helper`;
`EXIT xpcproxy[N] xstat 0`), so the eMMC root mounted, AMFI accepted the
binaries and dyld loaded the shared cache. The console is flooded with
`hfs: set hardlink bit on vol=iOSRoot cnid=... inoid=...`, at the end the
same cnid=321234 again and again: Linux-made hard links lack
kHFSHasLinkChainBit and XNU repairs them in memory on every lookup. 0041
limits this to 8 notes for SWEET only; 0401 extends that to M20LTE.

## 2026-11-12: iOS boot 4 with the persistent log (a5log=1)

BOOT: kernel run 43263294919 (0401), the same cmdline plus `a5log=1`. The
first 4 MiB + 512 bytes of SYSTEM p20 were saved to the PC first. TWRP read
of SYSTEM p20 (`dd ... count=8193`, tools/a5xelte-log.py): `A5XLOG1`,
flush #15, 31,596 bytes, 661 lines. **The log ring works on the M20.**

- `A5XELTE LOG: SYSTEM GPT first=442368, 8193 sectors reserved`,
  `BSD root: emmcroot0`, `hfs: mounted iOSRoot`, unsealed root, launchd
- launchd: Darwin Bootstrapper 7.0.0, ondemand mode, boot tasks fsck,
  mount-phase-1/2, data-protection, keybag, usermanagerd, dirs_cleaner;
  about 60 services exec'd through xpcproxy (all `xstat 0`)
- No backboardd or SpringBoard in ~160 s.
- `process logd_helper[92] thread 329 caught burning CPU! ... 56% over
  ~160 seconds`, lifetime 90.83 s system vs 0.10 s user: it spins in the
  kernel. The log stops ~10 s later (the flush thread no longer ran), as
  the first iOS boot stalled at the same point. With cpus=1 the spin
  starves everything.

Next: 0400 adds boot-arg `m20noexec=` (refuse exec by base name);
boot with `m20noexec=logd_helper`.

## 2026-11-12: iOS boot 5 with m20noexec=logd_helper

Kernel run 43270241404. Log flush #33 (~5.5 min, to the forced reset):
launchd's cache loader finishes, `Early boot complete. Continuing system
boot.`, then **`exec SpringBoard` and `exec backboardd`** with keybagd,
configd, mediaserverd, logd, lockdownd, IOMFB_FDR_Loader, notifyd,
runningboardd and ~60 more. logd_helper is refused about every 10 s; no
CPU-burning warning, and the log keeps flushing (no stall). But nothing
from backboardd or SpringBoard after exec (no exit, no crash line), and
the key presses at the end report `(0 clients)`: backboardd never opened
SweetHID. Next: 0400 builds bsd/dev/sweet_sample.c for M20LTE (started
with the eMMC root): user backtraces of SpringBoard/backboardd 90 s after
start and every 120 s, and with `sweettop=1` the busiest processes every 5 s.

## 2026-11-13: boot 6 sampler — backboardd and SpringBoard wait on logd

Kernel run 43276189360 (sweet_sample.c on M20LTE), `sweettop=1`. CPU table:
SpringBoard busy for ~2 min, then the whole system idle (`all 1-2%`);
backboardd never appears. Backtraces symbolicated in the private repo
(`symbolicate` workflow: SystemOS shared cache, `ipsw dyld a2s`):

- sample 0: backboardd in dyld `runAllInitializersForMain`; SpringBoard in
  objc `load_categories_nolock` (start-up, still moving)
- sample 1 (~2 min later), both main threads: `mach_msg2_trap` <-
  `firehose_send_register` <- `firehose_client_reconnect` <-
  `_os_trace_init_slow` <- `os_log_create` (backboardd from `BKLogCommon`,
  SpringBoard from `CFBundleLoadingLogger` <- `+[NSBundle mainBundle]`)

So logd never answers the firehose registration: every process blocks on
its first os_log. The donor (NOTES.md, image v7) found logd checks
/private/var/db/{diagnostics,uuidtext,diagnostics/timesync} for 272:272,
modes 0751/0755/0755 and a `.migrated` file, else asks logd_helper to
migrate. Here logd_helper spun in the kernel (boot 4) and, refused (boot 5),
leaves logd waiting. Next: inspect those directories in the image.

Image check (private `inspect-root` workflow): /private/var/db/diagnostics
272:272 0751, uuidtext 272:272 0755, diagnostics/timesync 272:272 0755,
each with `.migrated` — what logd requires, so not the cause. The dyld
cache files are hard links (link count 2) as mkiosroot.sh makes them.

New suspect: eMMC writes. Our driver writes one 512-byte sector per
polled CMD24 (A5 patch 0108); logd/logd_helper and the HFS journal write
constantly, and logd_helper's 90 s of system time fits busy-polled writes
on one CPU. 0400 now carries the A5 main-branch eMMC work (patches 0197
multiblock CMD23+CMD18/25 behind `a5emmc_blocks=32`, 0198 completion
events, 0208 bounded I/O limits, from orhunnx/ios-a5xelte), which also
prints eMMC request/byte/time metrics with each log flush.

## 2026-11-13: trying tlfares/iOS16-on-A40's prebuilt kernel (same SoC)

tlfares/iOS16-on-A40 boots iOS 16.7.16 to the lock and home screen on the
Galaxy A40 (Exynos 7904): XNU on the two Cortex-A73s with 16 KiB pages
(loader16 powers an A73 through the PMU), GIC-400, dw_mmc multiblock eMMC,
the same framebuffer/DECON trigger and GPA1 keys as the M20. User chose to
try its prebuilt `boot-ios16-a40.img` (SHA-1 30cfde05..., matches its
SHA1SUMS) adapted without rebuilding:

- payload mem_size and ADT /chosen dram-size 2 GiB -> 1 GiB (the M20 3 GB
  upper bank is 0x880000000-0x8bfffffff); ADT otherwise unchanged
- cmdline + `ufsroot=USERDATA` (M20 GPT name) `sweettouch=0` (its touch
  driver is for the A40's Zinitix and drives A40 pins)
- kernel slot (loader16 + payload) repacked with tools/m20lte-pack-boot.py
  around the M20 BOOT header and DTBH; BOOT readback matched
  (sha256 1b389f86...). USERDATA (our Linux-built iOS root) unchanged.
Its kernel log ring is at the end of the root partition (USERDATA).
