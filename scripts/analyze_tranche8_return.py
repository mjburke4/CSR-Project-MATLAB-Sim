#!/usr/bin/env python3
"""Verify a Tranche 8 MATLAB return and compare the ten pinned diagnostics.

The default gate covers all candidate portable unit tests, ten instrumented
diagnostics, two observer-disabled controls, and the seed-128 accepted T7 anchor.
It does not rerun the campus benchmark or the retained T7 sweep/scenario suite.
No numerical parity or population equivalence is inferred from five seeds.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import sys
import zipfile

import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import compare_benchmark_aggregates as compare
import tranche8_metrics as metrics

ROOT = Path(__file__).resolve().parents[1]
PIN = t7.PIN
BASE = "68e18181d90b27e5cfaa11f4537595c2e6640809"
T7_CODE = "28ed878f5673e308047cbea7878b933697d932f3"
ANCHOR_SHA = "ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655"
SCHEMA = "csr-matlab-tranche-8-validation-v1"
PLAN = "scenarios/link_diagnostics/plan.json"
BASE_CASES = {"two_node_admission_1200": (1200, 12), "three_node_contention_360": (360, 3.6)}
UNCHANGED_CSV = ("protocol_trace.csv", "trace.csv", "phy_trace.csv", "nodes.csv", "mac_nodes.csv",
                 "hop_nodes.csv", "nwk_nodes.csv", "neighbors.csv", "routes.csv",
                 "application_admission_statistics.csv", "application_admission_trace.csv")
require, integer, finite = sweep.require, sweep.integer, sweep.finite


def short_case_id(case_id):
    for base, prefix in (("two_node_admission_1200", "a"), ("three_node_contention_360", "c")):
        for seed in range(128, 133):
            if case_id == f"{base}_s{seed}":
                return f"{prefix}{seed}"
    raise ValueError("Unknown diagnostic case identifier")


def verify_plan(source_root):
    plan = sweep.json_object(source_root/PLAN)
    require(plan.get("schema") == "csr-link-diagnostic-plan-v1" and plan.get("ns3_source_commit") == PIN
            and plan.get("matlab_base_commit") == BASE and plan.get("accepted_tranche7_matlab_commit") == T7_CODE,
            "Diagnostic plan source/baseline identity mismatch")
    require(plan.get("seeds") == list(range(128, 133)) and plan.get("case_count") == 10
            and plan.get("opnet_available") is False, "Diagnostic plan seed/count/scope mismatch")
    cases = sweep.entries(plan.get("cases"), "planned cases")
    expected = {(base, seed) for base in BASE_CASES for seed in range(128, 133)}
    require(len(cases) == 10 and {(item.get("base_case_id"), item.get("seed")) for item in cases} == expected,
            "Diagnostic plan is not the complete two-fixture five-seed set")
    for item in cases:
        base, seed = item["base_case_id"], item["seed"]
        case_id = f"{base}_s{seed}"
        require(item.get("case_id") == case_id and item.get("reference_directory") == f"evidence/tranche-8-ns3-reference/{case_id}",
                "Diagnostic case path/identity mismatch")
        require((item.get("duration_s"), item.get("bucket_width_s")) == BASE_CASES[base]
                and item.get("profile_id") == "hist-adb97c54-bare" and item.get("flow_limit") == 0
                and item.get("source_kind") == "synthetic_multiseed_diagnostic" and item.get("opnet_available") is False,
                "Diagnostic timing/profile/scope differs from the accepted fixture")
        require(item.get("trace_limits") == {"protocol": 1500000, "phy": 1500000, "admission": 100000,
                                             "link_decisions": 100000, "feedback_transmissions": 100000},
                "Diagnostic trace limits differ from the bounded plan")
        scenario = sweep.safe_path(source_root, item.get("scenario_file"))
        recipe_path = sweep.safe_path(source_root, item.get("recipe_file"))
        require(sweep.digest(scenario) == item.get("scenario_sha256")
                and sweep.digest(recipe_path) == item.get("recipe_sha256"), "Derived scenario/recipe hash mismatch")
        recipe = sweep.json_object(recipe_path)
        parent_path = sweep.safe_path(source_root, recipe.get("parent_scenario"))
        require(recipe.get("schema") == "csr-link-diagnostic-derivation-v1"
                and recipe.get("base_case_id") == base
                and recipe.get("parent_scenario") == f"scenarios/benchmarks/{base}.csv"
                and sweep.digest(parent_path) == recipe.get("parent_scenario_sha256")
                and recipe.get("overrides") == {"scenario": item["scenario"], "seed": seed},
                "Diagnostic recipe changed the accepted source fixture")
        parent = list(t7.csv_records(parent_path, ("record",)))
        actual = list(t7.csv_records(scenario, ("record",)))
        require(sum(row["record"] == "run" for row in parent) == 1, "Parent fixture run row missing/duplicated")
        for row in parent:
            if row["record"] == "run":
                row["scenario"] = item["scenario"]
                row["seed"] = str(seed)
                row["source_sha256"] = item["recipe_sha256"]
        require(actual == parent, "Derived diagnostic changed fields beyond declared run-row scenario/seed provenance")
    anchor = plan.get("baseline_anchor", {})
    require(anchor.get("seed") == 128 and anchor.get("archive_sha256") == ANCHOR_SHA
            and anchor.get("archive") == "evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip",
            "Accepted MATLAB anchor identity mismatch")
    return plan


def verify_tests(root, metadata, source_root):
    options = metadata.get("Options")
    require(isinstance(options, dict) and set(options) == {"RunTests"} and type(options["RunTests"]) is bool,
            "Unsupported diagnostic options")
    requested = options["RunTests"]
    require(metadata.get("TestsRequested") is requested, "Test request flags disagree")
    require(metadata.get("TestResultsFile") == "tests/test_results.csv", "Noncanonical test evidence path")
    require(metadata.get("NativeRequested", False) is False and metadata.get("NativeExecuted", False) is False,
            "This diagnostic runner does not execute the native backend")
    path = root/"tests/test_results.csv"
    if not requested:
        require(not path.exists() and metadata.get("TestsExecuted") is False and metadata.get("TestsPassed") is False
                and all(integer(metadata.get(key), key) == 0 for key in t7.TEST_COUNTS),
                "Unrequested tests contain execution claims")
        return {"status": "not_run", "requested": False, "count": 0}
    rows = list(t7.csv_records(path, ("Name", "Passed", "Failed", "Incomplete", "DurationSeconds")))
    names = t7.portable_test_names(source_root)
    require(len(rows) == len(names) and {row["Name"] for row in rows} == names,
            "Test CSV does not contain every candidate portable test exactly once")
    require(all(sweep.boolean(row["Passed"], "passed") and not sweep.boolean(row["Failed"], "failed")
                and not sweep.boolean(row["Incomplete"], "incomplete")
                and finite(row["DurationSeconds"], "test duration") >= 0 for row in rows), "Requested portable tests did not all pass")
    require(metadata.get("TestsExecuted") is True and metadata.get("TestsPassed") is True
            and integer(metadata.get("TestCount"), "test count") == len(rows)
            and integer(metadata.get("PassedTests"), "passed tests") == len(rows)
            and integer(metadata.get("FailedTests"), "failed tests") == 0
            and integer(metadata.get("IncompleteTests"), "incomplete tests") == 0,
            "Test metadata/CSV counters disagree")
    return {"status": "passed", "requested": True, "count": len(rows),
            "scope": "Candidate portable unit tests; no retained scenario/sweep or campus rerun."}


def verify_reference_snapshot(root, metadata, source_root):
    require(metadata.get("ReferenceFilesStableDuringRun") is True, "Reference stability unproven")
    before = sweep.entries(metadata.get("ReferenceFiles"), "initial reference files")
    after = sweep.entries(metadata.get("ReferenceFilesFinal"), "final reference files")
    require(before == after, "Reference files changed during MATLAB execution")
    trees = ("evidence/tranche-8-ns3-reference", "evidence/tranche-7-ns3-reference", "evidence/tranche-7-benchmark-inputs")
    expected = {f"{tree}/{relative}" for tree in trees for relative in t7.listed_files(source_root/tree)}
    expected.add("evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip")
    require(len(before) == len(expected) and {row.get("path") for row in before} == expected,
            "Reference snapshot membership mismatch")
    for row in before:
        path = sweep.safe_path(source_root, row["path"])
        require(path.stat().st_size == integer(row.get("bytes"), "reference bytes")
                and sweep.digest(path) == sweep.valid_hash(row.get("sha256"), "reference hash"),
                "Reference snapshot hash mismatch")
    return len(before)


def check_compressed(directory, entry):
    path = sweep.safe_path(directory, entry.get("path"))
    require(path.suffix == ".gz" and sweep.digest(path) == entry.get("sha256")
            and path.stat().st_size == integer(entry.get("bytes"), "compressed bytes"), "Compressed artifact identity mismatch")
    expected = integer(entry.get("original_bytes"), "original bytes")
    hasher, size = hashlib.sha256(), 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            size += len(block)
            require(size <= expected, "Compressed artifact exceeds declared original size")
            hasher.update(block)
    require(size == expected and hasher.hexdigest() == entry.get("original_sha256"), "Compressed artifact roundtrip mismatch")


def verify_reference_suite(source_root, plan):
    directory = source_root/"evidence/tranche-8-ns3-reference"
    suite = sweep.json_object(directory/"manifest.json")
    require(suite.get("schema") == "csr-tranche8-link-diagnostic-reference-suite-v1"
            and suite.get("status") == "completed" and suite.get("ns3_source_commit") == PIN
            and suite.get("source_files_stable") is True and suite.get("input_files_stable") is True,
            "ns-3 diagnostic reference suite did not complete with stable pinned inputs")
    require(suite.get("plan_sha256") == sweep.digest(source_root/PLAN), "ns-3 reference plan hash mismatch")
    require(sweep.digest(directory/"build.json") == suite.get("build_manifest_sha256"), "ns-3 build manifest hash mismatch")
    build = sweep.json_object(directory/"build.json")
    require(build.get("schema") == "csr-tranche8-link-diagnostic-reference-build-v1"
            and build.get("ns3_source_commit") == PIN and build.get("source_headers_match_preserved_build") is True
            and build.get("standalone_runner_compiled") is True
            and build.get("observer_compile", {}).get("exit_code") == 0
            and build.get("pristine_compile", {}).get("exit_code") == 0
            and build.get("observer_helper_sha256") == sweep.digest(source_root/"scripts/ns3/tranche8-link-observer.h"),
            "ns-3 build source/helper/compilation identity mismatch")
    listed = sweep.entries(suite.get("cases"), "ns-3 reference cases")
    cases = {row["case_id"]: row for row in plan["cases"]}
    require(len(listed) == 10 and {row.get("case_id") for row in listed} == set(cases), "Missing/duplicated ns-3 diagnostic reference")
    nested_files = set()
    for row in listed:
        case = cases[row["case_id"]]
        require(row.get("status") == "completed" and row.get("manifest") == f"{row['case_id']}/manifest.json",
                "ns-3 reference case status/path mismatch")
        path = sweep.safe_path(directory, row["manifest"])
        require(sweep.digest(path) == row.get("manifest_sha256"), "ns-3 reference case manifest hash mismatch")
        manifest = sweep.json_object(path)
        require(manifest.get("schema") == "csr-tranche7-benchmark-reference-case-v1"
                and manifest.get("status") == "completed" and manifest.get("ns3_source_commit") == PIN
                and manifest.get("case") == case and manifest.get("tranche8_diagnostics") is True,
                "ns-3 reference case provenance mismatch")
        t7.inventory(path.parent, manifest.get("files"), "ns-3 reference case", excluded=("manifest.json",))
        compressed = sweep.entries(manifest.get("compressed_artifacts"), "compressed ns-3 observations")
        compressed += sweep.entries(manifest.get("control_compressed_artifacts"), "compressed ns-3 controls")
        require(len({entry.get("path") for entry in compressed}) == len(compressed), "Duplicate compressed reference artifact")
        for entry in compressed:
            check_compressed(path.parent, entry)
        nested_files.update(f"{row['case_id']}/{name}" for name in t7.listed_files(path.parent))
    t7.inventory(directory, suite.get("files"), "ns-3 reference suite", excluded={"manifest.json", *nested_files})
    return suite


def verify_nonperturbation(root, metadata, source, plan):
    record = sweep.json_object(root/"nonperturbation.json")
    require(record.get("schema") == "csr-link-diagnostic-nonperturbation-v1"
            and record.get("status") == "completed" and record.get("passed") is True
            and record.get("planned_control_count") == 2 and record.get("completed_control_count") == 2
            and metadata.get("NonperturbationPassed") is True, "Observer-disabled controls did not complete")
    expected = {case["case_id"] for case in plan["cases"] if case["seed"] == 128}
    rows = sweep.entries(record.get("cases"), "observer-disabled controls")
    require(len(rows) == 2 and {row.get("case_id") for row in rows} == expected,
            "Observer controls must contain both seed-128 fixtures exactly once")
    for row in rows:
        case_id = row["case_id"]
        token = short_case_id(case_id)
        require(row.get("observer_on_directory") == f"b/{token}/raw"
                and row.get("observer_off_directory") == f"c/{token}/raw"
                and row.get("statistics_equal") is True and row.get("config_equal") is True
                and row.get("passed") is True, "Observer control identity/result mismatch")
        on, off = (sweep.safe_path(root, row[key]) for key in ("observer_on_directory", "observer_off_directory"))
        raw = sweep.json_object(off/"case_manifest.json")
        enabled_raw = sweep.json_object(on/"case_manifest.json")
        require(raw.get("schema") == "csr-matlab-research-case-v1" and raw.get("status") == "completed"
                and raw.get("execution_completed") is True and raw.get("structural_checks_passed") is True
                and raw.get("source_files_stable") is True and raw.get("ns3_source_commit") == PIN
                and sweep.snapshot(raw.get("source_files"), "control source") == source,
                "Observer-disabled raw case source/completion mismatch")
        require(all(raw.get(field) == enabled_raw.get(field) for field in
                    ("scenario", "scenario_sha256", "duration_s", "seed", "flow_limit", "run_options",
                     "application_profile", "mac_profile", "hop_security_profile")),
                "Observer-disabled raw case identity differs from enabled case")
        t7.inventory(off, raw.get("files"), "observer-disabled raw case", excluded=("case_manifest.json",),
                     local=raw.get("local_files", []))
        left, right = sweep.json_object(on/"summary.json"), sweep.json_object(off/"summary.json")
        require(left["Statistics"] == right["Statistics"] and left["Config"] == right["Config"],
                "Observer altered statistics or configuration")
        require("LinkDiagnostics" not in right and not (off/"link_decisions.csv").exists()
                and not (off/"actual_feedback.csv").exists(), "Disabled control contains enabled observer outputs")
        files = sweep.entries(row.get("compared_files"), "nonperturbation comparisons")
        names = {*UNCHANGED_CSV, "scenario.csv"}
        require(len(files) == len(names) and {entry.get("path") for entry in files} == names,
                "Nonperturbation comparison omitted unchanged evidence")
        for entry in files:
            require(entry.get("equal") is True and sweep.digest(on/entry["path"]) == entry.get("observer_on_sha256")
                    and sweep.digest(off/entry["path"]) == entry.get("observer_off_sha256")
                    and entry["observer_on_sha256"] == entry["observer_off_sha256"],
                    "Observer on/off evidence differs or comparison hashes are unbound")
    return record


def rate_bps(key):
    intervals = {8: .000510, 16: .000254, 32: .000126, 64: .000062, 128: .000030,
                 500: 4/500000, 1000: 4/1000000}
    key = integer(key, "rate key")
    require(key in intervals, "Unsupported feedback rate key")
    return 4/intervals[key]


def check_rate(row, key, bps):
    require(math.isclose(finite(row[bps], bps), rate_bps(row[key]), rel_tol=2e-12, abs_tol=1e-7),
            "Feedback operational bps differs from the four-bit interval rate")


def distribution(rows, kind, rate, power):
    counts = Counter((row[kind], integer(row[rate], rate), finite(row[power], power)) for row in rows)
    return [{"frame_type": k, "rate_key_kbps": r, "power_dbm": p, "count": n}
            for (k, r, p), n in sorted(counts.items())]


def feedback_forms(selected, actual, *, ns3=False):
    window = "has_ack_window" if ns3 else "HasAckWindow"
    kind = "frame_type" if ns3 else "FrameKind"
    rate = "selected_rate_key_kbps" if ns3 else "SelectedRateKeyKbps"
    power = "selected_power_dbm" if ns3 else "SelectedPowerDbm"
    actual_rate = "actual_rate_key_kbps" if ns3 else "RateKeyKbps"
    actual_power = "actual_power_dbm" if ns3 else "TxPowerDbm"
    time = "time_s" if ns3 else "TimeSeconds"
    result = []
    for flag, label in ((False, "exact_sequence"), (True, "cumulative_window")):
        decisions = [row for row in selected if sweep.boolean(row[window], "ACK window") is flag]
        transmissions = [row for row in actual if sweep.boolean(row[window], "ACK window") is flag]
        changed = [row for row in transmissions if row[actual_rate] != row[rate]
                   or finite(row[actual_power], "actual power") != finite(row[power], "selected power")]
        result.append({"feedback_form": label, "selection_count": len(decisions), "ota_feedback_member_count": len(transmissions),
                       "selection_distribution": distribution(decisions, kind, rate, power),
                       "ota_member_distribution": distribution(transmissions, kind, actual_rate, actual_power),
                       "actual_vs_selected_rate_change_count": sum(row[actual_rate] != row[rate] for row in transmissions),
                       "actual_vs_selected_power_change_count": sum(finite(row[actual_power], "actual power") != finite(row[power], "selected power") for row in transmissions),
                       "first_radio_override_time_s": min(finite(row[time], "time") for row in changed) if changed else None,
                       "last_radio_override_time_s": max(finite(row[time], "time") for row in changed) if changed else None})
    return result


def verify_matlab_feedback(directory, case):
    raw = directory/"raw"
    summary = sweep.json_object(raw/"summary.json")
    observed = summary.get("LinkDiagnostics", {})
    config = summary["Config"]
    require(all(config.get("Trace", {}).get(field) == case["trace_limits"][key] for field, key in
                (("MaxRecords", "protocol"), ("MaxPhyRecords", "phy"), ("MaxApplicationAdmissionRecords", "admission")))
            and config.get("MaxEvents") == 12000000, "Actual diagnostic trace/event limits differ from plan")
    manifest = sweep.json_object(directory/"benchmark_manifest.json")
    require(manifest.get("observer_enabled") is True and manifest.get("observer_diagnostics") == observed
            and manifest.get("base_case_id") == case["base_case_id"], "MATLAB observer case/summary binding mismatch")
    require(observed.get("SchemaVersion") == "csr-matlab-link-diagnostics-v1" and observed.get("Enabled") is True
            and observed.get("Complete") is True and observed.get("Passive") is True
            and observed.get("MaxRecords") == case["trace_limits"]["link_decisions"]
            and observed.get("AckTransmissionsPerRetainedFrame") == summary["Config"]["Mac"]["AckTransmissions"],
            "MATLAB feedback observer schema/completion/capacity mismatch")
    for field in ("OmittedDecisionRecords", "OmittedActualFeedbackRecords", "UnmatchedActualFeedbackRecords",
                  "CorrelationErrors", "ScheduledEvents", "RandomDraws"):
        require(integer(observed.get(field), field) == 0, f"Incomplete or perturbing feedback observer: {field}")
    require(observed.get("LinkControlApplied") is False and observed.get("PeerS0Available") is False
            and observed.get("HopFailureCountAvailable") is False, "Observer invents unimplemented MATLAB feedback link-control inputs")
    rows = list(t7.csv_records(raw/"link_decisions.csv", ("DecisionId", "TimeSeconds", "Stage", "NodeId", "PeerId", "FrameKind",
                  "Sequence", "HasAckWindow", "AckBitmap", "DackBitmap", "SelectedRateKeyKbps", "SelectedRateBps",
                  "SelectedPowerDbm", "QueueAccepted", "QueueDisposition", "RetainedDecisionId", "InputContextAvailable")))
    actual = list(t7.csv_records(raw/"actual_feedback.csv", ("ObservationId", "DecisionId", "DecisionMatched", "TimeSeconds",
                  "Stage", "AggregateId", "SegmentIndex", "SegmentCount", "NodeId", "PeerId", "FrameKind", "Sequence",
                  "HasAckWindow", "AckBitmap", "DackBitmap", "SelectedRateKeyKbps", "SelectedRateBps", "SelectedPowerDbm",
                  "RateKeyKbps", "RateBps", "TxPowerDbm")))
    require(len(rows) == integer(observed.get("DecisionCount"), "decision count")
            and len(actual) == integer(observed.get("ActualFeedbackCount"), "feedback count"), "Observer trace coverage mismatch")
    decisions, previous = {}, -1.0
    nodes = {integer(row["Id"], "node"): row for row in sweep.entries(summary["Config"]["Nodes"], "nodes")}
    identity = ("NodeId", "PeerId", "FrameKind", "Sequence", "HasAckWindow", "AckBitmap", "DackBitmap")
    for index, row in enumerate(rows, 1):
        key, when = integer(row["DecisionId"], "decision"), finite(row["TimeSeconds"], "decision time")
        require(key == index and previous <= when <= case["duration_s"] and when >= 0
                and row["Stage"] == "feedback_mac_admission" and row["FrameKind"] in ("ACK", "DACK"),
                "Invalid decision identity/time/stage")
        previous = when
        node = integer(row["NodeId"], "node")
        require(node in nodes and integer(row["PeerId"], "peer") in nodes, "Feedback endpoint outside configured topology")
        for bitmap in ("AckBitmap", "DackBitmap"):
            require(integer(row[bitmap], bitmap) <= 2**64-1, "Feedback bitmap outside uint64 range")
        require(metrics.optional_number(row.get("PeerS0Dbm"), "peer S0") is None
                and metrics.optional_number(row.get("HopFailureCount"), "HOP failures") is None
                and not sweep.boolean(row.get("LinkControlApplied"), "link control"), "Unavailable MATLAB input was fabricated")
        configured = finite(nodes[node]["RadioProfile"]["TxPowerDbm"], "configured node power")
        require(finite(row.get("ConfiguredNodePowerDbm"), "configured power") == configured, "Observed configured node power mismatch")
        if sweep.boolean(row.get("PowerDefaulted"), "default power"):
            require(finite(row["SelectedPowerDbm"], "selected power") == configured, "Default feedback power differs from node setting")
        check_rate(row, "SelectedRateKeyKbps", "SelectedRateBps")
        if sweep.boolean(row["InputContextAvailable"], "input context"):
            require(row.get("InputFrameKind") in ("DATA", "CONTROL"), "Unknown feedback input frame")
            check_rate(row, "InputRateKeyKbps", "InputRateBps")
            require(integer(row["InputRateKeyKbps"], "incoming rate") == integer(row["SelectedRateKeyKbps"], "selected rate"),
                    "MATLAB feedback does not preserve received frame rate")
        else:
            for field in ("InputRateKeyKbps", "InputRateBps", "InputPowerDbm", "InputReceivedPowerDbm", "PathlossDb"):
                require(metrics.optional_number(row.get(field), field) is None, "Unavailable incoming context was fabricated")
        retained = integer(row["RetainedDecisionId"], "retained decision")
        disposition, accepted = row["QueueDisposition"], sweep.boolean(row["QueueAccepted"], "queue accepted")
        if disposition in ("enqueued", "replaced"):
            require(accepted and retained == key, "New/replaced feedback has invalid retained decision")
        elif disposition == "duplicate_retained":
            require(accepted and retained in decisions and not sweep.boolean(row["HasAckWindow"], "ACK window")
                    and all(row[field] == decisions[retained][field] for field in ("NodeId", "PeerId", "Sequence")),
                    "Duplicate feedback does not bind the original retained peer/sequence")
        else:
            require(disposition == "rejected" and not accepted and retained == 0, "Unknown/rejected feedback queue disposition")
        decisions[key] = row
    transmitted, positions, previous = Counter(), set(), -1.0
    tx_events = {(finite(row["TimeSeconds"], "tx time"), integer(row["NodeId"], "node"), integer(row["PacketId"], "aggregate"))
                 for row in t7.csv_records(raw/"protocol_trace.csv", ("Event", "TimeSeconds", "NodeId", "PacketId"))
                 if row["Event"] == "tx_start"}
    for index, row in enumerate(actual, 1):
        key, when = integer(row["DecisionId"], "decision"), finite(row["TimeSeconds"], "feedback time")
        require(integer(row["ObservationId"], "observation") == index and previous <= when <= case["duration_s"]
                and row["Stage"] == "ota_feedback" and sweep.boolean(row["DecisionMatched"], "decision matched")
                and key in decisions, "Invalid/unmatched actual feedback identity/time")
        previous = when
        decision = decisions[key]
        require(decision["QueueDisposition"] in ("enqueued", "replaced")
                and when >= finite(decision["TimeSeconds"], "decision time")
                and all(row[field] == decision[field] for field in (*identity, "SelectedRateKeyKbps", "SelectedPowerDbm")),
                "Actual feedback differs from its retained decision")
        check_rate(row, "SelectedRateKeyKbps", "SelectedRateBps")
        check_rate(row, "RateKeyKbps", "RateBps")
        finite(row["TxPowerDbm"], "actual power")
        aggregate, segment, count = (integer(row[field], field) for field in ("AggregateId", "SegmentIndex", "SegmentCount"))
        require(aggregate > 0 and 1 <= segment <= count <= 16 and (aggregate, segment) not in positions,
                "Duplicate/invalid feedback aggregate member")
        positions.add((aggregate, segment))
        require((when, integer(row["NodeId"], "node"), aggregate) in tx_events,
                "Actual feedback has no original protocol transmission event")
        transmitted[key] += 1
        require(transmitted[key] <= observed["AckTransmissionsPerRetainedFrame"], "Feedback exceeds retained-frame repeat limit")
    hop = list(t7.csv_records(raw/"hop_nodes.csv", ("NodeId", "AckGenerated", "DackGenerated", "FeedbackQueueDrops")))
    mac = list(t7.csv_records(raw/"mac_nodes.csv", ("NodeId", "AckTransmissions", "AckEnqueued", "AckQueueDrops", "AckReplacements")))
    require({integer(row["NodeId"], "node") for row in hop} == set(nodes) and len(hop) == len(nodes)
            and {integer(row["NodeId"], "node") for row in mac} == set(nodes) and len(mac) == len(nodes), "Feedback node counters incomplete")
    for node in nodes:
        selected, sent = [row for row in rows if int(row["NodeId"]) == node], [row for row in actual if int(row["NodeId"]) == node]
        h, m = next(row for row in hop if int(row["NodeId"]) == node), next(row for row in mac if int(row["NodeId"]) == node)
        require(len(selected) == integer(h["AckGenerated"], "ACK generated")+integer(h["DackGenerated"], "DACK generated")
                and len(sent) == integer(m["AckTransmissions"], "ACK transmissions"), "Feedback trace differs from original per-node counters")
        require(sum(row["FrameKind"] == "DACK" for row in selected) == integer(h["DackGenerated"], "DACK generated"), "DACK decision coverage mismatch")
        for disposition, field in (("enqueued", "AckEnqueued"), ("replaced", "AckReplacements"), ("rejected", "AckQueueDrops")):
            require(sum(row["QueueDisposition"] == disposition for row in selected) == integer(m[field], field), "Feedback queue disposition counter mismatch")
        require(sum(row["QueueDisposition"] == "rejected" for row in selected) == integer(h["FeedbackQueueDrops"], "feedback drops"), "HOP feedback drop count mismatch")
    return {"decision_count": len(rows), "actual_feedback_member_count": len(actual),
            "distinct_decisions_transmitted": len(transmitted), "decisions_not_transmitted": len(rows)-len(transmitted),
            "queue_dispositions": dict(Counter(row["QueueDisposition"] for row in rows)),
            "selection_distribution": distribution(rows, "FrameKind", "SelectedRateKeyKbps", "SelectedPowerDbm"),
            "ota_member_distribution": distribution(actual, "FrameKind", "RateKeyKbps", "TxPowerDbm"),
            "actual_vs_selected_rate_change_count": sum(row["RateKeyKbps"] != row["SelectedRateKeyKbps"] for row in actual),
            "actual_vs_selected_power_change_count": sum(finite(row["TxPowerDbm"], "power") != finite(row["SelectedPowerDbm"], "selected power") for row in actual),
            "incoming_context_missing_count": sum(not sweep.boolean(row["InputContextAvailable"], "context") for row in rows),
            "feedback_forms": feedback_forms(rows, actual),
            "peer_s0_dbm": None, "hop_failure_count": None,
            "scope": "Selections are MAC-admission observations; actual rows count transmitted members including repeats. Replaced/rejected/retained-duplicate decisions may never transmit."}


def verify_ns3_control_comparisons(directory, manifest, case):
    compressed = sweep.entries(manifest.get("compressed_artifacts"), "ns-3 compressed data")
    compressed += sweep.entries(manifest.get("control_compressed_artifacts"), "ns-3 compressed controls")
    original = {row["original_name"]: row for row in compressed}
    require(len(original) == len(compressed), "Duplicate original compressed artifact name")

    def original_hash(name):
        path = sweep.safe_path(directory, name)
        if path.is_file():
            return sweep.digest(path)
        require(name in original, "Compared ns-3 control artifact was not preserved")
        check_compressed(directory, original[name])
        return original[name]["original_sha256"]

    def compare_files(record, first_prefix, second_prefix):
        require(record.get("status") == "passed", "ns-3 observer control did not pass")
        rows = sweep.entries(record.get("compared_files"), "ns-3 control comparisons")
        names = {"ns3-trace.csv", "app-admission-diagnostics.csv"}
        require(len(rows) == 2 and {row.get("name") for row in rows} == names, "ns-3 control comparison omitted evidence")
        for row in rows:
            require(row.get("first_path") == first_prefix+row["name"]
                    and row.get("second_path") == second_prefix+row["name"] and row.get("equal") is True
                    and row.get("first_sha256") == row.get("second_sha256")
                    and original_hash(row["first_path"]) == row.get("first_sha256")
                    and original_hash(row["second_path"]) == row.get("second_sha256"),
                    "ns-3 control comparison is not bound to preserved original bytes")

    record = manifest.get("nonperturbation", {})
    compare_files(record, "", "observer-off-")
    if case["seed"] == 128:
        compare_files(record.get("source_runner_vs_observer_off", {}), "pristine-", "observer-off-")
        anchor = manifest.get("baseline_anchor", {})
        reference = directory.parents[1]/"tranche-7-ns3-reference"/case["base_case_id"]
        require(anchor.get("status") == "passed" and anchor.get("source_commit") == PIN
                and anchor.get("reference_manifest_sha256") == sweep.digest(reference/"manifest.json")
                and anchor.get("app_trace_byte_exact") is True, "ns-3 seed-128 T7 anchor identity mismatch")
        old = sweep.json_object(reference/"manifest.json")
        descriptors = [row for row in old["compressed_artifacts"] if row["original_name"] == "ns3-trace.csv"]
        require(len(descriptors) == 1 and descriptors[0]["original_sha256"] == original_hash("ns3-trace.csv"),
                "ns-3 seed-128 application event trace differs from T7")
        for name, ignored in (("app-admission-diagnostics.csv", {"scenario"}),
                              ("ns3-aggregates.csv", {"scenario", "source_file_sha256"})):
            normalize = lambda path: [{key: value for key, value in row.items() if key not in ignored}
                                      for row in t7.csv_records(path)]
            require(normalize(reference/name) == normalize(directory/name), "ns-3 T7 anchor observation values differ")
    else:
        require(manifest.get("baseline_anchor") is None, "Non-anchor seed incorrectly claims T7 comparison")
    return {"observer_on_off_application_evidence_equal": True,
            "pristine_runner_and_t7_anchor_checked": case["seed"] == 128,
            "scope": "Complete application trace and admission records; no claim that all ns-3 internal state was separately serialized."}


def check_ns3_selection(row):
    """Check the pinned HOP rate/power rule against observed inputs, without RNG."""
    low, high = integer(row["min_rate_key_kbps"], "minimum rate"), integer(row["max_rate_key_kbps"], "maximum rate")
    pmin, pmax = finite(row["min_power_dbm"], "minimum power"), finite(row["max_power_dbm"], "maximum power")
    require((low, high, pmin, pmax, finite(row["link_margin_db"], "margin")) == (8, 128, -36, 33, 12),
            "Observed HOP radio limits differ from diagnostic profile")
    known = sweep.boolean(row["peer_known"], "peer known")
    path = metrics.optional_number(row["path_loss_db"], "path loss")
    s0 = metrics.optional_number(row["peer_s0_dbm"], "peer S0")
    failures = metrics.optional_number(row["hop_failure_count"], "HOP failures")
    if not known:
        require(s0 is None and path is None and failures is None, "Unknown ns-3 peer has fabricated link inputs")
    if known and path is not None:
        remote = finite(row["advertised_rx_power_dbm"], "fallback S0") if s0 is None else s0
        margin = pmax-(remote+path)
        selected = next((rate for threshold, rate in ((23, 1000), (20, 500), (12, 128), (9, 64), (6, 32), (3, 16))
                         if margin >= threshold), 8 if margin > 0 else low)
        selected = min(high, max(low, selected))
        offset = {8: 0, 16: 3, 32: 6, 64: 9, 128: 12, 500: 20, 1000: 23}[selected]
        power = math.ceil(min(pmax, max(pmin, remote+path+offset)))
    else:
        selected, power = low, pmax
    require(integer(row["selected_rate_key_kbps"], "selected rate") == selected
            and finite(row["selected_power_dbm"], "selected power") == power,
            "ns-3 feedback choice disagrees with observed source HOP link-control inputs")


def verify_ns3_feedback(directory, case):
    manifest = sweep.json_object(directory/"manifest.json")
    reported = manifest.get("observer_diagnostics", {})
    require(reported == sweep.json_object(directory/"feedback-summary.json")
            and reported.get("schema") == "csr-ns3-feedback-observation-summary-v1"
            and reported.get("status") == "passed" and reported.get("all_ota_members_linked_to_selection") is True,
            "ns-3 feedback summary binding/completion mismatch")
    rows = list(metrics.csv_rows(directory/"ns3-link-decisions.csv.gz", ("schema", "stage", "time_s", "decision_id",
              "packet_uid", "node_id", "peer_id", "frame_type", "hop_sequence", "has_ack_window", "ack_bitmap", "dack_bitmap",
              "selected_rate_key_kbps", "selected_rate_bps", "selected_power_dbm", "peer_known", "peer_s0_dbm", "path_loss_db",
              "hop_failure_count", "incoming_rate_key_kbps", "incoming_rate_bps", "incoming_power_dbm", "actual_rate_key_kbps",
              "actual_rate_bps", "actual_power_dbm", "aggregate_id", "segment_index", "segment_count")))
    selected, contexts, actual, positions, previous = {}, {}, [], set(), -1.0
    identity = ("node_id", "peer_id", "frame_type", "hop_sequence", "packet_uid", "has_ack_window", "ack_bitmap", "dack_bitmap",
                "selected_rate_key_kbps", "selected_power_dbm", "peer_known", "peer_s0_dbm", "path_loss_db", "hop_failure_count")
    for row in rows:
        key, when = integer(row["decision_id"], "decision ID"), finite(row["time_s"], "feedback time")
        require(row["schema"] == "csr-ns3-feedback-observation-v1" and row["frame_type"] in ("ACK", "DACK")
                and previous <= when <= case["duration_s"] and when >= 0, "Invalid ns-3 feedback schema/type/time")
        previous = when
        for bitmap in ("ack_bitmap", "dack_bitmap"):
            require(integer(row[bitmap], bitmap) <= 2**64-1, "ns-3 feedback bitmap outside uint64 range")
        check_rate(row, "selected_rate_key_kbps", "selected_rate_bps")
        stage = row["stage"]
        if stage == "feedback_selection":
            require(key == len(selected)+1 and key not in selected, "Missing/duplicate ns-3 selection identity")
            check_ns3_selection(row)
            selected[key] = row
            require(all(metrics.optional_number(row[field], field) is None for field in
                        ("incoming_rate_key_kbps", "incoming_rate_bps", "incoming_power_dbm")),
                    "Selection stage claims incoming context before observation")
        else:
            require(key in selected and all(row[field] == selected[key][field] for field in identity),
                    "ns-3 feedback observation has no unchanged selection identity")
            if stage == "ack_response_context":
                require(key not in contexts, "Duplicate ns-3 incoming DATA context")
                check_rate(row, "incoming_rate_key_kbps", "incoming_rate_bps")
                metrics.optional_number(row["incoming_power_dbm"], "incoming power")
                contexts[key] = row
            else:
                require(stage == "ota_segment", "Unknown ns-3 feedback observation stage")
                check_rate(row, "actual_rate_key_kbps", "actual_rate_bps")
                finite(row["actual_power_dbm"], "actual power")
                aggregate, segment, count = (integer(row[field], field) for field in ("aggregate_id", "segment_index", "segment_count"))
                require(aggregate > 0 and 1 <= segment <= count <= 16 and (aggregate, segment) not in positions,
                        "Duplicate/invalid ns-3 OTA feedback member")
                positions.add((aggregate, segment))
                actual.append(row)
    computed = {"rows": len(rows), "selection_count": len(selected), "ordinary_data_context_count": len(contexts),
                "ota_feedback_member_count": len(actual), "ota_aggregates_containing_feedback": len({row["aggregate_id"] for row in actual}),
                "distinct_decisions_transmitted": len({row["decision_id"] for row in actual}),
                "actual_vs_selected_rate_change_count": sum(row["actual_rate_key_kbps"] != row["selected_rate_key_kbps"] for row in actual),
                "actual_vs_selected_power_change_count": sum(finite(row["actual_power_dbm"], "power") != finite(row["selected_power_dbm"], "selected power") for row in actual),
                "selection_distribution": distribution(list(selected.values()), "frame_type", "selected_rate_key_kbps", "selected_power_dbm"),
                "ota_member_distribution": distribution(actual, "frame_type", "actual_rate_key_kbps", "actual_power_dbm"),
                "incoming_vs_selected_rate_difference_count": sum(row["incoming_rate_key_kbps"] != row["selected_rate_key_kbps"] for row in contexts.values()),
                "incoming_vs_selected_power_difference_count": sum(metrics.optional_number(row["incoming_power_dbm"], "incoming power") is not None
                    and finite(row["incoming_power_dbm"], "incoming power") != finite(row["selected_power_dbm"], "selected power") for row in contexts.values())}
    require(all(reported.get(field) == value for field, value in computed.items()), "ns-3 feedback summary disagrees with complete observer trace")
    computed["incoming_context_missing_count"] = len(selected)-len(contexts)
    computed["feedback_forms"] = feedback_forms(list(selected.values()), actual, ns3=True)
    computed["nonperturbation"] = verify_ns3_control_comparisons(directory, manifest, case)
    computed["scope"] = reported.get("scope")
    return computed


def equivalent_csv(left, right, label):
    """Compare exported observations across newline/numeric formatting variants."""
    readers = [csv.DictReader(stream, strict=True) for stream in (left, right)]
    require(readers[0].fieldnames and readers[0].fieldnames == readers[1].fieldnames,
            f"{label}: CSV columns differ")
    require(len(set(readers[0].fieldnames)) == len(readers[0].fieldnames), f"{label}: duplicate CSV columns")
    count = 0
    for a, b in itertools.zip_longest(*readers):
        require(a is not None and b is not None and None not in a and None not in b
                and None not in a.values() and None not in b.values(), f"{label}: row count/malformed record mismatch")
        count += 1
        for key in a:
            if a[key] == b[key]:
                continue
            try:
                # Compare integral text exactly even if one exporter writes
                # uint64-like values with a .0 or exponent suffix. Binary64
                # would collapse neighboring large identities/bitmaps.
                da, db = Decimal(a[key]), Decimal(b[key])
                if da.is_finite() and db.is_finite() and (
                        (da == da.to_integral_value() and db == db.to_integral_value())
                        or max(abs(da), abs(db)) >= 2**53):
                    require(da == db, f"{label}: integer/large numeric {key} differs")
                    continue
                x, y = float(a[key]), float(b[key])
                require((math.isnan(x) and math.isnan(y)) or
                        (math.isfinite(x) and math.isfinite(y) and math.isclose(x, y, rel_tol=2e-12, abs_tol=1e-9)),
                        f"{label}: numeric {key} differs")
            except (TypeError, ValueError, InvalidOperation) as failure:
                raise ValueError(f"{label}: {key} differs at record {count}") from failure
    return count


def verify_t7_anchor(root, source_root, plan):
    archive = source_root/plan["baseline_anchor"]["archive"]
    require(sweep.digest(archive) == ANCHOR_SHA, "Accepted T7 archive hash mismatch")
    results = []
    with zipfile.ZipFile(archive) as bundle:
        for case in plan["cases"]:
            if case["seed"] != 128:
                continue
            new = root/"b"/short_case_id(case["case_id"])/"raw"
            prefix = f"benchmarks/{case['base_case_id']}/raw/"
            old_stats = json.loads(bundle.read(prefix+"summary.json"))["Statistics"]
            new_stats = sweep.json_object(new/"summary.json")["Statistics"]
            require(new_stats == old_stats, "Seed-128 statistics differ from accepted MATLAB T7 anchor")
            files = []
            for name in UNCHANGED_CSV:
                with bundle.open(prefix+name) as compressed, (new/name).open(encoding="utf-8-sig", newline="") as actual:
                    rows = equivalent_csv(io.TextIOWrapper(compressed, encoding="utf-8-sig", newline=""), actual,
                                          f"T7 anchor {case['case_id']}/{name}")
                files.append({"path": name, "semantic_records": rows})
            results.append({"case_id": case["case_id"], "base_case_id": case["base_case_id"], "passed": True,
                            "statistics_equal": True, "files": files})
    return {"archive_sha256": ANCHOR_SHA, "cases": results, "passed": len(results) == 2,
            "comparison": "All unchanged protocol/PHY/node/admission CSV observations and complete Statistics; only text numeric/newline formatting may differ."}


def verify_return(root, source_root):
    root, source_root = Path(root).resolve(), Path(source_root).resolve()
    metadata = sweep.json_object(root/"validation_metadata.json")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 8, "Unsupported Tranche 8 schema")
    require(metadata.get("MatlabBaseCommit") == BASE and metadata.get("ValidatedTranche7CodeCommit") == T7_CODE,
            "Tranche 8 accepted baseline identity mismatch")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB"
            and isinstance(runtime.get("Version"), str) and runtime["Version"]
            and isinstance(runtime.get("Release"), str) and runtime["Release"], "Missing actual MATLAB runtime/release record")
    require(metadata.get("DiagnosticPlan") == "diagnostic_plan.json" and metadata.get("NonperturbationFile") == "nonperturbation.json"
            and metadata.get("CrossSimulatorComparisonExecuted") is False and metadata.get("NumericalParityEstablished") is False,
            "Diagnostic metadata misstates artifact locations or comparison scope")
    source = t7.candidate_snapshot(source_root)
    t7.source_binding(metadata, source, runtime)
    t7.inventory(root, metadata.get("Artifacts"), "outer diagnostic artifacts",
                 excluded=("validation_metadata.json", "tranche8_evidence.zip"), local=metadata.get("LocalArtifacts", []))
    source_hash = sweep.digest(root/"source_snapshot.json")
    require(metadata.get("SourceSnapshotSHA256") == source_hash
            and sweep.snapshot(json.loads((root/"source_snapshot.json").read_text()), "source snapshot") == source,
            "Source snapshot file binding mismatch")
    plan = verify_plan(source_root)
    require(metadata.get("DiagnosticPlanSHA256") == sweep.digest(source_root/PLAN)
            and sweep.digest(root/"diagnostic_plan.json") == sweep.digest(source_root/PLAN), "Returned diagnostic plan mismatch")
    reference_count = verify_reference_snapshot(root, metadata, source_root)
    verify_reference_suite(source_root, plan)
    tests = verify_tests(root, metadata, source_root)
    cases = {case["case_id"]: case for case in plan["cases"]}
    completed = sweep.entries(metadata.get("Cases"), "returned diagnostic cases")
    require(len(completed) == 10 and {row.get("CaseId") for row in completed} == set(cases)
            and integer(metadata.get("PlannedCaseCount"), "planned cases") == 10
            and integer(metadata.get("CompletedCaseCount"), "completed cases") == 10,
            "Missing/duplicated instrumented diagnostic cases")
    observations, metric_rows, paths = [], [], []
    for item in completed:
        case = cases[item["CaseId"]]
        directory = sweep.safe_path(root, item["Directory"])
        reference = sweep.safe_path(source_root, case["reference_directory"])
        require(sweep.json_object(directory/"benchmark_manifest.json").get("storage_key") == short_case_id(case["case_id"]),
                "Diagnostic storage key differs from strict short-path mapping")
        observed = t7.verify_case(root, item, case, source, runtime, source_hash,
                                  expected_directory=f"b/{short_case_id(case['case_id'])}")
        # Validates canonical generator/MAC/atomic envelope and both aggregate
        # provenance chains, including complete compressed ns-3 source bytes.
        compare.case_input_manifest(directory, reference)
        observed["base_case_id"], observed["seed"] = case["base_case_id"], case["seed"]
        observed["matlab_applications"] = metrics.matlab_applications(directory, case)
        observed["ns3_applications"] = metrics.ns3_applications(reference, case)
        observed["matlab_feedback"] = verify_matlab_feedback(directory, case)
        observed["ns3_feedback"] = verify_ns3_feedback(reference, case)
        metric_rows.extend([observed["matlab_applications"], observed["ns3_applications"]])
        observations.append(observed)
        paths.append((directory, reference))
    nonperturbation = verify_nonperturbation(root, metadata, source, plan)
    anchor = verify_t7_anchor(root, source_root, plan)
    rows = list(t7.csv_records(root/"benchmark_summary.csv", ("CaseId", "BaseCaseId", *t7.COUNTS, "Attempts", "AdmissionBlocked")))
    require(len(rows) == 10 and {row["CaseId"] for row in rows} == set(cases), "Diagnostic summary membership mismatch")
    for row in rows:
        observed = next(item for item in observations if item["case_id"] == row["CaseId"])
        require(row["BaseCaseId"] == observed["base_case_id"]
                and t7.count_balance(row, row["CaseId"]) == observed["counts"]
                and integer(row["Attempts"], "attempts") == observed["admission"]["attempts"]
                and integer(row["AdmissionBlocked"], "blocked") == observed["admission"]["blocked"],
                "Diagnostic summary differs from reconstructed application counts")
    full = tests["status"] == "passed" and nonperturbation["passed"] and anchor["passed"]
    report = {"schema": "csr-matlab-tranche-8-return-review-v1", "status": "structural_review_completed",
              "evidence_integrity_verified": True, "default_structural_gate_completed": full,
              "diagnostic_only": not full, "matlab_runtime": runtime, "tests": tests,
              "source_files_verified": len(source), "source_snapshot_sha256": source_hash,
              "metadata_sha256": sweep.digest(root/"validation_metadata.json"),
              "reference_files_verified": reference_count, "cases": observations,
              "nonperturbation": nonperturbation, "accepted_tranche7_anchor": anchor,
              "multiseed": metrics.multiseed_summary(metric_rows), "acceptance_established": False,
              "numerical_parity_established": False, "population_equivalence_established": False,
              "limitations": ["Recorded MATLAB execution is owner-returned evidence; this Python reviewer does not run MATLAB.",
                              "No campus, retained sweep, native-backend, or OPNET execution is part of this diagnostic gate.",
                              "Finite-stop pending work remains reported; ns-3 unmatched sends are not classified as drops or pending work.",
                              "Packet identities and pseudorandom streams are simulator-specific; seed pairing is a declared experiment index.",
                              "ACK/DACK observer correlation proves recorded local choices and transmissions, not protocol equivalence."]}
    return report, paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output, created = args.output.resolve(), False
    try:
        require(not output.exists(), "Review output already exists")
        require(not output.is_relative_to(args.evidence.resolve()) and not output.is_relative_to(args.source_root.resolve()),
                "Review output must be outside evidence and candidate")
        output.mkdir(parents=True, exist_ok=False)
        created = True
        with t7.evidence_directory(args.evidence) as root:
            report, cases = verify_return(root, args.source_root)
            for case, reference in cases:
                compare.compare_case(case, reference, output/case.name)
            if args.evidence.is_file():
                report["uploaded_zip_sha256"] = sweep.digest(args.evidence)
            (output/"review.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
            flat = [observation[key] for observation in report["cases"] for key in ("matlab_applications", "ns3_applications")]
            fields = [name for name in flat[0] if name not in ("flows", "drop_reasons")]
            sweep.write_csv(output/"per_seed_metrics.csv", fields, [{name: row[name] for name in fields} for row in flat])
        print(f"Reviewed 10 instrumented cases and 2 controls; default structural gate={report['default_structural_gate_completed']}. Acceptance requires review.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error, zipfile.BadZipFile) as failure:
        if created:
            failure_report = {"schema": "csr-matlab-tranche-8-return-review-v1", "status": "structural_review_failed",
                              "evidence_integrity_verified": False, "default_structural_gate_completed": False,
                              "acceptance_established": False, "numerical_parity_established": False,
                              "error_type": type(failure).__name__, "error": str(failure)}
            if args.evidence.is_file():
                failure_report["uploaded_zip_sha256"] = sweep.digest(args.evidence)
            (output/"review-failure.json").write_text(json.dumps(failure_report, indent=2)+"\n", encoding="utf-8")
        print(f"Tranche 8 review failed: {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
