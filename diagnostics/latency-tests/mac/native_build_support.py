#!/usr/bin/env python3
"""Run shared CSR scenarios with the frozen ns-3 runner and preserved libraries.

Only the standalone scenario-runner translation unit is freshly compiled. The
ns-3 engine and CSR shared libraries are preserved build products, not rebuilt.
This utility neither edits the reference checkout nor runs MATLAB.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone


PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
REPOSITORY = Path(__file__).resolve().parents[1]
RUN_OPTIONS = {
    "opnetAppGating": False,
    "stochasticSyncThreshold": False,
    "dutyCycling": True,
    "opnetAlignedDutyCycle": True,
    "gatewayDiscovery": True,
}
MODULES = ("csr", "spectrum", "buildings", "propagation", "mobility",
           "antenna", "network", "stats", "core")
PROFILES = {
    "application_profile": "current-send-only",
    "mac_profile": "current-fine-free-slot",
    "hop_security_profile": "production-pairwise16",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def checked(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames
        if not names or len(names) != len(set(names)):
            raise ValueError(f"Invalid or duplicate CSV headers: {path}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Nonrectangular CSV: {path}")
    return rows


def validate_scenario(path: Path, flow_limit: int) -> dict:
    """Check the supported shared profile before invoking the source runner."""
    if b"\r" in path.read_bytes():
        raise ValueError("The frozen C++ CSV reader requires LF line endings; inputs are never normalized silently")
    if type(flow_limit) is not int or flow_limit < 1:
        raise ValueError("flow_limit must be a positive integer, per flow")
    rows = csv_rows(path)
    if not rows or any(row.get("schema") != "csr-opnet-scenario-v1" for row in rows):
        raise ValueError("Unsupported or empty scenario")
    if any(row.get("record") not in ("run", "node", "flow") for row in rows):
        raise ValueError("Unsupported scenario record")
    runs = [row for row in rows if row["record"] == "run"]
    nodes = [row for row in rows if row["record"] == "node"]
    flows = [row for row in rows if row["record"] == "flow"]
    if len(runs) != 1 or not nodes or not flows:
        raise ValueError("A shared case needs one run, nodes, and explicit flows")
    run = runs[0]
    for key, value in PROFILES.items():
        if run.get(key) != value:
            raise ValueError(f"Unsupported shared {key}: {run.get(key)}")
    if run.get("ack_envelope_profile", "") not in ("", PROFILES["hop_security_profile"]):
        raise ValueError("ACK and HOP security profiles disagree")
    if run.get("source_executable_sha256") or float(run["tmm"]) != 0:
        raise ValueError("Historical executable profiles and terrain are outside this bridge")
    if run.get("reservation_control_start_s", "") not in ("", "0"):
        raise ValueError("Controlled reservation overrides are outside this bridge")
    duration = float(run["duration_s"])
    seed = int(run["seed"])
    if not math.isfinite(duration) or duration <= 0 or not 1 <= seed <= 4294944442:
        raise ValueError("Invalid duration or ns-3 RNG seed")
    ids = [int(row["node_id"]) for row in nodes]
    if len(ids) != len(set(ids)) or any(i < 0 or i >= 16777215 for i in ids):
        raise ValueError("Invalid or duplicate concrete node ID")
    if sum(row["node_type"] == "gateway" for row in nodes) != 1:
        raise ValueError("Shared discovery requires exactly one gateway")
    common = ("height_m", "min_speed_kbps", "max_speed_kbps", "min_power_dbm",
              "max_power_dbm", "link_margin_db")
    for field in common:
        values = [float(row[field]) for row in nodes]
        if any(not math.isfinite(value) for value in values) or len(set(values)) != 1:
            raise ValueError(f"Shared bridge requires uniform finite {field}")
    for node in nodes:
        if node["node_type"] not in ("gateway", "routable", "ordinary"):
            raise ValueError("Unsupported node type")
        if node.get("forced_reservation_slot"):
            raise ValueError("Forced reservation slots are outside this bridge")
        rate = float(node["min_speed_kbps"])
        if rate not in (8, 16, 32, 64, 128, 500, 1000) or rate != float(node["max_speed_kbps"]):
            raise ValueError("Shared cases require a fixed operational rate")
        if float(node["min_power_dbm"]) != float(node["max_power_dbm"]):
            raise ValueError("Shared cases require fixed transmit power")
        for field in ("min_power_dbm", "max_power_dbm", "link_margin_db"):
            value = float(node[field]) * 10
            if not math.isclose(value, round(value), abs_tol=1e-9, rel_tol=0):
                raise ValueError(f"{field} must be representable in 0.1 dB")
        if float(node["height_m"]) < 0 or not 0 <= float(node["ecc_threshold"]) <= 1:
            raise ValueError("Invalid antenna height or ECC fraction")
    pairs = set()
    for flow in flows:
        pair = int(flow["flow_src"]), int(flow["flow_dst"])
        if pair[0] == pair[1] or any(i not in ids for i in pair) or pair in pairs:
            raise ValueError("Flows need distinct known endpoints and unique source/destination pairs")
        pairs.add(pair)
        if flow.get("flow_destination_mode") != "fixed":
            raise ValueError("Only explicit fixed destinations are supported")
        if not 0 <= int(flow["flow_dscp"]) <= 7:
            raise ValueError("Source DSCP must be in 0..7")
        if not 15 <= int(flow["flow_packet_bytes"]) <= 65550:
            raise ValueError("Configured bytes must map to a 0..65535-byte MATLAB payload")
        start, interval = float(flow["flow_start_s"]), float(flow["flow_interval_s"])
        last = start + (flow_limit - 1) * interval
        if not all(math.isfinite(x) for x in (start, interval, last)) or start < 0 or interval <= 0:
            raise ValueError("Invalid flow schedule")
        if last >= duration:
            raise ValueError("Every flow must finish generating strictly before stop time")
    return {"run": run, "nodes": nodes, "flows": flows}


def input_snapshot(source: Path, build: Path) -> dict[str, str]:
    paths = [source / "csr-opnet-scenario-runner.cc"]
    paths += sorted((source / "model").glob("csr-*"))
    paths += sorted((build / "include" / "ns3").glob("csr-*.h"))
    paths += [resolved_header(path) for path in sorted((build / "include" / "ns3").glob("csr-*.h"))]
    paths += [build / "lib" / f"libns3-dev-{name}-debug.so" for name in MODULES]
    return {str(path): digest(path) for path in paths if path.is_file()}


def resolved_header(path: Path) -> Path:
    """CMake may install a one-line include shim instead of copying a header."""
    if not path.is_file():
        return path
    if path.stat().st_size < 4096:
        match = re.fullmatch(r'\s*#include\s+"([^"\n]+)"\s*', path.read_text(encoding="utf-8"))
        if match:
            return (path.parent / match[1]).resolve()
    return path.resolve()


def check_source(source: Path, build: Path) -> None:
    if checked(["git", "rev-parse", "HEAD"], source) != PIN:
        raise ValueError(f"Reference source must remain pinned to {PIN}")
    if checked(["git", "status", "--porcelain", "--untracked-files=no"], source):
        raise ValueError("Reference checkout has tracked modifications")
    for header in sorted((source / "model").glob("csr-*.h")):
        installed = build / "include" / "ns3" / header.name
        if not installed.is_file() or digest(header) != digest(resolved_header(installed)):
            raise ValueError(f"Preserved build header differs from pinned source: {header.name}")
    for name in MODULES:
        if not (build / "lib" / f"libns3-dev-{name}-debug.so").is_file():
            raise ValueError(f"Preserved debug shared library missing: {name}")


def compile_runner(source: Path, build: Path, destination: Path, compiler: str) -> list[str]:
    library = str(build / "lib")
    return [compiler, "-std=c++23", "-g", "-DNS3_ASSERT_ENABLE", "-DNS3_BUILD_PROFILE_DEBUG",
            "-DNS3_LOG_ENABLE", "-DSTACKTRACE_LIBRARY_IS_LINKED=1", "-D__LINUX__",
            "-I" + str(build / "include"), str(source / "csr-opnet-scenario-runner.cc"),
            "-L" + library, "-Wl,-rpath," + library, "-Wl,--no-as-needed",
            "-lns3-dev-csr-debug", "-Wl,--as-needed",
            *[f"-lns3-dev-{name}-debug" for name in MODULES[1:]],
            "-lstdc++exp", "-o", str(destination)]


def file_record(path: Path, base: Path) -> dict:
    result = {"path": path.relative_to(base).as_posix(), "sha256": digest(path)}
    if path.suffix == ".csv":
        try:
            result["row_count"] = len(csv_rows(path))
        except (ValueError, csv.Error, UnicodeError) as error:
            # Preserve failure evidence even when the failed output is malformed.
            result["csv_error"] = str(error)
    return result


def execute_case(case: dict, catalog_dir: Path, output: Path, runner: Path,
                 source: Path, build: Path, inputs: dict, build_sha256: str) -> dict:
    name = case["name"]
    if not isinstance(name, str) or not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in name):
        raise ValueError("Invalid shared case name")
    destination = output / name
    destination.mkdir()
    manifest = {
        "schema": "csr-matlab-ns3-reference-case-v1", "case": name,
        "status": "running", "started_utc": utc_now(), "ns3_source_commit": PIN,
        "execution_completed": False, "source_files_stable": False,
        "matlab_executed": False, "run_options": RUN_OPTIONS.copy(),
        "flow_limit": case["flow_limit"], "extension": case["extension"],
        "build_manifest_sha256": build_sha256, "runner_sha256": digest(runner),
        **PROFILES,
    }
    command = []
    try:
        scenario = (catalog_dir / case["path"]).resolve()
        scenario.relative_to(catalog_dir.resolve())
        contract = validate_scenario(scenario, case["flow_limit"])
        high_rate = any(float(node["max_speed_kbps"]) > 128 for node in contract["nodes"])
        if type(case["extension"]) is not bool or high_rate != case["extension"]:
            raise ValueError("High-rate extension flag must agree with node rates")
        shutil.copyfile(scenario, destination / "scenario.csv")
        scenario_hash = digest(scenario)
        manifest["scenario_sha256"] = scenario_hash
        command = [str(runner), "--scenario=" + str(destination / "scenario.csv"),
                   "--trace=" + str(destination / "trace.csv"),
                   "--appDiagnostics=" + str(destination / "app_diagnostics.csv"),
                   *[f"--{key}={int(value)}" for key, value in RUN_OPTIONS.items()],
                   "--flowLimit=" + str(case["flow_limit"]), "--quietModelLogs=1",
                   "--aggregateTraceOnly=0", "--admissionTrace=1"]
        manifest["command"] = command
        started = time.monotonic()
        execution = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (destination / "run.log").write_text(execution.stdout + execution.stderr, encoding="utf-8")
        manifest["elapsed_seconds"] = time.monotonic() - started
        manifest["exit_code"] = execution.returncode
        if execution.returncode:
            raise RuntimeError(f"Reference runner exited {execution.returncode}")
        if "CSR differential scenario complete:" not in execution.stdout:
            raise RuntimeError("Reference runner omitted completion marker")
        trace = csv_rows(destination / "trace.csv")
        if not trace or any(row["schema"] != "csr-differential-trace-v1" for row in trace):
            raise ValueError("Missing or invalid canonical trace")
        if [int(row["event_index"]) for row in trace] != list(range(len(trace))):
            raise ValueError("Canonical event indices are not contiguous")
        expected = case["flow_limit"] * len(contract["flows"])
        sent = [row for row in trace if row["event"] == "app_send"]
        diagnostics = csv_rows(destination / "app_diagnostics.csv")
        if len(sent) != expected or sum(int(row["admitted"]) for row in diagnostics) != expected:
            raise ValueError("Source did not generate every configured fixed-flow application")
        stable = inputs == input_snapshot(source, build) and scenario_hash == digest(scenario)
        stable = stable and scenario_hash == digest(destination / "scenario.csv")
        stable = stable and manifest["runner_sha256"] == digest(runner)
        if not stable:
            raise ValueError("Reference inputs changed during execution")
        manifest.update(status="completed", execution_completed=True, source_files_stable=True)
        manifest["observations"] = {
            "app_send": len(sent),
            "nwk_delivery": sum(row["event"] == "nwk_delivery" for row in trace),
            "tx_start": sum(row["event"] == "tx_start" for row in trace),
            "rx_accept": sum(row["event"] == "rx_accept" for row in trace),
            "rx_drop": sum(row["event"] == "rx_drop" for row in trace),
        }
    except Exception as error:
        manifest.update(status="failed", error=str(error), command=command)
        raise
    finally:
        manifest["completed_utc"] = utc_now()
        manifest["files"] = [file_record(destination / name, destination) for name in
                             ("scenario.csv", "trace.csv", "app_diagnostics.csv", "run.log")
                             if (destination / name).is_file()]
        write_json(destination / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--ns3-build", required=True, type=Path,
                        help="ns-3 engine root or its build directory")
    parser.add_argument("--output", required=True, type=Path,
                        help="New or empty evidence directory; existing evidence is never overwritten")
    parser.add_argument("--catalog", type=Path, default=REPOSITORY / "scenarios/shared/catalog.json")
    parser.add_argument("--case", action="append", default=[], help="Optional selected case name; repeatable")
    parser.add_argument("--runner", type=Path, help="Use an existing runner and record its hash; no fresh build claim")
    parser.add_argument("--build-directory", type=Path, help="Optional scratch directory for the standalone binary")
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args(argv)
    source, build, output = args.source.resolve(), args.ns3_build.resolve(), args.output.resolve()
    if not (build / "include").is_dir():
        build = build / "build"
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"schema": "csr-matlab-ns3-reference-suite-v1", "status": "running",
               "started_utc": utc_now(), "ns3_source_commit": PIN, "matlab_executed": False,
               "full_ns3_rebuild_performed": False, "cases": []}
    try:
        check_source(source, build)
        inputs = input_snapshot(source, build)
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        if catalog.get("schema") != "csr-matlab-shared-scenario-catalog-v1":
            raise ValueError("Unsupported shared scenario catalog")
        cases = catalog["cases"]
        names = [case["name"] for case in cases]
        if len(names) != len(set(names)) or not cases:
            raise ValueError("Empty catalog or duplicate case names")
        if set(args.case) - set(names):
            raise ValueError("Requested case is absent from catalog")
        if args.case:
            cases = [case for case in cases if case["name"] in args.case]
        runner = args.runner.resolve() if args.runner else (
            (args.build_directory or output / "_build").resolve() / "csr-opnet-scenario-runner")
        build_record = {
            "schema": "csr-matlab-ns3-reference-build-v1", "ns3_source_commit": PIN,
            "standalone_runner_compiled": args.runner is None,
            "full_ns3_rebuild_performed": False, "matlab_executed": False,
            "library_provenance": "Preserved shared libraries; exact hashes recorded. No fresh engine/CSR library compilation.",
            "input_files_sha256": inputs, "source_headers_match_preserved_build": True,
            "runner_path": str(runner), "orchestrator_sha256": digest(Path(__file__)),
            "catalog_sha256": digest(args.catalog), "compile_command": [],
        }
        if args.runner is None:
            runner.parent.mkdir(parents=True, exist_ok=True)
            if runner.exists():
                raise ValueError("Standalone output binary already exists; select a new build directory")
            command = compile_runner(source, build, runner, args.compiler)
            build_record["compile_command"] = command
            build_record["compiler"] = checked([args.compiler, "--version"]).splitlines()[0]
            execution = subprocess.run(command, capture_output=True, text=True, timeout=300)
            (output / "compile.log").write_text(execution.stdout + execution.stderr, encoding="utf-8")
            build_record["compile_exit_code"] = execution.returncode
            if execution.returncode:
                write_json(output / "build.json", build_record)
                raise RuntimeError(f"Standalone compilation failed: {execution.stderr[-2000:]}")
        if not runner.is_file():
            raise ValueError("Reference runner is missing")
        build_record["runner_sha256"] = digest(runner)
        write_json(output / "build.json", build_record)
        for case in cases:
            result = execute_case(case, args.catalog.resolve().parent, output, runner,
                                  source, build, inputs, digest(output / "build.json"))
            summary["cases"].append({"name": case["name"], "status": result["status"],
                                     "manifest": case["name"] + "/manifest.json",
                                     "manifest_sha256": digest(output / case["name"] / "manifest.json"),
                                     "observations": result["observations"]})
            print(f"{case['name']}: completed; {result['observations']}")
        check_source(source, build)
        if inputs != input_snapshot(source, build):
            raise ValueError("Reference source/build inputs changed during the suite")
        summary["status"] = "completed"
        summary["source_files_stable"] = True
    except Exception as error:
        summary.update(status="failed", error=str(error))
        print(f"Reference validation failed: {error}", file=sys.stderr)
        return 1
    finally:
        summary["completed_utc"] = utc_now()
        if (output / "build.json").is_file():
            summary["build_manifest_sha256"] = digest(output / "build.json")
        write_json(output / "manifest.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
