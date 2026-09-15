#!/usr/bin/env python3
"""Reproduce the campus benchmark and bounded admission/contention references.

The pinned scenario runner is freshly compiled against verified preserved ns-3
libraries. No full engine rebuild, MATLAB execution, or new OPNET run is claimed.
Archived OPNET numerical differences are descriptive; structural failures fail.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module("tranche7_reference_shared", ROOT / "scripts/run_tranche4_ns3_reference.py")
CATALOG = ROOT / "scenarios/benchmarks/catalog.json"
INPUTS = ROOT / "evidence/tranche-7-benchmark-inputs/manifest.json"
CORE = (
    "Generator.Traffic Sent (packets/sec)", "Generator.Traffic Sent (bits/sec)",
    "Generator.Packet Size (bits)", "Sink.Traffic Received (packets/sec)",
    "Sink.Traffic Received (packets)", "Sink.Traffic Received (bits/sec)",
    "Sink.Traffic Received (bits)", "Sink.End-to-End Delay (seconds)",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_record(path: Path, base: Path) -> dict:
    return {"path": path.relative_to(base).as_posix(), "sha256": BASE.digest(path),
            "bytes": path.stat().st_size}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def synthetic_rows(parent: list[dict], recipe: dict, recipe_sha256: str) -> list[dict]:
    """Apply explicit synthetic stimuli while retaining every campus radio field."""
    run = copy.deepcopy(parent[0])
    run.update(scenario=recipe["scenario"], duration_s=str(float(recipe["duration_s"])),
               seed=str(recipe["seed"]), source_sha256=recipe_sha256)
    old_nodes = [row for row in parent if row["record"] == "node"]
    old_flow = next(row for row in parent if row["record"] == "flow")
    rows = [run]
    for index, position in enumerate(recipe["positions_m"]):
        node = copy.deepcopy(old_nodes[0 if index == 0 else 1])
        node.update(node_id=str(index + 1), name=f"CSR_node_{index + 1}",
                    node_type="gateway" if index == 0 else "routable",
                    x_m=str(float(position[0])), y_m=str(float(position[1])),
                    height_m=str(float(position[2])),
                    interarrival_s=str(recipe["flow_interval_s"]),
                    packet_bytes=str(recipe["flow_packet_bytes"]))
        rows.append(node)
    for node in range(2, len(recipe["positions_m"]) + 1):
        flow = copy.deepcopy(old_flow)
        flow.update(flow_src=str(node), flow_interval_s=str(recipe["flow_interval_s"]),
                    flow_start_s=str(float(recipe["flow_start_s"])),
                    flow_packet_bytes=str(recipe["flow_packet_bytes"]),
                    flow_dscp=str(recipe["flow_dscp"]))
        rows.append(flow)
    return rows


def verify_inputs(source: Path, destination: Path) -> dict:
    catalog, inputs = load_json(CATALOG), load_json(INPUTS)
    if catalog["ns3_source_commit"] != BASE.PIN or inputs["ns3_source_commit"] != BASE.PIN:
        raise ValueError("Benchmark catalog/source pin mismatch")
    if catalog["source_archive_sha256"] != inputs["source_archive_sha256"]:
        raise ValueError("Original archive identity mismatch")
    for record in inputs["files"]:
        path = ROOT / record["path"]
        if BASE.digest(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"Original input inventory mismatch: {path}")
        data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        if hashlib.sha256(data).hexdigest() != record["original_sha256"] or len(data) != record["original_bytes"]:
            raise ValueError(f"Original input byte identity mismatch: {path}")
    workflow = load_module("tranche7_upstream_workflow", source / "utils/run-opnet-aggregate-differential.py")
    reproductions = []
    with tempfile.TemporaryDirectory(prefix="csr-tranche7-import-check-") as directory:
        for case in catalog["cases"]:
            path = ROOT / case["scenario_file"]
            if BASE.digest(path) != case["scenario_sha256"]:
                raise ValueError(f"Canonical scenario digest mismatch: {path}")
            parsed = workflow.load_scenario_run(path)
            if (parsed["scenario"], parsed["duration_s"], parsed["seed"], parsed["hop_security_profile"]) != (
                    case["scenario"], case["duration_s"], case["seed"], case["profile_id"]):
                raise ValueError(f"Canonical scenario/catalog configuration mismatch: {path}")
            regenerated = Path(directory) / path.name
            if case["source_kind"] == "archived_opnet":
                command = [sys.executable, str(source / "utils/import-opnet-scenario.py"),
                           str(ROOT / case["opnet_source_file"]), str(regenerated),
                           "--infer-gateway-flows", "--application-profile", parsed["application_profile"],
                           "--mac-profile", parsed["mac_profile"], "--hop-security-profile", case["profile_id"]]
                subprocess.run(command, check=True, capture_output=True, text=True)
            elif case["source_kind"] == "synthetic_diagnostic":
                recipe_path = ROOT / case["recipe_file"]
                recipe = load_json(recipe_path)
                parent = recipe_path.parent / recipe["parent_scenario"]
                if BASE.digest(parent) != recipe["parent_scenario_sha256"]:
                    raise ValueError("Synthetic parent digest mismatch")
                rows = synthetic_rows(BASE.csv_rows(parent), recipe, BASE.digest(recipe_path))
                write_csv(regenerated, rows)
                command = ["synthetic_rows", case["recipe_file"], recipe["parent_scenario"]]
            else:
                raise ValueError("Unsupported benchmark source kind")
            if BASE.digest(regenerated) != BASE.digest(path):
                raise ValueError(f"Regenerated scenario differs from canonical bytes: {path}")
            reproductions.append({"case_id": case["case_id"], "command": command,
                                  "regenerated_sha256": BASE.digest(regenerated), "exact_match": True})
    record = {"schema": "csr-tranche7-benchmark-input-verification-v1", "status": "passed",
              "input_manifest_sha256": BASE.digest(INPUTS), "catalog_sha256": BASE.digest(CATALOG),
              "original_files_verified": len(inputs["files"]), "scenario_reproductions": reproductions}
    BASE.write_json(destination / "input-verification.json", record)
    return catalog


def run_stage(command: list[str], logfile: Path, timeout: int) -> dict:
    started = time.monotonic()
    with logfile.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, text=True)
    return {"command": command, "exit_code": result.returncode,
            "elapsed_seconds": time.monotonic() - started, "log": logfile.name}


def validate_workflow_completion(record: dict, exit_code: int) -> None:
    """Only an actual completed numerical comparison may return nonzero one."""
    if exit_code not in (0, 1) or record.get("status") not in (
            "selected_comparison_passed", "selected_comparison_failed"):
        raise ValueError("Historical workflow did not reach a completed comparison")
    stages = record.get("stages", {})
    if any(stages.get(name, {}).get("exit_code") != 0
           for name in ("extract_opnet", "run_ns3", "aggregate_ns3")):
        raise ValueError("Historical workflow extraction/execution/aggregation failed")
    if stages.get("compare", {}).get("exit_code") != exit_code:
        raise ValueError("Historical comparison status inconsistent with process result")


def normalized_sidecar(case: dict, directory: Path, source: str) -> dict:
    aggregate = directory / f"{source}-aggregates.csv"
    rows = BASE.csv_rows(aggregate)
    digests = {row["source_file_sha256"] for row in rows}
    if len(digests) != 1 or any(row["source"] != source or row["scenario"] != case["scenario"] for row in rows):
        raise ValueError("Aggregate source/scenario/input digest mismatch")
    statistics = {row["statistic"] for row in rows}
    if not set(CORE).issubset(statistics):
        raise ValueError("Aggregate omitted a required application series")
    original = directory / ("ns3-aggregates.provenance.json" if source == "ns3" else "opnet-extract.json")
    sidecar = {
        "schema": "csr-benchmark-source-provenance-v1", "source": source,
        "scenario": case["scenario"], "scenario_sha256": case["scenario_sha256"],
        "profile_id": case["profile_id"], "source_file_sha256": digests.pop(),
        "source_commit": BASE.PIN if source == "ns3" else None,
        "window": {"start_time_s": 0, "stop_time_s": case["duration_s"],
                   "bucket_width_s": case["bucket_width_s"],
                   "bucket_count": round(case["duration_s"] / case["bucket_width_s"]),
                   "start_endpoint": "inclusive", "stop_endpoint": "exclusive"},
        "output": {"path": aggregate.name, "sha256": BASE.digest(aggregate)},
        "upstream_provenance": file_record(original, directory),
        "excluded_extra_statistics": sorted(statistics - set(CORE)),
        "opnet_runtime_executed": False, "matlab_runtime_executed": False,
        "source_kind": case["source_kind"],
    }
    BASE.write_json(directory / f"{source}-benchmark.provenance.json", sidecar)
    return sidecar


def compress(path: Path) -> dict:
    """Preserve complete raw bytes with deterministic gzip and both identities."""
    record = {"original_name": path.name, "original_sha256": BASE.digest(path),
              "original_bytes": path.stat().st_size}
    target = path.with_name(path.name + ".gz")
    with path.open("rb") as source, target.open("wb") as sink:
        with gzip.GzipFile(filename="", fileobj=sink, mode="wb", mtime=0) as zipped:
            shutil.copyfileobj(source, zipped)
    with gzip.open(target, "rb") as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    if value.hexdigest() != record["original_sha256"]:
        raise ValueError("Compressed evidence does not reproduce original bytes")
    path.unlink()
    return {**record, **file_record(target, target.parent)}


def execute_case(case: dict, source: Path, output: Path, runner: Path, timeout: int) -> dict:
    destination = output / case["case_id"]
    workflow = load_module("tranche7_upstream_execution", source / "utils/run-opnet-aggregate-differential.py")
    record = {"schema": "csr-tranche7-benchmark-reference-case-v1", "case_id": case["case_id"],
              "status": "running", "started_utc": BASE.utc_now(), "case": case,
              "runner_sha256": BASE.digest(runner), "ns3_source_commit": BASE.PIN,
              "full_ns3_rebuild_performed": False, "matlab_executed": False,
              "opnet_executed": False, "stages": {}, "compressed_artifacts": []}
    try:
        scenario = ROOT / case["scenario_file"]
        parsed = workflow.load_scenario_run(scenario)
        if case["opnet_available"]:
            ov, probe = ROOT / case["opnet_ov_file"], ROOT / case["probe_definition_file"]
            command = [sys.executable, "-B", "-I", str(source / "utils/run-opnet-aggregate-differential.py"),
                       "--scenario", str(scenario), "--runner", str(runner), "--opnet-ov", str(ov),
                       "--probe-definition", str(probe), "--expected-opnet-ov-sha256", BASE.digest(ov),
                       "--expected-probe-definition-sha256", BASE.digest(probe), "--output-dir", str(destination)]
            execution = run_stage(command, output / (case["case_id"] + "-workflow.log"), timeout)
            historical = load_json(destination / "aggregate-run-manifest.json")
            validate_workflow_completion(historical, execution["exit_code"])
            record["stages"] = historical["stages"]
            record["workflow_process"] = execution
            record["opnet_numeric_parity_passed"] = execution["exit_code"] == 0
        else:
            destination.mkdir()
            command = [str(runner), f"--scenario={scenario}", f"--trace={destination / 'ns3-trace.csv'}",
                       f"--appDiagnostics={destination / 'app-admission-diagnostics.csv'}",
                       f"--stop={case['duration_s']}", "--flowLimit=0", "--dutyCycling=1",
                       "--opnetAlignedDutyCycle=1", "--gatewayDiscovery=1", "--opnetAppGating=1",
                       "--aggregateTraceOnly=1", "--quietModelLogs=1"]
            record["stages"]["run_ns3"] = run_stage(command, destination / "ns3-run.log", timeout)
            if record["stages"]["run_ns3"]["exit_code"] != 0:
                raise ValueError("Synthetic benchmark ns-3 runner failed")
            command = [sys.executable, "-B", "-I", str(source / "utils/aggregate-ns3-trace.py"),
                       str(destination / "ns3-trace.csv"), str(destination / "ns3-aggregates.csv"),
                       "--scenario", case["scenario"], "--bucket-width", str(case["bucket_width_s"]),
                       "--stop-time", str(case["duration_s"]), "--legacy-trace-size-exclusion-bits", "0",
                       "--require-zero-size-mismatches", "--provenance", str(destination / "ns3-aggregates.provenance.json")]
            record["stages"]["aggregate_ns3"] = run_stage(command, destination / "ns3-aggregate.log", timeout)
            if record["stages"]["aggregate_ns3"]["exit_code"] != 0:
                raise ValueError("Synthetic benchmark aggregation failed")
        record["application_admission_totals"] = workflow.validate_app_admission_diagnostics(
            destination / "app-admission-diagnostics.csv", case["scenario"], parsed["application_profile"], parsed["flows"])
        record["exact_sequence_validation"] = workflow._load_and_validate_ns3_provenance(
            destination / "ns3-aggregates.provenance.json", destination / "ns3-trace.csv",
            destination / "ns3-aggregates.csv", case["scenario"])
        record["normalized_sidecars"] = [normalized_sidecar(case, destination, "ns3")]
        if case["opnet_available"]:
            record["normalized_sidecars"].append(normalized_sidecar(case, destination, "opnet"))
        record["status"] = "completed"
    except Exception as error:
        record.update(status="failed", error=str(error))
        raise
    finally:
        destination.mkdir(exist_ok=True)
        for path in sorted(destination.glob("*-trace.csv")):
            record["compressed_artifacts"].append(compress(path))
        record["completed_utc"] = BASE.utc_now()
        record["files"] = [file_record(path, destination) for path in sorted(destination.iterdir())
                           if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(destination / "manifest.json", record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ns3-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--build-directory", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    source, build, output = args.source.resolve(), args.ns3_build.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be new or empty; reference evidence is never overwritten")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"schema": "csr-tranche7-benchmark-reference-suite-v1", "status": "running",
               "started_utc": BASE.utc_now(), "ns3_source_commit": BASE.PIN,
               "matlab_executed": False, "opnet_executed": False, "full_ns3_rebuild_performed": False,
               "cases": []}
    try:
        BASE.check_source(source, build)
        catalog = verify_inputs(source, output)
        if set(args.case) - {case["case_id"] for case in catalog["cases"]}:
            raise ValueError("Requested case is absent from the runnable catalog")
        cases = [case for case in catalog["cases"] if (case["case_id"] in args.case if args.case else case["default"])]
        paths = [Path(__file__).resolve(), ROOT / "scripts/run_tranche4_ns3_reference.py", CATALOG, INPUTS]
        paths += sorted((ROOT / "scenarios/benchmarks").glob("*"))
        paths += [ROOT / record["path"] for record in load_json(INPUTS)["files"]]
        paths += sorted((source / "utils").glob("*.py"))
        inputs = {**BASE.input_snapshot(source, build), **{str(path): BASE.digest(path) for path in paths if path.is_file()}}
        directory = (args.build_directory or Path(tempfile.mkdtemp(prefix="csr-tranche7-reference-"))).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        runner = directory / "csr-opnet-scenario-runner"
        command = BASE.compile_runner(source, build, runner, args.compiler)
        compiled = run_stage(command, output / "compile.log", 300)
        build_record = {"schema": "csr-tranche7-benchmark-reference-build-v1", **compiled,
                        "ns3_source_commit": BASE.PIN, "input_sha256": inputs,
                        "compiler_version": BASE.checked([args.compiler, "--version"]),
                        "standalone_runner_compiled": True, "full_ns3_rebuild_performed": False,
                        "source_headers_match_preserved_build": True,
                        "library_provenance_limit": "Preserved libraries are hash-bound and CSR headers match clean pinned source; no full engine rebuild performed."}
        if runner.exists():
            build_record["runner_sha256"] = BASE.digest(runner)
        BASE.write_json(output / "build.json", build_record)
        if compiled["exit_code"]:
            raise ValueError("Standalone scenario runner compilation failed")
        for case in cases:
            record = execute_case(case, source, output, runner, args.timeout_seconds)
            summary["cases"].append({"case_id": case["case_id"], "status": record["status"],
                                     "manifest": case["case_id"] + "/manifest.json",
                                     "manifest_sha256": BASE.digest(output / case["case_id"] / "manifest.json"),
                                     "application_admission_totals": record["application_admission_totals"],
                                     "exact_sequence_validation": record["exact_sequence_validation"]})
            print(case["case_id"] + ": completed; " + json.dumps(record["application_admission_totals"]), flush=True)
        BASE.check_source(source, build)
        if any(BASE.digest(Path(path)) != digest for path, digest in inputs.items()):
            raise ValueError("Reference source, build, tools, or benchmark inputs changed during execution")
        summary.update(status="completed", source_files_stable=True, input_files_stable=True,
                       build_manifest_sha256=BASE.digest(output / "build.json"))
    except Exception as error:
        summary.update(status="failed", error=str(error))
        print(f"Benchmark reference failed: {error}", file=sys.stderr)
        return 1
    finally:
        summary["completed_utc"] = BASE.utc_now()
        summary["files"] = [file_record(path, output) for path in sorted(output.iterdir())
                            if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(output / "manifest.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
