#!/usr/bin/env python3
"""Compile the SHA-guarded passive overlay and run native seed 131 to 85 s.

The result is accepted only if *every* canonical differential CSV row before
85 seconds matches the original, uninstrumented native reference in order.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from apply_overlay import apply

SOURCE_COMMIT = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
ENGINE_COMMIT = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
SCENARIO_SHA = "e10d210590c80cb839442b7847ee6c7e8b8c21d043da5fe5dcf1f2abb402ca7a"
REFERENCE_SHA = "8daa3cea2bcfae1162c373b39110745fe8889066fdaab3bd22fbb0c685fe3878"
SHORT_REFERENCE_SHA = "5b7ea32822f91e9404afd9ff25e31973c6c9f462e7360967bc0dcf5d8eab6bac"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def read_prefix(path: Path, compressed: bool):
    opener = gzip.open if compressed else open
    with opener(path, "rt", newline="") as stream:
        reader = csv.DictReader(stream)
        yield reader.fieldnames
        for row in reader:
            if float(row["time_s"]) >= 85.0:
                break
            yield row


def exact_prefix(reference: Path, observed: Path) -> dict:
    left = read_prefix(reference, compressed=True)
    right = read_prefix(observed, compressed=False)
    count = 0
    while True:
        a = next(left, None)
        b = next(right, None)
        if a != b:
            raise AssertionError(f"first native-prefix mismatch at row {count}: {a!r} != {b!r}")
        if a is None:
            return {"exact_prefix": True, "rows": count - 1,
                    "window": "[0,85)", "reference_sha256": digest(reference),
                    "observed_sha256": digest(observed)}
        count += 1


def validate_tape(path: Path) -> dict:
    counts: collections.Counter = collections.Counter()
    tx: dict[tuple[int, int], tuple[int, int]] = {}
    child_indices: dict[tuple[int, int], set[int]] = collections.defaultdict(set)
    boundary: dict[int, dict] = {}
    sequence = 0
    last_ns = -1
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert row["case_id"] == "discovery131"
        assert row["event_order"] == sequence + 1, "discovery tape order gap"
        assert 25_000_000_000 <= row["time_ns"] < 85_000_000_000
        assert row["time_ns"] >= last_ns, "discovery tape time reversal"
        sequence, last_ns = row["event_order"], row["time_ns"]
        counts[row["event"]] += 1
        if row["event"] == "boundary_state":
            assert row["time_ns"] == 25_000_000_000
            assert row["node"] not in boundary
            boundary[row["node"]] = row
        if row["event"] == "tx_start":
            key = (row["time_ns"], row["node"])
            assert key not in tx, "two aggregate IDs share one (time,node)"
            tx[key] = (int(row["detail"]["child_count"]), row["tx_id"])
        if row["event"] == "tx_child":
            key = (row["time_ns"], row["node"])
            assert key in tx and row["tx_id"] == tx[key][1]
            index = int(row["detail"]["child_index"])
            assert 0 <= index < tx[key][0]
            assert index not in child_indices[key], "duplicate aggregate child index"
            child_indices[key].add(index)
            assert len(row["detail"]["raw_bytes_hex"]) > 0
    assert set(boundary) == {1, 2, 3, 4, 5, 7, 8}, "missing 25-s receiver checkpoint"
    assert all(not row["detail"]["active_signal_ids"] for row in boundary.values()), \
        "active signal at 25-s replay boundary"
    for receiver in (2, 5):
        snapshot = boundary[receiver]
        assert snapshot["state_before"].lower() in ("idle", "search"), \
            "target receiver has nontrivial initial state"
        assert int(snapshot["detail"]["tracked_signal_id"]) == 0, \
            "target receiver tracks an unbound 25-s signal"
        assert snapshot["detail"]["acquisition_pending"] == "false", \
            "target receiver has unbound acquisition callback"
        assert snapshot["detail"]["sync_present"] == "false", \
            "target receiver has unbound 25-s SYNC state"
    assert counts["tx_child"] == sum(k for k, _ in tx.values())
    assert all(child_indices[key] == set(range(number))
               for key, (number, _) in tx.items()), "incomplete ordered aggregate children"
    assert counts["sync_decision"] > 0 and counts["rx_end"] > 0
    return {"events": dict(counts), "boundary_states": {
        str(n): r["state_before"] for n, r in sorted(boundary.items())}}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-native", required=True, type=Path,
                   help="Unmodified accepted native MAC-capture source directory")
    p.add_argument("--native-source-repo", required=True, type=Path,
                   help="Checkout at the frozen native source commit")
    p.add_argument("--engine-repo", required=True, type=Path,
                   help="ns-3 engine checkout at the frozen engine commit")
    p.add_argument("--engine-build", required=True, type=Path)
    p.add_argument("--scenario", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path,
                   help="Original full native seed-131 trace or bound unfiltered 0-85-s prefix.gz")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    assert commit(args.native_source_repo) == SOURCE_COMMIT, \
        "native source commit does not match original experiment"
    assert commit(args.engine_repo) == ENGINE_COMMIT, \
        "engine commit does not match original experiment"
    assert digest(args.scenario) == SCENARIO_SHA, "seed-131 scenario hash mismatch"
    assert digest(args.reference) in {REFERENCE_SHA, SHORT_REFERENCE_SHA}, \
        "seed-131 original/reference-prefix trace hash mismatch"
    assert (args.engine_build / "include").is_dir(), "missing ns-3 build/include"
    assert (args.engine_build / "lib").is_dir(), "missing ns-3 build/lib"
    assert not args.output.exists(), "output directory already exists"
    args.output.mkdir(parents=True)
    overlay = args.output / "compiled_overlay"
    identity = apply(args.base_native, overlay)
    executable = args.output / "capture_seed131"
    libraries = ["csr", "spectrum", "buildings", "propagation", "mobility",
                 "antenna", "network", "stats", "core"]
    cmd = ["g++", "-std=c++23", "-O0", "-g", "-DNS3_ASSERT_ENABLE",
           "-DNS3_BUILD_PROFILE_DEBUG", "-DNS3_LOG_ENABLE",
           "-DSTACKTRACE_LIBRARY_IS_LINKED=1", "-D__LINUX__",
           "-I" + str(overlay / "overlay"),
           "-I" + str(args.engine_build / "include"),
           str(overlay / "capture.cc"),
           "-L" + str(args.engine_build / "lib"),
           "-Wl,-rpath," + str(args.engine_build / "lib"),
           "-Wl,--no-as-needed", "-lns3-dev-csr-debug", "-Wl,--as-needed"]
    cmd += ["-lns3-dev-" + library + "-debug" for library in libraries[1:]]
    cmd += ["-lstdc++exp", "-o", str(executable)]
    with (args.output / "compile.log").open("w") as log:
        subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
    trace = args.output / "ns3-trace.csv"
    receiver_tape = args.output / "capture.jsonl"
    mac_tape = args.output / "mac-input.log"
    run = [str(executable), "--scenario=" + str(args.scenario.resolve()),
           "--trace=" + str(trace.resolve()),
           "--appDiagnostics=" + str((args.output / "app-admission.csv").resolve()),
           "--stop=85", "--flowLimit=0", "--dutyCycling=1",
           "--opnetAlignedDutyCycle=1", "--gatewayDiscovery=1",
           "--opnetAppGating=1", "--aggregateTraceOnly=0",
           "--admissionTrace=1", "--quietModelLogs=0",
           "--stochasticSyncThreshold=1"]
    env = dict(os.environ, CSR_DISCOVERY_CAPTURE=str(receiver_tape.resolve()),
               CSR_MAC_CAPTURE=str(mac_tape.resolve()))
    with (args.output / "run.log").open("w") as log:
        subprocess.run(run, check=True, env=env, stdout=log,
                       stderr=subprocess.STDOUT)
    try:
        gate = exact_prefix(args.reference, trace)
        tape = validate_tape(receiver_tape)
        subprocess.run([sys.executable,
                        str(args.base_native / "convert_capture.py"),
                        str(mac_tape), str(args.output / "mac_csv")], check=True)
        receipt = {"schema": "csr-seed131-native-discovery-capture-v1",
                   "status": "verified_exact_native_prefix",
                   "source_commit": SOURCE_COMMIT, "engine_commit": ENGINE_COMMIT,
                   "scenario_sha256": SCENARIO_SHA, "overlay": identity,
                   "gate": gate, "tape": tape,
                   "parent_full_reference_sha256": REFERENCE_SHA,
                   "compile_command": cmd, "run_command": run}
    except Exception as error:
        receipt = {"schema": "csr-seed131-native-discovery-capture-v1",
                   "status": "rejected", "error": str(error)}
        (args.output / "receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n")
        raise
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "gate": gate,
                      "events": tape["events"]}, indent=2))


if __name__ == "__main__":
    main()
