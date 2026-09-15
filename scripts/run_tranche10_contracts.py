#!/usr/bin/env python3
"""Generate matched MAC/receiver references using the recorded fresh ns-3 build.

The standalone fixtures prescribe MAC inputs or fixed RF transmissions. They
do not align random streams or establish end-to-end statistical parity.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tranche10_reference_base", ROOT / "scripts/run_tranche4_ns3_reference.py")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ENGINE_PIN = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
KINDS = {
    "mac": {
        "name": "contention", "count": 279,
        "cases": {"idle_p15", "idle_literal", "idle_p30", "idle_p51", "idle_p60",
                  "idle_before", "idle_after", "search_initial", "sync_initial",
                  "track_initial", "sync_busy", "track_busy", "track_tie_early",
                  "track_tie_late", "idle_restart"},
        "scope": "Prescribed receiver states and fixed neighbor occupancy; no RF or RNG-stream equivalence",
    },
    "rx": {
        "name": "receiver", "count": 154,
        "cases": {"preamble_before_wake", "preamble_at_wake", "preamble_after_wake",
                  "acquisition_canceled_by_sleep"},
        "scope": "Fixed transmissions through source BER/ECC with stochastic SYNC disabled; no HOP or RNG-stream equivalence",
    },
}


def validate_engine(record_path: Path, build: Path) -> list[dict]:
    record = json.loads(record_path.read_text())
    if (record.get("schema") != "csr-tranche10-native-engine-rebuild-v1"
            or record.get("status") != "passed"
            or record.get("engine_rebuilt") is not True
            or record.get("source_commit") != BASE.PIN
            or record.get("engine_commit") != ENGINE_PIN
            or record.get("engine_tracked_sources_unchanged") is not True
            or record.get("csr_tracked_sources_unchanged") is not True):
        raise ValueError("A passed, clean, pinned fresh-engine record is required")
    expected = {Path(row["path"]).name: row["sha256"] for row in record["libraries"]}
    required = {f"libns3-dev-{name}-debug.so" for name in BASE.MODULES}
    if set(expected) != required or len(record["libraries"]) != len(required):
        raise ValueError("Engine record must bind exactly the nine required libraries")
    libraries = []
    for name in sorted(required):
        path = build / "lib" / name
        if BASE.digest(path) != expected[name]:
            raise ValueError(f"Fresh engine library differs from build record: {name}")
        libraries.append({"path": str(path), "sha256": expected[name],
                          "bytes": path.stat().st_size})
    return libraries


def validate_rows(path: Path, kind: dict) -> list[dict]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["case", "checkpoint", "time_seconds", "field",
                                 "actual", "expected", "pass"]:
            raise ValueError("Unexpected checkpoint CSV columns")
        rows = list(reader)
    if len(rows) != kind["count"] or {r["case"] for r in rows} != kind["cases"]:
        raise ValueError("Native checkpoint/case coverage differs from the fixture contract")
    keys = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Nonrectangular checkpoint CSV")
        key = tuple(row[name] for name in ("case", "checkpoint", "field"))
        if key in keys:
            raise ValueError(f"Duplicate checkpoint identity: {key}")
        keys.add(key)
        actual, expected, at = (Decimal(row[name]) for name in
                                ("actual", "expected", "time_seconds"))
        if not all(value.is_finite() for value in (actual, expected, at)) or at < 0:
            raise ValueError(f"Invalid checkpoint number: {key}")
        tolerance = Decimal("1e-12") if row["field"].endswith("seconds") else Decimal(0)
        if row["pass"] != "1" or abs(actual - expected) > tolerance:
            raise ValueError(f"Failed native checkpoint: {key}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--ns3-source", type=Path, required=True)
    parser.add_argument("--ns3-build", type=Path, required=True)
    parser.add_argument("--engine-record", type=Path,
                        default=ROOT / "evidence/tranche-10-native-build.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-directory", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    source, build = args.ns3_source.resolve(), args.ns3_build.resolve()
    out, binary_dir = args.output.resolve(), args.build_directory.resolve()
    engine_record = args.engine_record.resolve()
    engine_record_relative = engine_record.relative_to(ROOT).as_posix()
    kind = KINDS[args.kind]
    BASE.check_source(source, build)
    libraries = validate_engine(engine_record, build)
    before = BASE.input_snapshot(source, build)
    out.mkdir(parents=True, exist_ok=False)
    binary_dir.mkdir(parents=True, exist_ok=True)
    binary = binary_dir / (args.kind + "-contract")
    contract_source = ROOT / f"scripts/ns3/tranche10_{kind['name']}_contract.cc"
    command = BASE.compile_runner(source, build, binary, args.compiler)
    command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(contract_source)
    compiled = subprocess.run(command, capture_output=True, text=True)
    (out / "compile.log").write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise RuntimeError(f"Native compilation failed: {out / 'compile.log'}")
    run_command = [str(binary), str(out / "checkpoints.csv")]
    completed = subprocess.run(run_command, capture_output=True, text=True, timeout=120)
    (out / "run.log").write_text(completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError(f"Native contract failed: {out / 'run.log'}")
    BASE.check_source(source, build)
    if before != BASE.input_snapshot(source, build):
        raise RuntimeError("Pinned source, headers, or fresh libraries changed during execution")
    rows = validate_rows(out / "checkpoints.csv", kind)
    summary = {"Schema": f"csr-tranche10-{kind['name']}-contract-v1", "Passed": True,
               "CheckpointCount": len(rows), "UnmatchedCount": 0, "FailedCount": 0,
               "ReferenceSHA256": BASE.digest(out / "checkpoints.csv"),
               "Runtime": "native ns-3 standalone contract on recorded fresh engine"}
    BASE.write_json(out / "summary.json", summary)
    manifest = {
        "schema": f"csr-tranche10-{kind['name']}-contract-reference-v1",
        "status": "passed", "generated_utc": BASE.utc_now(),
        "source_commit": BASE.PIN, "source_headers_unchanged": True,
        "input_snapshot_unchanged": True, "input_sha256": before,
        "matlab_executed": False, "native_contract_executed": True,
        "engine_rebuilt": True, "historical_library_byte_identity_claimed": False,
        "engine_build_record": {"path": engine_record_relative,
                                "sha256": BASE.digest(engine_record)},
        "checkpoint_count": len(rows), "case_count": len(kind["cases"]),
        "cases": sorted(kind["cases"]), "scope": kind["scope"],
        "contract_source": {"path": contract_source.relative_to(ROOT).as_posix(),
                            "sha256": BASE.digest(contract_source)},
        "runner_source": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                          "sha256": BASE.digest(Path(__file__))},
        "source_headers": [{"path": "model/" + path.name, "sha256": BASE.digest(path)}
                           for path in sorted((source / "model").glob("csr-*.h"))],
        "fresh_libraries": libraries,
        "compiler": subprocess.check_output([args.compiler, "--version"], text=True).splitlines()[0],
        "compile_command": command, "compile_returncode": compiled.returncode,
        "run_command": run_command, "run_returncode": completed.returncode,
        "output_captured_after_process_closed": True,
        "binary_sha256": BASE.digest(binary),
        "artifacts": [{"path": path.name, "sha256": BASE.digest(path), "bytes": path.stat().st_size}
                      for path in sorted(out.iterdir()) if path.is_file()],
    }
    BASE.write_json(out / "manifest.json", manifest)
    print(json.dumps({"status": "passed", "cases": len(kind["cases"]),
                      "checkpoints": len(rows), "output": str(out)}))


if __name__ == "__main__":
    main()
