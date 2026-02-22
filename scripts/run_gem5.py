#!/usr/bin/env python3
"""Run gem5 simulations for riscv64_smp and riscv32_mixed targets.

- riscv64_smp: Full-system Linux boot flow (deprecated fs_linux config backend).
- riscv32_mixed: three bare-metal Zephyr runs (AMP cpu0/cpu1 + SMP cluster1) to
  approximate mixed AMP/SMP execution in this phase.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def find_first_existing(candidates: List[str]) -> str:
    for c in candidates:
        if c and Path(c).exists():
            return c
    return ""


def auto_kernel_elf(kernel_hint: str) -> str:
    hint = Path(kernel_hint)
    if hint.exists() and hint.name != "Image":
        return str(hint)

    candidates: List[str] = ["build/linux/vmlinux"]
    if hint.name == "Image" and len(hint.parents) >= 4:
        candidates.append(str(hint.parents[3] / "vmlinux"))
    return find_first_existing(candidates)


def auto_disk_image() -> str:
    return find_first_existing(
        [
            "build/buildroot/images/rootfs.ext2",
            "build/buildroot/images/rootfs2.ext2",
            "sources/buildroot/output/images/rootfs.ext2",
            "sources/buildroot/output/images/rootfs2.ext2",
        ]
    )


def default_riscv_config() -> str:
    return "sources/gem5/configs/deprecated/example/riscv/fs_linux.py"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run gem5 for riscv64_smp/riscv32_mixed",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--target", choices=["riscv64_smp", "riscv32_mixed"], required=True)
    p.add_argument("--mode", choices=["simple", "complex"], default="simple")
    p.add_argument("--gem5-bin", default="sources/gem5/build/RISCV/gem5.opt")
    p.add_argument("--config", default="")

    # RV64 Linux inputs
    p.add_argument("--kernel", default="build/linux/arch/riscv/boot/Image")
    p.add_argument("--disk-image", default="")
    p.add_argument("--allow-no-disk", action="store_true")
    p.add_argument(
        "--command-line",
        default="console=ttyS0 root=/dev/vda rw init=/sbin/init",
    )

    # RV32 Zephyr inputs
    p.add_argument("--amp-cpu0-elf", default="build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf")
    p.add_argument("--amp-cpu1-elf", default="build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf")
    p.add_argument("--smp-elf", default="build/zephyr/cluster1_smp/zephyr/zephyr.elf")

    # Runtime knobs
    p.add_argument("--cpu-type", default="TimingSimpleCPU")
    p.add_argument("--max-ticks-simple", type=int, default=200_000_000)
    p.add_argument("--max-ticks-complex", type=int, default=2_000_000_000)
    p.add_argument("--timeout-sec", type=int, default=1800)

    p.add_argument("--results-root", default="workloads/results")
    p.add_argument("--log-root", default="build/logs")
    p.add_argument("--timestamp", default="")
    p.add_argument("--dry-run", action="store_true")
    return p


def ensure_dirs(results_dir: Path, logs_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)


def max_ticks_for_mode(args: argparse.Namespace) -> int:
    return args.max_ticks_simple if args.mode == "simple" else args.max_ticks_complex


def rv64_command(
    args: argparse.Namespace, config_path: Path, logs_dir: Path
) -> Tuple[List[str], str, str]:
    disk_image = args.disk_image or auto_disk_image()
    kernel_elf = auto_kernel_elf(args.kernel) or args.kernel
    cmd = [
        args.gem5_bin,
        f"--outdir={logs_dir}",
        str(config_path),
        "--num-cpus",
        "4",
        "--cpu-type",
        args.cpu_type,
        "--mem-size",
        "2GB",
        "--caches",
        "--l2cache",
        "--l1i_size",
        "32kB",
        "--l1d_size",
        "32kB",
        "--l2_size",
        "1MB",
        "--kernel",
        kernel_elf,
        "--command-line",
        args.command_line,
        "--abs-max-tick",
        str(max_ticks_for_mode(args)),
    ]
    if disk_image:
        cmd.extend(["--disk-image", disk_image])
    return cmd, disk_image, kernel_elf


def rv32_commands(args: argparse.Namespace, config_path: Path, logs_dir: Path) -> List[Tuple[str, List[str]]]:
    base = [
        args.gem5_bin,
        f"--outdir={logs_dir}",
        str(config_path),
        "--cpu-type",
        args.cpu_type,
        "--mem-size",
        "512MB",
        "--caches",
        "--l2cache",
        "--l1i_size",
        "16kB",
        "--l1d_size",
        "16kB",
        "--abs-max-tick",
        str(max_ticks_for_mode(args)),
        "--bare-metal",
        "--riscv-32bits",
    ]

    runs = [
        (
            "amp_cpu0",
            base
            + [
                "--num-cpus",
                "1",
                "--l2_size",
                "256kB",
                "--kernel",
                args.amp_cpu0_elf,
            ],
        ),
        (
            "amp_cpu1",
            base
            + [
                "--num-cpus",
                "1",
                "--l2_size",
                "256kB",
                "--kernel",
                args.amp_cpu1_elf,
            ],
        ),
        (
            "cluster1_smp",
            base
            + [
                "--num-cpus",
                "4",
                "--l2_size",
                "512kB",
                "--kernel",
                args.smp_elf,
            ],
        ),
    ]
    return runs


def quoted(cmd: List[str]) -> str:
    return " ".join(shlex.quote(x) for x in cmd)


def read_markers(log_path: Path, markers: List[str]) -> Dict[str, bool]:
    if not log_path.exists():
        return {m: False for m in markers}
    txt = log_path.read_text(encoding="utf-8", errors="ignore")
    return {m: (m in txt) for m in markers}


def run_one(cmd: List[str], log_path: Path, timeout_sec: int) -> Dict[str, object]:
    with log_path.open("w", encoding="utf-8") as fp:
        try:
            proc = subprocess.run(cmd, stdout=fp, stderr=subprocess.STDOUT, check=False, timeout=timeout_sec)
            return {"returncode": proc.returncode, "timeout": False}
        except subprocess.TimeoutExpired:
            return {"returncode": 124, "timeout": True}


def main() -> int:
    args = parser().parse_args()

    ts = args.timestamp or utc_ts()
    results_dir = Path(args.results_root) / ts
    logs_dir = Path(args.log_root) / args.target / ts
    ensure_dirs(results_dir, logs_dir)

    config_path = Path(args.config or default_riscv_config())
    manifest_path = results_dir / f"run_gem5_{args.target}_{args.mode}.json"

    missing: List[str] = []
    if not Path(args.gem5_bin).exists():
        missing.append(f"gem5 binary: {args.gem5_bin}")
    if not config_path.exists():
        missing.append(f"config: {config_path}")

    manifest: Dict[str, object] = {
        "timestamp": ts,
        "target": args.target,
        "mode": args.mode,
        "dry_run": args.dry_run,
        "gem5_bin": args.gem5_bin,
        "config": str(config_path),
        "results_dir": str(results_dir),
        "logs_dir": str(logs_dir),
    }

    if args.target == "riscv64_smp":
        cmd, disk_image, kernel_elf = rv64_command(args, config_path, logs_dir)
        manifest["commands"] = [cmd]
        manifest["disk_image"] = disk_image
        manifest["kernel_elf"] = kernel_elf

        if not Path(kernel_elf).exists():
            missing.append(f"kernel ELF: {kernel_elf}")
        if not disk_image and not args.allow_no_disk:
            missing.append("disk image: not found (expected rootfs.ext2)")

        if args.dry_run:
            print("[INFO] DRY-RUN mode")
            for item in missing:
                print(f"[WARN] Missing path: {item}")
            if not disk_image and args.allow_no_disk:
                print("[WARN] No disk image found, but continuing due to --allow-no-disk")
            print(f"[INFO] command={quoted(cmd)}")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"[OK] Manifest: {manifest_path}")
            return 0

        if missing:
            for item in missing:
                print(f"[ERROR] Missing path: {item}", file=sys.stderr)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            return 2

        run_log = logs_dir / "run_riscv64_smp.log"
        print(f"[INFO] Executing: {quoted(cmd)}")
        if not disk_image:
            print("[WARN] Running without disk image (--allow-no-disk).")
        run_result = run_one(cmd, run_log, args.timeout_sec)
        markers = read_markers(run_log, ["OpenSBI", "Linux version", "Kernel panic"])
        manifest.update({
            "run_log": str(run_log),
            "run_result": run_result,
            "markers": markers,
        })
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[INFO] run_log={run_log}")
        print(f"[OK] Manifest: {manifest_path}")
        return int(run_result["returncode"])

    # riscv32_mixed
    runs = rv32_commands(args, config_path, logs_dir)
    manifest["commands"] = [cmd for _, cmd in runs]

    for name, elf in [
        ("amp_cpu0_elf", args.amp_cpu0_elf),
        ("amp_cpu1_elf", args.amp_cpu1_elf),
        ("smp_elf", args.smp_elf),
    ]:
        if not Path(elf).exists():
            missing.append(f"{name}: {elf}")

    if args.dry_run:
        print("[INFO] DRY-RUN mode")
        for item in missing:
            print(f"[WARN] Missing path: {item}")
        for name, cmd in runs:
            print(f"[INFO] command[{name}]={quoted(cmd)}")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] Manifest: {manifest_path}")
        return 0

    if missing:
        for item in missing:
            print(f"[ERROR] Missing path: {item}", file=sys.stderr)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return 2

    run_results: Dict[str, object] = {}
    failed = 0
    for name, cmd in runs:
        run_log = logs_dir / f"run_riscv32_mixed_{name}.log"
        print(f"[INFO] Executing[{name}]: {quoted(cmd)}")
        result = run_one(cmd, run_log, args.timeout_sec)
        markers = read_markers(run_log, ["*** Booting Zephyr OS", "Kernel panic", "panic"])
        run_results[name] = {
            "run_log": str(run_log),
            "result": result,
            "markers": markers,
        }
        if int(result["returncode"]) != 0:
            failed += 1

    manifest["run_results"] = run_results
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Manifest: {manifest_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
