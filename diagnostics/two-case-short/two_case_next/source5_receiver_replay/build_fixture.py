#!/usr/bin/env python3
"""Build the immutable, observational seed-132 node-4 PHY oracle.

The native trace contains primary physical frames, not aggregate children or
the PHY draws. Those fields must be joined from a new native capture before a
common-input comparison is possible; this script never invents them.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "schema_review"
PREFIX_SHA = "6819889725eb891112b57dbc9f8e63c35af7e87fcf64f77c6dbe3f490d3c63a8"
SCENARIO_SHA = "fa45217f8631f34d203580842d8a1a12cb18c53a3efbe0b702b2e17aaeb30d48"
START = 300_000_000_000
STOP = 330_000_000_000
TX_FIELDS = ["time_ns", "event_order", "tx_id", "node", "peer", "packet_type",
             "sequence", "wire_bytes", "rate_kbps", "preamble", "tx_power_dbm"]
EXPECTED_FIELDS = ["tx_id", "source", "primary_packet", "sequence", "tx_time_ns",
                   "rx_time_ns", "rx_event_order", "success", "reason",
                   "collision_count", "header_errors", "payload_errors",
                   "total_errors", "rx_power_dbm", "snr_db"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ns(seconds: str) -> int:
    return round(float(seconds) * 1e9)


def write_rows(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def duration_ns(row: dict) -> int:
    assert int(row["rate_kbps"]) == 8, (row["event_index"], "unsupported rate")
    bits = {"short": 104, "long": 7888}[row["detail"]]
    return round(((bits + 48 + 8 * int(row["size_bytes"]) + 32) / 4) * .000510 * 1e9)


def run(prefix: Path, scenario: Path, output: Path) -> dict:
    assert digest(prefix) == PREFIX_SHA, "native exact-prefix fixture changed"
    assert digest(scenario) == SCENARIO_SHA, "seed-132 scenario changed"
    with gzip.open(prefix, "rt", newline="") as stream:
        original = list(csv.DictReader(stream))
    assert len(original) == 48_919 and all(ns(r["time_s"]) < STOP for r in original)
    indices = [int(r["event_index"]) for r in original]
    assert indices == list(range(len(original))), "native event index gap"
    with scenario.open(newline="") as stream:
        points = {int(r["node_id"]): (float(r["x_m"]), float(r["y_m"]),
                                       float(r["height_m"]))
                  for r in csv.DictReader(stream) if r["record"] == "node"}
    assert sorted(points) == [1, 2, 3, 4, 5, 7, 8]
    max_flight_ns = max(round(math.dist(points[i], points[j]) / 3e8 * 1e9)
                        for i in points for j in points if i != j)
    prior_tx = [r for r in original if r["event"] == "tx_start" and ns(r["time_s"]) < START]
    assert prior_tx
    latest_signal_end = max(ns(r["time_s"]) + duration_ns(r) + max_flight_ns for r in prior_tx)
    assert latest_signal_end < START, "prior physical signal overlaps t=300 boundary"
    prior_node4_states = [r for r in original if r["event"] == "mac_state" and
                          r["node"] == "4" and ns(r["time_s"]) < START]
    assert prior_node4_states and prior_node4_states[-1]["detail"] in {"idle", "search"}
    tx_native = [r for r in original if r["event"] == "tx_start" and START <= ns(r["time_s"]) < STOP]
    node4_native = [r for r in original if r["node"] == "4" and
                    r["event"] in {"rx_accept", "rx_drop"} and START <= ns(r["time_s"]) < STOP]
    node4_states = [r for r in original if r["node"] == "4" and r["event"] == "mac_state" and
                    START <= ns(r["time_s"]) < STOP]
    assert len(tx_native) == 299 and len(node4_native) == 255
    tx_times = {(ns(r["time_s"]), int(r["node"])) for r in tx_native}
    assert len(tx_times) == len(tx_native)
    assert all((ns(r["time_s"]), 4) not in tx_times for r in node4_states
               if r["detail"] in {"idle", "search"}), "same-time node4 state/TX tie"
    # A cross-stream tie is deliberately rejected rather than guessed.
    all_tx_times = {ns(r["time_s"]) for r in tx_native}
    assert all(ns(r["time_s"]) not in all_tx_times for r in node4_states
               if r["detail"] in {"idle", "search"}), "same-time receiver state/TX tie"

    all_tx = []
    expected = []
    matched_rx = set()
    for sent in tx_native:
        sent_ns = ns(sent["time_s"])
        all_tx.append({"time_ns": sent_ns, "event_order": sent["event_index"],
                       "tx_id": sent["event_index"], "node": sent["node"],
                       "peer": sent["peer"], "packet_type": sent["packet_type"],
                       "sequence": sent["sequence"], "wire_bytes": sent["size_bytes"],
                       "rate_kbps": sent["rate_kbps"], "preamble": sent["detail"],
                       "tx_power_dbm": 33})
        if sent["node"] == "4":
            continue
        propagate = round(math.dist(points[int(sent["node"])], points[4]) / 3e8 * 1e9)
        predicted_end_ns = sent_ns + duration_ns(sent) + propagate
        candidates = [r for r in node4_native
                      if r["peer"] == sent["node"] and
                      r["packet_type"] == sent["packet_type"] and
                      r["sequence"] == sent["sequence"] and
                      r["size_bytes"] == sent["size_bytes"] and
                      int(r["event_index"]) > int(sent["event_index"]) and
                      abs(ns(r["time_s"]) -
                          (sent_ns if r["reason"] == "closure" else predicted_end_ns)) <= 2]
        assert len(candidates) == 1, ("ambiguous TX→node4 RX", sent["event_index"], candidates)
        got = candidates[0]
        assert got["event_index"] not in matched_rx
        matched_rx.add(got["event_index"])
        expected.append({"tx_id": sent["event_index"], "source": sent["node"],
                         "primary_packet": sent["packet_type"],
                         "sequence": sent["sequence"], "tx_time_ns": sent_ns,
                         "rx_time_ns": ns(got["time_s"]),
                         "rx_event_order": got["event_index"],
                         "success": int(got["event"] == "rx_accept"),
                         "reason": got["reason"],
                         "collision_count": got["detail"].removeprefix("collisions=")
                         if got["detail"].startswith("collisions=") else "",
                         "header_errors": got["header_errors"],
                         "payload_errors": got["payload_errors"],
                         "total_errors": got["total_errors"],
                         "rx_power_dbm": got["rx_power_dbm"],
                         "snr_db": got["snr_db"]})
    assert len(matched_rx) == len(node4_native), "unmatched extra node4 RX"
    assert sum(int(x["success"]) for x in expected if x["source"] == "5" and
               x["primary_packet"] == "ack") == 6
    assert sum(1 for x in expected if x["source"] == "5" and
               x["primary_packet"] == "ack") == 10
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "tx.csv", TX_FIELDS, all_tx)
    write_rows(output / "expected.csv", EXPECTED_FIELDS, expected)
    (output / "scenario.csv").write_bytes(scenario.read_bytes())
    manifest = {
        "schema": "csr-source5-node4-rx-observed-v1", "seed": 132,
        "window_ns": [START, STOP], "native_prefix_sha256": PREFIX_SHA,
        "original_full_trace_sha256": "3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef",
        "prefix_rows": len(original), "last_preboundary_signal_end_upper_bound_ns": latest_signal_end,
        "initial_node4_state": prior_node4_states[-1]["detail"],
        "initial_node4_state_event_index": int(prior_node4_states[-1]["event_index"]),
        "tx_count": len(all_tx), "node4_decision_count": len(expected),
        "node5_ack_decision_count": 10, "node5_ack_accepted_count": 6,
        "fixture_sha256": {name: digest(output / name) for name in
                           ["tx.csv", "expected.csv", "scenario.csv"]},
        "common_input_complete": False,
        "capture_required": "t300 clean node4 PHY boundary; exact native prefix; TX children; all node4 state and PHY draws",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=REFERENCE / "native_s132_prefix_0_330.csv.gz")
    parser.add_argument("--scenario", type=Path, default=REFERENCE / "scenario_s132.csv")
    parser.add_argument("--output", type=Path, default=HERE / "fixture")
    args = parser.parse_args()
    result = run(args.prefix, args.scenario, args.output)
    print(json.dumps({"tx": result["tx_count"], "node4_rx": result["node4_decision_count"],
                      "node5_ack": result["node5_ack_decision_count"]}))
