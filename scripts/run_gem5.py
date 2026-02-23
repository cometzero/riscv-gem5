#!/usr/bin/env python3
"""Run gem5 simulations for riscv64_smp, riscv32_mixed, riscv32_simple targets.

- riscv64_smp: Full-system Linux boot flow (conf/riscv64_smp.py backend).
- riscv32_mixed: one gem5 launch with 6-core mixed topology and three Zephyr
  images (CPU0 AMP, CPU1 AMP, CPU2-5 SMP) in a single run.
- riscv32_simple: single-core bare-metal Zephyr run (CPU0 only).
- riscv_hybrid: one gem5 launch containing both riscv32_mixed + riscv64.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
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
    for path in sorted(Path("sources/buildroot/output/build").glob("linux-*/vmlinux"), reverse=True):
        candidates.append(str(path))
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


def auto_bootloader() -> str:
    return find_first_existing(
        [
            "build/buildroot/images/fw_jump.elf",
            "sources/buildroot/output/images/fw_jump.elf",
            "build/buildroot/images/fw_dynamic.elf",
            "sources/buildroot/output/images/fw_dynamic.elf",
        ]
    )


def auto_initramfs() -> str:
    return find_first_existing(
        [
            "build/initramfs/rootfs-shell.cpio",
            "build/initramfs/rootfs.cpio",
            "sources/buildroot/output/images/rootfs.cpio",
            "build/buildroot/images/rootfs.cpio",
        ]
    )


def default_riscv_config() -> str:
    return "sources/gem5/configs/deprecated/example/riscv/fs_linux.py"


def default_config_for_target(target: str) -> str:
    if target == "riscv64_smp":
        return "conf/riscv64_smp.py"
    if target == "riscv32_mixed":
        return "conf/riscv32_mixed.py"
    if target == "riscv_hybrid":
        return "conf/riscv_hybrid.py"
    return default_riscv_config()


def mixed_cpu_type(cpu_type: str) -> str:
    lowered = cpu_type.lower()
    if "atomic" in lowered:
        return "atomic"
    return "timing"


def read_elf_entry(path: str) -> int:
    proc = subprocess.run(
        ["readelf", "-h", path],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in proc.stdout.splitlines():
        if "Entry point address:" not in line:
            continue
        value = line.split(":", maxsplit=1)[1].strip()
        return int(value, 0)
    raise RuntimeError(f"failed to parse ELF entry point: {path}")


def maybe_build_mixed_boot(args: argparse.Namespace) -> None:
    amp0 = Path(args.amp_cpu0_elf)
    amp1 = Path(args.amp_cpu1_elf)
    smp = Path(args.smp_elf)
    if not (amp0.exists() and amp1.exists() and smp.exists()):
        return

    entry0 = read_elf_entry(str(amp0))
    entry1 = read_elf_entry(str(amp1))
    entry_smp = read_elf_entry(str(smp))

    boot_elf = Path(args.mixed_boot_elf)
    boot_script = Path(__file__).resolve().with_name("build_riscv32_mixed_boot.sh")
    boot_elf.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(boot_script),
        "--output",
        str(boot_elf),
        "--amp-cpu0-entry",
        hex(entry0),
        "--amp-cpu1-entry",
        hex(entry1),
        "--cluster1-smp-entry",
        hex(entry_smp),
    ]
    print(f"[INFO] Building mixed boot trampoline: {quoted(cmd)}")
    subprocess.run(cmd, check=True)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run gem5 for riscv64_smp/riscv32_mixed/riscv32_simple/riscv_hybrid",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--target",
        choices=["riscv64_smp", "riscv32_mixed", "riscv32_simple", "riscv_hybrid"],
        required=True,
    )
    p.add_argument("--mode", choices=["simple", "complex"], default="simple")
    p.add_argument("--gem5-bin", default="sources/gem5/build/RISCV/gem5.opt")
    p.add_argument("--config", default="")

    # RV64 Linux inputs
    p.add_argument("--kernel", default="build/linux/arch/riscv/boot/Image")
    p.add_argument("--bootloader", default="")
    p.add_argument("--initramfs", default="")
    p.add_argument("--disk-image", default="")
    p.add_argument("--allow-no-disk", action="store_true")
    p.add_argument(
        "--command-line",
        default=(
            "console=ttyS0,115200 earlycon=sbi root=/dev/ram0 rw "
            "rdinit=/init loglevel=8 ignore_loglevel"
        ),
    )
    p.add_argument("--sys-clock", default="1GHz")
    p.add_argument("--cpu-clock", default="3GHz")
    p.add_argument("--num-cpus", type=int, default=1)

    # RV32 Zephyr inputs
    p.add_argument("--amp-cpu0-elf", default="build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf")
    p.add_argument("--amp-cpu1-elf", default="build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf")
    p.add_argument("--smp-elf", default="build/zephyr/cluster1_smp/zephyr/zephyr.elf")
    p.add_argument("--mixed-boot-elf", default="build/boot/riscv32_mixed_boot.elf")
    p.add_argument("--simple-elf", default="build/zephyr/riscv32_simple/zephyr/zephyr.elf")

    # Runtime knobs
    p.add_argument("--cpu-type", default="TimingSimpleCPU")
    # rv64 simple mode needs a larger tick budget to expose UART boot banners
    # (OpenSBI/Linux early boot) in terminal logs.
    p.add_argument("--max-ticks-simple", type=int, default=1_200_000_000_000)
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


def refresh_latest_symlink(parent: Path, link_name: str, target_name: str) -> None:
    parent.mkdir(parents=True, exist_ok=True)
    link_path = parent / link_name
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_dir() and not link_path.is_symlink():
            print(
                f"[WARN] Skip symlink update for {link_path}: existing directory is not a symlink",
                file=sys.stderr,
            )
            return
        link_path.unlink()
    link_path.symlink_to(target_name)


def update_latest_symlinks(
    results_root: Path,
    log_root: Path,
    target: str,
    mode: str,
    timestamp: str,
) -> Dict[str, str]:
    refresh_latest_symlink(results_root, "latest", timestamp)
    refresh_latest_symlink(results_root, f"latest-{target}-{mode}", timestamp)

    target_log_root = log_root / target
    refresh_latest_symlink(target_log_root, "latest", timestamp)
    refresh_latest_symlink(target_log_root, f"latest-{mode}", timestamp)

    return {
        "results_latest": str(results_root / "latest"),
        "results_latest_mode": str(results_root / f"latest-{target}-{mode}"),
        "logs_latest": str(target_log_root / "latest"),
        "logs_latest_mode": str(target_log_root / f"latest-{mode}"),
    }


def max_ticks_for_mode(args: argparse.Namespace) -> int:
    return args.max_ticks_simple if args.mode == "simple" else args.max_ticks_complex


def rv64_command(
    args: argparse.Namespace, config_path: Path, logs_dir: Path
) -> Tuple[List[str], str, str, str, str, bool]:
    bootloader = args.bootloader or auto_bootloader()
    initramfs = args.initramfs or auto_initramfs()
    kernel_elf = auto_kernel_elf(args.kernel) or args.kernel
    use_conf_runtime = config_path.name == "riscv64_smp.py"
    disk_image = args.disk_image
    if not disk_image:
        if use_conf_runtime and "root=/dev/ram" in args.command_line:
            disk_image = ""
        else:
            disk_image = auto_disk_image()
    if use_conf_runtime:
        cpu_type = mixed_cpu_type(args.cpu_type)
        if args.cpu_type.lower() == "timingsimplecpu":
            cpu_type = "atomic"
        num_cpus = args.num_cpus if args.mode == "simple" else max(2, args.num_cpus)
        cmd = [
            args.gem5_bin,
            f"--outdir={logs_dir}",
            str(config_path),
            "--num-cpus",
            str(num_cpus),
            "--cpu-type",
            cpu_type,
            "--sys-clock",
            args.sys_clock,
            "--cpu-clock",
            args.cpu_clock,
            "--kernel",
            kernel_elf,
            "--kernel-elf",
            kernel_elf,
            "--cmdline",
            args.command_line,
            "--max-ticks",
            str(max_ticks_for_mode(args)),
        ]
        if bootloader:
            cmd.extend(["--bootloader", bootloader])
        if initramfs:
            cmd.extend(["--initramfs", initramfs])
        if disk_image:
            cmd.extend(["--disk-image", disk_image])
        return cmd, disk_image, kernel_elf, bootloader, initramfs, True

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
    if bootloader:
        cmd.extend(["--bootloader", bootloader])
    if disk_image:
        cmd.extend(["--disk-image", disk_image])
    return cmd, disk_image, kernel_elf, bootloader, initramfs, False


def rv32_mixed_command(
    args: argparse.Namespace, config_path: Path, logs_dir: Path
) -> Tuple[List[str], List[Dict[str, object]], List[str], List[str]]:
    # Keep a longer default runtime for mixed bring-up.
    abs_max_tick = args.max_ticks_complex if args.mode == "simple" else max_ticks_for_mode(args)
    cmd = [
        args.gem5_bin,
        f"--outdir={logs_dir}",
        str(config_path),
        "--num-cpus",
        "6",
        "--cpu-type",
        mixed_cpu_type(args.cpu_type),
        "--max-ticks",
        str(abs_max_tick),
        "--boot-elf",
        args.mixed_boot_elf,
        "--amp-cpu0-elf",
        args.amp_cpu0_elf,
        "--amp-cpu1-elf",
        args.amp_cpu1_elf,
        "--smp-elf",
        args.smp_elf,
    ]

    assignments = [
        {
            "name": "amp_cpu0",
            "cpu_ids": [0],
            "elf": args.amp_cpu0_elf,
            "marker_role": "AMP CPU0",
            "dt_role": "cluster0-amp-cpu0",
        },
        {
            "name": "amp_cpu1",
            "cpu_ids": [1],
            "elf": args.amp_cpu1_elf,
            "marker_role": "AMP CPU1",
            "dt_role": "cluster0-amp-cpu1",
        },
        {
            "name": "cluster1_smp",
            "cpu_ids": [2, 3, 4, 5],
            "elf": args.smp_elf,
            "marker_role": "CLUSTER1 SMP",
            "dt_role": "cluster1-smp",
        },
    ]
    role_markers: List[str] = []
    done_markers: List[str] = []
    for item in assignments:
        marker_role = str(item["marker_role"])
        dt_role = str(item["dt_role"])
        role_markers.extend(
            [
                f"RISCV32 MIXED {marker_role} WORKLOAD START",
                f"RISCV32 MIXED {marker_role} WORKLOAD DONE",
                f"role={dt_role}",
            ]
        )
        done_markers.append(f"RISCV32 MIXED {marker_role} WORKLOAD DONE")

    required_markers = done_markers + ["RISCV32 MIXED ROLE_SYNC mask=0x7 status=READY"]

    return cmd, assignments, required_markers, role_markers


def rv_hybrid_command(
    args: argparse.Namespace, config_path: Path, logs_dir: Path
) -> Tuple[List[str], str, str, str, str]:
    bootloader = args.bootloader or auto_bootloader()
    initramfs = args.initramfs or auto_initramfs()
    kernel_elf = auto_kernel_elf(args.kernel) or args.kernel
    disk_image = args.disk_image
    if not disk_image:
        if "root=/dev/ram" in args.command_line:
            disk_image = ""
        else:
            disk_image = auto_disk_image()

    rv32_cpu_type = mixed_cpu_type(args.cpu_type)
    rv64_cpu_type = "atomic" if args.cpu_type.lower() == "timingsimplecpu" else mixed_cpu_type(args.cpu_type)
    abs_max_tick = max_ticks_for_mode(args)

    cmd = [
        args.gem5_bin,
        f"--outdir={logs_dir}",
        str(config_path),
        "--max-ticks",
        str(abs_max_tick),
        "--rv32-cpu-type",
        rv32_cpu_type,
        "--rv64-cpu-type",
        rv64_cpu_type,
        "--rv64-num-cpus",
        str(max(4, args.num_cpus)),
        "--sys-clock",
        args.sys_clock,
        "--rv64-cpu-clock",
        args.cpu_clock,
        "--boot-elf",
        args.mixed_boot_elf,
        "--amp-cpu0-elf",
        args.amp_cpu0_elf,
        "--amp-cpu1-elf",
        args.amp_cpu1_elf,
        "--smp-elf",
        args.smp_elf,
        "--kernel",
        kernel_elf,
        "--kernel-elf",
        kernel_elf,
        "--cmdline",
        args.command_line,
    ]
    if bootloader:
        cmd.extend(["--bootloader", bootloader])
    if initramfs:
        cmd.extend(["--initramfs", initramfs])
    if disk_image:
        cmd.extend(["--disk-image", disk_image])

    return cmd, disk_image, kernel_elf, bootloader, initramfs


def rv32_simple_command(
    args: argparse.Namespace, config_path: Path, logs_dir: Path
) -> Tuple[List[str], str]:
    # Keep a longer default runtime for this bring-up target so Zephyr
    # application markers can be emitted reliably.
    abs_max_tick = args.max_ticks_complex if args.mode == "simple" else max_ticks_for_mode(args)
    cmd = [
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
        "--l2_size",
        "256kB",
        "--abs-max-tick",
        str(abs_max_tick),
        "--bare-metal",
        "--riscv-32bits",
        "--num-cpus",
        "1",
        "--kernel",
        args.simple_elf,
    ]
    return cmd, args.simple_elf


def quoted(cmd: List[str]) -> str:
    return " ".join(shlex.quote(x) for x in cmd)


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def clean_log_text(txt: str) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", txt)
    cleaned = cleaned.replace("\r", "\n").replace("\x00", " ")
    return cleaned


def normalize_log_text(txt: str) -> str:
    cleaned = clean_log_text(txt)
    return " ".join(cleaned.split())


def to_alnum_upper(txt: str) -> str:
    return "".join(ch for ch in txt.upper() if ch.isalnum())


def is_subsequence(needle: str, haystack: str) -> bool:
    if not needle:
        return False
    idx = 0
    for ch in haystack:
        if ch == needle[idx]:
            idx += 1
            if idx == len(needle):
                return True
    return False


def marker_present(text: str, marker: str, allow_interleaved: bool = False) -> bool:
    if marker in text:
        return True

    normalized = normalize_log_text(text)
    norm_marker = " ".join(marker.split())
    if norm_marker and norm_marker in normalized:
        return True

    if not allow_interleaved:
        return False

    needle = to_alnum_upper(norm_marker)
    if not needle:
        return False

    cleaned = clean_log_text(text)
    for line in cleaned.splitlines():
        hay = to_alnum_upper(line)
        if needle in hay or is_subsequence(needle, hay):
            return True

    hay_all = to_alnum_upper(normalized)
    return needle in hay_all or is_subsequence(needle, hay_all)


def read_markers_from_paths(
    paths: List[Path], markers: List[str], allow_interleaved: bool = False
) -> Dict[str, bool]:
    txt = ""
    for path in paths:
        if path.exists():
            txt += path.read_text(encoding="utf-8", errors="ignore")
            txt += "\n"
    return {marker: marker_present(txt, marker, allow_interleaved) for marker in markers}


def read_stats_counter(stats_path: Path, key: str) -> int:
    if not stats_path.exists():
        return -1
    for line in stats_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        columns = line.split()
        if len(columns) >= 2 and columns[0] == key:
            try:
                return int(float(columns[1]))
            except ValueError:
                return -1
    return -1


def run_one(cmd: List[str], log_path: Path, timeout_sec: int) -> Dict[str, object]:
    with log_path.open("w", encoding="utf-8") as fp:
        env = os.environ.copy()
        gem5_configs = str(Path("sources/gem5/configs").resolve())
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{gem5_configs}:{prev}" if prev else gem5_configs
        try:
            proc = subprocess.run(
                cmd,
                stdout=fp,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_sec,
                env=env,
            )
            return {"returncode": proc.returncode, "timeout": False}
        except subprocess.TimeoutExpired:
            return {"returncode": 124, "timeout": True}


def run_one_until_markers(
    cmd: List[str],
    log_path: Path,
    marker_log_path: Path,
    success_markers: List[str],
    timeout_sec: int,
) -> Dict[str, object]:
    with log_path.open("w", encoding="utf-8") as fp:
        env = os.environ.copy()
        gem5_configs = str(Path("sources/gem5/configs").resolve())
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{gem5_configs}:{prev}" if prev else gem5_configs
        proc = subprocess.Popen(
            cmd,
            stdout=fp,
            stderr=subprocess.STDOUT,
            env=env,
        )

        deadline = time.monotonic() + timeout_sec
        while True:
            if marker_log_path.exists():
                text = marker_log_path.read_text(encoding="utf-8", errors="ignore")
                if all(marker_present(text, marker) for marker in success_markers):
                    proc.terminate()
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    return {
                        "returncode": 0,
                        "timeout": False,
                        "terminated_on_marker": True,
                        "raw_returncode": proc.returncode,
                    }

            rc = proc.poll()
            if rc is not None:
                return {"returncode": rc, "timeout": False}

            if time.monotonic() >= deadline:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                return {
                    "returncode": 124,
                    "timeout": True,
                    "terminated_on_marker": False,
                    "raw_returncode": proc.returncode,
                }
            time.sleep(2)


def run_one_until_markers_multi(
    cmd: List[str],
    log_path: Path,
    marker_log_paths: List[Path],
    success_markers: List[str],
    timeout_sec: int,
) -> Dict[str, object]:
    with log_path.open("w", encoding="utf-8") as fp:
        env = os.environ.copy()
        gem5_configs = str(Path("sources/gem5/configs").resolve())
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{gem5_configs}:{prev}" if prev else gem5_configs
        proc = subprocess.Popen(
            cmd,
            stdout=fp,
            stderr=subprocess.STDOUT,
            env=env,
        )

        deadline = time.monotonic() + timeout_sec
        while True:
            merged = ""
            for marker_path in marker_log_paths:
                if marker_path.exists():
                    merged += marker_path.read_text(encoding="utf-8", errors="ignore")
                    merged += "\n"
            if merged and all(marker_present(merged, marker) for marker in success_markers):
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                return {
                    "returncode": 0,
                    "timeout": False,
                    "terminated_on_marker": True,
                    "raw_returncode": proc.returncode,
                }

            rc = proc.poll()
            if rc is not None:
                return {"returncode": rc, "timeout": False}

            if time.monotonic() >= deadline:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                return {
                    "returncode": 124,
                    "timeout": True,
                    "terminated_on_marker": False,
                    "raw_returncode": proc.returncode,
                }
            time.sleep(2)


def mixed_terminal_logs(logs_dir: Path) -> List[Path]:
    candidates = sorted(
        path for path in logs_dir.glob("system.platform.terminal*") if path.is_file()
    )
    if candidates:
        return candidates
    return [logs_dir / "system.platform.terminal"]


def hybrid_terminal_logs(logs_dir: Path) -> Tuple[List[Path], List[Path]]:
    rv32_logs = sorted(path for path in logs_dir.glob("system32.platform.terminal*") if path.is_file())
    rv64_logs = sorted(path for path in logs_dir.glob("system64.platform.terminal*") if path.is_file())
    if not rv32_logs:
        rv32_logs = [logs_dir / "system32.platform.terminal"]
    if not rv64_logs:
        rv64_logs = [logs_dir / "system64.platform.terminal"]
    return rv32_logs, rv64_logs


def main() -> int:
    args = parser().parse_args()

    ts = args.timestamp or utc_ts()
    results_dir = Path(args.results_root) / ts
    logs_dir = Path(args.log_root) / args.target / ts
    ensure_dirs(results_dir, logs_dir)
    latest_links = update_latest_symlinks(
        Path(args.results_root),
        Path(args.log_root),
        args.target,
        args.mode,
        ts,
    )

    config_path = Path(args.config or default_config_for_target(args.target))
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
        "latest_links": latest_links,
    }

    if args.target == "riscv64_smp":
        cmd, disk_image, kernel_elf, bootloader, initramfs, use_conf_runtime = rv64_command(
            args, config_path, logs_dir
        )
        manifest["commands"] = [cmd]
        manifest["disk_image"] = disk_image
        manifest["kernel_elf"] = kernel_elf
        manifest["bootloader"] = bootloader
        manifest["initramfs"] = initramfs
        manifest["conf_runtime"] = use_conf_runtime

        if not Path(kernel_elf).exists():
            missing.append(f"kernel ELF: {kernel_elf}")
        if not bootloader:
            missing.append("bootloader: not found (expected fw_jump.elf)")
        if use_conf_runtime and not initramfs:
            missing.append("initramfs: not found (expected rootfs-shell.cpio/rootfs.cpio)")
        if (not use_conf_runtime) and (not disk_image and not args.allow_no_disk):
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
        terminal_log = logs_dir / "system.platform.terminal"
        if use_conf_runtime and args.mode == "simple":
            run_result = run_one_until_markers(
                cmd,
                run_log,
                terminal_log,
                ["INITRAMFS_SHELL_READY", "initramfs#"],
                args.timeout_sec,
            )
        else:
            run_result = run_one(cmd, run_log, args.timeout_sec)
        markers = read_markers_from_paths(
            [run_log, terminal_log],
            [
                "OpenSBI",
                "Linux version",
                "Loaded bootloader",
                "Loaded kernel",
                "Run /init as init process",
                "INITRAMFS_SHELL_READY",
                "initramfs#",
                "simulate() limit reached",
                "Kernel panic",
                "fatal:",
            ],
        )
        required_markers_ok = markers["Loaded bootloader"] and markers["Loaded kernel"]
        if use_conf_runtime:
            required_markers_ok = required_markers_ok and markers["Run /init as init process"]
            if args.mode == "simple":
                required_markers_ok = (
                    required_markers_ok
                    and markers["INITRAMFS_SHELL_READY"]
                    and markers["initramfs#"]
                )
        checks = {
            "returncode_ok": int(run_result["returncode"]) == 0,
            "required_markers_ok": required_markers_ok,
            "terminal_markers_ok": (
                markers["OpenSBI"] or markers["Linux version"]
            ),
            "uart_log_present": terminal_log.exists() and terminal_log.stat().st_size > 0,
            "panic_free": (not markers["Kernel panic"]) and (not markers["fatal:"]),
            "shell_prompt_ok": (not use_conf_runtime)
            or (args.mode != "simple")
            or (markers["INITRAMFS_SHELL_READY"] and markers["initramfs#"]),
        }
        manifest.update({
            "run_log": str(run_log),
            "terminal_log": str(terminal_log),
            "run_result": run_result,
            "markers": markers,
            "checks": checks,
            "validation": {
                "single_run": True,
                "all_passed": all(checks.values()),
            },
        })
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[INFO] run_log={run_log}")
        print(f"[OK] Manifest: {manifest_path}")
        return 1 if not all(checks.values()) else 0

    if args.target == "riscv_hybrid":
        cmd, disk_image, kernel_elf, bootloader, initramfs = rv_hybrid_command(
            args, config_path, logs_dir
        )
        manifest["commands"] = [cmd]
        manifest["kernel_elf"] = kernel_elf
        manifest["bootloader"] = bootloader
        manifest["initramfs"] = initramfs
        manifest["disk_image"] = disk_image
        manifest["hybrid_components"] = {
            "rv32_mixed": {
                "boot_elf": args.mixed_boot_elf,
                "amp_cpu0_elf": args.amp_cpu0_elf,
                "amp_cpu1_elf": args.amp_cpu1_elf,
                "smp_elf": args.smp_elf,
            },
            "rv64": {
                "kernel_elf": kernel_elf,
                "bootloader": bootloader,
                "initramfs": initramfs,
            },
        }

        if not Path(kernel_elf).exists():
            missing.append(f"kernel ELF: {kernel_elf}")
        if not bootloader:
            missing.append("bootloader: not found (expected fw_jump.elf)")
        if not initramfs:
            missing.append("initramfs: not found (expected rootfs-shell.cpio/rootfs.cpio)")
        for name, elf in [
            ("amp_cpu0_elf", args.amp_cpu0_elf),
            ("amp_cpu1_elf", args.amp_cpu1_elf),
            ("smp_elf", args.smp_elf),
        ]:
            if not Path(elf).exists():
                missing.append(f"{name}: {elf}")

        if not args.dry_run:
            try:
                maybe_build_mixed_boot(args)
            except Exception as exc:
                missing.append(f"mixed_boot_build: {exc}")

        if not Path(args.mixed_boot_elf).exists():
            missing.append(f"mixed_boot_elf: {args.mixed_boot_elf}")

        if args.dry_run:
            print("[INFO] DRY-RUN mode")
            for item in missing:
                print(f"[WARN] Missing path: {item}")
            print(f"[INFO] command={quoted(cmd)}")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"[OK] Manifest: {manifest_path}")
            return 0

        if missing:
            for item in missing:
                print(f"[ERROR] Missing path: {item}", file=sys.stderr)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            return 2

        run_log = logs_dir / "run_riscv_hybrid.log"
        print(f"[INFO] Executing: {quoted(cmd)}")
        if not disk_image:
            print("[WARN] Running hybrid without rv64 disk image (--allow-no-disk path).")
        expected_marker_logs = [
            logs_dir / "system32.platform.terminal",
            logs_dir / "system32.platform.terminal1",
            logs_dir / "system32.platform.terminal2",
            logs_dir / "system64.platform.terminal",
        ]
        if args.mode == "simple":
            run_result = run_one_until_markers_multi(
                cmd,
                run_log,
                expected_marker_logs,
                [
                    "RISCV32 MIXED AMP CPU0 WORKLOAD DONE",
                    "RISCV32 MIXED AMP CPU1 WORKLOAD DONE",
                    "RISCV32 MIXED CLUSTER1 SMP WORKLOAD DONE",
                    "RISCV32 MIXED ROLE_SYNC mask=0x7 status=READY",
                    "Linux version",
                ],
                args.timeout_sec,
            )
        else:
            run_result = run_one(cmd, run_log, args.timeout_sec)
        rv32_logs, rv64_logs = hybrid_terminal_logs(logs_dir)

        rv32_workload_markers = [
            "RISCV32 MIXED AMP CPU0 WORKLOAD DONE",
            "RISCV32 MIXED AMP CPU1 WORKLOAD DONE",
            "RISCV32 MIXED CLUSTER1 SMP WORKLOAD DONE",
            "RISCV32 MIXED ROLE_SYNC mask=0x7 status=READY",
        ]
        rv32_role_markers = [
            "role=cluster0-amp-cpu0",
            "role=cluster0-amp-cpu1",
            "role=cluster1-smp",
        ]
        rv64_markers = [
            "OpenSBI",
            "Linux version",
            "Loaded bootloader",
            "Loaded kernel",
            "Kernel panic",
            "fatal:",
            "panic",
        ]

        rv32_observed = read_markers_from_paths(
            [run_log, *rv32_logs],
            rv32_workload_markers + rv32_role_markers,
            allow_interleaved=False,
        )
        rv64_observed = read_markers_from_paths([run_log, *rv64_logs], rv64_markers)

        markers = {
            **rv32_observed,
            **rv64_observed,
        }
        checks = {
            "single_command": len(manifest["commands"]) == 1,
            "returncode_ok": int(run_result["returncode"]) == 0,
            "rv32_markers_ok": all(markers[m] for m in rv32_workload_markers),
            "rv64_boot_ok": markers["OpenSBI"] and markers["Linux version"],
            "required_markers_ok": (
                all(markers[m] for m in rv32_workload_markers)
                and markers["OpenSBI"]
                and markers["Linux version"]
                and markers["Loaded bootloader"]
                and markers["Loaded kernel"]
            ),
            "panic_free": (not markers["Kernel panic"]) and (not markers["panic"]) and (not markers["fatal:"]),
        }

        manifest.update(
            {
                "run_log": str(run_log),
                "terminal_logs_rv32": [str(path) for path in rv32_logs],
                "terminal_logs_rv64": [str(path) for path in rv64_logs],
                "run_result": run_result,
                "markers": markers,
                "checks": checks,
                "validation": {
                    "single_run": True,
                    "single_command": checks["single_command"],
                    "all_passed": all(checks.values()),
                },
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] Manifest: {manifest_path}")
        return 1 if not all(checks.values()) else 0

    if args.target == "riscv32_simple":
        cmd, simple_elf = rv32_simple_command(args, config_path, logs_dir)
        manifest["commands"] = [cmd]
        manifest["simple_elf"] = simple_elf

        if not Path(simple_elf).exists():
            missing.append(f"simple_elf: {simple_elf}")

        if args.dry_run:
            print("[INFO] DRY-RUN mode")
            for item in missing:
                print(f"[WARN] Missing path: {item}")
            print(f"[INFO] command={quoted(cmd)}")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"[OK] Manifest: {manifest_path}")
            return 0

        if missing:
            for item in missing:
                print(f"[ERROR] Missing path: {item}", file=sys.stderr)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            return 2

        run_log = logs_dir / "run_riscv32_simple.log"
        print(f"[INFO] Executing: {quoted(cmd)}")
        run_result = run_one(cmd, run_log, args.timeout_sec)
        terminal_log = logs_dir / "system.platform.terminal"
        stats_path = logs_dir / "stats.txt"
        markers = read_markers_from_paths(
            [run_log, terminal_log],
            [
                "*** Booting Zephyr OS",
                "RISCV32 SIMPLE WORKLOAD START",
                "RISCV32 SIMPLE WORKLOAD DONE",
                "Kernel panic",
                "panic",
            ],
        )
        sim_insts = read_stats_counter(stats_path, "simInsts")
        manifest.update({
            "run_log": str(run_log),
            "terminal_log": str(terminal_log),
            "stats_path": str(stats_path),
            "run_result": run_result,
            "markers": markers,
            "sim_insts": sim_insts,
        })
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[INFO] run_log={run_log}")
        print(f"[INFO] terminal_log={terminal_log}")
        print(f"[OK] Manifest: {manifest_path}")
        return int(run_result["returncode"])

    # riscv32_mixed
    cmd, assignments, workload_markers, role_markers = rv32_mixed_command(args, config_path, logs_dir)
    manifest["commands"] = [cmd]
    manifest["mixed_boot_elf"] = args.mixed_boot_elf
    manifest["workload_assignments"] = assignments
    manifest["workload_markers"] = workload_markers
    manifest["role_markers"] = role_markers

    for name, elf in [
        ("amp_cpu0_elf", args.amp_cpu0_elf),
        ("amp_cpu1_elf", args.amp_cpu1_elf),
        ("smp_elf", args.smp_elf),
    ]:
        if not Path(elf).exists():
            missing.append(f"{name}: {elf}")

    if not args.dry_run:
        try:
            maybe_build_mixed_boot(args)
        except Exception as exc:
            missing.append(f"mixed_boot_build: {exc}")

    if not Path(args.mixed_boot_elf).exists():
        missing.append(f"mixed_boot_elf: {args.mixed_boot_elf}")

    if args.dry_run:
        print("[INFO] DRY-RUN mode")
        for item in missing:
            print(f"[WARN] Missing path: {item}")
        print(f"[INFO] command={quoted(cmd)}")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] Manifest: {manifest_path}")
        return 0

    if missing:
        for item in missing:
            print(f"[ERROR] Missing path: {item}", file=sys.stderr)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return 2

    run_log = logs_dir / "run_riscv32_mixed.log"
    print(f"[INFO] Executing: {quoted(cmd)}")
    run_result = run_one(cmd, run_log, args.timeout_sec)
    terminal_logs = mixed_terminal_logs(logs_dir)
    terminal_log = terminal_logs[0]
    stats_path = logs_dir / "stats.txt"
    terminal_markers = read_markers_from_paths(
        terminal_logs,
        workload_markers,
        allow_interleaved=True,
    )
    workload_and_role_markers = read_markers_from_paths(
        [run_log, *terminal_logs],
        workload_markers + role_markers,
        allow_interleaved=True,
    )
    panic_markers = read_markers_from_paths([run_log, *terminal_logs], ["Kernel panic", "panic"])
    markers = {**workload_and_role_markers, **panic_markers}
    sim_insts = read_stats_counter(stats_path, "simInsts")
    terminal_required_ok = all(terminal_markers[m] for m in workload_markers)
    if (not terminal_required_ok) or (not terminal_log.exists()):
        terminal_required_ok = all(markers[m] for m in workload_markers)

    checks = {
        "single_command": len(manifest["commands"]) == 1,
        "returncode_ok": int(run_result["returncode"]) == 0,
        "required_markers_ok": all(markers[m] for m in workload_markers),
        "terminal_markers_ok": terminal_required_ok,
        "panic_free": (not markers["Kernel panic"]) and (not markers["panic"]),
    }
    role_observations = {m: markers[m] for m in role_markers}
    manifest.update(
        {
            "run_log": str(run_log),
            "terminal_log": str(terminal_log),
            "terminal_logs": [str(path) for path in terminal_logs],
            "stats_path": str(stats_path),
            "run_result": run_result,
            "terminal_markers": terminal_markers,
            "markers": markers,
            "role_observations": role_observations,
            "sim_insts": sim_insts,
            "checks": checks,
            "validation": {
                "single_run": True,
                "single_command": checks["single_command"],
                "all_passed": all(checks.values()),
            },
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Manifest: {manifest_path}")
    return 1 if not all(checks.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
