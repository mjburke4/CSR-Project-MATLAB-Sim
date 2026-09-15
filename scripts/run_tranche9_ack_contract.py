#!/usr/bin/env python3
"""Compile matched ACK service contracts against pinned, unchanged ns-3 headers.

Only this standalone executable is compiled. Preserved ns-3 shared libraries
are verified and hash-bound; this does not claim an engine rebuild.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tranche9_ack_reference_base", ROOT / "scripts/run_tranche4_ns3_reference.py")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns3-source", type=Path, required=True)
    parser.add_argument("--ns3-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-directory", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    source, build = args.ns3_source.resolve(), args.ns3_build.resolve()
    out, binary_dir = args.output.resolve(), args.build_directory.resolve()
    BASE.check_source(source, build)
    out.mkdir(parents=True, exist_ok=False)
    binary_dir.mkdir(parents=True, exist_ok=True)
    binary = binary_dir / "ack-contract"
    contract_source = ROOT / "scripts/ns3/tranche9_ack_contract.cc"
    command = BASE.compile_runner(source, build, binary, args.compiler)
    command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(contract_source)
    before = {path.name: BASE.digest(path) for path in (source / "model").glob("csr-*.h")}
    compiled = subprocess.run(command, capture_output=True, text=True)
    (out / "compile.log").write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise RuntimeError(f"Standalone contract compilation failed: {out / 'compile.log'}")
    with (out / "run.log").open("w") as stream:
        completed = subprocess.run([str(binary), str(out / "checkpoints.csv")],
                                   stdout=stream, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError(f"Native contract failed: {out / 'run.log'}")
    BASE.check_source(source, build)
    after = {path.name: BASE.digest(path) for path in (source / "model").glob("csr-*.h")}
    if before != after:
        raise RuntimeError("Pinned headers changed during contract execution")
    with (out / "checkpoints.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(row["pass"] != "1" for row in rows):
        raise RuntimeError("Native contract has empty or failed checkpoints")
    summary = {"Schema": "csr-tranche9-ack-service-contract-v1", "Passed": True,
               "CheckpointCount": len(rows), "UnmatchedCount": 0, "FailedCount": 0,
               "ReferenceSHA256": BASE.digest(out / "checkpoints.csv"),
               "Runtime": "native ns-3 standalone contract"}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {
        "schema": "csr-tranche9-ack-contract-reference-v1", "status": "passed",
        "source_commit": BASE.PIN, "source_headers_unchanged": True,
        "matlab_executed": False, "native_contract_executed": True,
        "engine_rebuilt": False, "checkpoint_count": len(rows),
        "case_count": len({row["case"] for row in rows}),
        "scope": "Prescribed receiver states and ACK ingress; no RF delivery or RNG-stream equivalence",
        "contract_source": {"path": contract_source.relative_to(ROOT).as_posix(),
                            "sha256": BASE.digest(contract_source)},
        "runner_source": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                          "sha256": BASE.digest(Path(__file__))},
        "source_headers": [{"path": "model/" + name, "sha256": digest}
                           for name, digest in sorted(before.items())],
        "preserved_libraries": [
            {"path": str(build / "lib" / f"libns3-dev-{name}-debug.so"),
             "sha256": BASE.digest(build / "lib" / f"libns3-dev-{name}-debug.so")}
            for name in BASE.MODULES],
        "compiler": subprocess.check_output([args.compiler, "--version"], text=True).splitlines()[0],
        "compile_command": command, "compile_returncode": compiled.returncode,
        "run_command": [str(binary), str(out / "checkpoints.csv")],
        "run_returncode": completed.returncode,
        "binary_sha256": BASE.digest(binary),
        "artifacts": [{"path": path.name, "sha256": BASE.digest(path), "bytes": path.stat().st_size}
                      for path in sorted(out.iterdir()) if path.is_file()],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "passed", "cases": manifest["case_count"],
                      "checkpoints": len(rows), "output": str(out)}))


if __name__ == "__main__":
    main()
