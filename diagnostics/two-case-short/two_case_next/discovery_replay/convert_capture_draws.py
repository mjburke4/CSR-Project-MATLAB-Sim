#!/usr/bin/env python3
"""Bind native seed-131 receiver capture to the historical replay TX IDs.

This is intentionally strict: a fresh native run with a different history,
unknown signal ID, or unavailable random-draw record cannot become an oracle.
The native capture uses physical IDs `(node<<32)|ordinal`; the bound fixture
uses accepted differential-trace `tx_start.event_index` as `tx_id`.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

RECEIVERS = {2, 5}
START_NS = 25_000_000_000
STOP_NS = 85_000_000_000
PURPOSE = {"sync_decision": "sync_threshold_db",
           "header": "header_uniform", "payload": "payload_uniform"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()



def receiver_state_history(fixture_case: Path, trace: Path, receivers: set[int]):
    """Separate actual external wake/sleep from PHY-owned state outputs.

    SetReceiveState calls include completion echoes and calls ignored while TX;
    mac_state records are actual transitions. Never infer ownership from an
    expected receive success. Idle/Search transitions are MAC inputs to PHY;
    Track/Tx transitions and their Search returns are PHY outputs.
    """
    with (fixture_case / "initial_states.csv").open(newline="") as stream:
        previous = {int(r["node"]): r["state"] for r in csv.DictReader(stream)}
    with (fixture_case / "states.csv").open(newline="") as stream:
        original = list(csv.DictReader(stream))
    with trace.open(newline="") as stream:
        actual = [{"time_ns": str(round(float(r["time_s"]) * 1e9)),
                   "event_order": r["event_index"], "node": r["node"],
                   "state": r["detail"]}
                  for r in csv.DictReader(stream)
                  if r["event"] == "mac_state" and
                  START_NS <= round(float(r["time_s"]) * 1e9) < STOP_NS]
    assert actual == original, "fresh native state history differs from accepted fixture"
    ownership = {("idle", "search"): "external_wake",
                 ("search", "idle"): "external_sleep",
                 ("search", "track"): "phy_acquisition",
                 ("track", "search"): "phy_receive_completion",
                 ("search", "tx"): "phy_transmit_start",
                 ("idle", "tx"): "phy_transmit_start",
                 ("track", "tx"): "phy_transmit_start",
                 ("tx", "search"): "phy_transmit_completion"}
    audit, inputs = [], []
    for r in actual:
        node = int(r["node"])
        before, after = previous[node], r["state"]
        previous[node] = after
        assert (before, after) in ownership, ("unknown state transition", r, before)
        if node not in receivers:
            continue
        row = {"time_ns": int(r["time_ns"]), "event_order": int(r["event_order"]),
               "node": node, "state_before": before, "state": after,
               "origin": ownership[(before, after)]}
        audit.append(row)
        if row["origin"].startswith("external_"):
            inputs.append(row)
    return inputs, audit


def write_rows(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)

def run(capture: Path, fixture: Path, output: Path, mac_inputs: Path,
        mac_tx: Path) -> dict:
    assert output.parent.resolve() == capture.parent.resolve(), (
        "Place bound PHY draw CSV beside capture.jsonl for hash verification")
    manifest = json.loads((fixture / "manifest.json").read_text())
    assert manifest["schema"] == "csr-discovery-observed-history-v1"
    info = next(c for c in manifest["cases"] if c["seed"] == 131)
    tx_file = fixture / "s131/tx.csv"
    assert file_hash(tx_file) == info["fixture_sha256"]["tx_csv"]
    with tx_file.open(newline="") as stream:
        original_tx = list(csv.DictReader(stream))
    by_time = {(int(row["time_ns"]), int(row["node"])): row
               for row in original_tx}
    assert len(by_time) == info["tx_count"]
    with mac_tx.open(newline="") as stream:
        all_mac = list(csv.DictReader(stream))
    all_mac_keys = [(int(row["time_ns"]), int(row["node"])) for row in all_mac]
    assert len(all_mac_keys) == len(set(all_mac_keys)), "duplicate native MAC TX identity"
    # Native MAC capture includes the complete 0–85 s warmup. The receiver
    # fixture covers only 25–85 s; the separate canonical-prefix gate still
    # verifies every native event before this replay window.
    mac = {key: row for key, row in zip(all_mac_keys, all_mac)
           if START_NS <= key[0] < STOP_NS}
    assert mac, "native MAC TX export is empty"
    assert set(mac) == set(by_time), "native MAC TX differs from accepted replay window"
    lines = [json.loads(line) for line in capture.read_text().splitlines() if line]
    assert lines and all(row["case_id"] == "discovery131" for row in lines)
    assert all(row["event_order"] == n for n, row in enumerate(lines, 1))
    assert all(25e9 <= row["time_ns"] < 85e9 for row in lines)
    assert all(a["time_ns"] <= b["time_ns"] for a, b in zip(lines, lines[1:]))
    signals = {}
    actual_power = {}
    boundary = {}
    for row in lines:
        if row["event"] == "boundary_state":
            boundary[row["node"]] = row
        if row["event"] != "tx_start":
            continue
        original = by_time.pop((row["time_ns"], row["node"]), None)
        assert original is not None, ("unexpected native TX", row["time_ns"], row["node"])
        assert int(row["detail"]["payload_bytes"]) == int(original["wire_bytes"])
        assert int(row["detail"]["rate_kbps"]) == int(original["rate_kbps"])
        assert row["detail"]["preamble"] == original["preamble"]
        assert int(row["detail"]["sequence"]) == int(original["sequence"])
        power = float(row["detail"]["tx_power_dbm"])
        assert math.isfinite(power) and -36 <= power <= 33
        assert abs(power-float(original["tx_power_dbm"]))<1e-8, (
            "new native TX power differs from accepted RX/pathloss evidence",
            row["time_ns"],row["node"])
        key = (row["time_ns"],row["node"])
        if key in mac:
            native_mac = mac[key]
            assert int(native_mac["wirebytes"]) == int(original["wire_bytes"])
            assert int(native_mac["rate"]) == int(original["rate_kbps"])
            assert int(native_mac["preamble_bits"]) == (7888 if original["preamble"]=="long" else 104)
            assert abs(float(native_mac["power"])-power) < 1e-9, (
                "PHY/MAC actual TX power disagree", key)
        actual_power[key] = power
        assert row["tx_id"] not in signals
        signals[row["tx_id"]] = int(original["tx_id"])
    assert not by_time, ("missing native TX count", len(by_time))
    assert len(actual_power) == len(original_tx)
    assert len(boundary) == 7
    assert all(not x["detail"]["active_signal_ids"] for x in boundary.values())
    with (fixture / "s131/initial_states.csv").open(newline="") as stream:
        initial = {int(x["node"]): x["state"] for x in csv.DictReader(stream)}
    assert all(boundary[node]["state_before"].lower() == state
               for node, state in initial.items()), "25-second receiver state differs"

    draws = []
    counts = Counter()
    for row in lines:
        if row["node"] not in RECEIVERS or row["event"] not in (
                "sync_decision", "phy_uniform"):
            continue
        counts[row["event"]] += 1
        assert row["tx_id"] in signals, ("unbound native receiver signal", row)
        detail = row["detail"]
        if row["event"] == "sync_decision":
            ordinal, purpose, value = 0, PURPOSE["sync_decision"], float(detail["threshold_db"])
        else:
            ordinal = int(detail["ber_interval_index"]) + 1
            purpose = PURPOSE[detail["component"]]
            assert int(detail["draw_ordinal"]) in (1, 2)
            value = float(detail["uniform"])
            assert 0 <= value <= 1
        draws.append({"time_ns": row["time_ns"],
                      "event_order": row["event_order"],
                      "node": row["node"], "tx_id": signals[row["tx_id"]],
                      "interval_ordinal": ordinal,"purpose": purpose,
                      "value": format(value, ".17g")})
    assert draws and counts["sync_decision"] > 0
    keys = [(r["node"], r["tx_id"], r["interval_ordinal"], r["purpose"]) for r in draws]
    assert len(keys) == len(set(keys)), "duplicate receiver draw identity"
    with mac_inputs.open(newline="") as stream:
        requests = [row for row in csv.DictReader(stream)
                    if row["kind"] == "receiver_state" and
                    int(row["node"]) in RECEIVERS and
                    START_NS <= int(row["time_ns"]) < STOP_NS]
    assert requests, "native receiver-state request audit is required"
    native_trace = capture.parent / "ns3-trace.csv"
    assert native_trace.is_file(), "fresh native differential state history is required"
    for name in ("states.csv", "initial_states.csv"):
        assert file_hash(fixture / "s131" / name) == info["fixture_sha256"][name.replace(".", "_")]
    states, state_audit = receiver_state_history(fixture / "s131", native_trace, RECEIVERS)
    # Wake/sleep observers provide an independent source check, including
    # actual transitions that the MAC request hook can omit as internalState.
    observed_external = [row for row in lines
                         if row["node"] in RECEIVERS and
                         row["event"] in ("receiver_wake", "receiver_sleep")]
    expected_external = {(row["time_ns"], row["node"], row["state_before"], row["state"])
                         for row in states}
    observed_keys = {(row["time_ns"], row["node"], row["state_before"], row["state_after"])
                     for row in observed_external}
    assert observed_keys == expected_external, "wake/sleep observer and actual state trace disagree"
    assert len(observed_keys) == len(observed_external), "duplicate wake/sleep observer"
    # Both TX and actual state event_order now use the same differential
    # trace counter. A true same-node external action/TX tie still needs a
    # causal adapter rather than arbitrary FIFO insertion.
    tx_times = {(row["time_ns"], row["node"]) for row in lines
                if row["event"] == "tx_start"}
    assert all((row["time_ns"], row["node"]) not in tx_times for row in states), (
        "same-node external state/TX time tie needs explicit ordering")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, list(draws[0]))
        writer.writeheader()
        writer.writerows(draws)
    state_path = output.parent / "receiver_inputs.csv"
    audit_path = output.parent / "receiver_state_audit.csv"
    request_path = output.parent / "receiver_request_audit.csv"
    state_fields = ["time_ns", "event_order", "node", "state_before", "state", "origin"]
    write_rows(state_path, states, state_fields)
    write_rows(audit_path, state_audit, state_fields)
    write_rows(request_path, requests, list(requests[0]))
    actual_tx_path = output.parent / "tx_inputs.csv"
    actual_tx = []
    for row in original_tx:
        new = dict(row)
        new["tx_power_dbm"] = format(actual_power[(int(row["time_ns"]),int(row["node"]))], ".17g")
        actual_tx.append(new)
    with actual_tx_path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,list(actual_tx[0]))
        writer.writeheader()
        writer.writerows(actual_tx)
    result = {"schema": "csr-discovery-bound-phy-draws-v2",
              "state_input_policy": "actual_idle_search_transitions_only",
              "capture_sha256": file_hash(capture), "fixture_tx_sha256": file_hash(tx_file),
              "draws_sha256": file_hash(output),"mac_inputs_sha256":file_hash(mac_inputs),
              "mac_tx_sha256":file_hash(mac_tx),
              "receiver_inputs_sha256":file_hash(state_path),
              "receiver_state_audit_sha256":file_hash(audit_path),
              "receiver_request_audit_sha256":file_hash(request_path),
              "native_state_trace_sha256":file_hash(native_trace),
              "fixture_states_sha256":info["fixture_sha256"]["states_csv"],
              "fixture_initial_states_sha256":info["fixture_sha256"]["initial_states_csv"],
              "receiver_request_audit_count":len(requests),
              "receiver_actual_state_count":len(state_audit),
              "observer_wake_sleep_crosscheck_count":len(observed_external),
              "tx_inputs_sha256":file_hash(actual_tx_path),
              "actual_power_min_dbm":min(actual_power.values()),
              "actual_power_max_dbm":max(actual_power.values()),
              "mac_power_crosscheck_count":len(mac),
              "external_receiver_input_count":len(states),
              "capture_tx_count": len(signals),
              "draw_count": len(draws),"receiver_counts": dict(counts),
              "complete_common_input": False,
              "reason": "PHY boundary only; state-output agreement is checked by replay; network/MAC/HOP behavior is outside this gate"}
    (output.parent / "phy_draws.provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",type=Path,required=True)
    parser.add_argument("--fixture",type=Path,default=Path(__file__).parent / "fixture")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--mac-inputs",type=Path,required=True)
    parser.add_argument("--mac-tx",type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.capture,args.fixture,args.output,args.mac_inputs,args.mac_tx),indent=2))
