#!/usr/bin/env python3
"""Compile/run isolated liveness contracts against unchanged pinned CSR source."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess

from run_tranche4_ns3_reference import (
    PIN, check_source, checked, compile_runner, digest, input_snapshot, utc_now,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--ns3-build", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--build-directory", required=True, type=Path)
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    source, build = args.source.resolve(), args.ns3_build.resolve()
    if not (build / "include").is_dir():
        build /= "build"
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be new or empty; accepted evidence is immutable")
    runner_source = Path(__file__).resolve().parent / "ns3/tranche6_freshness_contract.cc"
    binary = args.build_directory.resolve() / "tranche6_freshness_contract"
    if binary.exists():
        parser.error("--build-directory already contains a contract binary")
    output.mkdir(parents=True, exist_ok=True)
    binary.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "csr-tranche6-ns3-freshness-contract-v1",
        "status": "running", "started_utc": utc_now(),
        "ns3_source_commit": PIN, "matlab_executed": False,
        "full_ns3_rebuild_performed": False,
        "scope": "Direct real HOP/NWK ingress contracts, without a physical radio channel; not PHY or network equivalence.",
        "wire_scope": "Explicit bare DATA/ACK and routing fixtures; actual production NeighborCheck completion callback boundary.",
        "library_provenance": "Unchanged preserved shared libraries with before/after hashes; only the standalone contract translation unit is freshly compiled.",
        "harness_sha256": digest(runner_source),
        "orchestrator_sha256": digest(Path(__file__)),
        "shared_build_helper_sha256": digest(Path(__file__).with_name("run_tranche4_ns3_reference.py")),
    }
    try:
        check_source(source, build)
        before = input_snapshot(source, build)
        record["source_tree"] = checked(["git", "rev-parse", "HEAD^{tree}"], source)
        record["input_files_sha256"] = before
        record["source_headers_match_preserved_build"] = True
        command = compile_runner(source, build, binary, args.compiler)
        command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(runner_source)
        record["compile_command"] = command
        record["compiler"] = checked([args.compiler, "--version"]).splitlines()[0]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (output / "compile.log").write_text(compiled.stdout + compiled.stderr)
        record["compile_exit_code"] = compiled.returncode
        if compiled.returncode:
            raise RuntimeError("Contract compilation failed; see compile.log")
        record["runner_sha256"] = digest(binary)
        run_command = [str(binary), str(output / "oracle_vectors.csv")]
        record["run_command"] = run_command
        execution = subprocess.run(run_command, capture_output=True, text=True, timeout=60)
        (output / "run.log").write_text(execution.stdout + execution.stderr)
        record["run_exit_code"] = execution.returncode
        vectors = list(csv.DictReader((output / "oracle_vectors.csv").open()))
        record["case_count"] = len({row["case"] for row in vectors})
        record["check_count"] = len(vectors)
        record["checks_passed"] = sum(row["pass"] == "1" for row in vectors)
        after = input_snapshot(source, build)
        record["source_and_libraries_unchanged"] = before == after
        check_source(source, build)
        if execution.returncode or not vectors or record["checks_passed"] != len(vectors):
            raise RuntimeError("One or more source contracts failed; inspect oracle_vectors.csv and run.log")
        if before != after:
            raise RuntimeError("Reference inputs changed during the contract run")
        record["status"] = "passed"
    except Exception as error:
        record["status"] = "failed"
        record["error"] = str(error)
    record["completed_utc"] = utc_now()
    record["artifacts_sha256"] = {
        path.name: digest(path) for path in sorted(output.iterdir()) if path.is_file()
    }
    (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record.get(key) for key in (
        "status", "case_count", "check_count", "checks_passed", "error",
    )}))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
