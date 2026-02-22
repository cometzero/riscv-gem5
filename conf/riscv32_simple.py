#!/usr/bin/env python3
"""RV32 simple single-core gem5 configuration skeleton.

Target:
- CPU0 only (single-core)
- RV32 bare-metal
- private L1I/L1D + unified L2
- shared UART console
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


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
class WorkloadConfig:
    zephyr_elf: str
    expected_markers: list[str]


@dataclass
class PlatformPlan:
    target: str
    isa: str
    topology: dict[str, int]
    core: CoreConfig
    l2: CacheConfig
    workload: WorkloadConfig


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RV32 simple gem5 plan generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--zephyr-elf", default="build/zephyr/riscv32_simple/zephyr/zephyr.elf")
    p.add_argument("--l1i-size", default="16kB")
    p.add_argument("--l1d-size", default="16kB")
    p.add_argument("--l1-assoc", type=int, default=2)
    p.add_argument("--l2-size", default="256kB")
    p.add_argument("--l2-assoc", type=int, default=8)
    p.add_argument("--print-json", action="store_true")
    return p


def build_plan(args: argparse.Namespace) -> PlatformPlan:
    l1i = CacheConfig(level="L1I", kind="private", size=args.l1i_size, assoc=args.l1_assoc)
    l1d = CacheConfig(level="L1D", kind="private", size=args.l1d_size, assoc=args.l1_assoc)
    l2 = CacheConfig(level="L2", kind="unified", size=args.l2_size, assoc=args.l2_assoc)

    core = CoreConfig(
        cpu_id=0,
        isa="rv32",
        cluster="cluster0",
        mode="SIMPLE",
        l1i=l1i,
        l1d=l1d,
        uart="uart_shared_cluster0",
    )

    workload = WorkloadConfig(
        zephyr_elf=args.zephyr_elf,
        expected_markers=[
            "*** Booting Zephyr OS",
            "RISCV32 SIMPLE WORKLOAD START",
            "RISCV32 SIMPLE WORKLOAD DONE",
        ],
    )

    return PlatformPlan(
        target="riscv32_simple",
        isa="rv32",
        topology={"clusters": 1, "cores": 1},
        core=core,
        l2=l2,
        workload=workload,
    )


def main() -> int:
    args = parser().parse_args()
    plan = build_plan(args)

    if args.print_json:
        print(json.dumps(asdict(plan), indent=2))
        return 0

    print("[INFO] riscv32_simple plan generated. Use --print-json to inspect details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
