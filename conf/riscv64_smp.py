#!/usr/bin/env python3
"""RV64 SMP gem5 configuration.

Modes:
- Plain Python: dry-run plan generator (`--print-json`).
- gem5 runtime: instantiate and run a real RISC-V full-system simulation.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class CacheConfig:
    level: str
    kind: str
    size: str
    assoc: int


@dataclass
class CoreConfig:
    cpu_id: int
    isa: str
    cluster: str
    l1i: CacheConfig
    l1d: CacheConfig


@dataclass
class ClusterConfig:
    name: str
    mode: str
    cores: List[int]
    l2: CacheConfig
    uart: str


@dataclass
class WorkloadConfig:
    kernel: str
    initramfs: str
    dtb: str
    cmdline: str


@dataclass
class PlatformPlan:
    target: str
    isa: str
    topology: Dict[str, int]
    cores: List[CoreConfig]
    clusters: List[ClusterConfig]
    workload: WorkloadConfig


def default_cmdline() -> str:
    return "console=ttyS0 earlycon=sbi root=/dev/ram rw init=/sbin/init"


def build_plan(args: argparse.Namespace) -> PlatformPlan:
    l1i = CacheConfig(level="L1I", kind="private", size=args.l1i_size, assoc=args.l1_assoc)
    l1d = CacheConfig(level="L1D", kind="private", size=args.l1d_size, assoc=args.l1_assoc)
    l2 = CacheConfig(level="L2", kind="unified", size=args.l2_size, assoc=args.l2_assoc)

    cores = [
        CoreConfig(cpu_id=i, isa="rv64", cluster="cluster0", l1i=l1i, l1d=l1d)
        for i in range(4)
    ]

    cluster0 = ClusterConfig(
        name="cluster0",
        mode="SMP",
        cores=[0, 1, 2, 3],
        l2=l2,
        uart="uart_shared_cluster0",
    )

    workload = WorkloadConfig(
        kernel=args.kernel,
        initramfs=args.initramfs,
        dtb=args.dtb,
        cmdline=args.cmdline,
    )

    return PlatformPlan(
        target="riscv64_smp",
        isa="rv64",
        topology={"clusters": 1, "cores": 4},
        cores=cores,
        clusters=[cluster0],
        workload=workload,
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RV64 SMP gem5 plan/runtime config",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--kernel", default="build/linux/arch/riscv/boot/Image")
    p.add_argument("--kernel-elf", default="build/linux/vmlinux")
    p.add_argument("--bootloader", default="build/buildroot/images/fw_jump.elf")
    p.add_argument("--initramfs", default="build/buildroot/images/rootfs.cpio")
    p.add_argument("--dtb", default="build/linux/arch/riscv/boot/dts/gem5-riscv64-smp.dtb")
    p.add_argument("--disk-image", default="build/buildroot/images/rootfs.ext2")
    p.add_argument("--cmdline", default=default_cmdline())
    p.add_argument("--num-cpus", type=int, default=4)
    p.add_argument("--cpu-type", choices=["atomic", "timing"], default="atomic")
    p.add_argument("--mem-size", default="2GiB")
    p.add_argument("--kernel-addr", default="0x80200000")
    p.add_argument("--dtb-addr", default="0x87E00000")
    p.add_argument("--initrd-addr", default="0xA0000000")
    p.add_argument("--max-ticks", type=int, default=5_000_000_000_000)

    p.add_argument("--l1i-size", default="32kB")
    p.add_argument("--l1d-size", default="32kB")
    p.add_argument("--l1-assoc", type=int, default=4)
    p.add_argument("--l2-size", default="1MB")
    p.add_argument("--l2-assoc", type=int, default=8)

    p.add_argument(
        "--print-json",
        action="store_true",
        help="Print resolved plan JSON (dry-run friendly)",
    )
    return p


def _has_gem5_runtime() -> bool:
    try:
        import m5  # noqa: F401
    except Exception:
        return False
    return True


def _resolve_kernel_elf(args: argparse.Namespace) -> str:
    preferred = Path(args.kernel_elf)
    if preferred.exists():
        return str(preferred)

    kernel = Path(args.kernel)
    if kernel.exists() and kernel.name != "Image":
        return str(kernel)

    if kernel.name == "Image" and len(kernel.parents) >= 4:
        vmlinux = kernel.parents[3] / "vmlinux"
        if vmlinux.exists():
            print(f"[INFO] kernel fallback: using {vmlinux} instead of {kernel}")
            return str(vmlinux)

    return str(kernel)


def _generate_dtb(system, dtb_path: str, cmdline: str) -> None:
    from m5.util.fdthelper import (  # type: ignore
        Fdt,
        FdtNode,
        FdtPropertyStrings,
        FdtPropertyWords,
        FdtState,
    )

    state = FdtState(addr_cells=2, size_cells=2, cpu_cells=1)
    root = FdtNode("/")
    root.append(state.addrCellsProperty())
    root.append(state.sizeCellsProperty())
    root.appendCompatible(["riscv-virtio"])

    for mem_range in system.mem_ranges:
        node = FdtNode(f"memory@{int(mem_range.start):x}")
        node.append(FdtPropertyStrings("device_type", ["memory"]))
        node.append(
            FdtPropertyWords(
                "reg",
                state.addrCells(mem_range.start) + state.sizeCells(mem_range.size()),
            )
        )
        root.append(node)

    for section in [*system.cpu, system.platform]:
        for node in section.generateDeviceTree(state):
            if node.get_name() == root.get_name():
                root.merge(node)
            else:
                root.append(node)

    chosen = FdtNode("chosen")
    chosen.append(FdtPropertyStrings("bootargs", [cmdline]))
    chosen.append(FdtPropertyStrings("stdout-path", ["/soc/uart@10000000"]))
    root.append(chosen)

    fdt = Fdt()
    fdt.add_rootnode(root)
    out_dtb = Path(dtb_path)
    out_dtb.parent.mkdir(parents=True, exist_ok=True)
    out_dts = out_dtb.with_suffix(".dts")
    fdt.writeDtsFile(str(out_dts))
    fdt.writeDtbFile(str(out_dtb))


def _run_gem5_runtime(args: argparse.Namespace) -> int:
    import m5  # type: ignore
    from m5.objects import (  # type: ignore
        AddrRange,
        AtomicSimpleCPU,
        Bridge,
        CowDiskImage,
        DDR3_1600_8x8,
        Frequency,
        HiFive,
        IOXBar,
        MemBus,
        MemCtrl,
        PMAChecker,
        RawDiskImage,
        RiscvBootloaderKernelWorkload,
        RiscvLinux,
        RiscvMmioVirtIO,
        RiscvRTC,
        RiscvSystem,
        Root,
        SrcClockDomain,
        TimingSimpleCPU,
        VirtIOBlock,
        VoltageDomain,
    )

    if args.num_cpus < 1:
        raise ValueError("--num-cpus must be >= 1")

    kernel_elf = _resolve_kernel_elf(args)
    kernel_path = Path(kernel_elf)
    if not kernel_path.exists():
        raise FileNotFoundError(f"kernel ELF missing: {kernel_elf}")

    bootloader = Path(args.bootloader)
    initramfs = Path(args.initramfs)
    disk_image = Path(args.disk_image)
    dtb_path = Path(args.dtb)
    if not dtb_path.exists():
        dtb_path = Path(m5.options.outdir) / "device.dtb"

    cpu_cls = AtomicSimpleCPU if args.cpu_type == "atomic" else TimingSimpleCPU

    system = RiscvSystem()
    system.mem_mode = "atomic" if args.cpu_type == "atomic" else "timing"
    system.mem_ranges = [AddrRange(start=0x80000000, size=args.mem_size)]
    system.cache_line_size = 64

    system.voltage_domain = VoltageDomain(voltage="1.0V")
    system.clk_domain = SrcClockDomain(clock="1GHz", voltage_domain=system.voltage_domain)
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(clock="1GHz", voltage_domain=system.cpu_voltage_domain)

    system.iobus = IOXBar()
    system.membus = MemBus()
    system.system_port = system.membus.cpu_side_ports

    system.platform = HiFive()
    system.platform.rtc = RiscvRTC(frequency=Frequency("100MHz"))
    system.platform.clint.int_pin = system.platform.rtc.int_pin
    system.platform.setNumCores(args.num_cpus)

    system.iobus.cpu_side_ports = system.platform.pci_host.up_request_port()
    system.iobus.mem_side_ports = system.platform.pci_host.up_response_port()
    system.platform.pci_bus.cpu_side_ports = system.platform.pci_host.down_request_port()
    system.platform.pci_bus.default = system.platform.pci_host.down_response_port()
    system.platform.pci_bus.config_error_port = system.platform.pci_host.config_error.pio

    if disk_image.exists():
        image = CowDiskImage(child=RawDiskImage(read_only=True), read_only=False)
        image.child.image_file = str(disk_image)
        system.platform.disk = RiscvMmioVirtIO(
            vio=VirtIOBlock(image=image),
            interrupt_id=0x8,
            pio_size=4096,
            pio_addr=0x10008000,
        )
    else:
        print(f"[WARN] disk image missing: {disk_image} (continuing without virtio-block)")

    system.bridge = Bridge(delay="50ns")
    system.bridge.mem_side_port = system.iobus.cpu_side_ports
    system.bridge.cpu_side_port = system.membus.mem_side_ports
    system.bridge.ranges = system.platform._off_chip_ranges()

    system.iobridge = Bridge(delay="50ns", ranges=system.mem_ranges)
    system.iobridge.cpu_side_port = system.iobus.mem_side_ports
    system.iobridge.mem_side_port = system.membus.cpu_side_ports

    system.platform.attachOnChipIO(system.membus)
    system.platform.attachOffChipIO(system.iobus)
    system.platform.attachPlic()

    system.cpu = [cpu_cls(clk_domain=system.cpu_clk_domain, cpu_id=i) for i in range(args.num_cpus)]
    uncacheable = [*system.platform._on_chip_ranges(), *system.platform._off_chip_ranges()]
    for cpu in system.cpu:
        cpu.createThreads()
        cpu.createInterruptController()
        cpu.icache_port = system.membus.cpu_side_ports
        cpu.dcache_port = system.membus.cpu_side_ports
        cpu.mmu.connectWalkerPorts(system.membus.cpu_side_ports, system.membus.cpu_side_ports)
        cpu.mmu.pma_checker = PMAChecker(uncacheable=uncacheable)

    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    has_bootloader = bootloader.exists()
    has_initramfs = initramfs.exists()
    if has_bootloader or has_initramfs:
        workload = RiscvBootloaderKernelWorkload()
        workload.object_file = str(kernel_path)
        workload.kernel_addr = int(args.kernel_addr, 0)
        workload.entry_point = workload.kernel_addr
        workload.command_line = args.cmdline
        workload.dtb_addr = int(args.dtb_addr, 0)
        if has_bootloader:
            workload.bootloader_filename = str(bootloader)
        else:
            print("[WARN] bootloader missing; booting kernel directly at kernel_addr")
        if has_initramfs:
            workload.initrd_filename = str(initramfs)
            workload.initrd_addr = int(args.initrd_addr, 0)
        else:
            print(f"[WARN] initramfs missing: {initramfs}")
        system.workload = workload
    else:
        workload = RiscvLinux()
        workload.object_file = str(kernel_path)
        workload.command_line = args.cmdline
        workload.dtb_addr = int(args.dtb_addr, 0)
        system.workload = workload

    if dtb_path.exists():
        system.workload.dtb_filename = str(dtb_path)
    else:
        _generate_dtb(system, str(dtb_path), args.cmdline)
        system.workload.dtb_filename = str(dtb_path)

    root = Root(full_system=True, system=system)

    print(
        "[INFO] runtime launch:",
        f"cpus={args.num_cpus}",
        f"cpu_type={args.cpu_type}",
        f"kernel={kernel_path}",
        f"bootloader={'yes' if has_bootloader else 'no'}",
        f"initramfs={'yes' if has_initramfs else 'no'}",
        f"disk={'yes' if disk_image.exists() else 'no'}",
        f"dtb={system.workload.dtb_filename}",
        f"max_ticks={args.max_ticks}",
    )

    m5.instantiate()
    exit_event = m5.simulate(args.max_ticks)
    cause = exit_event.getCause()
    tick = m5.curTick()
    print(f"[INFO] gem5 exit cause: {cause}")
    print(f"[INFO] gem5 exit tick: {tick}")

    lc = cause.lower()
    if "panic" in lc or "oops" in lc:
        return 2
    if "simulate() limit reached" in lc or "max tick" in lc:
        return 124
    return 0


def main() -> int:
    args = parser().parse_args()
    plan = build_plan(args)

    if args.print_json or not _has_gem5_runtime():
        print(json.dumps(asdict(plan), indent=2))
        return 0

    return _run_gem5_runtime(args)


if __name__ == "__main__":
    raise SystemExit(main())
