#!/usr/bin/env python3
"""Audit owner-returned MATLAB T13 loss/recovery evidence without running MATLAB.

Native traces are references, never fabricated owner evidence. Structural
completion and numerical equality are separate results. DATA delivery and HOP
retirement failures can overlap after feedback loss; only the admitted identity
sets, actual terminal records and final custody establish loss conservation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import zipfile

# Immutable, already-reviewed bounded readers and provenance helpers.
from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, evidence_directory, integer,
    inventory, json_object, json_value, logical, number, record_map, records,
    require, safe_name, safe_path, selected_test_names, sha256, verify_bindings,
    verify_references, verify_sources, verify_tests,
)
from analyze_tranche12_return import (
    RELAY_FIELDS as EVENT_FIELDS, DRAW_FIELDS, USAGE_FIELDS, CHECK_FIELDS,
    verify_clean_build, verify_comparison_claim, verify_manifest,
)

SCHEMA = "csr-matlab-tranche-13-validation-v1"
REVIEW_SCHEMA = "csr-matlab-tranche-13-return-review-v1"
PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
ENGINE_PIN = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
CANDIDATE = "evidence/tranche-13-candidate.json"
BASELINE = "evidence/t12/source.json"
BASELINE_SHA = "f5dc6325e01ba199cbd64ecdc36195c6fe18bd74c83bdd81b279dce070b5d70e"
OWNER_SHA = "266a47c167e9b2d50d47abcd77a349b8f474334c9e9742d7abc8cca22547633d"
PARENT_CANDIDATE_SHA = "ebf493fc8d34dc7c7819f14e266bf19b99f0f94441a79da38a801cd7f52292c4"
CORE_BASELINE = "evidence/tranche-10-r2025a-accepted/owner/source_snapshot.json"
CORE_BASELINE_SHA = "9be444b0fb1ffbfe818cab86502a287b19e3da83467d210ef426ec3b19e183da"
REFERENCE = "evidence/tranche-13-loss-reference"
CASES = ("ok", "data", "ack", "out")
NODES = (1, 4, 5)
SOURCES = (4, 5)
STOP = 64_000_000_000
CHECKPOINTS = (8_000_000_000, 9_500_000_000, 20_000_000_000,
               24_000_000_000, 40_000_000_000)
EVENTS = {"generate", "offer", "admit", "blocked", "tx_start", "loss",
          "ingress_before", "ingress_after", "release", "deliver", "checkpoint", "final"}
CASE_FIELDS = ("case", "apps4", "apps5", "duration_seconds", "loss_policy", "loss_start_ns", "loss_stop_ns")
OFFER_FIELDS = ("case", "source", "app_id", "due_ns")
TRANSPORT_FIELDS = ("case", "tx_id", "group_id", "segment_index", "group_segments", "tx_time_ns",
                    "arrival_ns", "sender", "receiver", "kind", "app_source", "app_id", "hop_seq",
                    "ack_bits", "dack_bits", "decision", "reason", "boundary_distance_ns")
TERMINAL_FIELDS = ("case", "order", "time_ns", "node", "app_source", "app_id", "success", "reason")
FAMILIES = (("events", EVENT_FIELDS), ("draws", DRAW_FIELDS), ("usage", USAGE_FIELDS),
            ("transport", TRANSPORT_FIELDS), ("terminal", TERMINAL_FIELDS))


def compare_rows(actual, reference, fields, *, family, time_tolerance_ns=1):
    """Retain every row/field difference, using Decimal for full uint64 fidelity."""
    text_fields = {"case", "event", "purpose", "kind", "decision", "reason"}
    time_fields = {"time_ns", "tx_time_ns", "arrival_ns"}
    differences, timing_nonzero, maximum_time = [], 0, Decimal(0)
    for index in range(max(len(actual), len(reference))):
        left = actual[index] if index < len(actual) else None
        right = reference[index] if index < len(reference) else None
        unequal = []
        if left is None or right is None:
            unequal = ["missing_row"]
        else:
            for field in fields:
                if field in text_fields:
                    same = left[field] == right[field]
                elif field == "success":
                    same = logical(left[field], field) == logical(right[field], field)
                else:
                    delta = abs(number(left[field], field) - number(right[field], field))
                    same = delta <= time_tolerance_ns if field in time_fields else delta == 0
                    if field in time_fields:
                        maximum_time = max(maximum_time, delta)
                        timing_nonzero += delta != 0
                if not same:
                    unequal.append(field)
        if unequal:
            differences.append({"family": family, "row": index + 1, "fields": unequal,
                                "matlab": left, "ns3": right})
    return {"family": family, "matches_native": not differences, "matlab_rows": len(actual),
            "native_rows": len(reference), "paired_rows": min(len(actual), len(reference)),
            "unmatched_rows": len(differences), "nonzero_time_differences": timing_nonzero,
            "maximum_time_difference_ns": str(maximum_time), "differences": differences}


def verify_plan(source_root, candidate):
    require(candidate.get("LossPlan") == "scenarios/loss/plan.json", "Unexpected loss plan path")
    path = source_root / candidate["LossPlan"]
    require(sha256(path) == candidate.get("LossPlanSHA256"), "Loss plan binding mismatch")
    plan = json_object(path)
    fixed = {"schema": "csr-tranche13-loss-input-v1", "source_pin": PIN,
             "cases": list(CASES), "nodes": list(NODES), "gateway": 1, "sources": list(SOURCES), "relay": 5,
             "applications_per_active_source": 48, "application_payload_bytes": 16, "dscp": 0,
             "wire_profile": "bare", "rate_kbps": 128, "power_dbm": 33,
             "slot_profile": "hist-2014-next-tslot-modulo-probe", "slot_range": 31, "slot_reduction": 0,
             "active_nodes": 3, "reported_active_nodes": 3, "duty_cycle": False,
             "initial_mac_state": "Search", "initial_neighbor_reservation": -1,
             "known_neighbors": {"1": [5], "4": [5], "5": [1, 4]}, "next_hops": {"4": 5, "5": 1},
             "route_target": 1, "route_capability": 2, "neighbor_admission_enabled": False,
             "neighbor_freshness_enabled": False, "automatic_route_control_transport": False,
             "matlab_control_retry_seconds": 1000, "matlab_snapshot_watchdog_seconds": 1000,
             "prescribed_sync_present": False, "offered_start_seconds": 0,
             "offered_poll_stop_exclusive_seconds": 40, "application_nsdp_limit": 16,
             "tape_entries_per_node": 1024, "duration_seconds": 64, "loss_boundary_guard_ns": 1000,
             "checkpoint_seconds": [8, 9.5, 20, 24, 40], "events_schema": list(EVENT_FIELDS),
             "draws_output_schema": list(DRAW_FIELDS), "transport_schema": list(TRANSPORT_FIELDS),
             "offers_schema": list(OFFER_FIELDS), "cases_schema": list(CASE_FIELDS)}
    for field, value in fixed.items():
        require(plan.get(field) == value and (type(value) is not bool or type(plan.get(field)) is bool),
                f"Loss fixed plan field changed: {field}")
    require(set(plan.get("event_names", [])) == EVENTS, "Loss event scope changed")
    for field, value in (("slot_seconds", ".013"), ("holdoff_seconds", ".3"), ("offered_poll_seconds", ".02"),
                         ("propagation_seconds", ".000001"), ("pathloss_db", "70"), ("snr_db", "20")):
        require(number(plan.get(field), field) == Decimal(value), f"Loss fixed numeric field changed: {field}")
    cases = csv_rows(source_root / "scenarios/loss/cases.csv", CASE_FIELDS)
    require([row["case"] for row in cases] == list(CASES), "Loss cases missing, duplicate or reordered")
    for row in cases:
        require(row["loss_policy"] == row["case"] and all(integer(row[field], field) == value for field, value in
            (("apps4", 48), ("apps5", 48), ("duration_seconds", 64),
             ("loss_start_ns", 8_000_000_000 if row["case"] == "out" else 0),
             ("loss_stop_ns", 9_500_000_000 if row["case"] == "out" else 0))), "Loss prescribed case changed")
    offers = csv_rows(source_root / "scenarios/loss/offers.csv", OFFER_FIELDS)
    expected = [(case, source, app_id, max(0, app_id - 20) * 1_000_000_000)
                for case in CASES for app_id in range(1, 49) for source in SOURCES]
    require([(row["case"], integer(row["source"], "source"), integer(row["app_id"], "app ID"),
              integer(row["due_ns"], "due time")) for row in offers] == expected,
            "Prescribed continued arrivals missing, duplicate, reordered or changed")
    tape = {}
    for row in csv_rows(source_root / "scenarios/loss/draws.csv", ("case", "node", "ordinal", "min", "max", "draw")):
        case, node, ordinal = row["case"], integer(row["node"], "tape node"), integer(row["ordinal"], "tape ordinal", 1)
        key = (case, node, ordinal)
        require(case in CASES and node in NODES and ordinal <= 1024 and key not in tape, "Invalid or duplicate tape identity")
        pattern = {1: (1, 1), 4: (3, 7), 5: (9, 1)}[node]
        observed = {field: integer(row[field], field) for field in ("min", "max", "draw")}
        require(observed == {"min": 0, "max": 31, "draw": pattern[(ordinal - 1) % 2]}, "Prescribed raw draw or support changed")
        tape[key] = observed
    require(set(tape) == {(case, node, ordinal) for case in CASES for node in NODES for ordinal in range(1, 1025)},
            "Loss tape is incomplete")
    return plan, tape, offers


def validate_events(rows, offers, *, label):
    require(rows, f"{label}: empty loss events")
    expected_generation = [(row["case"], integer(row["source"], "source"), integer(row["app_id"], "app ID"),
                            integer(row["due_ns"], "due")) for row in offers]
    generated, admissions, delivered = [], set(), set()
    pending_offer = {}
    next_admit_count = {(case, node): 0 for case in CASES for node in SOURCES}
    fifo = {(case, node): [] for case in CASES for node in SOURCES}
    previous_case, order, when = -1, 0, -1
    snapshots = set()
    required_snapshots = {(event, tick, node) for event, ticks in (("checkpoint", CHECKPOINTS), ("final", (STOP,)))
                          for tick in ticks for node in NODES}
    for row in rows:
        require(tuple(row) == EVENT_FIELDS, f"{label}: unexpected event schema")
        case = row["case"]
        require(case in CASES, f"{label}: unknown event case")
        index = CASES.index(case)
        if index != previous_case:
            require(index == previous_case + 1 and (previous_case < 0 or snapshots == required_snapshots),
                    f"{label}: missing or reordered cases/snapshots")
            previous_case, order, when, snapshots = index, 0, -1, set()
        order += 1
        require(integer(row["order"], "event order", 1) == order, f"{label}: missing or duplicate event order")
        time = integer(row["time_ns"], "event time")
        require(when <= time <= STOP, f"{label}: event time unordered or outside case")
        when = time
        node, peer = integer(row["node"], "node"), integer(row["peer"], "peer")
        event = row["event"]
        require(event in EVENTS and node in NODES and peer in (0, *NODES), f"{label}: unknown event identity")
        for field in EVENT_FIELDS[6:]:
            integer(row[field], field, -1 if field in ("counter", "opportunity", "advertised", "neighbor_threshold") else 0)
        require(integer(row["mac_state"], "state") <= 3 and integer(row["prep"], "prep") <= 1,
                f"{label}: invalid MAC state/preparation flag")
        require(max(integer(row[field], field) for field in ("ack_bits", "dack_bits")) <= 2**64 - 1,
                f"{label}: bitmap exceeds uint64")
        source, app_id = integer(row["app_source"], "source"), integer(row["app_id"], "app ID")
        require(source in (0, *SOURCES) and app_id <= 48, f"{label}: unknown application")
        if event == "tx_start":
            require(integer(row["rate_kbps"], "rate key") == 128 and integer(row["power_dbm"], "TX power") == 33,
                    f"{label}: emitted frame changed the prescribed fixed radio")
            if source:
                require(1 <= app_id <= 48 and ((node == 4 and source == 4 and peer == 5) or node == 5 and peer == 1),
                        f"{label}: DATA identity bypasses its source/relay chain")
        key = (case, source, app_id)
        require(integer(row["admitted"], "admitted") <= (48 if node in SOURCES else 0), f"{label}: excess admissions")
        if event in ("generate", "offer", "admit", "blocked"):
            require(node == source and source in SOURCES and 1 <= app_id <= 48, f"{label}: invalid source demand identity")
            queue = fifo[case, source]
            if event == "generate":
                generated.append((case, source, app_id, time)); queue.append(app_id)
            else:
                require(queue and queue[0] == app_id, f"{label}: offered/admitted identity violates generated FIFO")
                require(time < 40_000_000_000 and time % 20_000_000 == 0, f"{label}: demand outside admission polls")
                offer_key = case, source
                if event == "offer":
                    require(offer_key not in pending_offer, f"{label}: offer lacks an admission/blocked decision")
                    pending_offer[offer_key] = (time, app_id, integer(row["nsdp4" if source == 4 else "nsdp5"], "source NSDP"))
                else:
                    require(offer_key in pending_offer and pending_offer[offer_key][:2] == (time, app_id),
                            f"{label}: admission/blocked decision lacks its real offer")
                    _, _, nsdp = pending_offer.pop(offer_key)
                    require((nsdp >= 16) is (event == "blocked"), f"{label}: admission decision contradicts real NSDP16 state")
                if event == "admit":
                    require(key not in admissions, f"{label}: duplicate admitted application")
                    admissions.add(key); queue.pop(0)
                    next_admit_count[case, source] += 1
        require(integer(row["admitted"], "observed admitted") == next_admit_count.get((case, node), 0),
                f"{label}: admission snapshot counter contradicts actual admissions")
        if event == "deliver":
            require(node == 1 and key in admissions and key not in delivered, f"{label}: duplicate/unadmitted delivery")
            delivered.add(key)
        if event in ("checkpoint", "final"):
            identity = (event, time, node)
            require(identity in required_snapshots and identity not in snapshots, f"{label}: invalid or duplicate stable snapshot")
            snapshots.add(identity)
    require(previous_case == 3 and snapshots == required_snapshots, f"{label}: incomplete final loss case")
    require(not pending_offer, f"{label}: final pending admission decision")
    require(generated == expected_generation, f"{label}: generation differs from independent continued arrival schedule")
    expected_polls = []
    for case in CASES:
        admission_times = {source: [integer(row["time_ns"], "admit time") for row in rows
                           if row["case"] == case and row["event"] == "admit" and row["node"] == str(source)] for source in SOURCES}
        due = [max(0, app_id - 20) * 1_000_000_000 for app_id in range(1, 49)]
        for tick in range(0, 40_000_000_000, 20_000_000):
            for source in SOURCES:
                if sum(time <= tick for time in due) > sum(time < tick for time in admission_times[source]):
                    expected_polls.append((case, tick, source))
    observed_polls = [(row["case"], integer(row["time_ns"], "offer time"), integer(row["node"], "offer source"))
                      for row in rows if row["event"] == "offer"]
    require(observed_polls == expected_polls, f"{label}: continued admission poll coverage/order differs from generated demand")
    return {"generated": len(generated), "admitted": len(admissions), "delivered": len(delivered),
            "remaining_demand": sum(map(len, fifo.values()))}


def validate_draws(rows, usage, tape, *, label):
    counts = {(case, node): 0 for case in CASES for node in NODES}
    previous_case, previous_time = -1, 0
    require(rows, f"{label}: empty raw draws")
    for row in rows:
        require(tuple(row) == DRAW_FIELDS, f"{label}: unexpected draw schema")
        key = (row["case"], integer(row["node"], "draw node"))
        require(key in counts, f"{label}: unknown draw identity")
        index = CASES.index(row["case"])
        require(index >= previous_case, f"{label}: reordered draw case")
        if index != previous_case:
            previous_case, previous_time = index, 0
        time = integer(row["time_ns"], "draw time")
        require(previous_time <= time <= STOP, f"{label}: unordered draw time")
        previous_time = time
        counts[key] += 1
        ordinal = integer(row["ordinal"], "draw ordinal", 1)
        tape_key = (*key, ordinal)
        require(ordinal == counts[key] and tape_key in tape, f"{label}: duplicate, missing or exhausted raw draw")
        require({field: integer(row[field], field) for field in ("min", "max", "draw")} == tape[tape_key],
                f"{label}: raw draw differs from prescribed tape")
        require(row["purpose"] in ("prepare", "advertise") and integer(row["resolved"], "resolved") <= 31,
                f"{label}: invalid draw resolution")
    seen = set()
    for row in usage:
        require(tuple(row) == USAGE_FIELDS, f"{label}: unexpected usage schema")
        key = (row["case"], integer(row["node"], "usage node"))
        require(key in counts and key not in seen, f"{label}: duplicate or unknown tape usage")
        seen.add(key)
        require(integer(row["supplied"], "supplied") == 1024 and integer(row["consumed"], "consumed") == counts[key]
                and integer(row["unused"], "unused") == 1024 - counts[key], f"{label}: unused tape suffix does not reconcile")
    require(seen == set(counts), f"{label}: incomplete tape usage")
    return counts


def frame_identity(row, *, transport=False, transmit=False):
    """Same addressed segment identity in the independent transport and event logs."""
    fields = ("app_source", "app_id", "hop_seq", "ack_bits", "dack_bits")
    if transport:
        time = "tx_time_ns" if transmit else "arrival_ns"
        nodes = ("sender", "receiver") if transmit else ("receiver", "sender")
    else:
        time, nodes = "time_ns", ("node", "peer")
    return (row["case"], integer(row[time], time), *(integer(row[field], field) for field in (*nodes, *fields)))


def validate_transport(rows, events, *, label):
    require(rows, f"{label}: empty addressed transport")
    by_case = {case: [] for case in CASES}
    for row in rows:
        require(tuple(row) == TRANSPORT_FIELDS and row["case"] in CASES, f"{label}: unexpected transport schema/case")
        for field in TRANSPORT_FIELDS:
            if field not in ("case", "kind", "decision", "reason"):
                integer(row[field], field, -1 if field == "boundary_distance_ns" else 0)
        require(row["kind"] in ("DATA", "ACK", "DACK"), f"{label}: unknown transport segment kind")
        require(row["decision"] in ("pass", "drop"), f"{label}: unknown transport decision")
        require(max(integer(row[field], field) for field in ("ack_bits", "dack_bits")) <= 2**64 - 1,
                f"{label}: transport bitmap exceeds uint64")
        require(integer(row["arrival_ns"], "arrival") > integer(row["tx_time_ns"], "transmit")
                and integer(row["arrival_ns"], "arrival") <= STOP, f"{label}: invalid transport interval")
        by_case[row["case"]].append(row)
    require([row["case"] for row in rows] == [case for case in CASES for _ in by_case[case]], f"{label}: reordered transport cases")
    dropped_groups = {}
    for case in CASES:
        selected = by_case[case]
        require(selected, f"{label}: missing transport case")
        transmissions = defaultdict(list)
        for row in selected:
            transmissions[integer(row["tx_id"], "tx ID", 1)].append(row)
        require(list(transmissions) == list(range(1, len(transmissions) + 1)), f"{label}: missing/reordered aggregate transmission")
        require([integer(row["tx_id"], "tx ID") for row in selected] ==
                [tx for tx, group in transmissions.items() for _ in group], f"{label}: interleaved aggregate transmissions")
        next_group, seen_edges, drop_count, previous_time = 1, set(), 0, -1
        for tx_rows in transmissions.values():
            time = integer(tx_rows[0]["tx_time_ns"], "TX time")
            require(time >= previous_time, f"{label}: reordered transport time")
            previous_time = time
            require([integer(row["segment_index"], "segment index") for row in tx_rows] == list(range(1, len(tx_rows) + 1)),
                    f"{label}: missing/duplicate aggregate segment")
            require(len({(row["tx_time_ns"], row["arrival_ns"], row["sender"]) for row in tx_rows}) == 1,
                    f"{label}: aggregate sender or times disagree")
            groups = {}
            for row in tx_rows:
                receiver = integer(row["receiver"], "receiver")
                groups.setdefault(receiver, []).append(row)
            for receiver, group in groups.items():
                sender = integer(group[0]["sender"], "sender")
                edge = sender, receiver
                require(edge in ((4, 5), (5, 1), (5, 4), (1, 5)), f"{label}: transport bypasses fixed chain")
                require(all(integer(row["group_id"], "group ID") == next_group and
                            integer(row["group_segments"], "group segments") == len(group) for row in group),
                        f"{label}: missing/duplicate receiver group or segment count")
                next_group += 1
                kinds = {row["kind"] for row in group}
                decision, reason = "pass", "none"
                distance = min(abs(time - 8_000_000_000), abs(time - 9_500_000_000)) if case == "out" else -1
                if case == "out":
                    require(distance > 1000, f"{label}: ambiguous loss boundary within guard")
                    if 8_000_000_000 <= time < 9_500_000_000:
                        decision, reason = "drop", "outage"
                elif case == "data" and edge in ((4, 5), (5, 1)) and "DATA" in kinds and edge not in seen_edges:
                    seen_edges.add(edge); decision, reason = "drop", "first_data"
                elif case == "ack" and edge in ((5, 4), (1, 5)) and kinds.intersection(("ACK", "DACK")) and edge not in seen_edges:
                    seen_edges.add(edge); decision, reason = "drop", "first_feedback"
                drop_count += decision == "drop"
                require(all(row["decision"] == decision and row["reason"] == reason
                            and integer(row["boundary_distance_ns"], "boundary distance", -1) == distance for row in group),
                        f"{label}: receiver-group loss decision contradicts independent policy")
        require(drop_count == 0 if case == "ok" else drop_count == 2 if case in ("data", "ack") else drop_count > 0,
                f"{label}: intended loss policy was not exercised")
        dropped_groups[case] = drop_count
    # Every emitted segment has one actual TX and exactly one arrival outcome;
    # dropped segments have no before/after ingress observations.
    emitted = Counter(frame_identity(row, transport=True, transmit=True) for row in rows)
    actual_tx = Counter(frame_identity(row) for row in events if row["event"] == "tx_start")
    require(emitted == actual_tx, f"{label}: transport segments disagree with actual emitted events")
    for decision, event_names in (("drop", ("loss",)), ("pass", ("ingress_before", "ingress_after"))):
        expected = Counter(frame_identity(row, transport=True) for row in rows if row["decision"] == decision)
        for event in event_names:
            observed = Counter(frame_identity(row) for row in events if row["event"] == event)
            require(expected == observed, f"{label}: {decision} transport disagrees with {event} ingress evidence")
    return dropped_groups


def validate_terminals(rows, events, *, label):
    # mac_queue_full or route/security outcomes are not declared injected
    # faults in this bounded fixture: preserve the archive and reject them as
    # a structural failure, never reinterpret them as numerical residuals.
    require(rows, f"{label}: empty terminal outcomes")
    admitted = {(row["case"], integer(row["app_source"], "source"), integer(row["app_id"], "ID"))
                for row in events if row["event"] == "admit"}
    delivered = {(row["case"], integer(row["app_source"], "source"), integer(row["app_id"], "ID"))
                 for row in events if row["event"] == "deliver"}
    received = {(row["case"], integer(row["app_source"], "source"), integer(row["app_id"], "ID"))
                for row in events if row["event"] == "ingress_after" and row["node"] == "5" and row["app_source"] == "4"}
    seen, failed = set(), set()
    previous_case, order, time = -1, 0, -1
    for row in rows:
        require(tuple(row) == TERMINAL_FIELDS and row["case"] in CASES, f"{label}: unexpected terminal schema/case")
        case = row["case"]; index = CASES.index(case)
        if index != previous_case:
            require(index == previous_case + 1, f"{label}: terminal cases missing or reordered")
            previous_case, order, time = index, 0, -1
        order += 1
        require(integer(row["order"], "terminal order", 1) == order, f"{label}: duplicate/missing terminal order")
        current = integer(row["time_ns"], "terminal time")
        require(time <= current <= STOP, f"{label}: terminal time unordered or outside case")
        time = current
        node, source, app_id = (integer(row[field], field) for field in ("node", "app_source", "app_id"))
        key = case, source, app_id
        owner_key = case, node, source, app_id
        require(key in admitted and node in SOURCES and (node == source or node == 5 and key in received),
                f"{label}: terminal lacks real admission/relay ownership")
        require(owner_key not in seen, f"{label}: duplicate terminal owner identity")
        seen.add(owner_key)
        success = logical(row["success"], "terminal success")
        require(row["reason"] in ("ack", "dack_custody", "retry_exhausted") and
                success is (row["reason"] != "retry_exhausted"), f"{label}: terminal reason/success contradicts normalized retirement")
        if not success:
            failed.add(key)
    require(previous_case == 3, f"{label}: missing final terminal case")
    unexplained = admitted - delivered - failed
    require(not unexplained, f"{label}: undelivered admission has no real terminal failure")
    expected_owners = {(case, source, source, app_id) for case, source, app_id in admitted} | \
                      {(case, 5, source, app_id) for case, source, app_id in received}
    require(seen == expected_owners, f"{label}: admitted/relayed custody does not reconcile with terminal owners")
    return {"admitted": len(admitted), "delivered": len(delivered), "terminal_owners": len(seen),
            "failed_identities": len(failed), "delivered_with_failed_retirement": len(delivered & failed),
            "genuine_undelivered_identities": len(admitted - delivered), "unexplained": len(unexplained)}


def native_terminals(raw, case):
    """Read HOP retirement semantics from actual native trace, not summary counts."""
    normalized = []
    mapping = {("ack", "1"): ("1", "ack"), ("dack", "0"): ("1", "dack_custody"),
               ("no_ack", "0"): ("0", "retry_exhausted")}
    for row in raw:
        if row["event"] != "hop_completion":
            continue
        pair = row["reason"], row["success"]
        require(pair in mapping, "Native raw terminal reason/success pair is unsupported")
        success, reason = mapping[pair]
        ns = number(row["time_s"], "native terminal time", minimum=0) * 1_000_000_000
        # The generic native trace serializes GetSeconds() binary64; the
        # canonical integer trace preserves nearest-nanosecond time. Reject
        # material fractional nanoseconds, retain raw seconds in the archive.
        require(abs(ns - ns.to_integral_value()) < Decimal(".0001"), "Native terminal timestamp lost nanosecond precision")
        normalized.append({"case": case, "order": str(len(normalized) + 1), "time_ns": str(int(ns.to_integral_value())),
                           "node": row["node"], "app_source": row["src"], "app_id": row["sequence"],
                           "success": success, "reason": reason})
    return normalized


def verify_native(source_root, candidate, plan, tape, offers):
    require(candidate.get("LossReferenceManifest") == REFERENCE + "/manifest.json", "Unexpected native loss reference path")
    directory, manifest = verify_manifest(source_root, candidate["LossReferenceManifest"],
        candidate.get("LossReferenceManifestSHA256"), "csr-tranche13-reference-files-v1")
    summary = json_object(directory / "summary.json")
    require(summary.get("schema") == "csr-tranche13-native-reference-v1" and summary.get("status") == "completed"
            and summary.get("source_pin") == PIN and summary.get("engine_pin") == ENGINE_PIN and summary.get("scope") == plan["scope"]
            and summary.get("native_source_unchanged") is True and summary.get("native_libraries_unchanged") is True
            and summary.get("instrumented_native_fixture") is True and summary.get("real_nwk_application_and_relay_path") is True
            and summary.get("matlab_execution") is False and summary.get("cross_simulator_parity_established") is False,
            "Native loss runtime, source identity or scope mismatch")
    inputs = {name: sha256(source_root / "scenarios/loss" / name) for name in ("plan.json", "cases.csv", "offers.csv", "draws.csv")}
    fixtures = ("scripts/run_tranche13_ns3_reference.py", "scripts/run_tranche4_ns3_reference.py", "scripts/build_tranche12_overlay.py",
                "scripts/ns3/tranche13_loss.cc", "scripts/ns3/tranche12-relay-hooks.h",
                "scripts/ns3/tranche9_ack_contract.cc", "scripts/ns3/tranche10_receiver_contract.cc")
    require(summary.get("input_hashes") == inputs and
            summary.get("fixture_hashes") == {Path(name).name: sha256(source_root / name) for name in fixtures},
            "Native loss fixture/input binding mismatch")
    build, libraries, digest = verify_clean_build(source_root)
    short_libraries = {name.removeprefix("libns3-dev-").removesuffix("-debug.so"): value for name, value in libraries.items()}
    models = {Path(name).name: value for name, value in build["input_sha256"].items()
              if name.startswith(build["source_path"] + "/model/csr-")}
    require(summary.get("shared_libraries") == short_libraries and summary.get("native_source_hashes") == models
            and summary.get("clean_build_record") == "evidence/tranche-11-native-build.json"
            and summary.get("clean_build_record_sha256") == digest and summary.get("engine_build_reused_after_hash_verification") is True,
            "Native loss source/library identity differs from audited clean build")
    commands = records(summary.get("commands"), "native commands")
    require(len(commands) >= 10 and all(integer(row.get("exit_code"), "command exit") == 0 for row in commands),
            "Native loss command missing or failed")
    controls = summary.get("disabled_seam_controls")
    require(isinstance(controls, dict) and set(controls) == {"ack", "receiver"}, "Missing disabled-seam controls")
    for family, count, digest in (("ack", 101, "2991bbc93e5ba2c64d06a93cee278160cd9baf2fdc11b052ee5b0cb561fe4b73"),
                                  ("receiver", 154, "a3562a3f23e5603359610b150e20551f5a671298d7db529e037d842ce7206c1a")):
        paths = [directory / "controls" / f"{family}-{mode}.csv" for mode in ("clean", "off")]
        rows = csv_rows(paths[0])
        require(len(rows) == count and all(logical(row["pass"], "native control pass") for row in rows)
                and all(sha256(path) == digest for path in paths)
                and controls[family] == {"checkpoints": count, "passed": True, "clean_and_disabled_byte_equal": True, "sha256": digest},
                "Native disabled-seam controls changed the retained contracts")
    require(integer(summary.get("self_tests"), "native self-tests") == 25
            and (directory / "controls/self-test.log").read_text().strip() == "LOSS_SELF_TEST checks=25 failed=0",
            "Native loss self-test execution evidence missing")
    loaded = {name: csv_rows(directory / (name + ".csv"), fields) for name, fields in FAMILIES}
    validate_events(loaded["events"], offers, label="native")
    validate_draws(loaded["draws"], loaded["usage"], tape, label="native")
    groups = validate_transport(loaded["transport"], loaded["events"], label="native")
    outcomes = validate_terminals(loaded["terminal"], loaded["events"], label="native")
    raw_events, raw_transport, raw_terminal, raw_draws = [], [], [], []
    for case in CASES:
        raw = directory / "raw" / case
        raw_events.extend(csv_rows(raw / "events.csv", EVENT_FIELDS))
        raw_transport.extend(csv_rows(raw / "transport.csv", TRANSPORT_FIELDS))
        native = csv_rows(raw / "native.csv")
        raw_terminal.extend(native_terminals(native, case))
        purposes = defaultdict(list)
        for row in native:
            if row["event"] == "reservation_advertise":
                purpose = "advertise"
            elif row["event"] == "reservation_prepare" and row["reason"] == "new":
                purpose = "prepare"
            else:
                continue
            when = number(row["time_s"], "native reservation time") * 1_000_000_000
            require(abs(when - when.to_integral_value()) < Decimal(".0001"), "Native reservation lost nanosecond precision")
            purposes[row["node"], str(int(when.to_integral_value()))].append((purpose, row["reservation_slot"]))
        for row in csv_rows(raw / "raw.csv"):
            key = row["node"], row["time_ns"]
            require(purposes[key], "Native raw draw has no observed MAC reservation purpose")
            purpose, resolved = purposes[key].pop(0)
            require(resolved == row["resolved"], "Native raw draw resolution contradicts actual MAC trace")
            raw_draws.append({field: row[field] for field in DRAW_FIELDS[:-1]} | {"purpose": purpose})
        require(not any(purposes.values()), "Native MAC reservation lacks a raw draw")
    require(raw_events == loaded["events"] and raw_transport == loaded["transport"] and raw_terminal == loaded["terminal"]
            and raw_draws == loaded["draws"], "Native canonical rows differ from independently read raw execution")
    for key, family in (("event_count", "events"), ("draw_count", "draws"), ("terminal_count", "terminal")):
        require(integer(summary.get(key), key) == len(loaded[family]), "Native summary counter disagrees")
    checks = compute_checks(loaded["events"], loaded["draws"], loaded["transport"], loaded["terminal"])
    require(all(row["pass"] for row in checks), "Native loss/recovery structural checks failed")
    return loaded, {"source_pin": PIN, "engine_pin": ENGINE_PIN, "artifact_count": len(manifest["files"]),
                    "event_count": len(loaded["events"]), "draw_count": len(loaded["draws"]),
                    "checkpoint_count": len(checks), "disabled_seam_checkpoints": 255, "self_tests": 25,
                    "dropped_groups": groups, "outcomes": outcomes,
                    "scope": "Instrumented native fixture; controlled whole-addressed-group loss; no RF/campus parity claim"}


def compute_checks(events, draws, transport, terminals, case_results=None):
    """Recompute structural checks from complete event/transport/terminal records.

The separate NWK Dropped callback counter exists only in CaseResults; its
cross-check is identified as a reported counter, not an independent raw event.
"""
    checks = []
    reported = {row["Case"]: row for row in case_results} if case_results is not None else {}
    def add(case, checkpoint, node, actual, expected=0):
        checks.append({"case": case, "checkpoint": checkpoint, "node": node,
                       "actual": actual, "expected": expected, "pass": actual == expected})
    for case in CASES:
        selected = [row for row in events if row["case"] == case]
        ending = [row for row in terminals if row["case"] == case]
        carried = [row for row in transport if row["case"] == case]
        for source in SOURCES:
            admissions = [row for row in selected if row["event"] == "admit" and integer(row["app_source"], "source") == source]
            delivered = [row for row in selected if row["event"] == "deliver" and integer(row["app_source"], "source") == source]
            generated = [row for row in selected if row["event"] == "generate" and integer(row["app_source"], "source") == source]
            source_ending = [row for row in ending if integer(row["app_source"], "source") == source]
            admitted_ids = [integer(row["app_id"], "admit ID") for row in admissions]
            delivered_ids = [integer(row["app_id"], "delivery ID") for row in delivered]
            failed_ids = {integer(row["app_id"], "terminal ID") for row in source_ending if not logical(row["success"], "success")}
            add(case, "generated", source, len(generated), 48)
            add(case, "admitted", source, len(admissions), 48)
            add(case, "unexplained_loss", source, len(set(admitted_ids) - set(delivered_ids) - failed_ids))
            add(case, "unknown_terminal", source, sum(integer(row["app_id"], "terminal ID") not in admitted_ids for row in source_ending))
            add(case, "duplicate_delivery", source, len(delivered_ids) - len(set(delivered_ids)))
            add(case, "admitted_after20_seen", source, int(any(integer(row["time_ns"], "admit time") > 20_000_000_000 for row in admissions)), 1)
            add(case, "final_demand", source, len(generated) - len(admissions))
            add(case, "admitted_before_due", source, sum(integer(row["time_ns"], "admit time") <
                    max(0, integer(row["app_id"], "ID") - 20) * 1_000_000_000 for row in admissions))
            add(case, "duplicate_admission", source, len(admitted_ids) - len(set(admitted_ids)))
            add(case, "nsdp_blocked_seen", source, int(any(row["event"] == "blocked" and integer(row["node"], "node") == source for row in selected)), 1)
        for node in NODES:
            own = [row for row in selected if integer(row["node"], "node") == node]
            final = [row for row in own if row["event"] == "final"]
            require(len(final) == 1, "Missing final node snapshot")
            for field in ("hop_pending", "dack_holds", "resend_queue", "nwk_waiting", "nwk_custody", "nsdp4", "nsdp5"):
                add(case, field, node, integer(final[0][field], field))
            add(case, "mac_ack_queue", node, integer(final[0]["ack_queue"], "ACK queue"))
            add(case, "mac_data_queue", node, integer(final[0]["data_queue"], "DATA queue"))
            node_ending = [row for row in ending if integer(row["node"], "node") == node]
            add(case, "terminal_release_difference", node, sum(row["event"] == "release" for row in own) - len(node_ending))
            owned = {(integer(row["app_source"], "source"), integer(row["app_id"], "ID")) for row in own
                     if row["event"] == "admit" or node == 5 and row["event"] == "ingress_before" and row["app_source"] == "4"}
            ended = {(integer(row["app_source"], "source"), integer(row["app_id"], "ID")) for row in node_ending}
            add(case, "ownership_identity_difference", node, len(owned ^ ended))
        stable = [row for row in selected if row["event"] in ("checkpoint", "final")]
        add(case, "custody_conservation_failures", 0, sum(integer(row["nwk_custody"], "custody") !=
                integer(row["nsdp4"], "NSDP4") + integer(row["nsdp5"], "NSDP5") for row in selected))
        add(case, "stable_capacity_failures", 0, sum(integer(row["hop_pending"], "pending") !=
                integer(row["resend_queue"], "resends") + integer(row["dack_holds"], "holds") for row in stable))
        releases = [row for row in selected if row["event"] == "release"]
        require(len(releases) == len(ending) and all((left["time_ns"], left["node"], left["app_source"]) ==
                (right["time_ns"], right["node"], right["app_source"]) for left, right in zip(releases, ending)),
                "Release callbacks do not reconcile with ordered terminal observations")
        release_failures = sum(end["reason"] == "ack" and (integer(row["hop_pending"], "pending") !=
                integer(row["neighbor_outstanding"], "outstanding") or integer(row["resend_queue"], "resends") <=
                integer(row["hop_pending"], "pending") - integer(row["dack_holds"], "holds"))
                for row, end in zip(releases, ending))
        add(case, "release_order_failures", 0, release_failures)
        add(case, "draw_resolution_failures", 0, sum(row["purpose"] == "unresolved" or integer(row["resolved"], "resolved", -1) < 0
                for row in draws if row["case"] == case))
        failed_count = sum(not logical(row["success"], "success") for row in ending)
        drops = integer(reported[case]["Drops"], "reported NWK drops") if case in reported else failed_count
        add(case, "drops_terminal_difference", 0, drops - failed_count)
        deliveries = [row for row in selected if row["event"] == "deliver"]
        add(case, "unknown_deliveries", 0, sum(integer(row["app_source"], "source") not in SOURCES or
                not 1 <= integer(row["app_id"], "ID") <= 48 or row["node"] != "1" or row["peer"] != "5" for row in deliveries))
        terminal_ids = {(row["node"], row["app_source"], row["app_id"]) for row in ending}
        add(case, "terminal_duplicates", 0, len(ending) - len(terminal_ids))
        add(case, "invalid_terminal_owner", 0, sum(row["node"] not in ("4", "5") or row["node"] == "4" and row["app_source"] != "4" for row in ending))
        # Full policy and TX/pass/drop event coverage are independently checked
        # in validate_transport; summary cannot turn an invalid policy into 0.
        add(case, "loss_policy_failures", 0, 0)
        groups = len({row["group_id"] for row in carried if row["decision"] == "drop"})
        add(case, "loss_groups_expected", 0, int(groups > 0) if case == "out" else groups,
            0 if case == "ok" else 1 if case == "out" else 2)
        add(case, "post_loss_delivery_seen", 0, int(any(integer(row["time_ns"], "delivery time") > 9_500_000_000 for row in deliveries)), 1)
        add(case, "control_delivery_failures", 0, sum(abs(48 - sum(row["app_source"] == str(source) for row in deliveries))
                for source in SOURCES) + failed_count if case == "ok" else 0)
        add(case, "case_completed", 0, int(sum(row["event"] == "final" for row in selected) == 3), 1)
    return checks


def verify_checks(directory, events, draws, transport, terminals, case_results):
    expected = compute_checks(events, draws, transport, terminals, case_results)
    actual = csv_rows(directory / "check.csv", CHECK_FIELDS)
    require(len(actual) == len(expected), "Recovery checkpoint inventory incomplete")
    for row, target in zip(actual, expected):
        require((row["case"], row["checkpoint"], integer(row["node"], "checkpoint node")) ==
                (target["case"], target["checkpoint"], target["node"]), "Checkpoint identity missing, duplicate or reordered")
        require(integer(row["actual"], "checkpoint actual", -10**9) == target["actual"]
                and integer(row["expected"], "checkpoint expected", -10**9) == target["expected"]
                and logical(row["pass"], "checkpoint pass") is target["pass"], "Checkpoint contradicts independently recomputed observations")
    require(all(row["pass"] for row in expected), "Loss/recovery structural check failed")
    return expected


def verify_case_results(cases, actual, checks, loss_groups):
    result = []
    for claim in cases:
        case = claim["Case"]
        selected = [row for row in actual["events"] if row["case"] == case]
        ending = [row for row in actual["terminal"] if row["case"] == case]
        carried = [row for row in actual["transport"] if row["case"] == case]
        expected = {field: [0] * 5 for field in ("Requested", "Generated", "Admitted", "Delivered", "Released", "Unexplained",
                    "FinalDemand", "FinalHopPending", "FinalDackHolds", "FinalResends", "FinalMacAckQueue", "FinalMacDataQueue")}
        for source in SOURCES:
            expected["Requested"][source - 1] = 48
            for field, event in (("Generated", "generate"), ("Admitted", "admit"), ("Delivered", "deliver")):
                expected[field][source - 1] = sum(row["event"] == event and row["app_source"] == str(source) for row in selected)
            expected["FinalDemand"][source - 1] = expected["Generated"][source - 1] - expected["Admitted"][source - 1]
            expected["Unexplained"][source - 1] = next(row["actual"] for row in checks if
                row["case"] == case and row["checkpoint"] == "unexplained_loss" and row["node"] == source)
        for node in NODES:
            own = [row for row in selected if row["node"] == str(node)]
            expected["Released"][node - 1] = sum(row["event"] == "release" for row in own)
            final = next(row for row in own if row["event"] == "final")
            for field, raw in (("FinalHopPending", "hop_pending"), ("FinalDackHolds", "dack_holds"), ("FinalResends", "resend_queue"),
                                ("FinalMacAckQueue", "ack_queue"), ("FinalMacDataQueue", "data_queue")):
                expected[field][node - 1] = integer(final[raw], raw)
        require(all(isinstance(claim.get(field), list) and [integer(value, field) for value in claim[field]] == counts
                    for field, counts in expected.items()), "Recovery per-case counters contradict observations")
        relay_custody = len({(row["app_source"], row["app_id"]) for row in selected if row["event"] == "ingress_after"
                            and row["node"] == "5" and row["app_source"] == "4"})
        failed = sum(not logical(row["success"], "terminal success") for row in ending)
        maximum_hold = max(integer(row["dack_holds"], "DACK holds") for row in selected)
        for field, count in (("RelayCustodyAccepted", relay_custody), ("Drops", failed), ("FailedTerminals", failed),
                             ("LossGroups", loss_groups[case]), ("MaximumDackHolds", maximum_hold)):
            require(integer(claim.get(field), field) == count, f"Recovery {field} claim contradicts observations")
        controls = claim.get("PendingControls")
        require(isinstance(controls, list) and len(controls) == 5 and controls[1:3] == [0, 0]
                and all(integer(value, "pending controls") >= 0 for value in controls), "Malformed excluded-control inventory")
        failed_ids = {(row["app_source"], row["app_id"]) for row in ending if not logical(row["success"], "success")}
        delivered_ids = {(row["app_source"], row["app_id"]) for row in selected if row["event"] == "deliver"}
        data_counts = Counter((row["sender"], row["app_source"], row["app_id"]) for row in carried if row["kind"] == "DATA")
        result.append({"case": case, "generated": sum(expected["Generated"]), "admitted": sum(expected["Admitted"]),
                       "delivered": sum(expected["Delivered"]), "genuine_undelivered": sum(expected["Admitted"]) - len(delivered_ids),
                       "terminal_failures": failed, "delivered_with_failed_retirement": len(failed_ids & delivered_ids),
                       "loss_groups": loss_groups[case], "lost_segments": sum(row["decision"] == "drop" for row in carried),
                       "data_retransmissions": sum(value - 1 for value in data_counts.values()), "maximum_dack_holds": maximum_hold,
                       "reported_pending_controls": controls, "final_queues_clear": all(not any(expected[key]) for key in
                           ("FinalHopPending", "FinalDackHolds", "FinalResends", "FinalMacAckQueue", "FinalMacDataQueue"))})
    return result


def verify_recovery(root, metadata, source_root, candidate):
    plan, tape, offers = verify_plan(source_root, candidate)
    require(metadata.get("RecoveryDirectory") == "loss", "Unexpected recovery output directory")
    directory = root / "loss"
    native, provenance = verify_native(source_root, candidate, plan, tape, offers)
    actual = {name: csv_rows(directory / (name + ".csv"), fields) for name, fields in FAMILIES}
    demand = validate_events(actual["events"], offers, label="MATLAB")
    validate_draws(actual["draws"], actual["usage"], tape, label="MATLAB")
    loss_groups = validate_transport(actual["transport"], actual["events"], label="MATLAB")
    outcomes = validate_terminals(actual["terminal"], actual["events"], label="MATLAB")
    comparisons = [compare_rows(actual[name], native[name], fields, family=name) for name, fields in FAMILIES]
    unmatched = sum(row["unmatched_rows"] for row in comparisons)
    matches = unmatched == 0
    summary = json_object(directory / "summary.json")
    require(summary.get("Schema") == "csr-tranche13-loss-contract-v1" and summary.get("DiagnosticCompleted") is True
            and summary.get("Passed") is True and summary.get("MatchesNative") is matches
            and summary.get("Runtime") == metadata["Runtime"]["Version"], "Recovery completion/runtime/match summary disagrees")
    require(summary.get("ComparedEntireTrajectories") is True and summary.get("TimeToleranceNanoseconds") == 1
            and summary.get("Scope") == plan["scope"], "Recovery comparison scope or tolerance changed")
    verify_bindings(summary.get("InputBindings"), source_root,
        ["scenarios/loss/" + name for name in ("plan.json", "cases.csv", "offers.csv", "draws.csv")], "Loss inputs")
    verify_bindings(summary.get("ReferenceBindings"), source_root,
        [REFERENCE + "/" + name + ".csv" for name, _ in FAMILIES], "Loss references")
    cases = records(summary.get("CaseResults"), "loss case results")
    require([row.get("Case") for row in cases] == list(CASES)
            and all(row.get("Completed") is True and row.get("ErrorIdentifier") == "" and row.get("ErrorMessage") == "" for row in cases),
            "Recovery case completion/identities disagree")
    checks = verify_checks(directory, actual["events"], actual["draws"], actual["transport"], actual["terminal"], cases)
    for field, value in (("CaseCount", 4), ("EventCount", len(actual["events"])), ("DrawCount", len(actual["draws"])),
                          ("TransportCount", len(actual["transport"])), ("TerminalCount", len(actual["terminal"])),
                          ("CheckpointCount", len(checks)), ("FailedCount", 0), ("UnmatchedCount", unmatched)):
        require(integer(summary.get(field), field) == value, f"Recovery summary {field} contradicts observations")
    for field, value in (("RecoveryCaseCount", 4), ("RecoveryEventCount", len(actual["events"])),
                          ("RecoveryDrawCount", len(actual["draws"])), ("RecoveryCheckpointCount", len(checks)), ("RecoveryUnmatchedCount", unmatched)):
        require(integer(metadata.get(field), field) == value, f"Recovery metadata {field} disagrees")
    require(metadata.get("RecoveryCompleted") is True and metadata.get("RecoveryPassed") is True
            and metadata.get("RecoveryMatchesNative") is matches, "Recovery metadata completion/match claim disagrees")
    for title, comparison in zip(("Event", "Draw", "Usage", "Transport", "Terminal"), comparisons):
        verify_comparison_claim(summary.get(title + "Comparison"), comparison, title + " comparison")
        if title in ("Event", "Draw", "Usage"):
            plural = title + "s" if title != "Usage" else title
            require(integer(summary.get(plural + "Compared"), plural + " compared") ==
                    max(comparison["matlab_rows"], comparison["native_rows"]), "Recovery compared row count disagrees")
    reports = verify_case_results(cases, actual, checks, loss_groups)
    return {"structural_complete": True, "matches_native": matches, "unmatched_rows": unmatched,
            "case_count": 4, "event_count": len(actual["events"]), "draw_count": len(actual["draws"]),
            "checkpoint_count": len(checks), "comparisons": comparisons, "scope": plan["scope"],
            "native_provenance": provenance, "demand": demand, "outcomes": outcomes, "cases": reports,
            "reported_counter_scope": "Pending bootstrap controls and NWK Dropped callback counts are owner-reported; "
                "Dropped counts are corroborated against actual terminal failures. No control queue parity claim."}


def verify_baseline(metadata, source_root, candidate):
    result = {}
    for label, name, digest, source_count, matlab_count, prefix in (
        ("tranche12", BASELINE, BASELINE_SHA, 259, 135, "Baseline"),
        ("accepted_core", CORE_BASELINE, CORE_BASELINE_SHA, 225, 124, "CoreBaseline"),
    ):
        require(candidate.get(prefix + "SourceSnapshot") == name, f"Unexpected {label} baseline path")
        key = "BaseSourceSnapshotSHA256" if prefix == "Baseline" else prefix + "SourceSnapshotSHA256"
        require(sha256(source_root / name) == candidate.get(key) == digest, f"{label} baseline snapshot binding mismatch")
        expected = record_map(json_value(source_root / name), label + " source")
        require(len(expected) == source_count and sum(name.endswith(".m") for name in expected) == matlab_count,
                f"{label} source membership/count changed")
        for relative, row in expected.items():
            require(sha256(safe_path(source_root, relative)) == row["sha256"], f"{label} baseline source changed: {relative}")
        for field, count in (("SourceFiles", source_count), ("MatlabFiles", matlab_count)):
            require(integer(metadata.get(prefix + field + "Verified"), field) == count and
                    integer(candidate.get(prefix + field + "Unchanged"), field) == count,
                    f"{label} baseline verification counts disagree")
        result[label] = {"source_files": source_count, "matlab_files": matlab_count,
                         "unchanged": True, "snapshot_sha256": digest}
    for field, name, digest in (("BaselineOwnerEvidence", "evidence/t12/owner.zip", OWNER_SHA),
                                 ("BaselineCandidate", "evidence/t12/candidate.json", PARENT_CANDIDATE_SHA)):
        require(candidate.get(field) == name and candidate.get(field + "SHA256") == digest
                and sha256(source_root / name) == digest, "Reviewed T12 owner/candidate provenance mismatch")
    # The parent owner archive must itself bind exactly this source snapshot and
    # candidate; a renamed unrelated archive is not an accepted source anchor.
    with evidence_directory(source_root / "evidence/t12/owner.zip") as owner:
        parent = json_object(owner / "metadata.json")
        require(parent.get("CandidateSHA256") == PARENT_CANDIDATE_SHA and
                parent.get("SourceSnapshotSHA256") == BASELINE_SHA and sha256(owner / "source.json") == BASELINE_SHA,
                "T12 source snapshot is not bound by the reviewed owner run")
    return result


def verify_run_identity(root, metadata, source_root, candidate):
    require(candidate.get("Schema") == "csr-tranche-13-candidate-v1" and candidate.get("Tranche") == 13
            and candidate.get("SourceCommit") == PIN, "Candidate schema or native source pin mismatch")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 13 and metadata.get("Status") == "completed",
            "Return is not a completed T13 diagnostic")
    require(metadata.get("MATLABExecuted") is True and metadata.get("NativeExecuted") is False
            and metadata.get("SourceCommit") == PIN, "Owner MATLAB execution/source identity missing")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB" and runtime.get("DefaultBackend") == "portable"
            and isinstance(runtime.get("Version"), str) and runtime["Version"], "Missing or unsupported MATLAB runtime provenance")
    require(metadata.get("CandidateFile") == CANDIDATE and metadata.get("CandidateSHA256") == sha256(source_root / CANDIDATE),
            "Candidate identity mismatch")
    started, completed = (datetime.fromisoformat(metadata.get(field, "").replace("Z", "+00:00"))
                          for field in ("StartedUTC", "CompletedUTC"))
    require(started.tzinfo is not None and completed.tzinfo is not None and completed >= started,
            "Invalid owner execution timestamps")
    require(metadata.get("InventoryExcludedPaths") == ["metadata.json"] and metadata.get("EvidenceArchive") == "t13.zip",
            "Evidence inventory exclusion or archive identity changed")
    local = record_map(metadata.get("LocalArtifacts", []), "local artifacts", sizes=True, empty=True)
    require(all(name.endswith(".mat") and name not in all_files(root) for name in local), "Invalid local-only artifacts")
    require(metadata.get("FocusedGateExecuted") is True and metadata.get("DiagnosticOnly") is True
            and all(metadata.get(field) is False for field in ("FullAcceptanceGateExecuted", "AcceptanceEstablished", "NumericalParityEstablished")),
            "Focused diagnostic scope or acceptance claim contradicts authorized gate")
    return runtime


def review(evidence, source_root, output):
    evidence, source_root, output = Path(evidence).resolve(), Path(source_root).resolve(), Path(output).resolve()
    candidate = json_object(source_root / CANDIDATE)
    with evidence_directory(evidence) as root:
        metadata = json_object(root / "metadata.json")
        runtime = verify_run_identity(root, metadata, source_root, candidate)
        artifacts = inventory(root, metadata.get("Artifacts"), excluded=("metadata.json",))
        require({"run.log", "source.json", "references.json", "tests.csv", "loss/check.csv", "loss/summary.json"} |
                {"loss/" + name + ".csv" for name, _ in FAMILIES} <= set(artifacts), "Required loss/recovery evidence missing")
        source = verify_sources(root, metadata, source_root)
        baseline = verify_baseline(metadata, source_root, candidate)
        references = verify_references(root, metadata, source_root, candidate)
        tests = verify_tests(root, metadata, source_root, candidate)
        recovery = verify_recovery(root, metadata, source_root, candidate)
        result = {"schema": REVIEW_SCHEMA, "status": "focused_diagnostic_review_completed",
                  "evidence_integrity_verified": True, "focused_structural_gate_completed": True,
                  "recovery_matches_native": recovery["matches_native"],
                  "acceptance_established": False, "numerical_parity_established": False,
                  "matlab_executed_by_reviewer": False, "runtime": runtime,
                  "evidence": {"path": evidence.name, "sha256": sha256(evidence), "bytes": evidence.stat().st_size},
                  "source": source, "baseline": baseline, "references": references,
                  "tests": tests, "recovery": recovery}
    output.mkdir(parents=True, exist_ok=True)
    (output / "review.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = review(args.evidence, args.source_root, args.output)
    except (ValueError, OSError, csv.Error, zipfile.BadZipFile, KeyError, TypeError) as error:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {"schema": REVIEW_SCHEMA, "status": "review_failed", "evidence_integrity_verified": False,
                   "focused_structural_gate_completed": False, "acceptance_established": False,
                   "numerical_parity_established": False, "matlab_executed_by_reviewer": False, "error": str(error)}
        (args.output / "review.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(f"T13 evidence rejected: {error}")
        return 1
    print(f"T13 focused review complete; native match={result['recovery_matches_native']}. "
          "MATLAB execution is owner-returned; exact differences remain recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
