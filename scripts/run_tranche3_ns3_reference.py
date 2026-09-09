#!/usr/bin/env python3
"""Build/run unchanged current ns-3 NWK/ARL workflows in an existing engine.

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
    "csr-nwk-discovery-ordering-smoke",
    "csr-nwk-autonomous-convergence-smoke",
    "csr-nwk-arl-admission-security-smoke",
    "csr-nwk-arl-routing-stream-smoke",
    "csr-nwk-self-capability-smoke",
    "csr-nwk-grouped-route-propagation-smoke",
    "csr-nwk-residual-routing-retry-smoke",
    "csr-nwk-same-pass-info-coupling-smoke",
    "csr-nwk-legacy-strict-smoke",
    "csr-nwk-hop-integration-smoke",
    "csr-nwk-relay-holdoff-smoke",
    "csr-hop-multidest-routing-smoke",
]

SOURCE_COMMIT = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"


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
    logs = output / "tranche-3-ns3-workflows"
    logs.mkdir(parents=True, exist_ok=True)
    source_commit = command_output(["git", "rev-parse", "HEAD"], source)
    if source_commit != SOURCE_COMMIT:
        raise RuntimeError(f"Expected pinned source {SOURCE_COMMIT}, got {source_commit}")
    engine_commit = command_output(["git", "rev-parse", "HEAD"], engine)
    # Verify the engine's module really is this source, including local edits.
    source_inputs = [source / "CMakeLists.txt"] + sorted((source / "model").glob("*"))
    for file in source_inputs:
        if file.is_file() and sha256(file) != sha256(engine / "contrib/csr" / file.relative_to(source)):
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
    configured = subprocess.run(
        ["cmake", "-S", str(engine), "-B", str(engine / "cmake-cache")],
        cwd=engine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    configure_log.write_text(configured.stdout)
    configured.check_returncode()
    build_log = logs / "build.log"
    build_command = ["cmake", "--build", str(engine / "cmake-cache"),
                     "-j", str(args.jobs), "--target"] + ["scratch_" + n for n in WORKFLOWS]
    built = subprocess.run(build_command, cwd=engine, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
    build_log.write_text(built.stdout)
    built.check_returncode()
    cache = {}
    for line in (engine / "cmake-cache/CMakeCache.txt").read_text().splitlines():
        if "=" in line and not line.startswith(("#", "//")):
            key, value = line.split("=", 1)
            cache[key.split(":", 1)[0]] = value
    results = []
    for name in WORKFLOWS:
        binary = engine / "build/scratch" / ("ns3-dev-" + name + "-debug")
        log = logs / (name + ".log")
        start = time.perf_counter()
        completed = subprocess.run([str(binary)], cwd=engine, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, timeout=120)
        log.write_text(completed.stdout)
        elapsed = time.perf_counter() - start
        lines = log.read_text().splitlines()
        # Retry scenarios deliberately log protocol "FAILED" events. Only
        # the smoke's explicit assertion verdicts classify its outcome.
        passes = [line for line in lines if line.startswith("PASS:")]
        failures = [line for line in lines if line.startswith("FAIL:")]
        protocol_failures = [line for line in lines if "FAILED" in line]
        passed = completed.returncode == 0 and bool(passes) and not failures
        results.append({
            "name": name, "binary": str(binary.relative_to(engine)),
            "binary_sha256": sha256(binary), "source_sha256": sha256(source / (name + ".cc")),
            "exit_code": completed.returncode, "pass_lines": passes, "fail_lines": failures,
            "protocol_failure_lines": protocol_failures,
            "passed": passed, "elapsed_seconds": elapsed,
            "log": "evidence/" + str(log.relative_to(output)), "log_sha256": sha256(log),
        })
        print(f"{'PASS' if passed else 'FAIL'} {name} ({elapsed:.3f}s)", flush=True)
    manifest = {
        "schema": "csr-matlab-t3-native-ns3-workflows-v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": source_commit, "ns3_engine_commit": engine_commit,
        "runner_sha256": sha256(Path(__file__)),
        "scope": ("Actual unchanged native ns-3 NWK/ARL discovery, admission, routing "
                  "serialization, gateway, grouped retry and route recovery workflows; "
                  "source-side reference only."),
        "ns3_network_simulation_executed": True, "matlab_executed": False,
        "compiler": command_output(["g++", "--version"], engine).splitlines()[0],
        "cmake_version": command_output(["cmake", "--version"], engine).splitlines()[0],
        "build_configuration": {
            "build_type": cache.get("CMAKE_BUILD_TYPE"),
            "assertions": cache.get("NS3_ASSERT") == "ON",
            "logging": cache.get("NS3_LOG") == "ON",
            "examples_enabled": cache.get("NS3_EXAMPLES") == "ON",
            "ns3_test_suites_enabled": cache.get("NS3_TESTS") == "ON",
            "jobs": args.jobs,
        },
        "source_inputs_sha256": {
            str(file.relative_to(source)): sha256(file)
            for file in source_inputs if file.is_file()
        },
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
    (output / "tranche-3-ns3-workflows.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
