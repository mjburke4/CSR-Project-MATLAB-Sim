#!/usr/bin/env python3
"""Fail-closed join of a fresh native capture to the exact node-4 RX oracle.

This creates a MATLAB input tape only after a full canonical native prefix,
clean 300-s PHY boundary, all aggregate children, and receiver random draws
are present. It never manufactures a missing draw or ACK child.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path

from build_fixture import HERE, REFERENCE, START, STOP, digest, ns

FIELDS = ["time_ns", "event_order", "node", "tx_id", "interval_ordinal",
          "purpose", "value", "draw_ordinal", "component", "interval_start_ns",
          "interval_end_ns", "bits", "probability"]
INTERVAL_FIELDS = ["time_ns", "event_order", "node", "tx_id", "interval_ordinal",
                   "interval_start_ns", "interval_end_ns", "noise_watts",
                   "jsr_db", "offset_sec", "collisions", "same_rate_interference"]
RX_STATES = ("idle", "search")


def receiver_history(observed: list[dict], mac_inputs: list[dict],
                     mac_tx: list[dict], trace: list[dict], initial: str):
    """Separate MAC wake/sleep commands from PHY state output and refreshes.

    The MAC input observer logs calls to SetReceiveState, including redundant
    RefreshDutyState calls made inside PHY callbacks. Those are observations,
    not exogenous commands to inject ahead of the replayed PHY callback.
    Conversely, MAC IdleRts deliberately suppresses its MAC-input hook, so its
    actual Idle->Search transition must be recovered from the state trace.
    """
    transitions = []
    previous = initial
    for row in trace:
        at = ns(row["time_s"])
        if row["event"] != "mac_state" or row["node"] != "4" or not START <= at < STOP:
            continue
        after = row["detail"].lower()
        assert after in {"idle", "search", "track", "tx"} and after != previous
        pair = (previous, after)
        if set(pair) == {"idle", "search"}:
            owner = "external_mac"
        elif after == "tx":
            owner = "phy_tx_start"
        elif pair == ("tx", "search"):
            owner = "phy_tx_complete"
        elif pair == ("search", "track"):
            owner = "phy_acquire"
        elif pair == ("track", "search"):
            owner = "phy_rx_complete"
        else:
            raise AssertionError(("unclassified native receiver transition", at, pair))
        transitions.append({"time_ns": at, "event_order": row["event_index"],
                            "node": 4, "state_before": previous,
                            "state_after": after, "owner": owner})
        previous = after

    # The two independently recorded state streams must agree. Direct TX
    # start/completion assignments bypass SetReceiveState and occur only in
    # the full trace, while all other real transitions have observer rows.
    observer_changes = [(int(r["time_ns"]), r["state_before"], r["state_after"])
                        for r in observed if r["node"] == "4" and
                        r["event"] == "receiver_state"]
    actual_changes = [(r["time_ns"], r["state_before"], r["state_after"])
                      for r in transitions if r["owner"] not in
                      {"phy_tx_start", "phy_tx_complete"}]
    assert observer_changes == actual_changes, "native actual state streams differ"
    tx_start = {int(r["time_ns"]) for r in mac_tx if r["node"] == "4" and
                START <= int(r["time_ns"]) < STOP}
    tx_end = {int(r["time_ns"]) + int(r["duration_ns"]) for r in mac_tx
              if r["node"] == "4" and
              START <= int(r["time_ns"]) + int(r["duration_ns"]) < STOP}
    assert {r["time_ns"] for r in transitions if r["owner"] == "phy_tx_start"} == tx_start
    assert {r["time_ns"] for r in transitions if r["owner"] == "phy_tx_complete"} == tx_end
    acquire = {int(r["time_ns"]) for r in observed if r["node"] == "4" and
               r["event"] == "rx_acquire"}
    assert {r["time_ns"] for r in transitions if r["owner"] == "phy_acquire"} == acquire

    state_rows = [{"time_ns": r["time_ns"], "event_order": r["event_order"],
                   "node": 4, "state": r["state_after"]}
                  for r in transitions if r["owner"] == "external_mac"]
    assert [(r["time_ns"], r["state"]) for r in state_rows] == [(300001000000, "search")], (
        "bounded native external wake/sleep history changed")
    arrivals = {int(r["time_ns"]) for r in observed if r["node"] == "4" and
                r["event"] == "rx_signal_arrival"}
    decisions = {int(r["time_ns"]) for r in observed if r["node"] == "4" and
                 r["event"] in {"rx_phy_decision", "rx_prior_stage"}}
    receive_returns = {r["time_ns"] for r in transitions if r["owner"] == "phy_rx_complete"}
    assert receive_returns <= decisions, "unexpected delayed receiver return in this capture"
    audit = []
    for row in mac_inputs:
        at = int(row["time_ns"])
        if row["kind"] != "receiver_state" or row["node"] != "4" or not START <= at < STOP:
            continue
        if row["value"].lower() not in RX_STATES:
            continue
        assert row["value"].lower() == "search", "unclassified external receiver request"
        if at in tx_end:
            context = "tx_completion_refresh"
        elif at in arrivals:
            context = "signal_arrival_refresh"
        elif at in receive_returns:
            context = "tracked_completion_refresh"
        elif at in decisions:
            context = "other_completion_refresh"
        else:
            raise AssertionError(("receiver request lacks native PHY context", row))
        audit.append({"time_ns": at, "mac_input_event_order": row["event_order"],
                      "node": 4, "requested_state": "search", "classification": context,
                      "replayed_as_input": 0})
    counts = Counter(r["classification"] for r in audit)
    assert counts == {"tx_completion_refresh": 44, "signal_arrival_refresh": 87,
                      "tracked_completion_refresh": 61, "other_completion_refresh": 43}
    assert Counter(r["owner"] for r in transitions) == {
        "external_mac": 1, "phy_tx_start": 44, "phy_tx_complete": 44,
        "phy_acquire": 61, "phy_rx_complete": 61}
    return state_rows, transitions, audit


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        assert reader.fieldnames, f"missing CSV header: {path}"
        return list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def strict_prefix(prefix: Path, observed: Path) -> int:
    with gzip.open(prefix, "rt", newline="") as baseline, observed.open(newline="") as current:
        old = csv.DictReader(baseline)
        new = csv.DictReader(current)
        assert old.fieldnames == new.fieldnames, "native full-trace CSV schema differs"
        count = 0
        for expected in old:
            actual = next(new, None)
            assert actual == expected, ("native prefix mismatch", count)
            count += 1
        next_row = next(new, None)
        assert next_row is None or ns(next_row["time_s"]) >= STOP, "extra native row before 330 s"
    assert count == 48_919
    return count


def detail(row: dict) -> dict:
    value = json.loads(row["detail_json"])
    assert isinstance(value, dict)
    return value


def assert_bool(value: str, label: str) -> bool:
    if value in ("0", "false", "False"):
        return False
    if value in ("1", "true", "True"):
        return True
    raise AssertionError(f"non-boolean {label}: {value!r}")


def capture_guard(root: Path, expected_sha: str) -> dict:
    manifest_path = root / "source5_132.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema"] == "csr-two-case-capture-v1"
    assert manifest["case_id"] == "source5_132" and manifest["seed"] == 132
    assert manifest["window_ns"] == [START, STOP]
    assert manifest["reference_lineage"]["original_full_trace_sha256"] == expected_sha
    assert manifest["capture"]["status"] == "verified"
    assert manifest["capture"]["prefix_fidelity"] == "passed"
    assert manifest["capture"]["prefix_rows"] == 48_919
    assert manifest["capture"]["prefix_end_ns"] == STOP
    for source in manifest["source_files"]:
        path = root / source["path"]
        assert path.is_file() and digest(path) == source["sha256"], ("capture source changed", source)
    fidelity = json.loads((root / "reference/fidelity.json").read_text())
    assert fidelity["schema"] == "csr-source5-native-capture-v1" and fidelity["all_passed"] is True
    assert fidelity["source_capture"]["exact_prefix"] is True
    for name, sha in fidelity["input_sha256"].items():
        assert digest(root / "inputs" / name) == sha, ("MAC input changed", name)
    assert digest(root / "capture/source5_native.tsv") == fidelity["observer_sha256"]
    assert digest(root / "provenance/native_s132_prefix_0_330.csv.gz") == expected_sha or (
        # The compact prefix is a separate immutable extract of the full
        # source; the fixture SHA check below binds the extract itself.
        digest(root / "provenance/native_s132_prefix_0_330.csv.gz") ==
        "6819889725eb891112b57dbc9f8e63c35af7e87fcf64f77c6dbe3f490d3c63a8")
    return manifest


def bind(capture: Path, output: Path, fixture: Path, prefix: Path) -> dict:
    provenance = json.loads((fixture / "manifest.json").read_text())
    assert provenance["schema"] == "csr-source5-node4-rx-observed-v1"
    assert provenance["window_ns"] == [START, STOP]
    assert digest(prefix) == provenance["native_prefix_sha256"]
    for name, sha in provenance["fixture_sha256"].items():
        assert digest(fixture / name) == sha, ("fixture changed", name)
    manifest = capture_guard(capture, provenance["original_full_trace_sha256"])
    assert strict_prefix(prefix, capture / manifest["capture"]["trace_path"]) == provenance["prefix_rows"]
    physical = read_csv(fixture / "tx.csv")
    oracle = read_csv(fixture / "expected.csv")
    observed = read_csv(capture / manifest["capture"]["observations_path"], delimiter="\t")
    assert observed and all(row["case_id"] == "source5_132" for row in observed)
    assert [int(r["event_order"]) for r in observed] == list(range(1, len(observed) + 1))
    assert all(START <= int(r["time_ns"]) < STOP for r in observed)
    assert all(int(a["time_ns"]) <= int(b["time_ns"]) for a, b in zip(observed, observed[1:]))
    mac_tx = read_csv(capture / manifest["capture"]["mac_tape_paths"]["tx"])
    mac_children = read_csv(capture / manifest["capture"]["mac_tape_paths"]["tx_frames"])
    mac_inputs = read_csv(capture / manifest["capture"]["mac_tape_paths"]["inputs"])
    observed_tx = [r for r in observed if r["event"] in {"mac_tx", "node5_mac_tx"}]
    by_time_node = {(int(r["time_ns"]), int(r["node"])): r for r in physical}
    assert len(by_time_node) == len(physical) == 299
    fresh_ids = {}
    for row in observed_tx:
        key = (int(row["time_ns"]), int(row["node"]))
        reference = by_time_node.pop(key, None)
        assert reference is not None, ("unexpected physical TX", key)
        signal_id = int(row["tx_id"])
        assert signal_id not in fresh_ids and signal_id != 0
        fresh_ids[signal_id] = reference
        info = detail(row)
        assert int(info["sequence"]) == int(reference["sequence"])
        assert int(row["peer"]) == int(reference["peer"])
        assert int(row["kind"]) == int({
            "data": 0, "ack": 1, "dack": 2, "hello": 3, "discover": 4,
            "neighbor_check": 5, "routing_control": 6, "snmp": 7,
            "key_request": 8, "key_update": 9, "pairwise32_data": 10,
            "neighborcast": 11}[reference["packet_type"]])
    assert not by_time_node and len(observed_tx) == len(physical), "missing native physical TX"
    mac_by_time = {(int(r["time_ns"]), int(r["node"])): r for r in mac_tx
                   if START <= int(r["time_ns"]) < STOP}
    assert len(mac_by_time) == 299
    by_child = defaultdict(list)
    for row in mac_children:
        at = int(row["time_ns"])
        if START <= at < STOP:
            by_child[(at, int(row["node"]))].append(row)
    bound_children = []
    bound_tx = []
    by_id = {int(r["tx_id"]): r for r in physical}
    for fresh, row in fresh_ids.items():
        key = (int(row["time_ns"]), int(row["node"]))
        tape = mac_by_time.pop(key)
        children = sorted(by_child.pop(key), key=lambda r: int(r["child_index"]))
        assert children and [int(c["child_index"]) for c in children] == list(range(len(children)))
        assert int(tape["wirebytes"]) == int(row["wire_bytes"]) == sum(
            int(c["wirebytes"]) for c in children)
        assert int(tape["rate"]) == int(row["rate_kbps"])
        assert int(tape["preamble_bits"]) == (7888 if row["preamble"] == "long" else 104)
        assert int(children[0]["sequence"]) == int(row["sequence"])
        actual_power = float(tape["power"])
        assert math_is_finite(actual_power) and -200 < actual_power < 200
        bound_tx.append({**row, "tx_power_dbm":tape["power"]})
        for child in children:
            bound_children.append({"tx_id": row["tx_id"], "native_signal_id": fresh,
                                   "time_ns": row["time_ns"], "node": row["node"],
                                   "child_index": child["child_index"],
                                   "source": child["source"],
                                   "destination": child["destination"],
                                   "sequence": child["sequence"], "type": child["type"],
                                   "wirebytes": child["wirebytes"],
                                   "frame_id": child["frame_id"]})
    assert not mac_by_time and not by_child
    bound_tx.sort(key=lambda x:int(x["event_order"]))
    assert [(r["time_ns"],r["node"],r["tx_id"]) for r in bound_tx] == [
        (r["time_ns"],r["node"],r["tx_id"]) for r in physical]
    observed_child = [r for r in observed if r["event"] == "mac_tx_child"]
    assert len(observed_child) == len(bound_children)
    by_triple = {(int(c["native_signal_id"]), int(c["child_index"])): c for c in bound_children}
    for row in observed_child:
        key = (int(row["tx_id"]), int(detail(row)["child_index"]))
        child = by_triple.pop(key)
        assert int(row["time_ns"]) == int(child["time_ns"])
        assert int(row["frame_id"]) == int(child["frame_id"])
        assert int(row["kind"]) == int(child["type"])
        assert int(row["peer"]) == int(child["destination"])
        assert int(detail(row)["sequence"]) == int(child["sequence"])
    assert not by_triple

    boundary = [r for r in observed if r["event"] == "boundary_state" and int(r["node"]) == 4]
    assert len(boundary) == 1 and int(boundary[0]["time_ns"]) == START
    b = boundary[0]
    data = detail(b)
    for name in ("rx_signal_count", "tracked_id"):
        assert int(data[name]) == 0, ("active receiver PHY at 300", name, data[name])
    assert data["rx_signal_ids"] in ("", "[]"), "receiver has in-flight signals"
    for name in ("acquisition_pending", "done_rx_pending", "signal_wake_pending"):
        assert not assert_bool(data[name], name), ("pending node4 PHY timer at t300", name)
    assert b["state_before"].lower() == provenance["initial_node4_state"]
    assert b["state_before"].lower() in RX_STATES
    assert not assert_bool(data["sync_present"], "sync_present")

    # Replay actual MAC wake/sleep changes only. Calls emitted inside the
    # native PHY are audit evidence; PHY state transitions remain outputs.
    state_rows, state_expected, state_request_audit = receiver_history(
        observed, mac_inputs, mac_tx,
        read_csv(capture / manifest["capture"]["trace_path"]),
        provenance["initial_node4_state"])
    tx_times = {int(r["time_ns"]) for r in physical}
    assert not any(int(r["time_ns"]) in tx_times for r in state_rows), "same-time TX/state order unresolved"
    assert all(int(a["time_ns"]) <= int(z["time_ns"]) for a, z in zip(state_rows, state_rows[1:]))
    assert len({int(r["event_order"]) for r in state_rows}) == len(state_rows)

    expected_by_fresh = {fresh: next((x for x in oracle if int(x["tx_id"]) == int(row["tx_id"])), None)
                         for fresh, row in fresh_ids.items() if int(row["node"]) != 4}
    assert len(expected_by_fresh) == len(oracle) == 255 and all(expected_by_fresh.values())
    decisions = [r for r in observed if r["node"] == "4" and
                 r["event"] in {"rx_phy_decision", "rx_prior_stage"}]
    by_decision = {}
    for r in decisions:
        signal = int(r["tx_id"])
        native = expected_by_fresh.get(signal)
        assert native is not None and native["reason"] != "closure"
        assert signal not in by_decision
        assert abs(int(r["time_ns"]) - int(native["rx_time_ns"])) <= 2
        assert int(r["peer"]) == int(native["source"])
        if r["event"] == "rx_phy_decision":
            assert assert_bool(r["outcome"], "rx_phy_decision") == bool(int(native["success"]))
        else:
            assert not int(native["success"]), "accepted decision absent PHY tracked path"
        for observed_key, reference_key in [("header_errors", "header_errors"),
                                            ("payload_errors", "payload_errors"),
                                            ("collision_count", "collision_count")]:
            if native[reference_key] != "" and r["event"] == "rx_phy_decision":
                assert int(detail(r)[observed_key]) == int(native[reference_key]), (
                    "observer vs original PHY outcome", signal, observed_key)
        by_decision[signal] = r
    assert len(by_decision) == sum(r["reason"] != "closure" for r in oracle)
    assert all(x["reason"] == "closure" or fresh in by_decision
               for fresh, x in expected_by_fresh.items())
    arrivals = [r for r in observed if r["node"] == "4" and
                r["event"] == "rx_signal_arrival"]
    by_arrival = {}
    for r in arrivals:
        fresh = int(r["tx_id"])
        native = expected_by_fresh.get(fresh)
        assert native is not None and native["reason"] != "closure"
        assert fresh not in by_arrival
        info = detail(r)
        assert int(r["peer"]) == int(native["source"])
        assert abs(ns(info["end_sec"]) - int(native["rx_time_ns"])) <= 2
        assert abs(ns(info["start_sec"]) - int(r["time_ns"])) <= 2
        assert int(r["event_order"]) < int(by_decision[fresh]["event_order"])
        by_arrival[fresh] = r
    assert len(by_arrival) == len(by_decision), "missing or extra receiver signal arrival"
    sync_draws = {(int(r["tx_id"]),int(r["node"])): r for r in observed
                  if r["node"] == "4" and r["event"] == "rx_sync_draw"}
    sync_gates = {(int(r["tx_id"]),int(r["node"])): r for r in observed
                  if r["node"] == "4" and r["event"] == "rx_sync_gate"}
    assert len(sync_draws) == sum(r["node"] == "4" and r["event"] == "rx_sync_draw"
                                  for r in observed)
    assert len(sync_gates) == sum(r["node"] == "4" and r["event"] == "rx_sync_gate"
                                  for r in observed)
    assert sync_draws.keys() == sync_gates.keys(), "SYNC threshold draw/gate mismatch"
    for key, draw in sync_draws.items():
        gate = sync_gates[key]
        assert int(draw["event_order"]) < int(gate["event_order"])
        assert abs(int(draw["time_ns"]) - int(gate["time_ns"])) <= 2
        assert abs(float(detail(draw)["draw"]) -
                   float(detail(gate)["sync_threshold_db"])) <= 1e-12

    native_children = defaultdict(list)
    for r in observed:
        if r["node"] == "4" and r["event"] == "rx_child":
            assert int(r["tx_id"]) in expected_by_fresh
            native_children[int(r["tx_id"])].append(r)
    by_signal_children = defaultdict(list)
    for child in bound_children:
        by_signal_children[int(child["native_signal_id"])].append(child)
    for fresh, native in expected_by_fresh.items():
        actual = native_children.pop(fresh, [])
        wanted = by_signal_children[fresh] if int(native["success"]) else []
        assert len(actual) == len(wanted), ("missing or extra received aggregate child", fresh)
        assert Counter((int(r["frame_id"]), int(detail(r)["sequence"]), int(r["kind"]))
                       for r in actual) == Counter((int(c["frame_id"]), int(c["sequence"]),
                                                    int(c["type"])) for c in wanted)
    assert not native_children
    all_ack_children = [c for c in bound_children if int(c["type"]) == 1 and
                        int(c["node"]) != 4]
    ack_children = [c for c in all_ack_children if int(c["destination"]) == 4]
    ack_outcomes = []
    for child in ack_children:
        native = expected_by_fresh[int(child["native_signal_id"])]
        ack_outcomes.append({"tx_id": child["tx_id"], "source": child["node"],
                             "sequence": child["sequence"], "frame_id": child["frame_id"],
                             "native_success": native["success"],
                             "native_reason": native["reason"],
                             "rx_time_ns": native["rx_time_ns"]})
    native_ack_rx = Counter((int(r["tx_id"]), int(r["frame_id"]), int(detail(r)["sequence"]))
                            for r in observed if r["node"] == "4" and r["event"] == "node4_ack_rx"
                            and int(r["tx_id"]) in expected_by_fresh)
    expected_ack_rx = Counter((int(c["native_signal_id"]), int(c["frame_id"]),
                               int(c["sequence"])) for c in all_ack_children
                              if int(expected_by_fresh[int(c["native_signal_id"])]["success"]))
    assert native_ack_rx == expected_ack_rx, "captured ACK child reception differs"
    native_ack_drop = Counter((int(r["tx_id"]), int(detail(r)["sequence"]))
                              for r in observed if r["node"] == "4" and
                              r["event"] == "node4_ack_drop" and
                              int(r["tx_id"]) in expected_by_fresh)
    expected_ack_drop = Counter((int(c["native_signal_id"]), int(c["sequence"]))
                                for c in all_ack_children if not int(
                                    expected_by_fresh[int(c["native_signal_id"])]["success"]) and
                                expected_by_fresh[int(c["native_signal_id"])]["reason"] != "closure")
    assert native_ack_drop == expected_ack_drop, "captured ACK child drops differ"

    intervals = []
    by_interval = {}
    per_signal_ordinals = defaultdict(list)
    for r in observed:
        if r["node"] != "4" or r["event"] != "rx_error_interval":
            continue
        fresh = int(r["tx_id"])
        assert fresh in expected_by_fresh, ("unmapped error interval", fresh)
        data = detail(r)
        ordinal = int(data["interval_ordinal"])
        start_ns, end_ns = int(data["interval_start_ns"]), int(data["interval_end_ns"])
        assert ordinal > 0 and start_ns < end_ns and abs(end_ns-int(r["time_ns"])) <= 2
        assert float(data["noise_watts"]) > 0
        same_rate = assert_bool(data["same_rate_interference"], "same_rate_interference")
        key = (fresh, ordinal)
        assert key not in by_interval
        by_interval[key] = (start_ns, end_ns)
        per_signal_ordinals[fresh].append(ordinal)
        intervals.append({"time_ns": r["time_ns"], "event_order": r["event_order"],
                          "node": 4, "tx_id": fresh_ids[fresh]["tx_id"],
                          "interval_ordinal": ordinal,
                          "interval_start_ns": start_ns, "interval_end_ns": end_ns,
                          "noise_watts": data["noise_watts"],
                          "jsr_db": data["jsr_db"], "offset_sec": data["offset_sec"],
                          "collisions": data["collisions"],
                          "same_rate_interference": int(same_rate)})
    assert intervals, "no native node4 error interval input"
    assert all(v == list(range(1,len(v)+1)) for v in per_signal_ordinals.values()), (
        "missing or re-ordered native BER interval")

    draws = []
    for r in observed:
        if int(r["node"]) != 4 or r["event"] not in {"rx_sync_draw", "rx_binomial_draw"}:
            continue
        fresh = int(r["tx_id"])
        assert fresh in expected_by_fresh, ("unmapped receiver draw signal", fresh)
        info = detail(r)
        if r["event"] == "rx_sync_draw":
            ordinal, component, purpose = 0, "sync", "sync_threshold_db"
            interval_start_ns = interval_end_ns = ""
            bits = probability = ""
        else:
            component = info["component"]
            assert component in ("header", "payload"), "unlabeled BER draw"
            purpose = component + "_uniform"
            ordinal = int(info["interval_ordinal"])
            assert ordinal > 0
            interval_start_ns = int(info["interval_start_ns"])
            interval_end_ns = int(info["interval_end_ns"])
            assert interval_start_ns < interval_end_ns and abs(
                interval_end_ns - int(r["time_ns"])) <= 2
            assert by_interval[(fresh, ordinal)] == (interval_start_ns, interval_end_ns)
            bits = int(info["bits"])
            probability = float(info["probability"])
            assert bits > 0 and 0 < probability < 1
            assert assert_bool(info["rng_consumed"], "rng_consumed")
        value = float(info["draw"])
        assert math_is_finite(value) and (r["event"] == "rx_sync_draw" or 0 <= value <= 1)
        draws.append({"time_ns": r["time_ns"], "event_order": r["event_order"],
                      "node": 4, "tx_id": fresh_ids[fresh]["tx_id"],
                      "interval_ordinal": ordinal, "purpose": purpose,
                      "value": format(value, ".17g"),
                      "draw_ordinal": info.get("draw_ordinal", ""),
                      "component": component, "interval_start_ns": interval_start_ns,
                      "interval_end_ns": interval_end_ns, "bits": bits,
                      "probability": probability})
    assert draws and any(r["purpose"] == "sync_threshold_db" for r in draws)
    assert len({(r["tx_id"], r["interval_ordinal"], r["purpose"]) for r in draws}) == len(draws)
    assert all(int(a["event_order"]) < int(z["event_order"]) for a, z in zip(draws, draws[1:]))
    if output.exists():
        assert not any(output.iterdir()), "output exists and is nonempty; choose a fresh directory"
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "tx.csv", list(bound_tx[0]), bound_tx)
    write_csv(output / "phy_draws.csv", FIELDS, draws)
    write_csv(output / "phy_intervals.csv", INTERVAL_FIELDS, intervals)
    write_csv(output / "receiver_inputs.csv", ["time_ns", "event_order", "node", "state"], state_rows)
    write_csv(output / "receiver_state_expected.csv", list(state_expected[0]), state_expected)
    write_csv(output / "receiver_request_audit.csv", list(state_request_audit[0]), state_request_audit)
    write_csv(output / "tx_children.csv", list(bound_children[0]), bound_children)
    write_csv(output / "ack_outcomes.csv", list(ack_outcomes[0]), ack_outcomes)
    summary = {
        "schema": "csr-source5-node4-rx-bound-v1", "status": "native_capture_bound",
        "seed": 132, "window_ns": [START, STOP], "node": 4,
        "native_prefix_sha256": digest(prefix),
        "fixture_manifest_sha256": digest(fixture / "manifest.json"),
        "native_capture_manifest_sha256": digest(capture / "source5_132.manifest.json"),
        "original_native_prefix_rows_verified": 48_919,
        "clean_boundary_at_300s": True,
        "tx_count": 299, "node4_decision_count": 255,
        "node4_observed_phy_decision_count": len(decisions),
        "node4_external_state_count": len(state_rows),
        "receiver_input_semantics": "actual_mac_idle_search_transitions_v2",
        "node4_state_transition_count": len(state_expected),
        "node4_phy_owned_transition_count": sum(r["owner"] != "external_mac" for r in state_expected),
        "node4_refresh_request_count": len(state_request_audit),
        "node4_refresh_classification": dict(Counter(r["classification"] for r in state_request_audit)),
        "node4_draw_count": len(draws), "ack_child_count": len(ack_outcomes),
        "node4_interval_count": len(intervals),
        "node5_ack_child_count": sum(int(r["source"]) == 5 for r in ack_outcomes),
        "source_capture_path": str(capture.resolve()),
        "fixture_path": str(fixture.resolve()),
        "files_sha256": {name: digest(output / name) for name in
                         ["tx.csv", "phy_draws.csv", "phy_intervals.csv", "receiver_inputs.csv",
                          "receiver_state_expected.csv", "receiver_request_audit.csv",
                          "tx_children.csv", "ack_outcomes.csv"]},
        "matlab_executed": False, "parity_verified": False,
    }
    (output / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def math_is_finite(value: float) -> bool:
    import math
    return math.isfinite(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True,
                        help="fresh source5_132_capture output directory")
    parser.add_argument("--output", type=Path, required=True,
                        help="empty directory for hash-bound MATLAB input tape")
    parser.add_argument("--fixture", type=Path, default=HERE / "fixture")
    parser.add_argument("--prefix", type=Path, default=REFERENCE / "native_s132_prefix_0_330.csv.gz")
    args = parser.parse_args()
    print(json.dumps(bind(args.capture, args.output, args.fixture, args.prefix), indent=2))
