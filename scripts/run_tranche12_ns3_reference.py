#!/usr/bin/env python3
"""Build and record the short native matched-draw NWK/MAC/HOP reference.

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

from build_tranche12_overlay import build as build_overlay
from run_tranche4_ns3_reference import MODULES, compile_runner, check_source

PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
PLAN_SHA256 = "0fce57f9ca952914b19c3e1fc69479255ad5bd5733a0756849b705680793c9b4"


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
    inputs = root / "scenarios" / "relay"
    plan = json.loads((inputs / "plan.json").read_text())
    # This executable is deliberately a finite v1 experiment. A changed plan
    # requires review and a regenerated fixture, never silently ignored options.
    if sha(inputs / "plan.json") != PLAN_SHA256:
        raise ValueError("Unsupported fixture plan identity")
    cases = read(inputs / "cases.csv")
    expected_cases = [{"case": name, "duration_seconds": "24", "apps4": str(a), "apps5": str(b)}
                      for name, a, b in (("relay", 20, 0), ("local", 0, 20), ("mix", 20, 20), ("sw", 20, 20))]
    if cases != expected_cases:
        raise ValueError("Case order, horizon or workload differs from fixed v1")
    tapes = read(inputs / "draws.csv")
    wanted_tapes = []
    for row in cases:
        for node in (1, 4, 5):
            values = [1] if node == 1 else ([9, 1] if ((node == 4) == (row["case"] == "sw")) else [3, 7])
            for ordinal in range(1, 257):
                wanted_tapes.append({"case": row["case"], "node": str(node), "ordinal": str(ordinal), "min": "0", "max": "31", "draw": str(values[(ordinal - 1) % len(values)])})
    if tapes != wanted_tapes:
        raise ValueError("Tape CSV differs from declared complete v1 pattern")
    check_source(source, build)
    native_build_path = root / "evidence" / "tranche-11-native-build.json"
    native_build = json.loads(native_build_path.read_text())
    if native_build["status"] != "passed" or native_build["source_commit"] != PIN or native_build["engine_commit"] != "6b5cd24ea80713ce16d88575869aedd6f432bdae":
        raise ValueError("Unverified native build provenance")
    for record in native_build["libraries"]:
        if sha(build / "lib" / Path(record["path"]).name) != record["sha256"]:
            raise ValueError("Native library no longer matches verified T11 clean build")
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
        for path in [root / "scripts" / "build_tranche12_overlay.py", root / "scripts" / "ns3" / "tranche12_relay.cc", root / "scripts" / "ns3" / "tranche12-relay-hooks.h"]:
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
    binary = work / "relay"
    compile_one(root / "scripts" / "ns3" / "tranche12_relay.cc", binary, True)
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
            usage.append({"case": case, "node": row["node"], "supplied": "256", "consumed": row["draws_consumed"], "unused": row["draws_unused"]})
        case_input = next(r for r in cases if r["case"] == case)
        target4, target5 = int(case_input["apps4"]), int(case_input["apps5"])
        if sum(int(r["admitted"]) for r in summary) != target4 + target5 or sum(int(r["delivered"]) for r in summary) != target4 + target5:
            raise ValueError(f"Complete real NWK delivery did not finish in {case}")
        if sum(int(r["releases"]) for r in summary) != 2 * target4 + target5:
            raise ValueError(f"Real NWK hop-by-hop capacity release incomplete in {case}")
        if any(int(r[k]) for r in summary for k in ("nsdp4", "nsdp5", "nwk_waiting", "resend_queue", "ack_queue", "data_queue")):
            raise ValueError(f"Unexpected DATA ownership/queue residue in {case}")
        case_events = read(folder / "events.csv")
        # Real holds must be observed at 16 seconds and expire by 24 seconds;
        # invariants apply only at stable checkpoints, not inside callbacks.
        expected_holds = 4 if case == "mix" else (1 if case == "sw" else 0)
        checkpoints = [r for r in case_events if r["event"] == "checkpoint"]
        finals = [r for r in case_events if r["event"] == "final"]
        if len(checkpoints) != 3 or len(finals) != 3 or sum(int(r["dack_holds"]) for r in checkpoints) != expected_holds:
            raise ValueError(f"Native DACK checkpoint changed in {case}")
        if any(int(r["hop_pending"]) != int(r["resend_queue"]) + int(r["dack_holds"]) for r in checkpoints + finals):
            raise ValueError("Stable HOP capacity accounting failed")
        if any(int(r[k]) for r in finals for k in ("hop_pending", "dack_holds", "resend_queue", "nwk_waiting", "nwk_custody")):
            raise ValueError("Actual DACK/custody expiry did not complete by stop")
        deliveries = read(folder / "deliveries.csv")
        wanted = [{"case": case, "app_source": str(source), "app_id": str(app)}
                  for source, target in ((4, target4), (5, target5)) for app in range(1, target + 1)]
        if deliveries != wanted:
            raise ValueError("Actual NWK callback identities incomplete or duplicated")
        case_events = read(folder / "events.csv")
        admitted = {(r["app_source"], r["app_id"]): int(r["time_ns"]) for r in case_events if r["event"] == "admit"}
        delivered = {(r["app_source"], r["app_id"]): int(r["time_ns"]) for r in case_events if r["event"] == "deliver"}
        if len(admitted) != len(wanted) or set(admitted) != set(delivered):
            raise ValueError("Observed delivered identity differs from actual NWK admission")
        flows = []
        for source_id, target in ((4, target4), (5, target5)):
            delays = [delivered[(str(source_id), str(app))] - admitted[(str(source_id), str(app))] for app in range(1, target + 1)]
            flows.append({"source": source_id, "admitted": target, "delivered": len(delays),
                          "mean_delay_ns": sum(delays) / len(delays) if delays else 0,
                          "max_delay_ns": max(delays, default=0),
                          "last_delivery_ns": max([v for (src, _), v in delivered.items() if src == str(source_id)], default=0)})
        summaries.append({"case": case, "nodes": [{k: int(v) if k != "case" else v for k, v in r.items()} for r in summary],
                          "flows": flows, "dack_holds_at_checkpoint": expected_holds, "dack_holds_at_stop": 0,
                          "routing_controls_excluded_from_transport": True})
    write(output / "events.csv", plan["events_schema"], events)
    write(output / "draws.csv", plan["draws_output_schema"], draws)
    write(output / "usage.csv", ["case", "node", "supplied", "consumed", "unused"], usage)
    shutil.copy2(overlay / "seams.patch", output / "seams.patch")
    shutil.copy2(overlay / "overlay.json", output / "overlay.json")
    if model_before != {p.name: sha(p) for p in sorted((source / "model").glob("csr-*")) if p.is_file()}:
        raise ValueError("Pinned native model changed")
    if libraries != {name: sha(build / "lib" / f"libns3-dev-{name}-debug.so") for name in MODULES}:
        raise ValueError("Native shared libraries changed")
    summary = {"schema": "csr-tranche12-native-reference-v1", "status": "completed",
               "source_pin": PIN, "scope": plan["scope"], "cases": summaries,
               "matlab_execution": False, "cross_simulator_parity_established": False,
               "event_count": len(events), "draw_count": len(draws),
               "wall_seconds": execution["wall_seconds"], "self_tests": 6,
               "disabled_seam_controls": control_results,
               "native_source_unchanged": True, "native_libraries_unchanged": True,
               "instrumented_native_fixture": True, "real_nwk_application_and_relay_path": True,
               "clean_build_record": "evidence/tranche-11-native-build.json",
               "clean_build_record_sha256": sha(native_build_path),
               "engine_build_reused_after_hash_verification": True,
               "input_hashes": {p.name: sha(p) for p in sorted(inputs.iterdir()) if p.is_file()},
               "fixture_hashes": {p.name: sha(p) for p in [Path(__file__), root / "scripts" / "build_tranche12_overlay.py",
                   root / "scripts" / "ns3" / "tranche12_relay.cc", root / "scripts" / "ns3" / "tranche12-relay-hooks.h"]},
               "shared_libraries": libraries, "commands": records}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "manifest.json").write_text(json.dumps({"schema": "csr-tranche12-reference-files-v1", "files": manifest}, indent=2) + "\n")
    print(f"Native replay completed: 4 cases, 120 applications, {len(events)} events, {len(draws)} draws; disabled controls 255/255")


if __name__ == "__main__":
    main()
