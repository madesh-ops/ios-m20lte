# ios-m20lte

**Apple's iOS 16 on the Samsung Galaxy M20 (`m20lte`, SM-M205F, Exynos 7904).**

This is a port of Apple's open-source XNU kernel (xnu-8796, the iOS 16 generation) to the Galaxy M20. On top of it runs the **unmodified iOS 16.7.16 userland of the iPhone X**: launchd, the system daemons, backboardd and SpringBoard.

As of **2026-11-13** the phone boots to the **iOS lock screen**, and the touchscreen works: you can unlock it with the swipe-up gesture. Rendering runs entirely on the CPU; there is no GPU driver.

> Experimental bring-up, not a usable phone OS. Apple's security model is mostly switched off. The iOS root goes into the `USERDATA` partition and so **erases Android's (or any other OS's) user data**.

## What works

| Area | State |
| --- | --- |
| Boot | Samsung S-Boot loads our BOOT image (p12): a loader, then XNU. RECOVERY (TWRP) is never touched |
| CPU | XNU runs on the two Cortex-A73 cores with 16 KiB pages. 0085 raises them from 1352 to 1768 MHz once at boot (ACPM BUCK2 + PLL; boot-arg `m20a73mhz`) |
| Memory | 1 GiB at `0x880000000`. 0086 (extra RAM banks) is built but not yet tested on the phone |
| Storage | iOS root is an HFS+ volume in USERDATA (p28), read/write |
| Display | S-Boot's framebuffer at `0xec000000`, 1080x2340; CoreAnimation renders in software |
| Touch | Himax HX83112A on USI0 HS-I2C (`0x13930000`), polled (0084, `bsd/dev/m20_touch.c`) |
| GUI | backboardd, SpringBoard, lock screen; unlock works |

## What does not work (yet)

- **The six Cortex-A53 cores are idle.** They have no 16 KiB page support, and this kernel uses 16 KiB pages.
- No GPU, Wi-Fi, Bluetooth, cellular, audio, camera or sensors.
- No thermal throttling of the faster A73 clock.
- Security is off: permissive code signing, stub keystore, no data protection. Don't put anything personal on it.

## Branches

| Branch | What it is |
| --- | --- |
| `a40m20` | **The working line.** ios-sweet's patches plus the A40 port's kernel (XNU on the A73s, 16 KiB pages) and the M20 patches 0084-0086. Log: [`A40M20.md`](https://github.com/madesh-ops/ios-m20lte/blob/a40m20/A40M20.md) |
| `m20lte` | The first attempt: a 4 KiB-page kernel that could use all cores. It reached launchd but stalled before the GUI. Its loader (`shim/m20lte/`), BOOT packer and board notes are still used. Log: [`M20LTE_PROGRESS.md`](https://github.com/madesh-ops/ios-m20lte/blob/m20lte/M20LTE_PROGRESS.md) |

## How it boots

```
S-Boot (stock Samsung bootloader)
  -> BOOT p12: Android header + DTBH kept from the stock image
     -> loader16 (A40 port): MMU with 16 KiB pages on an A73
        -> XNU Mach-O + Apple Device Tree (ADT) + boot-args
           -> XNU -> eMMC -> HFS+ root in USERDATA
              -> dyld + shared cache -> launchd -> daemons -> backboardd + SpringBoard
```

If it fails, the PMU INFORM3 register (`0x11c8080c` = `0x12345674`) makes the next reset land in TWRP.

## How to do it yourself

You need a Galaxy M20 with an unlocked bootloader and TWRP in RECOVERY, a Linux PC (or GitHub Actions), and an iPhone X iOS 16.7.16 IPSW. **Everything in USERDATA is lost.**

1. **Back up** BOOT, EFS and the other small partitions from TWRP and keep them off git. Never write EFS or RECOVERY.
2. **Build the kernel**: run `.github/workflows/xnu.yml` on branch `a40m20`.
3. **Build the iOS root** with `tools/mkiosroot.sh` and `tools/sweet-root-tweaks.py`. Do this in a **private** repository or on your own machine: the image contains Apple's software and must not be published.
4. **Build BOOT** with `tools/m20-a40-boot.py` (kernel, M20 ADT, the A40 port's `loader16`, your stock BOOT). Optional: `tools/m20-adt-ram-banks.py` for more RAM.
5. **Flash from TWRP**: the root image to `/dev/block/by-name/USERDATA`, BOOT to `/dev/block/by-name/BOOT`. Read both back and compare hashes before rebooting.
6. **Read the kernel log** from TWRP: the last 4 MiB of USERDATA hold a log ring. Decode it with `tools/sweet-log.py`.

## Key hardware facts

| Item | Value |
| --- | --- |
| CPUs | 2x Cortex-A73 (MPIDR 0x0, 0x1; 16 KiB pages) + 6x Cortex-A53 (0x100-0x103, 0x200-0x201; 4 KiB only) |
| GIC | GIC-400 (GICv2): distributor `0x12301000`, CPU interface `0x12302000` |
| Timer | 26 MHz; virtual timer INTID 27 |
| RAM (3 GB) | `0x80000000-0xbd9fffff`, `0xc0000000-0xffffffff`, `0x880000000-0x8bfffffff` |
| Display | DECON_F `0x14860000`; refresh needs HW_SW_TRIG_CONTROL (+0x70) = `0x1281` |
| eMMC | DesignWare MSHC at `0x13500000` |
| PMU | `0x11c80000`: INFORM3 +0x80c, SWRESET +0x400 |
| Partitions | BOOT p12 (32 MiB), RECOVERY p13 (TWRP), EFS p3, SYSTEM p20, USERDATA p28 |

## Credits

Built on [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) (the XNU port and iOS userland bring-up), [tlfares/iOS16-on-A40](https://github.com/tlfares/iOS16-on-A40) (XNU on the Exynos 7904's A73s with 16 KiB pages, and loader16), the [orhunnx](https://github.com/orhunnx/ios-a5xelte) / [wardevsa](https://github.com/wardevsa/ios-a5xelte) Exynos ports (4 KiB kernel base, RAM banks), [ztOS](https://github.com/madesh-ops/ztOS) (M20 hardware notes and clock tables), Apple's open-source releases (xnu, IOHIDFamily, libpthread, hfs) and [BearSSL](https://bearssl.org). iOS itself is Apple's and is not distributed here.
