#!/usr/bin/env python3
"""Build and record the short native matched-draw MAC/HOP reference.

Requires a separately verified clean nine-module ns-3 build. The test overlay
does not modify that build or the pinned native source checkout.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from build_tranche11_overlay import build as build_overlay
from run_tranche4_ns3_reference import MODULES, compile_runner

PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader(); writer.writerows(rows)


def execute(command, log, timeout=180):
    started = time.monotonic()
    run = subprocess.run([str(x) for x in command], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=timeout)
    log.write_bytes(run.stdout)
    if run.returncode:
        raise RuntimeError(f"Command failed ({run.returncode}): see {log}")
    return {"argv": [str(x) for x in command], "exit_code": run.returncode,
            "wall_seconds": time.monotonic() - started, "log_sha256": sha(log)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-verified-binaries", type=Path,
                        help="Prior completed reference summary; verify unchanged source/overlay/libraries before reusing its binaries")
    parser.add_argument("--compiler", default="/usr/bin/g++")
    args = parser.parse_args()
    source, build, work, output = [p.resolve() for p in (args.source, args.build, args.work, args.output)]
    root = Path(__file__).resolve().parent.parent
    inputs = root / "scenarios" / "replay"
    plan = json.loads((inputs / "plan.json").read_text())
    # The C++ fixture deliberately has a bounded API contract. Reject an
    # edited plan rather than silently ignoring unsupported fixture settings.
    expected = {"schema": "csr-tranche11-replay-input-v1", "source_pin": PIN, "cases": ["ab", "ba", "slow", "track"],
                "nodes": [1, 2, 3], "gateway": 1, "sources": [2, 3],
                "applications_per_source": 4, "application_payload_bytes": 16,
                "dscp": 0, "rate_kbps": 128, "power_dbm": 33,
                "slot_range": 31, "slot_reduction": 0, "active_nodes": 3, "reported_active_nodes": 3,
                "wire_profile": "bare", "slot_profile": "hist-2014-next-tslot-modulo-probe",
                "slot_seconds": .013, "holdoff_seconds": .3, "initial_mac_state": "Search",
                "initial_neighbor_reservation": -1, "initial_neighbor_last_heard_seconds": 0,
                "known_neighbors": {"1": [2, 3], "2": [1], "3": [1]},
                "prescribed_sync_present": False, "receiver_track_node": 1, "receiver_track_cases": ["track"],
                "native_link_margin_db": 6,
                "final_snapshots": [{"node": 1, "peer": 0}, {"node": 2, "peer": 1}, {"node": 3, "peer": 1}],
                "duty_cycle": False, "propagation_seconds": 1e-6,
                "pathloss_db": 70, "snr_db": 20, "offered_start_seconds": 0,
                "offered_poll_seconds": .02, "offered_poll_stop_exclusive_seconds": 8,
                "tape_entries_per_node": 128}
    for key, value in expected.items():
        if plan.get(key) != value:
            raise ValueError(f"Unsupported fixture plan setting {key}")
    cases = read(inputs / "cases.csv")
    if [r["case"] for r in cases] != expected["cases"] or any(float(r["duration_seconds"]) != 8 for r in cases):
        raise ValueError("Fixture case order/horizon mismatch")
    for row in cases:
        name = row["case"]
        values = [float(row[k]) for k in ("node2_a", "node2_b", "node3_a", "node3_b", "gateway_draw", "track_start_seconds", "track_stop_seconds")]
        wanted = ([9, 1, 3, 7] if name == "ba" else [3, 7, 9, 1]) + [28 if name == "slow" else 1] + ([.25, .65] if name == "track" else [-1, -1])
        if values != wanted:
            raise ValueError(f"Unsupported fixed-v1 case settings: {name}")
    tapes = read(inputs / "draws.csv")
    wanted_tapes = []
    for row in cases:
        for node in (1, 2, 3):
            values = [int(row["gateway_draw"])] if node == 1 else [int(row[f"node{node}_a"]), int(row[f"node{node}_b"])]
            for ordinal in range(1, 129):
                wanted_tapes.append({"case": row["case"], "node": str(node), "ordinal": str(ordinal), "min": "0", "max": "31", "draw": str(values[(ordinal - 1) % len(values)])})
    if tapes != wanted_tapes:
        raise ValueError("Tape CSV differs from declared complete fixed-v1 case pattern")
    for path in (work, output):
        if path.exists() and any(path.iterdir()) and not (path == work and args.reuse_verified_binaries):
            raise ValueError(f"Use an empty destination: {path}")
        path.mkdir(parents=True, exist_ok=True)
    libraries = {name: sha(build / "lib" / f"libns3-dev-{name}-debug.so") for name in MODULES}
    model_before = {p.name: sha(p) for p in sorted((source / "model").glob("csr-*")) if p.is_file()}
    overlay = work / "overlay"
    previous = None
    if args.reuse_verified_binaries:
        previous = json.loads(args.reuse_verified_binaries.read_text())
        if previous["status"] != "completed" or previous["shared_libraries"] != libraries:
            raise ValueError("Previously verified library identity changed")
        for path in [root / "scripts" / "build_tranche11_overlay.py", root / "scripts" / "ns3" / "tranche11_replay.cc", root / "scripts" / "ns3" / "tranche11-replay-hooks.h"]:
            if previous["fixture_hashes"][path.name] != sha(path):
                raise ValueError("Cannot reuse binaries after fixture source/overlay changes")
        overlay_manifest = json.loads((overlay / "overlay.json").read_text())
        if overlay_manifest["original_files"] != model_before:
            raise ValueError("Previously verified native source identity changed")
        for name, original in model_before.items():
            wanted = overlay_manifest["modified_files"].get(name, {}).get("overlay_sha256", original)
            if sha(overlay / "ns3" / name) != wanted:
                raise ValueError("Previously verified overlay file changed")
    else:
        overlay_manifest = build_overlay(source, overlay)
    controls = output / "controls"; controls.mkdir()
    records = []

    def compile_one(src, target, use_overlay):
        if previous:
            matches = [r for r in previous["commands"] if r.get("binary_sha256") and r["argv"][-1] == str(target)]
            if len(matches) != 1 or sha(target) != matches[0]["binary_sha256"]:
                raise ValueError("Previously verified executable identity changed")
            prior_log = args.reuse_verified_binaries.parent / "controls" / (target.name + "-build.log")
            if not prior_log.is_file() or sha(prior_log) != matches[0]["log_sha256"]:
                raise ValueError("Previously verified compiler log is missing or changed")
            shutil.copy2(prior_log, controls / prior_log.name)
            records.append(matches[0] | {"reused_verified_binary": True})
            return
        command = compile_runner(source, build, target, args.compiler)
        command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(src)
        if use_overlay:
            command.insert(1, "-I" + str(overlay))
        record = execute(command, controls / (target.name + "-build.log"))
        record["binary_sha256"] = sha(target)
        records.append(record)

    control_results = {}
    for label, filename, count in (("ack", "tranche9_ack_contract.cc", 101),
                                   ("receiver", "tranche10_receiver_contract.cc", 154)):
        for mode in ("clean", "off"):
            binary = work / (label + "-" + mode)
            compile_one(root / "scripts" / "ns3" / filename, binary, mode == "off")
            records.append(execute([binary, controls / (label + "-" + mode + ".csv")],
                                   controls / (label + "-" + mode + ".log")))
        clean = controls / (label + "-clean.csv"); off = controls / (label + "-off.csv")
        rows = read(clean)
        if len(rows) != count or any(r["pass"] != "1" for r in rows) or clean.read_bytes() != off.read_bytes():
            raise ValueError(f"Disabled seams changed {label} contract")
        control_results[label] = {"checkpoints": count, "passed": True,
                                 "clean_and_disabled_byte_equal": True, "sha256": sha(clean)}
    binary = work / "replay"
    compile_one(root / "scripts" / "ns3" / "tranche11_replay.cc", binary, True)
    records.append(execute([binary, "--self-test"], controls / "replay-self-test.log"))
    raw = output / "raw"
    execution = execute([binary, inputs / "cases.csv", inputs / "draws.csv", raw], output / "run.log")
    records.append(execution)
    events, draws, usage, summaries = [], [], [], []
    for case in plan["cases"]:
        folder = raw / case
        events.extend(read(folder / "events.csv"))
        original_draws = read(folder / "raw.csv")
        native_events = read(folder / "native.csv")
        # Native already emits the semantic purpose after PickTxSlot returns.
        # Associate every raw request with exactly one new/advertise event;
        # preserve its raw time and resolved result from the seam observer.
        purposes = {}
        for row in native_events:
            if row["event"] == "reservation_advertise":
                purpose = "advertise"
            elif row["event"] == "reservation_prepare" and row["reason"] == "new":
                purpose = "prepare"
            else:
                continue
            ns = int((Decimal(row["time_s"]) * 1_000_000_000).to_integral_value())
            purposes.setdefault((row["node"], str(ns)), []).append((purpose, row["reservation_slot"]))
        for row in original_draws:
            key = (row["node"], row["time_ns"])
            if not purposes.get(key):
                raise ValueError(f"Unclassified raw request {case}: {row}")
            purpose, resolved = purposes[key].pop(0)
            if resolved != row["resolved"]:
                raise ValueError("Observed raw resolution differs from native reservation trace")
            draws.append({k: row[k] for k in plan["draws_output_schema"] if k != "purpose"} | {"purpose": purpose})
        if any(purposes.values()):
            raise ValueError(f"Native slot purpose without a raw request in {case}")
        summary = read(folder / "summary.csv")
        for row in summary:
            usage.append({"case": case, "node": row["node"], "supplied": "128", "consumed": row["draws_consumed"], "unused": row["draws_unused"]})
        if sum(int(r["admitted"]) for r in summary) != 8 or sum(int(r["delivered"]) for r in summary) != 8:
            raise ValueError(f"Complete delivery chain did not finish in {case}")
        if sum(int(r["releases"]) for r in summary) != 8 or any(int(r["pending"]) for r in summary):
            raise ValueError(f"Capacity release did not close in {case}")
        summaries.append({"case": case, "nodes": [{k: int(v) if k != "case" else v for k, v in r.items()} for r in summary]})
    write(output / "events.csv", plan["events_schema"], events)
    write(output / "draws.csv", plan["draws_output_schema"], draws)
    write(output / "usage.csv", ["case", "node", "supplied", "consumed", "unused"], usage)
    shutil.copy2(overlay / "seams.patch", output / "seams.patch")
    shutil.copy2(overlay / "overlay.json", output / "overlay.json")
    if model_before != {p.name: sha(p) for p in sorted((source / "model").glob("csr-*")) if p.is_file()}:
        raise ValueError("Pinned native model changed")
    if libraries != {name: sha(build / "lib" / f"libns3-dev-{name}-debug.so") for name in MODULES}:
        raise ValueError("Native shared libraries changed")
    summary = {"schema": "csr-tranche11-native-reference-v1", "status": "completed",
               "source_pin": PIN, "scope": plan["scope"], "cases": summaries,
               "matlab_execution": False, "cross_simulator_parity_established": False,
               "event_count": len(events), "draw_count": len(draws),
               "wall_seconds": execution["wall_seconds"], "self_tests": 6,
               "disabled_seam_controls": control_results,
               "native_source_unchanged": True, "native_libraries_unchanged": True,
               "input_hashes": {p.name: sha(p) for p in sorted(inputs.iterdir()) if p.is_file()},
               "fixture_hashes": {p.name: sha(p) for p in [Path(__file__), root / "scripts" / "build_tranche11_overlay.py",
                   root / "scripts" / "ns3" / "tranche11_replay.cc", root / "scripts" / "ns3" / "tranche11-replay-hooks.h"]},
               "shared_libraries": libraries, "commands": records}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "manifest.json").write_text(json.dumps({"schema": "csr-tranche11-reference-files-v1", "files": manifest}, indent=2) + "\n")
    print(f"Native replay completed: 4 cases, 32 applications, {len(events)} events, {len(draws)} draws; disabled controls 255/255")


if __name__ == "__main__":
    main()
