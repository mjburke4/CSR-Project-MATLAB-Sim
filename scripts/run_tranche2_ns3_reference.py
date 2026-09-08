#!/usr/bin/env python3
"""Build/run unchanged current ns-3 MAC/HOP workflows in an existing engine.

This is source-side execution evidence, not MATLAB execution or aggregate
differential certification. The configured ns-3 engine must already build CSR.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import time


WORKFLOWS = [
    "csr-mac-hop-queue-limit-smoke",
    "csr-mac-ack-queue-smoke",
    "csr-ack-window-smoke",
    "csr-hop-retry-dscp-smoke",
    "csr-hop-dack-hold-smoke",
    "csr-hop-mac-sent-time-smoke",
    "csr-mac-concat-smoke",
    "csr-mac-preamble-selection-smoke",
    "csr-mac-reservation-lifecycle-smoke",
    "csr-mac-slot-parity-smoke",
    "csr-mac-receive-contention-smoke",
    "csr-wireless-overhearing-smoke",
    "csr-hop-mac-link-control-smoke",
    "csr-hop-no-route-relay-smoke",
    "csr-nwk-relay-holdoff-smoke",
    "csr-queue-observation-smoke",
    "csr-opnet-packet-envelope-smoke",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command: list[str], cwd: Path) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "evidence")
    args = parser.parse_args()
    source = args.source_dir.resolve()
    engine = args.engine_dir.resolve()
    output = args.output_dir.resolve()
    logs = output / "tranche-2-ns3-workflows"
    logs.mkdir(parents=True, exist_ok=True)
    source_commit = command_output(["git", "rev-parse", "HEAD"], source)
    engine_commit = command_output(["git", "rev-parse", "HEAD"], engine)
    # Verify the engine's module really is this source, including local edits.
    for file in (source / "model").glob("*"):
        if file.is_file() and sha256(file) != sha256(engine / "contrib/csr/model" / file.name):
            raise RuntimeError(f"Engine module differs from source: {file.name}")
    tracked_edits = command_output(["git", "diff", "HEAD", "--name-only"], source)
    if tracked_edits:
        raise RuntimeError("Reference source must have no tracked local edits")
    for name in WORKFLOWS:
        target = engine / "scratch" / (name + ".cc")
        original = source / (name + ".cc")
        if target.exists():
            if sha256(target) != sha256(original):
                raise RuntimeError(f"Existing scratch source differs: {target}")
        else:
            target.symlink_to(original)
    configure_log = logs / "configure.log"
    with configure_log.open("w") as handle:
        subprocess.run(["cmake", "-S", str(engine), "-B", str(engine / "cmake-cache")],
                       cwd=engine, stdout=handle, stderr=subprocess.STDOUT, check=True)
    build_log = logs / "build.log"
    build_command = ["cmake", "--build", str(engine / "cmake-cache"),
                     "-j", str(args.jobs), "--target"] + ["scratch_" + n for n in WORKFLOWS]
    with build_log.open("w") as handle:
        subprocess.run(build_command, cwd=engine, stdout=handle,
                       stderr=subprocess.STDOUT, check=True)
    results = []
    for name in WORKFLOWS:
        binary = engine / "build/scratch" / ("ns3-dev-" + name + "-debug")
        log = logs / (name + ".log")
        start = time.perf_counter()
        with log.open("w") as handle:
            completed = subprocess.run([str(binary)], cwd=engine, stdout=handle,
                                       stderr=subprocess.STDOUT, timeout=120)
        elapsed = time.perf_counter() - start
        lines = log.read_text().splitlines()
        passes = [line for line in lines if "PASS" in line]
        failures = [line for line in lines if "FAIL" in line]
        passed = completed.returncode == 0 and bool(passes) and not failures
        results.append({
            "name": name, "binary": str(binary.relative_to(engine)),
            "binary_sha256": sha256(binary), "source_sha256": sha256(source / (name + ".cc")),
            "exit_code": completed.returncode, "pass_lines": passes, "fail_lines": failures,
            "passed": passed, "elapsed_seconds": elapsed,
            "log": "evidence/" + str(log.relative_to(output)), "log_sha256": sha256(log),
        })
        print(f"{'PASS' if passed else 'FAIL'} {name} ({elapsed:.3f}s)", flush=True)
    manifest = {
        "schema": "csr-matlab-t2-native-ns3-workflows-v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": source_commit, "ns3_engine_commit": engine_commit,
        "scope": "Actual original native ns-3 MAC/HOP workflows; source-side reference only.",
        "ns3_network_simulation_executed": True, "matlab_executed": False,
        "compiler": command_output(["g++", "--version"], engine).splitlines()[0],
        "cmake_version": command_output(["cmake", "--version"], engine).splitlines()[0],
        "build_configuration": {"build_type": "Debug", "assertions": True,
                                "logging": True, "jobs": args.jobs},
        "configure_log_sha256": sha256(configure_log), "build_log_sha256": sha256(build_log),
        "cmake_cache_sha256": sha256(engine / "cmake-cache/CMakeCache.txt"),
        "results": results, "passed_workflows": sum(row["passed"] for row in results),
        "total_workflows": len(results),
        "limitations": [
            "Focused reference workflows do not validate the MATLAB port.",
            "MATLAB R2025a/R2026a execution and cross-simulator scenario comparison are separate gates.",
            "The complete ns-3 release and 6000-second OPNET aggregate scenario were not rerun.",
        ],
    }
    (output / "tranche-2-ns3-workflows.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
