#!/usr/bin/env python3
"""Hybrid one-gem5 configuration: RV32 mixed + RV64 Linux SMP.

Goal:
- Use one gem5 process
- Run RV32 mixed Zephyr topology and RV64 Linux topology together
"""

import argparse
import json
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Hybrid RV32 mixed + RV64 Linux on one gem5 process",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # RV32 mixed inputs.
    p.add_argument("--boot-elf", default="build/boot/riscv32_mixed_boot.elf")
    p.add_argument("--amp-cpu0-elf", default="build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf")
    p.add_argument("--amp-cpu1-elf", default="build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf")
    p.add_argument("--smp-elf", default="build/zephyr/cluster1_smp/zephyr/zephyr.elf")
    p.add_argument("--rv32-cpu-type", choices=["timing", "atomic"], default="timing")
    p.add_argument("--rv32-uart0-port", type=int, default=3456)
    p.add_argument("--rv32-uart1-port", type=int, default=3457)
    p.add_argument("--rv32-uart2-port", type=int, default=3458)

    p.add_argument("--boot-base", default="0x80000000")
    p.add_argument("--boot-size", default="0x01000000")
    p.add_argument("--amp-cpu0-base", default="0x81000000")
    p.add_argument("--amp-cpu0-size", default="0x02000000")
    p.add_argument("--amp-cpu1-base", default="0x84000000")
    p.add_argument("--amp-cpu1-size", default="0x02000000")
    p.add_argument("--cluster1-smp-base", default="0x88000000")
    p.add_argument("--cluster1-smp-size", default="0x08000000")
    p.add_argument("--shared-base", default="0x90000000")
    p.add_argument("--shared-size", default="0x10000000")

    p.add_argument("--rv32-l1i-size", default="16kB")
    p.add_argument("--rv32-l1d-size", default="16kB")
    p.add_argument("--rv32-l1-assoc", type=int, default=2)
    p.add_argument("--rv32-l2-cluster0-size", default="256kB")
    p.add_argument("--rv32-l2-cluster1-size", default="512kB")
    p.add_argument("--rv32-l2-assoc", type=int, default=8)

    # RV64 Linux inputs.
    p.add_argument("--kernel", default="build/linux/vmlinux")
    p.add_argument("--kernel-elf", default="build/linux/vmlinux")
    p.add_argument("--bootloader", default="sources/buildroot/output/images/fw_jump.elf")
    p.add_argument("--bootloader-addr", default="0x80000000")
    p.add_argument("--initramfs", default="build/initramfs/rootfs-shell.cpio")
    p.add_argument("--disk-image", default="")
    p.add_argument(
        "--cmdline",
        default=(
            "console=ttyS0,115200 earlycon=sbi root=/dev/ram0 rw "
            "rdinit=/init loglevel=8 ignore_loglevel"
        ),
    )
    p.add_argument("--rv64-num-cpus", type=int, default=4)
    p.add_argument("--rv64-cpu-type", choices=["timing", "atomic"], default="atomic")
    p.add_argument("--rv64-uart-port", type=int, default=3460)
    p.add_argument("--rv64-mem-size", default="2GiB")
    p.add_argument("--kernel-addr", default="0x80200000")
    p.add_argument("--dtb-addr", default="0x87E00000")
    p.add_argument("--initrd-addr", default="0xA0000000")
    p.add_argument("--rv64-l1i-size", default="32kB")
    p.add_argument("--rv64-l1d-size", default="32kB")
    p.add_argument("--rv64-l1-assoc", type=int, default=4)
    p.add_argument("--rv64-l2-size", default="1MB")
    p.add_argument("--rv64-l2-assoc", type=int, default=8)

    # Shared runtime.
    p.add_argument("--sys-clock", default="1GHz")
    p.add_argument("--rv32-cpu-clock", default="1GHz")
    p.add_argument("--rv64-cpu-clock", default="3GHz")
    p.add_argument("--max-ticks", type=int, default=2_000_000_000)
    p.add_argument("--print-json", action="store_true")
    return p


def _to_int(value: str) -> int:
    return int(value, 0)


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
    if kernel.exists():
        return str(kernel)
    return str(preferred)


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


def _build_rv32_system(args: argparse.Namespace):
    from m5.objects import (  # type: ignore
        AddrRange,
        AtomicSimpleCPU,
        Bridge,
        Frequency,
        HiFive,
        IOXBar,
        L2XBar,
        PMAChecker,
        RiscvBareMetal,
        RiscvRTC,
        RiscvSystem,
        SimpleMemory,
        SrcClockDomain,
        SystemXBar,
        Terminal,
        TimingSimpleCPU,
        Uart8250,
        VoltageDomain,
    )
    from m5.util import addToPath  # type: ignore

    repo_root = Path(__file__).resolve().parents[1]
    addToPath(str(repo_root / "sources" / "gem5" / "configs"))
    from common.Caches import L1_DCache, L1_ICache, L2Cache  # type: ignore

    cpu_cls = TimingSimpleCPU if args.rv32_cpu_type == "timing" else AtomicSimpleCPU

    segments = [
        ("boot", _to_int(args.boot_base), _to_int(args.boot_size), ""),
        ("amp_cpu0", _to_int(args.amp_cpu0_base), _to_int(args.amp_cpu0_size), args.amp_cpu0_elf),
        ("amp_cpu1", _to_int(args.amp_cpu1_base), _to_int(args.amp_cpu1_size), args.amp_cpu1_elf),
        (
            "cluster1_smp",
            _to_int(args.cluster1_smp_base),
            _to_int(args.cluster1_smp_size),
            args.smp_elf,
        ),
        ("shared", _to_int(args.shared_base), _to_int(args.shared_size), ""),
    ]

    memories = []
    for _, base, size, image in segments:
        mem = SimpleMemory(range=AddrRange(start=base, size=size), latency="50ns")
        if image:
            mem.image_file = image
        memories.append(mem)

    system = RiscvSystem(memories=memories)
    system.mem_mode = "timing" if args.rv32_cpu_type == "timing" else "atomic"
    system.mem_ranges = [AddrRange(start=base, size=size) for _, base, size, _ in segments]
    system.cache_line_size = 64

    system.voltage_domain = VoltageDomain(voltage="1.0V")
    system.clk_domain = SrcClockDomain(clock=args.sys_clock, voltage_domain=system.voltage_domain)
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(clock=args.rv32_cpu_clock, voltage_domain=system.cpu_voltage_domain)

    system.iobus = IOXBar()
    system.membus = SystemXBar()
    system.system_port = system.membus.cpu_side_ports

    system.platform = HiFive()
    system.platform.rtc = RiscvRTC(frequency=Frequency("100MHz"))
    system.platform.clint.int_pin = system.platform.rtc.int_pin
    system.platform.setNumCores(6)
    system.platform.terminal.port = args.rv32_uart0_port
    system.platform.terminal1 = Terminal(port=args.rv32_uart1_port, number=1)
    system.platform.terminal2 = Terminal(port=args.rv32_uart2_port, number=2)
    system.platform.uart.device = system.platform.terminal
    system.platform.uart1 = Uart8250(
        pio_addr=0x10001000,
        platform=system.platform,
        device=system.platform.terminal1,
    )
    system.platform.uart2 = Uart8250(
        pio_addr=0x10002000,
        platform=system.platform,
        device=system.platform.terminal2,
    )
    extra_uart_ranges = [
        AddrRange(system.platform.uart1.pio_addr, size=system.platform.uart1.pio_size),
        AddrRange(system.platform.uart2.pio_addr, size=system.platform.uart2.pio_size),
    ]

    system.iobus.cpu_side_ports = system.platform.pci_host.up_request_port()
    system.iobus.mem_side_ports = system.platform.pci_host.up_response_port()
    system.platform.pci_bus.cpu_side_ports = system.platform.pci_host.down_request_port()
    system.platform.pci_bus.default = system.platform.pci_host.down_response_port()
    system.platform.pci_bus.config_error_port = system.platform.pci_host.config_error.pio

    system.bridge = Bridge(delay="50ns")
    system.bridge.mem_side_port = system.iobus.cpu_side_ports
    system.bridge.cpu_side_port = system.membus.mem_side_ports
    system.bridge.ranges = [*system.platform._off_chip_ranges(), *extra_uart_ranges]

    system.iobridge = Bridge(delay="50ns", ranges=system.mem_ranges)
    system.iobridge.cpu_side_port = system.iobus.mem_side_ports
    system.iobridge.mem_side_port = system.membus.cpu_side_ports

    system.platform.attachOnChipIO(system.membus)
    system.platform.attachOffChipIO(system.iobus)
    system.platform.uart1.pio = system.iobus.mem_side_ports
    system.platform.uart2.pio = system.iobus.mem_side_ports
    system.platform.attachPlic()

    system.cluster0_bus = L2XBar()
    system.cluster1_bus = L2XBar()
    system.cluster0_l2 = L2Cache(size=args.rv32_l2_cluster0_size, assoc=args.rv32_l2_assoc)
    system.cluster1_l2 = L2Cache(size=args.rv32_l2_cluster1_size, assoc=args.rv32_l2_assoc)
    system.cluster0_l2.cpu_side = system.cluster0_bus.mem_side_ports
    system.cluster0_l2.mem_side = system.membus.cpu_side_ports
    system.cluster1_l2.cpu_side = system.cluster1_bus.mem_side_ports
    system.cluster1_l2.mem_side = system.membus.cpu_side_ports

    system.cpu = [cpu_cls(clk_domain=system.cpu_clk_domain, cpu_id=i) for i in range(6)]
    uncacheable = [*system.platform._on_chip_ranges(), *system.platform._off_chip_ranges(), *extra_uart_ranges]
    for i, cpu in enumerate(system.cpu):
        cpu.createThreads()
        cpu.createInterruptController()
        if getattr(cpu, "isa", None):
            cpu.isa[0].riscv_type = "RV32"
        else:
            cpu.ArchISA.riscv_type = "RV32"
        l1i = L1_ICache(size=args.rv32_l1i_size, assoc=args.rv32_l1_assoc)
        l1d = L1_DCache(size=args.rv32_l1d_size, assoc=args.rv32_l1_assoc)
        setattr(cpu, "l1i", l1i)
        setattr(cpu, "l1d", l1d)
        l1i.cpu_side = cpu.icache_port
        l1d.cpu_side = cpu.dcache_port
        cluster_bus = system.cluster0_bus if i < 2 else system.cluster1_bus
        l1i.mem_side = cluster_bus.cpu_side_ports
        l1d.mem_side = cluster_bus.cpu_side_ports
        cpu.mmu.connectWalkerPorts(cluster_bus.cpu_side_ports, cluster_bus.cpu_side_ports)
        cpu.mmu.pma_checker = PMAChecker(uncacheable=uncacheable)

    for mem in system.memories:
        mem.port = system.membus.mem_side_ports

    system.workload = RiscvBareMetal(
        bootloader=args.boot_elf,
        bare_metal=True,
        auto_reset_vect=True,
    )
    return system


def _build_rv64_system(args):
    from m5.objects import (  # type: ignore
        AddrRange,
        AtomicSimpleCPU,
        Bridge,
        CowDiskImage,
        DDR3_1600_8x8,
        Frequency,
        HiFive,
        IOXBar,
        MemCtrl,
        PMAChecker,
        RawDiskImage,
        RiscvBootloaderKernelWorkload,
        RiscvLinux,
        RiscvMmioVirtIO,
        RiscvRTC,
        RiscvSystem,
        SrcClockDomain,
        SystemXBar,
        TimingSimpleCPU,
        VoltageDomain,
        VirtIOBlock,
    )

    kernel_elf = _resolve_kernel_elf(args)
    kernel_path = Path(kernel_elf)
    if not kernel_path.exists():
        raise FileNotFoundError(f"kernel ELF missing: {kernel_elf}")

    cpu_cls = AtomicSimpleCPU if args.rv64_cpu_type == "atomic" else TimingSimpleCPU

    system = RiscvSystem()
    system.mem_mode = "atomic" if args.rv64_cpu_type == "atomic" else "timing"
    system.mem_ranges = [AddrRange(start=0x80000000, size=args.rv64_mem_size)]
    system.cache_line_size = 64

    system.voltage_domain = VoltageDomain(voltage="1.0V")
    system.clk_domain = SrcClockDomain(clock=args.sys_clock, voltage_domain=system.voltage_domain)
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(clock=args.rv64_cpu_clock, voltage_domain=system.cpu_voltage_domain)

    system.iobus = IOXBar()
    system.membus = SystemXBar()
    system.system_port = system.membus.cpu_side_ports

    system.platform = HiFive()
    system.platform.rtc = RiscvRTC(frequency=Frequency("100MHz"))
    system.platform.clint.int_pin = system.platform.rtc.int_pin
    system.platform.setNumCores(args.rv64_num_cpus)
    system.platform.terminal.port = args.rv64_uart_port

    system.iobus.cpu_side_ports = system.platform.pci_host.up_request_port()
    system.iobus.mem_side_ports = system.platform.pci_host.up_response_port()
    system.platform.pci_bus.cpu_side_ports = system.platform.pci_host.down_request_port()
    system.platform.pci_bus.default = system.platform.pci_host.down_response_port()
    system.platform.pci_bus.config_error_port = system.platform.pci_host.config_error.pio

    disk_image = Path(args.disk_image) if args.disk_image else Path("")
    use_disk = bool(
        args.disk_image
        and disk_image.exists()
        and "root=/dev/ram" not in args.cmdline
    )
    if use_disk:
        image = CowDiskImage(child=RawDiskImage(read_only=True), read_only=False)
        image.child.image_file = str(disk_image)
        system.platform.disk = RiscvMmioVirtIO(
            vio=VirtIOBlock(image=image),
            interrupt_id=0x8,
            pio_size=4096,
            pio_addr=0x10008000,
        )

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

    system.cpu = [cpu_cls(clk_domain=system.cpu_clk_domain, cpu_id=i) for i in range(args.rv64_num_cpus)]
    uncacheable = [*system.platform._on_chip_ranges(), *system.platform._off_chip_ranges()]
    for cpu in system.cpu:
        cpu.createThreads()
        cpu.createInterruptController()
        if getattr(cpu, "isa", None):
            cpu.isa[0].riscv_type = "RV64"
        cpu.icache_port = system.membus.cpu_side_ports
        cpu.dcache_port = system.membus.cpu_side_ports
        cpu.mmu.connectWalkerPorts(system.membus.cpu_side_ports, system.membus.cpu_side_ports)
        cpu.mmu.pma_checker = PMAChecker(uncacheable=uncacheable)

    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    bootloader = Path(args.bootloader)
    initramfs = Path(args.initramfs)
    has_bootloader = bootloader.exists()
    has_initramfs = initramfs.exists()
    if has_bootloader or has_initramfs:
        workload = RiscvBootloaderKernelWorkload()
        workload.object_file = str(kernel_path)
        workload.kernel_addr = int(args.kernel_addr, 0)
        if has_bootloader:
            workload.bootloader_addr = int(args.bootloader_addr, 0)
            workload.entry_point = workload.bootloader_addr
            workload.bootloader_filename = str(bootloader)
        else:
            workload.entry_point = workload.kernel_addr
        workload.command_line = args.cmdline
        workload.dtb_addr = int(args.dtb_addr, 0)
        if has_initramfs:
            workload.initrd_filename = str(initramfs)
            workload.initrd_addr = int(args.initrd_addr, 0)
        system.workload = workload
    else:
        workload = RiscvLinux()
        workload.object_file = str(kernel_path)
        workload.command_line = args.cmdline
        workload.dtb_addr = int(args.dtb_addr, 0)
        system.workload = workload

    return system


def _build_plan(args: argparse.Namespace) -> dict:
    return {
        "target": "riscv_hybrid",
        "description": "one gem5 process for rv32_mixed + rv64_linux",
        "rv32": {
            "topology": {"clusters": 2, "cores": 6},
            "cpu_type": args.rv32_cpu_type,
            "uart": {"cpu0": "UART0", "cpu1": "UART1", "cpu2-5": "UART2"},
        },
        "rv64": {
            "topology": {"clusters": 1, "cores": args.rv64_num_cpus},
            "cpu_type": args.rv64_cpu_type,
            "workload": {
                "kernel": args.kernel,
                "bootloader": args.bootloader,
                "initramfs": args.initramfs,
            },
        },
    }


def _run_gem5_runtime(args: argparse.Namespace) -> int:
    import m5  # type: ignore
    from m5.objects import Root  # type: ignore

    required = [args.boot_elf, args.amp_cpu0_elf, args.amp_cpu1_elf, args.smp_elf]
    for path in required:
        if not Path(path).exists():
            raise FileNotFoundError(f"missing file: {path}")

    system32 = _build_rv32_system(args)
    system64 = _build_rv64_system(args)

    dtb_path = Path(m5.options.outdir) / "system64.device.dtb"
    if not dtb_path.exists():
        _generate_dtb(system64, str(dtb_path), args.cmdline)
    system64.workload.dtb_filename = str(dtb_path)

    root = Root(full_system=True)
    root.system32 = system32
    root.system64 = system64

    print(
        "[INFO] hybrid launch:",
        "systems=2",
        "rv32_cores=6",
        f"rv64_cores={args.rv64_num_cpus}",
        f"max_ticks={args.max_ticks}",
    )
    print(
        "[INFO] uart map:",
        "system32: UART0(cpu0), UART1(cpu1), UART2(cpu2-5)",
        "system64: UART(shared)",
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
        return 0
    return 0


def main() -> int:
    args = parser().parse_args()
    plan = _build_plan(args)

    if args.print_json or not _has_gem5_runtime():
        print(json.dumps(plan, indent=2))
        return 0

    return _run_gem5_runtime(args)


if __name__ in {"__main__", "__m5_main__"}:
    raise SystemExit(main())
