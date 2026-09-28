#!/usr/bin/env python3
"""Hash-bind each finished native capture to the shared exact-prefix validator.

An instrumented run alone is not a MATLAB replay pass. The resulting verified
capture manifests keep replay_pending until the separate MATLAB checks run.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_csv(path: Path) -> int:
    with path.open(newline="") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def observer_counts(path: Path) -> collections.Counter:
    if path.suffix == ".jsonl":
        return collections.Counter(json.loads(line)["event"] for line in
                                   path.read_text().splitlines() if line)
    with path.open(newline="") as stream:
        return collections.Counter(row["event"] for row in csv.DictReader(stream, delimiter="\t"))


def promote(kit: Path, native: Path, case: str) -> dict:
    schema = kit / "schema_review"
    m = copy.deepcopy(json.loads((schema / (case + ".manifest.json")).read_text()))
    if case == "discovery131":
        result = native / "seed131"
        receipt = json.loads((result / "receipt.json").read_text())
        assert receipt["status"] == "verified_exact_native_prefix"
        assert receipt["gate"]["exact_prefix"] and receipt["gate"]["rows"] == 8710
        trace, inputs, observer = (result / "ns3-trace.csv", result / "mac_csv",
                                    result / "capture.jsonl")
        overlay = result / "compiled_overlay/overlay/ns3/csr-net-device.h"
        source = result / "compiled_overlay/capture.cc"
        runner = kit / "discovery_capture/run_seed131_capture.py"
        extra_sources = {
            "native_overlay_phy": result / "compiled_overlay/overlay/ns3/csr-phy-model.h",
            "native_overlay_mac": result / "compiled_overlay/overlay/ns3/mac-replay-hooks.h",
            "native_observer": result / "compiled_overlay/overlay/ns3/csr-discovery-capture.h",
        }
        stop = 85_000_000_000
    else:
        result = native / "seed132"
        receipt = json.loads((result / "reference/fidelity.json").read_text())
        assert receipt["all_passed"] and receipt["source_capture"]["exact_prefix"]
        assert receipt["source_capture"]["rows"] == 48919
        trace, inputs, observer = (result / "capture/ns3-trace.csv", result / "inputs",
                                    result / "capture/source5_native.tsv")
        overlay = result / "overlay/ns3/csr-net-device.h"
        source = kit / "source5_capture/vendor/capture.cc"
        runner = kit / "source5_capture/run_bounded_capture.py"
        extra_sources = {"native_overlay_" + name.replace(".", "_"): result /
                         "overlay/ns3" / name for name in (
                             "csr-mac-core.h", "csr-phy-model.h", "csr-hop-layer.h",
                             "csr-nwk-layer.h", "source5-observer.h", "mac-replay-hooks.h")}
        stop = 330_000_000_000
    manifest_path = native / (case + ".verified.manifest.json")
    relative = lambda path: os.path.relpath(path.resolve(), native.resolve())
    for item in m["source_files"]:
        item["path"] = relative(schema / item["path"])
    for role, path in (("native_overlay", overlay),
                       ("native_capture_source", source),
                       ("native_capture_runner", runner),
                       *extra_sources.items()):
        m["source_files"].append({"role": role, "path": relative(path),
                                   "sha256": digest(path)})
    tapes = {name: inputs / (name + ".csv") for name in
             ("inputs", "frames", "draws", "tx", "tx_frames")}
    events = observer_counts(observer)
    m["capture"] = {
        "status": "verified", "prefix_fidelity": "passed", "prefix_end_ns": stop,
        "prefix_rows": receipt["gate"]["rows"] if case == "discovery131" else
                       receipt["source_capture"]["rows"],
        "trace_path": relative(trace), "observations_path": relative(observer),
        "mac_tape_paths": {name: relative(path) for name, path in tapes.items()},
    }
    coverage = m["coverage"]
    coverage["counts"] = {
        "mac_inputs": count_csv(tapes["inputs"]), "mac_draws": count_csv(tapes["draws"]),
        "tx": count_csv(tapes["tx"]), "tx_children": count_csv(tapes["tx_frames"]),
        "observer_events": sum(events.values()),
    }
    coverage["event_counts"] = dict(events)
    coverage["observability"] = {
        "aggregate_children": "observed" if events[
            "tx_child" if case == "discovery131" else "mac_tx_child"] else "unavailable",
        "receiver_state": "observed" if events[
            "boundary_state" if case == "discovery131" else "receiver_state"] else "unavailable",
        "competing_signals": "observed" if events[
            "rx_begin" if case == "discovery131" else "rx_signal_arrival"] else "unavailable",
        "mac_integer_draws": "observed" if coverage["counts"]["mac_draws"] else "unavailable",
        "phy_random_tape": "observed" if events[
            "sync_decision" if case == "discovery131" else "rx_sync_draw"] and events[
            "phy_uniform" if case == "discovery131" else "rx_binomial_draw"] else "unavailable",
        "nwk_hop_capacity": "observed" if case == "source5_132" and
            events["node5_nwk_gate"] and events["node5_hop_admit"] else "unavailable",
    }
    m["replay"] = {"status": "replay_pending"}
    manifest_path.write_text(json.dumps(m, indent=2) + "\n")
    validated = subprocess.run([sys.executable, str(schema / "validate_two_case.py"),
                                str(manifest_path)], capture_output=True, text=True)
    if validated.returncode:
        manifest_path.rename(manifest_path.with_suffix(".invalid.json"))
        raise RuntimeError(f"{case} manifest rejected: {validated.stdout} {validated.stderr}")
    return json.loads(validated.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--case", choices=["discovery131", "source5_132"], action="append")
    arguments = parser.parse_args()
    results = {}
    for name in arguments.case or ["discovery131", "source5_132"]:
        try:
            results[name] = promote(arguments.kit.resolve(), arguments.native_root.resolve(), name)
        except (AssertionError, OSError, ValueError, KeyError, RuntimeError) as error:
            results[name] = {"accepted_manifest": False, "error": str(error)}
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(r.get("accepted_manifest") for r in results.values()) else 1)
