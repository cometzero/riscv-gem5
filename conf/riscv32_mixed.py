#!/usr/bin/env python3
"""RV32 mixed AMP/SMP gem5 configuration.

Goal:
- one gem5 process
- six RV32 harts
  - Hart0 -> Zephyr AMP CPU0 image
  - Hart1 -> Zephyr AMP CPU1 image
  - Hart2-5 -> Zephyr SMP image
- per-core private L1I/L1D
- per-cluster shared L2 (cluster0: hart0/1, cluster1: hart2-5)

This script supports:
- plain Python mode (`--print-json`) for dry-run planning
- gem5 runtime mode when executed by gem5 binary
"""

import argparse
import json
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
    mode: str
    entry: str
    l1i: CacheConfig
    l1d: CacheConfig
    uart: str


@dataclass
class ClusterConfig:
    name: str
    mode: str
    cores: List[int]
    l2: CacheConfig
    uart: str


@dataclass
class MemorySegment:
    name: str
    base: str
    size: str
    image: str


@dataclass
class WorkloadConfig:
    boot_elf: str
    amp_cpu0_elf: str
    amp_cpu1_elf: str
    smp_elf: str


@dataclass
class PlatformPlan:
    target: str
    isa: str
    topology: Dict[str, int]
    cores: List[CoreConfig]
    clusters: List[ClusterConfig]
    memory_segments: List[MemorySegment]
    workload: WorkloadConfig


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RV32 mixed AMP/SMP single-gem5 configuration",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--boot-elf", default="build/boot/riscv32_mixed_boot.elf")
    p.add_argument("--amp-cpu0-elf", default="build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf")
    p.add_argument("--amp-cpu1-elf", default="build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf")
    p.add_argument("--smp-elf", default="build/zephyr/cluster1_smp/zephyr/zephyr.elf")

    p.add_argument("--num-cpus", type=int, default=6)
    p.add_argument("--cpu-type", choices=["timing", "atomic"], default="timing")
    p.add_argument("--max-ticks", type=int, default=2_000_000_000)

    p.add_argument("--l1i-size", default="16kB")
    p.add_argument("--l1d-size", default="16kB")
    p.add_argument("--l1-assoc", type=int, default=2)
    p.add_argument("--l2-cluster0-size", default="256kB")
    p.add_argument("--l2-cluster1-size", default="512kB")
    p.add_argument("--l2-assoc", type=int, default=8)

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

    p.add_argument("--print-json", action="store_true")
    return p


def _to_int(value: str) -> int:
    return int(value, 0)


def build_plan(args: argparse.Namespace) -> PlatformPlan:
    l1i = CacheConfig(level="L1I", kind="private", size=args.l1i_size, assoc=args.l1_assoc)
    l1d = CacheConfig(level="L1D", kind="private", size=args.l1d_size, assoc=args.l1_assoc)
    l2_cluster0 = CacheConfig(level="L2", kind="unified", size=args.l2_cluster0_size, assoc=args.l2_assoc)
    l2_cluster1 = CacheConfig(level="L2", kind="unified", size=args.l2_cluster1_size, assoc=args.l2_assoc)

    cores: List[CoreConfig] = [
        CoreConfig(
            cpu_id=0,
            isa="rv32",
            cluster="cluster0",
            mode="AMP",
            entry=args.amp_cpu0_base,
            l1i=l1i,
            l1d=l1d,
            uart="UART0",
        ),
        CoreConfig(
            cpu_id=1,
            isa="rv32",
            cluster="cluster0",
            mode="AMP",
            entry=args.amp_cpu1_base,
            l1i=l1i,
            l1d=l1d,
            uart="UART1",
        ),
    ]
    for cpu_id in [2, 3, 4, 5]:
        cores.append(
            CoreConfig(
                cpu_id=cpu_id,
                isa="rv32",
                cluster="cluster1",
                mode="SMP",
                entry=args.cluster1_smp_base,
                l1i=l1i,
                l1d=l1d,
                uart="UART2",
            )
        )

    clusters = [
        ClusterConfig(
            name="cluster0",
            mode="AMP",
            cores=[0, 1],
            l2=l2_cluster0,
            uart="UART0/CPU0 + UART1/CPU1",
        ),
        ClusterConfig(
            name="cluster1",
            mode="SMP",
            cores=[2, 3, 4, 5],
            l2=l2_cluster1,
            uart="UART2 shared by CPU2-5",
        ),
    ]

    memory_segments = [
        MemorySegment(name="boot", base=args.boot_base, size=args.boot_size, image=""),
        MemorySegment(name="amp_cpu0", base=args.amp_cpu0_base, size=args.amp_cpu0_size, image=args.amp_cpu0_elf),
        MemorySegment(name="amp_cpu1", base=args.amp_cpu1_base, size=args.amp_cpu1_size, image=args.amp_cpu1_elf),
        MemorySegment(
            name="cluster1_smp",
            base=args.cluster1_smp_base,
            size=args.cluster1_smp_size,
            image=args.smp_elf,
        ),
        MemorySegment(name="shared", base=args.shared_base, size=args.shared_size, image=""),
    ]

    workload = WorkloadConfig(
        boot_elf=args.boot_elf,
        amp_cpu0_elf=args.amp_cpu0_elf,
        amp_cpu1_elf=args.amp_cpu1_elf,
        smp_elf=args.smp_elf,
    )

    return PlatformPlan(
        target="riscv32_mixed",
        isa="rv32",
        topology={"clusters": 2, "cores": 6},
        cores=cores,
        clusters=clusters,
        memory_segments=memory_segments,
        workload=workload,
    )


def _has_gem5_runtime() -> bool:
    try:
        import m5  # noqa: F401
    except Exception:
        return False
    return True


def _run_gem5_runtime(args: argparse.Namespace) -> int:
    import m5  # type: ignore
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
        SystemXBar,
        Terminal,
        Root,
        SimpleMemory,
        SrcClockDomain,
        TimingSimpleCPU,
        Uart8250,
        VoltageDomain,
    )
    from m5.util import addToPath  # type: ignore

    repo_root = Path(__file__).resolve().parents[1]
    addToPath(str(repo_root / "sources" / "gem5" / "configs"))
    from common.Caches import L1_DCache, L1_ICache, L2Cache  # type: ignore

    if args.num_cpus != 6:
        raise ValueError("--num-cpus must be 6 for riscv32_mixed")

    required = [args.boot_elf, args.amp_cpu0_elf, args.amp_cpu1_elf, args.smp_elf]
    for f in required:
        if not Path(f).exists():
            raise FileNotFoundError(f"missing file: {f}")

    cpu_cls = TimingSimpleCPU if args.cpu_type == "timing" else AtomicSimpleCPU

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
    for name, base, size, image in segments:
        mem = SimpleMemory(range=AddrRange(start=base, size=size), latency="50ns")
        if image:
            mem.image_file = image
        memories.append(mem)
        print(
            "[INFO] memory",
            f"name={name}",
            f"base=0x{base:08x}",
            f"size=0x{size:08x}",
            f"image={image or '-'}",
        )

    system = RiscvSystem(memories=memories)
    system.mem_mode = "timing" if args.cpu_type == "timing" else "atomic"
    system.mem_ranges = [AddrRange(start=base, size=size) for _, base, size, _ in segments]
    system.cache_line_size = 64

    system.voltage_domain = VoltageDomain(voltage="1.0V")
    system.clk_domain = SrcClockDomain(clock="1GHz", voltage_domain=system.voltage_domain)
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(clock="1GHz", voltage_domain=system.cpu_voltage_domain)

    system.iobus = IOXBar()
    system.membus = SystemXBar()
    system.system_port = system.membus.cpu_side_ports

    system.platform = HiFive()
    system.platform.rtc = RiscvRTC(frequency=Frequency("100MHz"))
    system.platform.clint.int_pin = system.platform.rtc.int_pin
    system.platform.setNumCores(args.num_cpus)

    # UART topology:
    # - UART0 (0x10000000): Zephyr RTOS Instance 0 (CPU0 AMP)
    # - UART1 (0x10001000): Zephyr RTOS Instance 1 (CPU1 AMP)
    # - UART2 (0x10002000): Zephyr RTOS Instance 2 (CPU2-5 SMP)
    system.platform.terminal1 = Terminal(port=3457, number=1)
    system.platform.terminal2 = Terminal(port=3458, number=2)
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
    system.cluster0_l2 = L2Cache(size=args.l2_cluster0_size, assoc=args.l2_assoc)
    system.cluster1_l2 = L2Cache(size=args.l2_cluster1_size, assoc=args.l2_assoc)
    system.cluster0_l2.cpu_side = system.cluster0_bus.mem_side_ports
    system.cluster0_l2.mem_side = system.membus.cpu_side_ports
    system.cluster1_l2.cpu_side = system.cluster1_bus.mem_side_ports
    system.cluster1_l2.mem_side = system.membus.cpu_side_ports

    system.cpu = [cpu_cls(clk_domain=system.cpu_clk_domain, cpu_id=i) for i in range(args.num_cpus)]
    uncacheable = [
        *system.platform._on_chip_ranges(),
        *system.platform._off_chip_ranges(),
        *extra_uart_ranges,
    ]
    for i, cpu in enumerate(system.cpu):
        cpu.ArchISA.riscv_type = "RV32"
        cpu.createThreads()
        cpu.createInterruptController()

        l1i = L1_ICache(size=args.l1i_size, assoc=args.l1_assoc)
        l1d = L1_DCache(size=args.l1d_size, assoc=args.l1_assoc)
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

    system.workload = RiscvBareMetal(bootloader=args.boot_elf, bare_metal=True, auto_reset_vect=True)

    root = Root(full_system=True, system=system)
    print(
        "[INFO] runtime launch:",
        f"cpus={args.num_cpus}",
        f"cpu_type={args.cpu_type}",
        f"boot_elf={args.boot_elf}",
        f"amp_cpu0={args.amp_cpu0_elf}",
        f"amp_cpu1={args.amp_cpu1_elf}",
        f"smp={args.smp_elf}",
        f"max_ticks={args.max_ticks}",
    )
    print(
        "[INFO] uart map:",
        "UART0=CPU0(system.platform.terminal)",
        "UART1=CPU1(system.platform.terminal1)",
        "UART2=CPU2-5 SMP(system.platform.terminal2)",
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
    plan = build_plan(args)

    if args.print_json or not _has_gem5_runtime():
        print(json.dumps(asdict(plan), indent=2))
        return 0

    return _run_gem5_runtime(args)


if __name__ in {"__main__", "__m5_main__"}:
    raise SystemExit(main())
