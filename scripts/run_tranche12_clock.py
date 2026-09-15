#!/usr/bin/env python3
"""Compile/run the six production-MAC clock microcases on a verified clean build."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

from run_tranche4_ns3_reference import MODULES, PIN, compile_runner


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def included_header(path, engine):
    # CMake generates one-line include forwarding files rather than symlinks.
    match = re.fullmatch(r'#include "([^"\n]+)"\s*', path.read_text())
    if match:
        target = Path(match[1]).resolve()
        target.relative_to(engine.resolve())
        return target
    return path


def write_manifest(output):
    expected = {"build.log", "checks.csv", "events.csv", "run.log", "summary.json"}
    entries = {p.name for p in output.iterdir()}
    if entries - {"manifest.json"} != expected or any(
            not (output / name).is_file() or (output / name).is_symlink()
            for name in expected):
        raise ValueError("Clock reference contains missing, extra, or unsafe artifacts")
    manifest = {"schema": "csr-tranche12-clock-reference-files-v1",
                "files": {name: sha(output / name) for name in sorted(expected)}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "build", "work", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--compiler", default="/usr/bin/g++")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    source, build, work, output = [p.resolve() for p in
                                  (args.source, args.build, args.work, args.output)]
    plan_path = root / "scenarios/clock/plan.json"
    plan = json.loads(plan_path.read_text())
    fixed = {"schema": "csr-tranche12-clock-input-v1", "source_pin": PIN,
             "cases": ["tie_early", "tie_late", "before", "after", "continuous", "quantized"],
             "mac_epoch_ns": 1699501000, "boundary_ns": 2011501000,
             "slot_ns": 13000000, "free_slot": 16, "neighbor_slot": 16,
             "slot_profile": "hist-2014-next-tslot-modulo-probe", "active_nodes": 3, "slot_range": 31,
             "enqueue_ns": 1699501000, "early_arm_ns": 1989000000,
             "late_arm_ns": 2011500998, "neighbor_reset_ns": 2011500995,
             "settled_ns": 2011501002, "reconstructed_tx_seconds": 1.989,
             "wire_payload_bytes": 48, "rate_kbps": 128, "preamble": "short",
             "propagation_seconds": .000001}
    if set(plan) != set(fixed) | {"scope"} or any(plan[k] != v for k, v in fixed.items()):
        raise ValueError("Unsupported fixed-v1 clock plan")
    for target in (work, output):
        if target.exists() and any(target.iterdir()):
            raise ValueError(f"Use an empty directory: {target}")
        target.mkdir(parents=True, exist_ok=True)
    clean_path = root / "evidence/tranche-11-native-build.json"
    clean = json.loads(clean_path.read_text())
    if clean["source_commit"] != PIN or clean["status"] != "passed":
        raise ValueError("Clean build is not the pinned accepted build")
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != PIN:
        raise ValueError("Source checkout pin mismatch")
    subprocess.run(["git", "-C", str(source), "diff", "--exit-code", "HEAD", "--", "model"], check=True)
    engine_commit = subprocess.check_output(
        ["git", "-C", str(build.parent), "rev-parse", "HEAD"], text=True).strip()
    if engine_commit != clean["engine_commit"]:
        raise ValueError("Engine checkout pin mismatch")
    subprocess.run(["git", "-C", str(build.parent), "diff", "--exit-code", "HEAD", "--", "src"], check=True)
    library_hashes = {p["path"].split("/")[-1]: p["sha256"] for p in clean["libraries"]}
    for name in MODULES:
        library = build / "lib" / f"libns3-dev-{name}-debug.so"
        if sha(library) != library_hashes[library.name]:
            raise ValueError(f"Clean library hash mismatch: {name}")
    headers = {}
    for header in sorted((source / "model").glob("csr-*.h")):
        included = build / "include/ns3" / header.name
        if sha(header) != sha(included_header(included, build.parent)):
            raise ValueError(f"Included production header differs from pinned source: {header.name}")
        headers["model/" + header.name] = sha(header)
    fixture = root / "scripts/ns3/tranche12_clock.cc"
    command = compile_runner(source, build, work / "clock", args.compiler)
    command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(fixture)
    compiled = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / "build.log").write_bytes(compiled.stdout)
    if compiled.returncode:
        raise RuntimeError("Clock compile failed; inspect build.log")
    executed = subprocess.run([str(work / "clock"), str(output)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=30)
    (output / "run.log").write_bytes(executed.stdout)
    if executed.returncode:
        raise RuntimeError("Native clock contract failed; inspect events/checks/run.log")
    events, checks = read(output / "events.csv"), read(output / "checks.csv")
    if len(events) != 18 or len(checks) != 72 or any(r["pass"] != "1" for r in checks):
        raise ValueError("Native clock output did not complete the fixed contract")
    for path, value in headers.items():
        if sha(source / path) != value or sha(included_header(build / "include/ns3" / Path(path).name, build.parent)) != value:
            raise ValueError("Production source changed during native clock execution")
    for name, value in library_hashes.items():
        if sha(build / "lib" / name) != value:
            raise ValueError("Clean library changed during native clock execution")
    summary = {
        "schema": "csr-tranche12-clock-native-v1", "status": "passed",
        "generated_utc": datetime.now(timezone.utc).isoformat(), "source_commit": PIN,
        "engine_commit": clean["engine_commit"], "source_headers": headers,
        "shared_libraries": library_hashes, "clean_build_sha256": sha(clean_path),
        "scheduler_header_sha256": sha(included_header(build / "include/ns3/scheduler.h", build.parent)),
        "fixture_sources": {str(p.relative_to(root)): sha(p) for p in
                            (fixture, Path(__file__).resolve(), root / "scripts/run_tranche4_ns3_reference.py")},
        "input_path": "scenarios/clock/plan.json", "input_sha256": sha(plan_path),
        "compiler_command": command, "compiler_exit_code": compiled.returncode,
        "binary_sha256": sha(work / "clock"), "execution_exit_code": executed.returncode,
        "case_count": 6, "event_count": 18, "checkpoint_count": 72, "failed_count": 0,
        "native_time_resolution": "integer nanoseconds", "production_source_unchanged": True,
        "engine_tracked_sources_unchanged": True,
        "native_overlay": False, "matlab_executed": False,
        "scope": plan["scope"],
        "expected_matlab_residual": {
            "case": "continuous", "event_rows": 3, "counter_fields": 4,
            "shared_integer_cases_expected_to_match": 5,
            "reason": "Reconstructed continuous ingress is one binary64 ULP after the integer-anchored MAC tick."
        }
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_manifest(output)
    print(json.dumps({"status": "passed", "events": 18, "checks": 72,
                      "manifest_sha256": sha(output / "manifest.json")}))


if __name__ == "__main__":
    main()
