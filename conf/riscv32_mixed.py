#!/usr/bin/env python3
"""RV32 mixed AMP/SMP gem5 configuration skeleton.

Topology:
- Cluster0 AMP: CPU0, CPU1
- Cluster1 SMP: CPU2, CPU3, CPU4, CPU5
- per-core L1I/L1D caches
- per-cluster shared unified L2 caches
- UART mapping: AMP per-core UART + SMP shared UART

Dry-run friendly (no gem5 python dependency required).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
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
class WorkloadConfig:
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
    workload: WorkloadConfig


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
            l1i=l1i,
            l1d=l1d,
            uart="uart_amp_cpu0",
        ),
        CoreConfig(
            cpu_id=1,
            isa="rv32",
            cluster="cluster0",
            mode="AMP",
            l1i=l1i,
            l1d=l1d,
            uart="uart_amp_cpu1",
        ),
    ]

    for cpu_id in [2, 3, 4, 5]:
        cores.append(
            CoreConfig(
                cpu_id=cpu_id,
                isa="rv32",
                cluster="cluster1",
                mode="SMP",
                l1i=l1i,
                l1d=l1d,
                uart="uart_smp_cluster1_shared",
            )
        )

    clusters = [
        ClusterConfig(
            name="cluster0",
            mode="AMP",
            cores=[0, 1],
            l2=l2_cluster0,
            uart="per-core (cpu0/cpu1)",
        ),
        ClusterConfig(
            name="cluster1",
            mode="SMP",
            cores=[2, 3, 4, 5],
            l2=l2_cluster1,
            uart="shared",
        ),
    ]

    workload = WorkloadConfig(
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
        workload=workload,
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RV32 mixed AMP/SMP gem5 configuration skeleton generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--amp-cpu0-elf", default="build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf")
    p.add_argument("--amp-cpu1-elf", default="build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf")
    p.add_argument("--smp-elf", default="build/zephyr/cluster1_smp/zephyr/zephyr.elf")

    p.add_argument("--l1i-size", default="16kB")
    p.add_argument("--l1d-size", default="16kB")
    p.add_argument("--l1-assoc", type=int, default=2)
    p.add_argument("--l2-cluster0-size", default="256kB")
    p.add_argument("--l2-cluster1-size", default="512kB")
    p.add_argument("--l2-assoc", type=int, default=8)

    p.add_argument(
        "--print-json",
        action="store_true",
        help="Print resolved plan JSON (dry-run friendly)",
    )
    return p


def main() -> int:
    args = parser().parse_args()
    plan = build_plan(args)

    if args.print_json:
        print(json.dumps(asdict(plan), indent=2))
        return 0

    # TODO(execution-phase): instantiate real gem5 objects and bind UART map:
    #   CPU0->uart_amp_cpu0, CPU1->uart_amp_cpu1, CPU2-5->uart_smp_cluster1_shared.
    print("[INFO] riscv32_mixed plan generated. Use --print-json to inspect details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
