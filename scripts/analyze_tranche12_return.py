#!/usr/bin/env python3
"""Verify a focused Tranche 12 owner return; never execute or impersonate MATLAB.

The relay experiment and the clock-boundary diagnostic have separate scopes.
Closed, completed evidence can contain numerical residuals: those residuals are
retained in the review and never promoted to full-network parity or acceptance.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import struct
import zipfile

# The audited T11 helpers are part of the immutable 241-file baseline. Reuse the
# bounded ZIP/JSON/CSV readers and identity checks without editing their source.
from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, evidence_directory,
    integer, inventory, json_object, json_value, logical, number, record_map,
    records, require, safe_name, safe_path, selected_test_names, sha256,
    verify_bindings, verify_references, verify_sources, verify_tests,
)

SCHEMA = "csr-matlab-tranche-12-validation-v1"
REVIEW_SCHEMA = "csr-matlab-tranche-12-return-review-v1"
PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
ENGINE_PIN = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
CANDIDATE = "evidence/tranche-12-candidate.json"
BASELINE = "evidence/tranche-11-r2025a-review/source.json"
BASELINE_SHA = "9093dea75f92205dbd782b8ce5691e7bf75cdf0181d055cd234755515624cf26"
BASE_ARCHIVE_SHA = "76b2d2ba6bd653efb0657730d3b286f03b7d0fc782ff242f92243c69e7f0f57e"
CORE_BASELINE = "evidence/tranche-10-r2025a-accepted/owner/source_snapshot.json"
CORE_BASELINE_SHA = "9be444b0fb1ffbfe818cab86502a287b19e3da83467d210ef426ec3b19e183da"
RELAY_REFERENCE = "evidence/tranche-12-relay-reference"
RELAY_CASES = ("relay", "local", "mix", "sw")
RELAY_NODES = (1, 4, 5)
RELAY_COUNTS = {"relay": {4: 20, 5: 0}, "local": {4: 0, 5: 20}, "mix": {4: 20, 5: 20}, "sw": {4: 20, 5: 20}}
RELAY_FIELDS = ("case", "order", "time_ns", "event", "node", "peer", "app_source", "app_id", "hop_seq",
                "ack_bits", "dack_bits", "mac_state", "ack_queue", "data_queue", "prep", "counter", "opportunity",
                "advertised", "hop_pending", "neighbor_outstanding", "neighbor_threshold", "resend_queue", "admitted",
                "rate_kbps", "power_dbm", "nwk_waiting", "nwk_custody", "nsdp4", "nsdp5", "dack_holds")
DRAW_FIELDS = ("case", "node", "ordinal", "time_ns", "min", "max", "draw", "resolved", "purpose")
USAGE_FIELDS = ("case", "node", "supplied", "consumed", "unused")
RELAY_EVENTS = {"offer", "admit", "blocked", "tx_start", "ingress_before", "ingress_after", "release", "deliver", "checkpoint", "final"}
CLOCK_REFERENCE = "evidence/tranche-12-clock-reference"
CLOCK_CASES = ("tie_early", "tie_late", "before", "after", "continuous", "quantized")
CLOCK_PHASES = ("ingress_before", "ingress_after", "settled")
CLOCK_FIELDS = ("case", "order", "phase", "time_ns", "local_counter", "neighbor_counter", "data_queue", "transmissions")
CLOCK_CHECK_FIELDS = ("case", "phase", "field", "actual", "expected", "pass")
BOUNDARY_FIELDS = ("case", "arrival_seconds_hex", "tick_seconds_hex", "arrival_minus_tick_seconds", "transport_quantized", "late_insertion")


def clock_expected_events(*, matlab):
    """Derived FIFO expectations; the continuous binary64 case is explicit."""
    rows = []
    for case in CLOCK_CASES:
        follows_tick = case in ("tie_late", "after") or (matlab and case == "continuous")
        arrival_ns = 2_011_501_000 + ({"before": -1, "after": 1}.get(case, 0))
        for order, phase in enumerate(CLOCK_PHASES, 1):
            local = 15 if follows_tick or phase == "settled" else 16
            neighbor = 15 if (phase == "ingress_before" and follows_tick) or (phase == "settled" and not follows_tick) else 16
            row = {"case": case, "order": str(order), "phase": phase,
                   "time_ns": str(2_011_501_002 if phase == "settled" else arrival_ns),
                   "local_counter": str(local), "neighbor_counter": str(neighbor), "data_queue": "1", "transmissions": "0"}
            rows.append(row)
    return rows


def verify_clock_plan(source_root, candidate):
    require(candidate.get("ClockPlan") == "scenarios/clock/plan.json", "Unexpected clock plan path")
    path = source_root / candidate["ClockPlan"]
    require(sha256(path) == candidate.get("ClockPlanSHA256"), "Clock plan binding mismatch")
    plan = json_object(path)
    fixed = {"schema": "csr-tranche12-clock-input-v1", "source_pin": PIN, "cases": list(CLOCK_CASES),
             "mac_epoch_ns": 1699501000, "boundary_ns": 2011501000, "slot_ns": 13000000,
             "free_slot": 16, "slot_profile": "hist-2014-next-tslot-modulo-probe", "active_nodes": 3, "slot_range": 31,
             "neighbor_slot": 16, "enqueue_ns": 1699501000, "early_arm_ns": 1989000000,
             "late_arm_ns": 2011500998, "neighbor_reset_ns": 2011500995, "settled_ns": 2011501002,
             "reconstructed_tx_seconds": 1.989, "wire_payload_bytes": 48, "rate_kbps": 128,
             "preamble": "short", "propagation_seconds": .000001}
    require(set(plan) == set(fixed) | {"scope"} and all(plan.get(key) == value for key, value in fixed.items()),
            "Clock fixed-v1 scenario changed")
    return plan


def validate_clock_events(events, *, matlab, label):
    expected = clock_expected_events(matlab=matlab)
    require(len(events) == len(expected), f"{label}: incomplete clock event inventory")
    for row, target in zip(events, expected):
        require(tuple(row) == CLOCK_FIELDS, f"{label}: unexpected clock event schema")
        require((row["case"], integer(row["order"], "clock order"), row["phase"]) ==
                (target["case"], integer(target["order"], "expected order"), target["phase"]),
                f"{label}: duplicate or reordered clock case/phase")
        for field in CLOCK_FIELDS[3:]:
            require(integer(row[field], field) == integer(target[field], field), f"{label}: clock observation contradicts {field} boundary contract")
    return expected


def verify_clock_checks(rows, events, *, matlab):
    expected = clock_expected_events(matlab=matlab)
    require(len(rows) == 72, "Clock check inventory incomplete")
    index = 0
    for event, target in zip(events, expected):
        for field in CLOCK_FIELDS[4:]:
            row = rows[index]
            require(tuple(row) == CLOCK_CHECK_FIELDS and (row["case"], row["phase"], row["field"]) ==
                    (event["case"], event["phase"], field), "Clock check identity missing, duplicate or reordered")
            actual, expectation = integer(event[field], field), integer(target[field], field)
            require(integer(row["actual"], "clock actual") == actual and integer(row["expected"], "clock expected") == expectation
                    and logical(row["pass"], "clock check pass") is (actual == expectation),
                    "Clock check contradicts independently derived observation")
            require(actual == expectation, "Clock structural check failed")
            index += 1
    return index


def verify_boundaries(rows):
    require(len(rows) == 6 and [row.get("case") for row in rows] == list(CLOCK_CASES), "Clock boundary inventory incomplete or reordered")
    tick = 2_011_501_000 / 1e9
    # 128 is the historical rate key; its operational payload rate is four
    # bits per 30 microseconds, as in the immutable rateDefinition source.
    duration = (104 + 48) / 4 * .000510 + (48 * 8 + 32) / (4 / .000030)
    continuous = 1.989 + duration + .000001
    hex64 = lambda value: struct.pack(">d", value).hex()
    offsets = {}
    for row in rows:
        require(tuple(row) == BOUNDARY_FIELDS, "Unexpected binary64 boundary schema")
        case = row["case"]
        arrival = continuous if case == "continuous" else ((2_011_501_000 + {"before": -1, "after": 1}.get(case, 0)) / 1e9)
        require(row["arrival_seconds_hex"] == hex64(arrival) and row["tick_seconds_hex"] == hex64(tick),
                "Clock binary64 arrival/tick evidence contradicts reconstruction")
        expected = Decimal(str(arrival - tick))
        observed = number(row["arrival_minus_tick_seconds"], "clock binary64 offset")
        require(abs(observed - expected) <= abs(expected) * Decimal("1e-14"), "Clock decimal offset contradicts binary64 evidence")
        require(logical(row["transport_quantized"], "transport quantization") is (case == "quantized")
                and logical(row["late_insertion"], "late insertion") is (case == "tie_late"), "Clock transport/FIFO scope changed")
        offsets[case] = str(expected)
    return offsets


def verify_native_clock(source_root, candidate, plan):
    require(candidate.get("ClockReferenceManifest") == CLOCK_REFERENCE + "/manifest.json", "Unexpected clock reference path")
    native, manifest = verify_manifest(source_root, candidate["ClockReferenceManifest"], candidate.get("ClockReferenceManifestSHA256"),
                                      "csr-tranche12-clock-reference-files-v1")
    summary = json_object(native / "summary.json")
    build, libraries, build_digest = verify_clean_build(source_root)
    require(summary.get("schema") == "csr-tranche12-clock-native-v1" and summary.get("status") == "passed"
            and summary.get("source_commit") == PIN and summary.get("engine_commit") == ENGINE_PIN
            and summary.get("shared_libraries") == libraries and summary.get("clean_build_sha256") == build_digest
            and summary.get("production_source_unchanged") is True and summary.get("native_overlay") is False
            and summary.get("matlab_executed") is False and summary.get("scope") == plan["scope"],
            "Native clock source, runtime, scope or library provenance mismatch")
    sources = ("scripts/ns3/tranche12_clock.cc", "scripts/run_tranche12_clock.py", "scripts/run_tranche4_ns3_reference.py")
    require(summary.get("fixture_sources") == {name: sha256(source_root / name) for name in sources}
            and summary.get("input_path") == "scenarios/clock/plan.json"
            and summary.get("input_sha256") == candidate["ClockPlanSHA256"], "Native clock fixture/input binding mismatch")
    require(integer(summary.get("compiler_exit_code"), "clock compiler exit") == 0
            and integer(summary.get("execution_exit_code"), "clock execution exit") == 0,
            "Native clock compile or execution failed")
    expected_headers = {"model/" + Path(name).name: digest for name, digest in build.get("input_sha256", {}).items()
                        if name.startswith(build["source_path"] + "/model/") and name.endswith(".h")}
    require(expected_headers and summary.get("source_headers") == expected_headers,
            "Native clock headers differ from audited build")
    events = csv_rows(native / "events.csv", CLOCK_FIELDS)
    validate_clock_events(events, matlab=False, label="native")
    count = verify_clock_checks(csv_rows(native / "checks.csv", CLOCK_CHECK_FIELDS), events, matlab=False)
    require(all(integer(summary.get(field), field) == value for field, value in
                (("case_count", 6), ("event_count", 18), ("checkpoint_count", count), ("failed_count", 0))),
            "Native clock summary counters disagree")
    return events, {"source_pin": PIN, "engine_pin": ENGINE_PIN, "production_mac_unmodified": True,
                    "case_count": 6, "event_count": 18, "checkpoint_count": count, "artifact_count": len(manifest["files"])}


def verify_clock(root, metadata, source_root, candidate):
    plan = verify_clock_plan(source_root, candidate)
    require(metadata.get("ClockDirectory") == "clock", "Unexpected clock output directory")
    directory = root / "clock"
    native, provenance = verify_native_clock(source_root, candidate, plan)
    events = csv_rows(directory / "events.csv", CLOCK_FIELDS)
    validate_clock_events(events, matlab=True, label="MATLAB")
    checks = verify_clock_checks(csv_rows(directory / "checks.csv", CLOCK_CHECK_FIELDS), events, matlab=True)
    offsets = verify_boundaries(csv_rows(directory / "boundary.csv", BOUNDARY_FIELDS))
    comparison = compare_rows(events, native, CLOCK_FIELDS, family="clock", time_tolerance_ns=0)
    shared = compare_rows([row for row in events if row["case"] != "continuous"],
                          [row for row in native if row["case"] != "continuous"], CLOCK_FIELDS,
                          family="clock_shared_integer", time_tolerance_ns=0)
    residual_expected = (comparison["unmatched_rows"] == 3 and shared["matches_native"] and
                         all(row["matlab"]["case"] == "continuous" for row in comparison["differences"]) and
                         sum(len(row["fields"]) for row in comparison["differences"]) == 4)
    summary = json_object(directory / "summary.json")
    require(summary.get("Schema") == "csr-tranche12-clock-contract-v1" and summary.get("DiagnosticCompleted") is True
            and summary.get("Passed") is True and summary.get("MatchesNative") is comparison["matches_native"]
            and summary.get("SharedIntegerMatchesNative") is shared["matches_native"]
            and summary.get("ExpectedContinuousResidual") is residual_expected, "Clock completion/match claims contradict observations")
    require(summary.get("InputSHA256") == candidate["ClockPlanSHA256"]
            and summary.get("ReferenceSHA256") == sha256(source_root / CLOCK_REFERENCE / "events.csv")
            and summary.get("GlobalClockChanged") is False and summary.get("TransportQuantizationScope") == "quantized case only"
            and summary.get("Scope") == plan["scope"], "Clock binding or transport scope changed")
    for field, value in (("CaseCount", 6), ("EventCount", 18), ("CheckpointCount", checks), ("FailedCount", 0),
                         ("UnmatchedCount", comparison["unmatched_rows"])):
        require(integer(summary.get(field), field) == value, f"Clock {field} summary disagrees")
    require(metadata.get("ClockCompleted") is True and metadata.get("ClockPassed") is True
            and metadata.get("ClockMatchesNative") is comparison["matches_native"], "Clock metadata completion or match claim disagrees")
    for field, value in (("ClockCaseCount", 6), ("ClockCheckpointCount", checks), ("ClockUnmatchedCount", comparison["unmatched_rows"])):
        require(integer(metadata.get(field), field) == value, f"Clock metadata {field} disagrees")
    return {"structural_complete": True, "matches_native": comparison["matches_native"],
            "shared_integer_matches_native": shared["matches_native"], "expected_continuous_residual": residual_expected,
            "case_count": 6, "event_count": 18, "checkpoint_count": checks,
            "unmatched_rows": comparison["unmatched_rows"], "comparison": comparison,
            "binary64_offsets_seconds": offsets, "native_provenance": provenance, "scope": plan["scope"]}


def compare_rows(actual, reference, fields, *, family, text_fields=("case", "event", "purpose", "phase"), time_tolerance_ns=1):
    """Compare complete original order, retaining suffix and all counter residuals."""
    differences, timing_nonzero = [], 0
    maximum_time = Decimal(0)
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
                else:
                    delta = abs(number(left[field], field) - number(right[field], field))
                    same = delta <= time_tolerance_ns if field == "time_ns" else delta == 0
                    if field == "time_ns":
                        maximum_time = max(maximum_time, delta)
                        timing_nonzero += delta != 0
                if not same:
                    unequal.append(field)
        if unequal:
            differences.append({"family": family, "row": index + 1, "fields": unequal, "matlab": left, "ns3": right})
    return {"family": family, "matches_native": not differences, "matlab_rows": len(actual),
            "native_rows": len(reference), "paired_rows": min(len(actual), len(reference)),
            "unmatched_rows": len(differences), "nonzero_time_differences": timing_nonzero,
            "maximum_time_difference_ns": str(maximum_time), "differences": differences}


def verify_relay_plan(source_root, candidate):
    name = candidate.get("RelayPlan")
    require(name == "scenarios/relay/plan.json", "Unexpected relay plan path")
    path = safe_path(source_root, name)
    require(sha256(path) == candidate.get("RelayPlanSHA256"), "Relay plan hash mismatch")
    plan = json_object(path)
    expected = {"schema": "csr-tranche12-relay-input-v1", "source_pin": PIN,
                "cases": list(RELAY_CASES), "nodes": list(RELAY_NODES), "gateway": 1, "sources": [4, 5], "relay": 5,
                "applications_per_active_source": 20, "application_payload_bytes": 16, "dscp": 0,
                "wire_profile": "bare", "rate_kbps": 128, "power_dbm": 33,
                "slot_profile": "hist-2014-next-tslot-modulo-probe", "slot_range": 31, "slot_reduction": 0,
                "active_nodes": 3, "reported_active_nodes": 3, "duty_cycle": False,
                "initial_mac_state": "Search", "initial_neighbor_reservation": -1,
                "known_neighbors": {"1": [5], "4": [5], "5": [1, 4]}, "next_hops": {"4": 5, "5": 1},
                "route_target": 1, "route_capability": 2, "neighbor_admission_enabled": False,
                "neighbor_freshness_enabled": False, "automatic_route_control_transport": False,
                "matlab_control_retry_seconds": 1000, "matlab_snapshot_watchdog_seconds": 1000,
                "prescribed_sync_present": False, "offered_start_seconds": 0,
                "offered_poll_stop_exclusive_seconds": 16, "application_nsdp_limit": 16,
                "tape_entries_per_node": 256, "events_schema": list(RELAY_FIELDS),
                "draws_output_schema": list(DRAW_FIELDS), "event_names": list(RELAY_EVENTS)}
    for field, value in expected.items():
        if field == "event_names":
            require(set(plan.get(field, [])) == RELAY_EVENTS, "Relay event scope changed")
        else:
            require(plan.get(field) == value and (type(value) is not bool or type(plan.get(field)) is bool),
                    f"Relay fixed plan field changed: {field}")
    for field, value in (("slot_seconds", ".013"), ("holdoff_seconds", ".3"), ("offered_poll_seconds", ".02"),
                         ("propagation_seconds", ".000001"), ("pathloss_db", "70"), ("snr_db", "20")):
        require(number(plan.get(field), field) == Decimal(value), f"Relay fixed numeric plan field changed: {field}")
    cases = csv_rows(source_root / "scenarios/relay/cases.csv", ("case", "duration_seconds", "apps4", "apps5"))
    require([row["case"] for row in cases] == list(RELAY_CASES), "Relay cases missing, duplicated or reordered")
    for row in cases:
        require(number(row["duration_seconds"], "case duration") == 24 and
                {node: integer(row[f"apps{node}"], "application count") for node in (4, 5)} == RELAY_COUNTS[row["case"]],
                "Relay prescribed case population changed")
    tape = {}
    for row in csv_rows(source_root / "scenarios/relay/draws.csv", ("case", "node", "ordinal", "min", "max", "draw")):
        case, node, ordinal = row["case"], integer(row["node"], "tape node"), integer(row["ordinal"], "tape ordinal", 1)
        key = (case, node, ordinal)
        require(case in RELAY_CASES and node in RELAY_NODES and ordinal <= 256 and key not in tape,
                "Duplicate, excess or unknown relay tape identity")
        pattern = (1, 1) if node == 1 else ((9, 1) if (node == 5) != (case == "sw") else (3, 7))
        observed = {field: integer(row[field], field) for field in ("min", "max", "draw")}
        require(observed == {"min": 0, "max": 31, "draw": pattern[(ordinal - 1) % 2]}, "Relay prescribed draw or support changed")
        tape[key] = observed
    require(set(tape) == {(case, node, ordinal) for case in RELAY_CASES for node in RELAY_NODES for ordinal in range(1, 257)},
            "Relay tape is incomplete")
    return plan, tape


def validate_relay_events(rows, *, label):
    require(rows, f"{label}: empty relay events")
    previous_case, next_order, last_time, finals, checkpoints = -1, 1, Decimal(0), set(), set()
    admissions, delivered = set(), set()
    counts = {case: 0 for case in RELAY_CASES}
    for row in rows:
        require(tuple(row) == RELAY_FIELDS, f"{label}: unexpected relay schema")
        case = row["case"]
        require(case in RELAY_CASES, f"{label}: unknown relay case")
        case_index = RELAY_CASES.index(case)
        if case_index != previous_case:
            require(case_index == previous_case + 1 and (previous_case < 0 or finals == checkpoints == set(RELAY_NODES)),
                    f"{label}: missing or reordered relay case/finals")
            previous_case, next_order, last_time, finals, checkpoints = case_index, 1, Decimal(0), set(), set()
        require(integer(row["order"], "event order", 1) == next_order, f"{label}: missing or duplicate relay event order")
        next_order += 1
        when = number(row["time_ns"], "event time", minimum=0)
        require(last_time <= when <= 24_000_000_000, f"{label}: relay event time unordered or outside case")
        last_time = when
        event, node, peer = row["event"], integer(row["node"], "node"), integer(row["peer"], "peer")
        require(event in RELAY_EVENTS and node in RELAY_NODES and peer in (0, *RELAY_NODES), f"{label}: unsupported relay identity")
        for field in RELAY_FIELDS[6:]:
            if field == "power_dbm":
                number(row[field], field)
            else:
                integer(row[field], field, -1 if field in ("counter", "opportunity", "advertised", "neighbor_threshold") else 0)
        require(integer(row["mac_state"], "MAC state") <= 3 and integer(row["prep"], "preparation flag") <= 1,
                f"{label}: invalid MAC state or preparation flag")
        require(integer(row["ack_bits"], "ACK bitmap") <= 2**64 - 1 and integer(row["dack_bits"], "DACK bitmap") <= 2**64 - 1,
                f"{label}: bitmap out of range")
        source, app_id = integer(row["app_source"], "application source"), integer(row["app_id"], "application ID")
        require(source in (0, 4, 5) and 0 <= app_id <= 20, f"{label}: unknown application identity")
        require(integer(row["admitted"], "admission count") <= RELAY_COUNTS[case].get(node, 0), f"{label}: excess application admission")
        if event in ("offer", "admit", "blocked"):
            require(node in (4, 5) and source == node and 1 <= app_id <= RELAY_COUNTS[case][node],
                    f"{label}: invalid offered application identity")
        if event == "admit":
            key = (case, source, app_id)
            require(key not in admissions, f"{label}: duplicate admitted application")
            admissions.add(key)
        if event == "deliver":
            key = (case, source, app_id)
            require(node == 1 and source in (4, 5) and 1 <= app_id <= RELAY_COUNTS[case][source]
                    and key in admissions and key not in delivered, f"{label}: duplicate, unadmitted or invalid delivery")
            delivered.add(key)
        if event == "checkpoint":
            require(when == 16_000_000_000 and node not in checkpoints, f"{label}: missing, early or duplicate checkpoint observation")
            checkpoints.add(node)
        if event == "final":
            require(when == 24_000_000_000 and node not in finals, f"{label}: early or duplicate final observation")
            finals.add(node)
        counts[case] += 1
    require(previous_case == len(RELAY_CASES) - 1 and finals == checkpoints == set(RELAY_NODES), f"{label}: incomplete final relay case")
    return counts


def validate_relay_draws(rows, usage, tape, *, label):
    require(rows, f"{label}: empty relay draws")
    counts = {(case, node): 0 for case in RELAY_CASES for node in RELAY_NODES}
    previous_case, previous_time = -1, Decimal(0)
    for row in rows:
        require(tuple(row) == DRAW_FIELDS, f"{label}: unexpected draw schema")
        case, node = row["case"], integer(row["node"], "draw node")
        require((case, node) in counts, f"{label}: unknown relay draw identity")
        case_index = RELAY_CASES.index(case)
        require(case_index >= previous_case, f"{label}: reordered draw case")
        if case_index != previous_case:
            previous_case, previous_time = case_index, Decimal(0)
        when = number(row["time_ns"], "draw time", minimum=0)
        require(previous_time <= when <= 24_000_000_000, f"{label}: draw time unordered or outside case")
        previous_time = when
        counts[case, node] += 1
        ordinal = integer(row["ordinal"], "draw ordinal", 1)
        require(ordinal == counts[case, node] and (case, node, ordinal) in tape, f"{label}: duplicate, missing or exhausted draw ordinal")
        require({field: integer(row[field], field) for field in ("min", "max", "draw")} == tape[case, node, ordinal],
                f"{label}: raw contention draw or support differs from prescribed tape")
        require(row["purpose"] in ("prepare", "advertise") and 0 <= integer(row["resolved"], "resolved slot") <= 255,
                f"{label}: invalid resolved slot or draw purpose")
    seen = set()
    for row in usage:
        require(tuple(row) == USAGE_FIELDS, f"{label}: unexpected usage schema")
        key = (row["case"], integer(row["node"], "usage node"))
        require(key in counts and key not in seen, f"{label}: unknown or duplicate usage identity")
        seen.add(key)
        supplied, consumed, unused = (integer(row[field], field) for field in ("supplied", "consumed", "unused"))
        require(supplied == 256 and consumed == counts[key] and supplied == consumed + unused,
                f"{label}: raw tape unused suffix accounting mismatch")
    require(seen == set(counts), f"{label}: incomplete raw tape usage inventory")
    return counts


CHECK_FIELDS = ("case", "checkpoint", "node", "actual", "expected", "pass")


def compute_relay_checks(events, draws):
    checks = []
    def add(case, name, node, actual, expected=0):
        checks.append({"case": case, "checkpoint": name, "node": node,
                       "actual": actual, "expected": expected, "pass": actual == expected})
    for case in RELAY_CASES:
        selected = [row for row in events if row["case"] == case]
        wanted = RELAY_COUNTS[case]
        for source in (4, 5):
            own = [row for row in selected if integer(row["node"], "node") == source]
            delivered = {integer(row["app_id"], "app ID") for row in selected if row["event"] == "deliver"
                         and integer(row["app_source"], "app source") == source}
            add(case, "admitted", source, sum(row["event"] == "admit" for row in own), wanted[source])
            add(case, "delivered", source, len(delivered), wanted[source])
            add(case, "nsdp_blocked_seen", source, int(any(row["event"] == "blocked" for row in own)), int(wanted[source] > 16))
        for node in RELAY_NODES:
            own = [row for row in selected if integer(row["node"], "node") == node]
            final = [row for row in own if row["event"] == "final"]
            checkpoint = [row for row in own if row["event"] == "checkpoint"]
            require(len(final) == len(checkpoint) == 1, "Relay final/checkpoint node missing")
            for snapshot in final + checkpoint:
                require(integer(snapshot["hop_pending"], "stable pending") == integer(snapshot["resend_queue"], "stable resend") +
                        integer(snapshot["dack_holds"], "stable DACK holds"), "Stable HOP pending capacity is not accounted by resends and DACK holds")
            for field in ("hop_pending", "dack_holds", "resend_queue", "nwk_waiting", "nwk_custody", "nsdp4", "nsdp5"):
                add(case, field, node, integer(final[0][field], field))
            target = wanted[4] if node == 4 else sum(wanted.values()) if node == 5 else 0
            add(case, "released", node, sum(row["event"] == "release" for row in own), target)
        relay_custody = {integer(row["app_id"], "relay app ID") for row in selected if row["event"] == "ingress_after"
                        and integer(row["node"], "relay node") == 5 and integer(row["app_source"], "source") == 4
                        and integer(row["app_id"], "relay app ID") > 0}
        add(case, "relay_custody", 5, len(relay_custody), wanted[4])
        # A terminal data loss leaves an admitted identity undelivered. Offers
        # retain the same ID only until admission, and duplicate delivery is
        # rejected by validate_relay_events.
        loss = sum(row["event"] == "admit" for row in selected) - sum(row["event"] == "deliver" for row in selected)
        add(case, "drops", 0, loss)
        releases = [row for row in selected if row["event"] == "release"]
        release_failures = sum(integer(row["hop_pending"], "release pending") != integer(row["neighbor_outstanding"], "release outstanding")
            or integer(row["resend_queue"], "release resend") + integer(row["dack_holds"], "release DACK holds") -
            integer(row["hop_pending"], "release pending") not in (0, 1) for row in releases)
        add(case, "release_order_failures", 0, release_failures)
        add(case, "draw_resolution_failures", 0, sum(row["purpose"] not in ("prepare", "advertise") or
            integer(row["resolved"], "resolved", -1) < 0 for row in draws if row["case"] == case))
        add(case, "custody_conservation_failures", 0, sum(integer(row["nwk_custody"], "custody") !=
            integer(row["nsdp4"], "NSDP4") + integer(row["nsdp5"], "NSDP5") for row in selected))
        data = [row for row in selected if row["event"] == "tx_start" and integer(row["app_source"], "source") > 0]
        add(case, "direct_source_gateway_transmissions", 4, sum(integer(row["node"], "node") == 4 and integer(row["peer"], "peer") == 1 for row in data))
        add(case, "source4_wrong_next_hop", 4, sum(integer(row["node"], "node") == 4 and integer(row["peer"], "peer") != 5 for row in data))
        add(case, "relay_wrong_next_hop", 5, sum(integer(row["node"], "node") == 5 and integer(row["peer"], "peer") != 1 for row in data))
        feedback = [row for row in selected if row["event"] == "tx_start" and integer(row["app_source"], "source") == 0]
        add(case, "relay_ack_seen", 5, int(any(integer(row["node"], "node") == 5 and integer(row["peer"], "peer") == 4 for row in feedback)), int(wanted[4] > 0))
        add(case, "gateway_ack_seen", 1, int(any(integer(row["node"], "node") == 1 and integer(row["peer"], "peer") == 5 for row in feedback)), int(sum(wanted.values()) > 0))
        add(case, "case_completed", 0, int(sum(row["event"] == "final" for row in selected) == 3), 1)
    return checks


def verify_relay_checks(directory, events, draws):
    expected = compute_relay_checks(events, draws)
    actual = csv_rows(directory / "check.csv", CHECK_FIELDS)
    require(len(actual) == len(expected) == 164, "Relay checkpoint inventory incomplete")
    for row, target in zip(actual, expected):
        require((row["case"], row["checkpoint"], integer(row["node"], "checkpoint node")) ==
                (target["case"], target["checkpoint"], target["node"]), "Relay checkpoint identity missing, duplicated or reordered")
        require(integer(row["actual"], "checkpoint actual") == target["actual"]
                and integer(row["expected"], "checkpoint expected") == target["expected"]
                and logical(row["pass"], "checkpoint pass") is target["pass"], "Relay checkpoint contradicts raw observations")
    require(all(row["pass"] for row in expected), "Relay service check failed")
    return expected


def verify_relay_claims(metadata, summary, *, event_count, draw_count, checks, comparisons):
    unmatched = sum(row["unmatched_rows"] for row in comparisons)
    matches = unmatched == 0
    require(summary.get("DiagnosticCompleted") is True and summary.get("Passed") is True, "Relay structural completion missing")
    require(summary.get("MatchesNative") is matches and metadata.get("RelayMatchesNative") is matches,
            "Relay native match claim contradicts independently compared rows")
    for field, expected in (("CaseCount", 4), ("EventCount", event_count), ("DrawCount", draw_count),
                            ("CheckpointCount", len(checks)), ("FailedCount", 0), ("UnmatchedCount", unmatched)):
        require(integer(summary.get(field), field) == expected, f"Relay summary {field} contradicts raw observations")
    for field, expected in (("RelayCaseCount", 4), ("RelayEventCount", event_count), ("RelayDrawCount", draw_count), ("RelayUnmatchedCount", unmatched)):
        require(integer(metadata.get(field), field) == expected, f"Relay metadata {field} contradicts raw observations")
    require(metadata.get("RelayCompleted") is True, "Relay completion metadata missing")
    return matches, unmatched


def verify_relay(root, metadata, source_root, candidate):
    plan, tape = verify_relay_plan(source_root, candidate)
    require(metadata.get("RelayDirectory") == "relay", "Unexpected relay output directory")
    directory = root / "relay"
    native, provenance = verify_native_relay(source_root, candidate, plan, tape)
    files = (("events", RELAY_FIELDS), ("draws", DRAW_FIELDS), ("usage", USAGE_FIELDS))
    actual = {family: csv_rows(directory / (family + ".csv"), fields) for family, fields in files}
    validate_relay_events(actual["events"], label="MATLAB")
    validate_relay_draws(actual["draws"], actual["usage"], tape, label="MATLAB")
    comparisons = [compare_rows(actual[family], native[family], fields, family=family) for family, fields in files]
    checks = verify_relay_checks(directory, actual["events"], actual["draws"])
    summary = json_object(directory / "summary.json")
    require(summary.get("Schema") == "csr-tranche12-relay-contract-v1" and summary.get("Runtime") == metadata.get("Runtime", {}).get("Version"),
            "Relay summary schema or owner runtime mismatch")
    verify_bindings(summary.get("InputBindings"), source_root,
                    ["scenarios/relay/" + name for name in ("plan.json", "cases.csv", "draws.csv")], "Relay inputs")
    verify_bindings(summary.get("ReferenceBindings"), source_root,
                    [RELAY_REFERENCE + "/" + name for name in ("events.csv", "draws.csv", "usage.csv")], "Relay references")
    require(summary.get("ComparedEntireTrajectories") is True and summary.get("TimeToleranceNanoseconds") == 1
            and summary.get("Scope") == plan["scope"], "Relay comparison scope or timing tolerance changed")
    for count_field, comparison_field, comparison in zip(("EventsCompared", "DrawsCompared", "UsageCompared"),
            ("EventComparison", "DrawComparison", "UsageComparison"), comparisons):
        require(integer(summary.get(count_field), count_field) == max(comparison["matlab_rows"], comparison["native_rows"]),
                f"Relay {count_field} summary disagrees")
        verify_comparison_claim(summary.get(comparison_field), comparison, comparison_field)
    cases = records(summary.get("CaseResults"), "relay case results")
    require([row.get("Case") for row in cases] == list(RELAY_CASES)
            and all(row.get("Completed") is True and row.get("ErrorIdentifier") == "" and row.get("ErrorMessage") == "" for row in cases),
            "Relay case completion or identities disagree")
    pending_controls = {}
    for result in cases:
        selected = [row for row in actual["events"] if row["case"] == result["Case"]]
        counters = {key: [0] * 5 for key in ("Admitted", "Delivered", "Released", "FinalHopPending", "FinalDackHolds", "FinalResends")}
        for node in RELAY_NODES:
            own = [row for row in selected if integer(row["node"], "node") == node]
            counters["Admitted"][node - 1] = sum(row["event"] == "admit" for row in own)
            counters["Released"][node - 1] = sum(row["event"] == "release" for row in own)
            counters["Delivered"][node - 1] = sum(row["event"] == "deliver" and integer(row["app_source"], "source") == node for row in selected)
            final = next(row for row in own if row["event"] == "final")
            for field, raw in (("FinalHopPending", "hop_pending"), ("FinalDackHolds", "dack_holds"), ("FinalResends", "resend_queue")):
                counters[field][node - 1] = integer(final[raw], raw)
        require(all(isinstance(result.get(key), list) and [integer(value, key) for value in result[key]] == values
                    for key, values in counters.items()), "Relay per-case counters contradict raw observations")
        custody = next(row["actual"] for row in checks if row["case"] == result["Case"] and row["checkpoint"] == "relay_custody")
        require(integer(result.get("RelayCustodyAccepted"), "relay custody") == custody and integer(result.get("Drops"), "drops") == 0,
                "Relay custody or terminal loss claims disagree")
        controls = result.get("PendingControls")
        require(isinstance(controls, list) and len(controls) == 5 and all(integer(value, "pending controls") >= 0 for value in controls)
                and controls[1:3] == [0, 0], "Relay reported control inventory malformed")
        pending_controls[result["Case"]] = controls
    matches, unmatched = verify_relay_claims(metadata, summary, event_count=len(actual["events"]), draw_count=len(actual["draws"]),
                                             checks=checks, comparisons=comparisons)
    return {"structural_complete": True, "matches_native": matches, "unmatched_rows": unmatched,
            "case_count": 4, "event_count": len(actual["events"]), "draw_count": len(actual["draws"]),
            "checkpoint_count": len(checks), "comparisons": comparisons, "scope": plan["scope"], "native_provenance": provenance,
            "reported_pending_controls": pending_controls,
            "pending_control_scope": "Owner-reported excluded bootstrap controls; event schema does not independently observe these counters."}


def verify_baseline(metadata, source_root, candidate):
    """Pin both the reviewed T11 sources and their accepted T10 core subset."""
    result = {}
    for label, name, digest, source_count, matlab_count, prefix in (
        ("tranche11", BASELINE, BASELINE_SHA, 241, 130, "Baseline"),
        ("accepted_core", CORE_BASELINE, CORE_BASELINE_SHA, 225, 124, "CoreBaseline"),
    ):
        require(candidate.get(prefix + "SourceSnapshot") == name, f"Unexpected {label} baseline path")
        declared_digest = "BaseSourceSnapshotSHA256" if prefix == "Baseline" else prefix + "SourceSnapshotSHA256"
        path = safe_path(source_root, name)
        require(sha256(path) == candidate.get(declared_digest) == digest, f"{label} source provenance hash mismatch")
        expected = record_map(json_value(path), label + " source")
        require(len(expected) == source_count and sum(name.endswith(".m") for name in expected) == matlab_count,
                f"{label} source identity/count changed")
        for relative, row in expected.items():
            require(sha256(safe_path(source_root, relative)) == row["sha256"], f"{label} baseline changed: {relative}")
        require(integer(metadata.get(prefix + "SourceFilesVerified"), prefix + " source count") == source_count
                and integer(metadata.get(prefix + "MatlabFilesVerified"), prefix + " MATLAB count") == matlab_count,
                f"{label} baseline verification counters disagree")
        require(integer(candidate.get(prefix + "SourceFilesUnchanged"), prefix + " source count") == source_count
                and integer(candidate.get(prefix + "MatlabFilesUnchanged"), prefix + " MATLAB count") == matlab_count,
                f"{label} candidate baseline counters disagree")
        result[label] = {"source_files": source_count, "matlab_files": matlab_count, "unchanged": True, "snapshot_sha256": digest}
    require(candidate.get("BaseArchive") == "csr11r.zip" and candidate.get("BaseArchiveSHA256") == BASE_ARCHIVE_SHA,
            "Reviewed T11 package provenance mismatch")
    return result


def verify_manifest(source_root, manifest_name, expected_digest, schema):
    """A hash-only list must close over every native artifact, not selected rows."""
    path = safe_path(source_root, manifest_name)
    require(path.name == "manifest.json" and sha256(path) == expected_digest, "Candidate native manifest binding mismatch")
    manifest = json_object(path)
    require(manifest.get("schema") == schema and isinstance(manifest.get("files"), dict), "Native manifest schema mismatch")
    listed = manifest["files"]
    require(set(listed) == all_files(path.parent) - {"manifest.json"}, "Native reference manifest is not closed")
    require(len({name.casefold() for name in listed}) == len(listed), "Case-colliding native manifest paths")
    for name, digest in listed.items():
        require(sha256(safe_path(path.parent, name)) == digest, f"Native manifest hash mismatch: {name}")
    return path.parent, manifest


def verify_clean_build(source_root):
    path = source_root / "evidence/tranche-11-native-build.json"
    build = json_object(path)
    require(build.get("schema") == "csr-tranche11-native-control-build-v1" and build.get("status") == "passed"
            and build.get("source_commit") == PIN and build.get("engine_commit") == ENGINE_PIN
            and build.get("engine_rebuilt") is True and build.get("reused_historical_libraries") is False
            and build.get("csr_tracked_sources_unchanged") is True and build.get("engine_tracked_sources_unchanged") is True
            and build.get("build_record", {}).get("exit_code") == 0, "Audited native build provenance missing")
    libraries = {Path(row["path"]).name: row["sha256"] for row in records(build.get("libraries"), "audited libraries")}
    require(len(libraries) == 9, "Audited native library membership changed")
    return build, libraries, sha256(path)


def verify_native_relay(source_root, candidate, plan, tape):
    require(candidate.get("RelayReferenceManifest") == RELAY_REFERENCE + "/manifest.json", "Unexpected relay reference path")
    native, manifest = verify_manifest(source_root, candidate["RelayReferenceManifest"],
                                      candidate.get("RelayReferenceManifestSHA256"), "csr-tranche12-reference-files-v1")
    summary = json_object(native / "summary.json")
    require(summary.get("schema") == "csr-tranche12-native-reference-v1" and summary.get("status") == "completed"
            and summary.get("source_pin") == PIN and summary.get("scope") == plan["scope"]
            and summary.get("native_source_unchanged") is True and summary.get("native_libraries_unchanged") is True
            and summary.get("instrumented_native_fixture") is True and summary.get("real_nwk_application_and_relay_path") is True
            and summary.get("matlab_execution") is False and summary.get("cross_simulator_parity_established") is False,
            "Native relay execution, source or diagnostic scope mismatch")
    expected_inputs = {name: sha256(source_root / "scenarios/relay" / name) for name in ("plan.json", "cases.csv", "draws.csv")}
    fixture_paths = ("scripts/run_tranche12_ns3_reference.py", "scripts/build_tranche12_overlay.py",
                     "scripts/ns3/tranche12_relay.cc", "scripts/ns3/tranche12-relay-hooks.h")
    require(summary.get("input_hashes") == expected_inputs and
            summary.get("fixture_hashes") == {Path(name).name: sha256(source_root / name) for name in fixture_paths},
            "Native relay fixture or input source binding mismatch")
    build, libraries, build_digest = verify_clean_build(source_root)
    short_libraries = {name.removeprefix("libns3-dev-").removesuffix("-debug.so"): digest for name, digest in libraries.items()}
    require(summary.get("shared_libraries") == short_libraries
            and summary.get("clean_build_record") == "evidence/tranche-11-native-build.json"
            and summary.get("clean_build_record_sha256") == build_digest
            and summary.get("engine_build_reused_after_hash_verification") is True,
            "Native relay libraries or clean build binding mismatch")
    commands = records(summary.get("commands"), "native relay commands")
    require(all(integer(row.get("exit_code"), "native command exit") == 0 for row in commands), "Native relay command failed")
    controls = summary.get("disabled_seam_controls")
    require(isinstance(controls, dict) and set(controls) == {"ack", "receiver"}, "Native disabled-seam controls missing")
    for family, count, digest in (("ack", 101, "2991bbc93e5ba2c64d06a93cee278160cd9baf2fdc11b052ee5b0cb561fe4b73"),
                                  ("receiver", 154, "a3562a3f23e5603359610b150e20551f5a671298d7db529e037d842ce7206c1a")):
        paths = [native / "controls" / f"{family}-{mode}.csv" for mode in ("clean", "off")]
        observed = csv_rows(paths[0])
        require(len(observed) == count and all(logical(row["pass"], "native control pass") for row in observed)
                and all(sha256(path) == digest for path in paths), "Native disabled seams changed retained contracts")
        require(controls[family] == {"checkpoints": count, "passed": True, "clean_and_disabled_byte_equal": True, "sha256": digest},
                "Native disabled-seam summary contradicts controls")
    loaded = {family: csv_rows(native / (family + ".csv"), fields)
              for family, fields in (("events", RELAY_FIELDS), ("draws", DRAW_FIELDS), ("usage", USAGE_FIELDS))}
    validate_relay_events(loaded["events"], label="native")
    validate_relay_draws(loaded["draws"], loaded["usage"], tape, label="native")
    raw_events, raw_draws = [], []
    for case in RELAY_CASES:
        raw_events.extend(csv_rows(native / "raw" / case / "events.csv", RELAY_FIELDS))
        raw_draws.extend(csv_rows(native / "raw" / case / "raw.csv", (*DRAW_FIELDS[:-1], "probes")))
    require(raw_events == loaded["events"], "Native relay canonical events differ from raw execution order")
    require(len(raw_draws) == len(loaded["draws"]) and all(all(left[field] == right[field] for field in DRAW_FIELDS[:-1])
            for left, right in zip(raw_draws, loaded["draws"])), "Native relay canonical draw differs from raw execution")
    require(integer(summary.get("event_count"), "native relay events") == len(loaded["events"])
            and integer(summary.get("draw_count"), "native relay draws") == len(loaded["draws"])
            and integer(summary.get("self_tests"), "native fixture self-tests") == 6, "Native relay summary counts disagree")
    checks = compute_relay_checks(loaded["events"], loaded["draws"])
    require(all(row["pass"] for row in checks), "Native relay service checks incomplete")
    return loaded, {"source_pin": PIN, "engine_pin": ENGINE_PIN, "controlled_transport": True,
                    "instrumented_native_fixture": True, "event_count": len(loaded["events"]),
                    "draw_count": len(loaded["draws"]), "disabled_seam_checkpoints": 255, "self_tests": 6,
                    "artifact_count": len(manifest["files"]), "checkpoint_count": len(checks)}


def verify_comparison_claim(declared, comparison, label):
    expected = {"ReferencePresent": True, "SchemaMatches": True,
                "ActualRows": comparison["matlab_rows"], "ReferenceRows": comparison["native_rows"],
                "ComparedRows": max(comparison["matlab_rows"], comparison["native_rows"]),
                "UnmatchedCount": comparison["unmatched_rows"],
                "FirstUnmatchedRow": comparison["differences"][0]["row"] if comparison["differences"] else 0}
    require(isinstance(declared, dict), f"{label}: missing comparison")
    for key, value in expected.items():
        if isinstance(value, bool):
            require(declared.get(key) is value, f"{label}: {key} claim disagrees")
        else:
            require(integer(declared.get(key), key) == value, f"{label}: {key} claim disagrees")
    require(number(declared.get("MaximumTimeDifferenceNanoseconds"), "maximum timing difference") ==
            number(comparison["maximum_time_difference_ns"], "computed maximum timing difference"),
            f"{label}: maximum timing residual claim disagrees")


def verify_run_identity(root, metadata, source_root, candidate):
    require(candidate.get("Schema") == "csr-tranche-12-candidate-v1" and candidate.get("Tranche") == 12
            and candidate.get("SourceCommit") == PIN, "Candidate schema or source pin mismatch")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 12 and metadata.get("Status") == "completed",
            "Return is not a completed Tranche 12 diagnostic")
    require(metadata.get("MATLABExecuted") is True and metadata.get("NativeExecuted") is False
            and metadata.get("SourceCommit") == PIN, "MATLAB execution or source identity missing")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB"
            and isinstance(runtime.get("Version"), str) and runtime["Version"]
            and runtime.get("DefaultBackend") == "portable", "Unsupported or missing MATLAB runtime provenance")
    require(metadata.get("CandidateFile") == CANDIDATE and metadata.get("CandidateSHA256") == sha256(source_root / CANDIDATE),
            "Candidate identity mismatch")
    started, completed = (datetime.fromisoformat(metadata.get(field, "").replace("Z", "+00:00"))
                          for field in ("StartedUTC", "CompletedUTC"))
    require(started.tzinfo is not None and completed.tzinfo is not None and completed >= started,
            "Invalid owner execution timestamps")
    require(metadata.get("InventoryExcludedPaths") == ["metadata.json"] and metadata.get("EvidenceArchive") == "t12.zip",
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
        require({"run.log", "source.json", "references.json", "tests.csv", "relay/events.csv", "relay/draws.csv",
                 "relay/usage.csv", "relay/check.csv", "relay/summary.json", "clock/summary.json", "clock/checks.csv",
                 "clock/events.csv", "clock/boundary.csv"}
                <= set(artifacts), "Required focused evidence missing")
        source = verify_sources(root, metadata, source_root)
        baseline = verify_baseline(metadata, source_root, candidate)
        references = verify_references(root, metadata, source_root, candidate)
        tests = verify_tests(root, metadata, source_root, candidate)
        relay = verify_relay(root, metadata, source_root, candidate)
        clock = verify_clock(root, metadata, source_root, candidate)
        result = {"schema": REVIEW_SCHEMA, "status": "focused_diagnostic_review_completed",
                  "evidence_integrity_verified": True, "focused_structural_gate_completed": True,
                  "relay_matches_native": relay["matches_native"], "clock_matches_native": clock["matches_native"],
                  "acceptance_established": False, "numerical_parity_established": False,
                  "matlab_executed_by_reviewer": False, "runtime": runtime,
                  "evidence": {"path": evidence.name, "sha256": sha256(evidence), "bytes": evidence.stat().st_size},
                  "source": source, "baseline": baseline, "references": references,
                  "tests": tests, "relay": relay, "clock": clock}
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
        print(f"T12 evidence rejected: {error}")
        return 1
    print(f"T12 focused review complete; relay match={result['relay_matches_native']}; "
          f"clock match={result['clock_matches_native']}. MATLAB execution is owner-returned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
