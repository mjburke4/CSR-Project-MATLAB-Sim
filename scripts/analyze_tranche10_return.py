#!/usr/bin/env python3
"""Review owner-returned Tranche 10 evidence without executing MATLAB.

The default structural gate requires portable tests, three native-referenced
contract families, 29 retained scenarios, 18 sweeps, six diagnostics, two
observer controls and campus6000. Numerical differences never fail an invented
tolerance or establish acceptance automatically. Use the exact candidate tree.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import analyze_tranche8_return as t8
import analyze_tranche9_return as t9
import compare_benchmark_aggregates as compare
import tranche8_metrics as metrics
import tranche9_metrics as service
import tranche10_metrics as timing

ROOT = Path(__file__).resolve().parents[1]
PIN = t7.PIN
BASE = "386f669f369f90b18d1d553db85b017b0ca8c77c"
T9_CODE = "99fff0381fe9621ccd76fbdce41eac9aba5a9469"
SCHEMA = "csr-matlab-tranche-10-validation-v1"
REVIEW_SCHEMA = "csr-matlab-tranche-10-return-review-v1"
PLAN = "scenarios/contention_timing/plan.json"
DIAGNOSTIC_SHA = "372db92a385781d9854a096149fd419b90ae79823125b79269506bd9877e0116"
NATIVE_BUILD = "evidence/tranche-10-native-build.json"
BUILD_ROOT = "evidence/tranche-10-native-build"
SOURCE_RECHECK = "evidence/tranche-10-source-recheck.json"
CONTRACTS = [
    {"kind": "mac", "directory": "evidence/tranche-10-contract-reference",
     "reference_schema": "csr-tranche10-contention-contract-reference-v1",
     "summary_schema": "csr-tranche10-contention-contract-v1"},
    {"kind": "rx", "directory": "evidence/tranche-10-receiver-reference",
     "reference_schema": "csr-tranche10-receiver-contract-reference-v1",
     "summary_schema": "csr-tranche10-receiver-contract-v1"},
    {"kind": "ack", "directory": t9.CONTRACT_ROOT,
     "reference_schema": "csr-tranche9-ack-contract-reference-v1",
     "summary_schema": "csr-tranche9-ack-service-contract-v1"},
]
REFERENCE_TREES = ["evidence/tranche-7-ns3-reference", "evidence/tranche-7-benchmark-inputs",
                   "evidence/tranche-8-ns3-reference", t9.REFERENCE_ROOT, t9.CONTRACT_ROOT,
                   CONTRACTS[0]["directory"], CONTRACTS[1]["directory"], BUILD_ROOT]
MAC_NAMES = ("reliable", "ack_loss", "data_loss", "dack", "collision", "relay", "queue_pressure", "high_rate_500", "high_rate_1000")
ROUTED_NAMES = ("autonomous", "no_route_custody", "control_loss", "route_recovery", "gateway", "leaf_no_transit", "high_rate_500", "high_rate_1000")
RESEARCH_NAMES = ("two_node", "line_4", "hidden_node", "mesh_6", "route_recovery", "leaf_no_transit")
require, integer, finite = sweep.require, sweep.integer, sweep.finite


def retained_membership(source_root):
    shared = sweep.json_object(source_root/"scenarios/shared/catalog.json")["cases"]
    rows = [("foundation", "default", "csr.scenario.smallNetwork", "", "")]
    rows += [("mac_hop", name, "csr.scenario.macHopNetwork", name, "") for name in MAC_NAMES]
    rows += [("routed", name, "csr.scenario.routedNetwork", name, "") for name in ROUTED_NAMES]
    rows += [("shared", row["name"], "csr.scenario.importNs3", row["name"], "scenarios/shared/"+row["path"]) for row in shared]
    rows += [("research", name+"_seed_128", "csr.scenario.researchNetwork", name, "") for name in RESEARCH_NAMES]
    return [{"case_id": f"{kind}_{name}", "kind": kind, "name": name, "storage_key": f"{index:02d}",
             "factory": factory, "fixture": fixture, "scenario_file": scenario}
            for index, (kind, name, factory, fixture, scenario) in enumerate(rows, 1)]


def sweep_membership():
    names = [f"{kind}_{token}{value}_seed{seed}"
             for kind, token, values in (("offered_load", "x", (1, 2, 4)), ("recovery_freshness", "s", (60, 180, 300)))
             for value in values for seed in (128, 129, 130)]
    return [{"case_id": name, "storage_key": f"{index:02d}"} for index, name in enumerate(names, 1)]


def verify_plan(source_root):
    source_root = Path(source_root)
    plan = sweep.json_object(source_root/PLAN)
    require(plan.get("schema") == "csr-contention-timing-plan-v1" and plan.get("status") == "planned-not-executed"
            and plan.get("matlab_base_commit") == BASE and plan.get("accepted_tranche9_matlab_commit") == T9_CODE
            and plan.get("ns3_source_commit") == PIN, "T10 plan source/baseline identity mismatch")
    require(plan.get("stimuli_changed") is False and plan.get("policy_changes") is True
            and all(plan.get(name) is False for name in ("phy_ecc_changed", "radio_policy_changed", "rng_policy_changed")),
            "T10 plan experiment scope mismatch")
    require(plan.get("diagnostic_plan") == t9.PLAN and plan.get("diagnostic_plan_sha256") == DIAGNOSTIC_SHA
            and sweep.digest(source_root/t9.PLAN) == DIAGNOSTIC_SHA, "T10 diagnostic input plan changed")
    diagnostics, parent = t9.verify_plan(source_root)
    require(plan.get("diagnostic_case_count") == 6 and plan.get("diagnostic_order") == t9.CASE_ORDER
            and all(plan.get(field) == diagnostics.get(field) for field in
                    ("control_keys", "service_window_s", "service_window_end_exclusive", "service_max_records", "feedback_max_records")),
            "T10 diagnostic order, observer limits or boundaries changed")
    require(plan.get("retained_case_count") == 29 and plan.get("retained_cases") == retained_membership(source_root),
            "T10 retained cases missing, changed, duplicated or reordered")
    require(plan.get("sweep_case_count") == 18 and plan.get("sweep_cases") == sweep_membership(),
            "T10 sweep cases missing, changed, duplicated or reordered")
    catalog = sweep.json_object(source_root/"scenarios/benchmarks/catalog.json")
    campus = [case for case in catalog["cases"] if case["case_id"] == "campus_multihop_6000"]
    require(len(campus) == 1 and plan.get("campus") == dict(campus[0], storage_key="campus")
            and campus[0]["duration_s"] == 6000 and campus[0]["seed"] == 128 and campus[0]["opnet_available"] is True,
            "T10 campus fixture differs from the accepted 6000-second seed-128 benchmark")
    require(plan.get("contract_references") == CONTRACTS and plan.get("reference_directories") == REFERENCE_TREES,
            "T10 reference family/order mismatch")
    anchors = sweep.entries(plan.get("accepted_anchors"), "accepted anchors")
    expected = [(7, timing.T7_ARCHIVE, timing.T7_SHA),
                (8, "evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip", t9.ANCHOR_SHA),
                (9, timing.T9_ARCHIVE, timing.T9_SHA)]
    require([(row.get("tranche"), row.get("path"), row.get("sha256")) for row in anchors] == expected,
            "T10 accepted archive identity mismatch")
    inputs = sweep.entries(plan.get("input_files"), "T10 unchanged inputs")
    required = {"+csr/+scenario/"+name+".m" for name in ("smallNetwork", "macHopNetwork", "routedNetwork", "researchNetwork",
                "researchSweep", "benchmarkSuite", "ackServiceSuite", "linkDiagnosticSuite")}
    required |= {"scenarios/shared/catalog.json", "scenarios/benchmarks/catalog.json", t9.PLAN, campus[0]["scenario_file"]}
    required |= {row["scenario_file"] for row in plan["retained_cases"] if row["scenario_file"]}
    require(len(inputs) == len(required) and {row.get("path") for row in inputs} == required,
            "T10 unchanged input binding membership mismatch")
    references = sweep.entries(plan.get("reference_files"), "T10 reference records")
    require([row.get("path") for row in references] == [NATIVE_BUILD, SOURCE_RECHECK], "T10 individual reference records changed")
    for row in [*inputs, *anchors, *references]:
        path = sweep.safe_path(source_root, row["path"])
        require(sweep.digest(path) == sweep.valid_hash(row.get("sha256"), "input SHA-256")
                and path.stat().st_size == integer(row.get("bytes"), "input bytes"), "T10 unchanged input hash/size mismatch")
    recheck = sweep.json_object(source_root/SOURCE_RECHECK)
    require(recheck.get("schema") == "csr-tranche10-source-recheck-v1" and recheck.get("status") == "passed"
            and recheck.get("source_commit") == PIN and recheck.get("branch") == "main"
            and recheck.get("repository") == "mjburke4/CSR-Project-NS3-part2"
            and recheck.get("source_tracked_clean") is True and recheck.get("unchanged_from_tranche9") is True
            and recheck.get("matlab_base_commit") == BASE and recheck.get("accepted_tranche9_code") == T9_CODE,
            "T10 authoritative source recheck identity failed")
    return plan, diagnostics, parent


def verify_options(metadata):
    options = metadata.get("Options")
    require(isinstance(options, dict) and set(options) == {"RunTests", "RunCampus"}
            and all(type(value) is bool for value in options.values()), "Unsupported T10 options")
    require(metadata.get("TestsRequested") is options["RunTests"]
            and metadata.get("CampusRequested") is options["RunCampus"], "T10 request flags disagree")
    require(metadata.get("NativeRequested") is False and metadata.get("NativeExecuted") is False,
            "T10 portable runner must not claim MATLAB native-backend execution")
    return options


def verify_tests(root, metadata, source_root):
    adapted = copy.deepcopy(metadata)
    adapted["Options"] = {"RunTests": metadata["Options"]["RunTests"]}
    result = t8.verify_tests(root, adapted, source_root)
    result["scope"] = "Every candidate portable test exactly once; retained scenarios and sweeps are separately verified."
    return result


def verify_gate_claims(metadata, *, tests, campus, contracts, retained, sweeps, controls):
    full = (tests["status"] == "passed" and campus["status"] == "passed" and contracts["passed"]
            and retained["case_count"] == 29 and sweeps["case_count"] == 18 and controls["passed"])
    require(metadata.get("FullAcceptanceGateExecuted") is full and metadata.get("DiagnosticOnly") is (not full),
            "Full default gate/diagnostic-only claim disagrees with executed phases")
    return full


def verify_reference_snapshot(metadata, source_root, plan):
    require(metadata.get("ReferenceFilesStableDuringRun") is True, "T10 reference stability unproven")
    before = sweep.entries(metadata.get("ReferenceFiles"), "initial references")
    require(before == sweep.entries(metadata.get("ReferenceFilesFinal"), "final references"), "T10 references changed during execution")
    expected = {f"{tree}/{name}" for tree in REFERENCE_TREES for name in t7.listed_files(source_root/tree)}
    expected.update(row["path"] for row in plan["accepted_anchors"])
    expected.update(row["path"] for row in plan["reference_files"])
    require(len(before) == len(expected) and {row.get("path") for row in before} == expected,
            "T10 reference snapshot membership mismatch")
    for row in before:
        path = sweep.safe_path(source_root, row["path"])
        require(path.stat().st_size == integer(row.get("bytes"), "reference bytes")
                and sweep.digest(path) == sweep.valid_hash(row.get("sha256"), "reference SHA-256"),
                "T10 reference snapshot hash mismatch")
    return len(before)


def verify_native_build(source_root):
    record = sweep.json_object(source_root/NATIVE_BUILD)
    require(record.get("schema") == "csr-tranche10-native-engine-rebuild-v1" and record.get("status") == "passed"
            and record.get("source_commit") == PIN and record.get("engine_commit") == "6b5cd24ea80713ce16d88575869aedd6f432bdae"
            and record.get("source_tree") == "b611b233fb369569b98f0914ece24d029ccc2f42"
            and record.get("engine_tree") == "f30343185fb057e3a9cdd54f496cca0cef49ae23"
            and all(record.get(k) is True for k in ("engine_rebuilt", "engine_tracked_sources_unchanged", "csr_tracked_sources_unchanged",
                                                   "copied_csr_module_files_match", "native_contract_executed"))
            and all(record.get(k) is False for k in ("reused_historical_libraries", "historical_libraries_byte_identity_claimed",
                                                    "matlab_executed", "full_engine_test_suite_executed", "historical_benchmarks_rerun")),
            "Fresh native engine source/build scope mismatch")
    require(record.get("published_artifact_root") == BUILD_ROOT, "Native build artifact root mismatch")
    original = record.get("original_manifest", {})
    require(original.get("path") == BUILD_ROOT+"/manifest.json"
            and original.get("sha256") == sweep.digest(source_root/original["path"]), "Original native build manifest hash mismatch")
    original_record = sweep.json_object(source_root/original["path"])
    require({key: value for key, value in record.items() if key not in ("published_artifact_root", "original_manifest")} == original_record,
            "Published native engine record differs from the original build record")
    artifacts = t7.inventory(source_root/BUILD_ROOT, record.get("artifacts"), "native engine build artifacts", excluded=("manifest.json",))
    for name in ("configure_record", "build_record", "nothing_pending_record"):
        require(record.get(name, {}).get("exit_code") == 0, "Native engine command did not finish successfully")
    require(record["build_record"].get("output_captured_after_process_closed") is True
            and record["nothing_pending_record"].get("nothing_pending") is True, "Native build output/completion unproven")
    smoke = record.get("smoke_contract", {})
    require(smoke.get("checkpoint_count") == 101 and smoke.get("case_count") == 6
            and smoke.get("t9_reference_bytes_equal") is True and smoke.get("inputs_unchanged") is True
            and smoke.get("compile", {}).get("exit_code") == 0 and smoke.get("run", {}).get("exit_code") == 0
            and smoke.get("source_sha256") == sweep.digest(source_root/"scripts/ns3/tranche9_ack_contract.cc")
            and smoke.get("checkpoint_sha256") == smoke.get("t9_reference_sha256")
            == sweep.digest(source_root/t9.CONTRACT_ROOT/"checkpoints.csv"), "Fresh engine retained ACK smoke contract failed")
    smoke_files = [entry for entry in artifacts.values() if entry["path"].endswith("/checkpoints.csv")]
    require(len(smoke_files) == 1 and smoke_files[0]["sha256"] == smoke["checkpoint_sha256"],
            "Fresh engine ACK smoke checkpoint artifact mismatch")
    libraries = sweep.entries(record.get("libraries"), "native engine libraries")
    require(len(libraries) == 9 and len({row.get("path") for row in libraries}) == 9,
            "Fresh engine library inventory incomplete")
    for row in libraries:
        sweep.valid_hash(row.get("sha256"), "native library SHA-256")
        require(integer(row.get("bytes"), "native library bytes") > 0, "Empty native library")
    return record


def verify_native_contract_reference(source_root, spec):
    directory = source_root/spec["directory"]
    record = sweep.json_object(directory/"manifest.json")
    require(record.get("schema") == spec["reference_schema"] and record.get("status") == "passed"
            and record.get("source_commit") == PIN and record.get("source_headers_unchanged") is True
            and record.get("native_contract_executed") is True and record.get("matlab_executed") is False
            and record.get("compile_returncode") == 0 and record.get("run_returncode") == 0,
            "Native contract execution/source provenance incomplete")
    if spec["kind"] == "ack":
        expected = ("scripts/ns3/tranche9_ack_contract.cc", "scripts/run_tranche9_ack_contract.py")
        require(record.get("engine_rebuilt") is False, "Retained ACK contract engine provenance changed")
    else:
        name = "contention" if spec["kind"] == "mac" else "receiver"
        expected = (f"scripts/ns3/tranche10_{name}_contract.cc", "scripts/run_tranche10_contracts.py")
        require(record.get("engine_rebuilt") is True, "T10 native contracts require the fresh pinned engine build")
        engine = record.get("engine_build_record", {})
        require(engine.get("path") == NATIVE_BUILD and engine.get("sha256") == sweep.digest(source_root/NATIVE_BUILD),
                "T10 native contract fresh engine binding mismatch")
        build = verify_native_build(source_root)
        canonical = lambda rows: sorted((row["path"], row["sha256"], row["bytes"]) for row in rows)
        require(record.get("input_snapshot_unchanged") is True and record.get("output_captured_after_process_closed") is True
                and record.get("historical_library_byte_identity_claimed") is False
                and canonical(sweep.entries(record.get("fresh_libraries"), "native contract libraries")) == canonical(build["libraries"]),
                "Native contract did not use the declared fresh engine libraries")
        previous = sweep.json_object(source_root/t9.CONTRACT_ROOT/"manifest.json")
        require(record.get("source_headers") == previous.get("source_headers"), "Native contract pinned source headers changed")
    for field, path in zip(("contract_source", "runner_source"), expected):
        entry = record.get(field, {})
        require(entry.get("path") == path and entry.get("sha256") == sweep.digest(source_root/path),
                "Native contract executable source binding mismatch")
    sweep.valid_hash(record.get("binary_sha256"), "native binary SHA-256")
    t7.inventory(directory, record.get("artifacts"), "native contract artifacts", excluded=("manifest.json",))
    checkpoints = directory/"checkpoints.csv"
    count = timing.exact_contract_rows(checkpoints, checkpoints)
    cases = {row["case"] for row in t7.csv_records(checkpoints)}
    expected_cases = {
        "mac": {"idle_after", "idle_before", "idle_literal", "idle_p15", "idle_p30", "idle_p51", "idle_p60", "idle_restart",
                "search_initial", "sync_busy", "sync_initial", "track_busy", "track_initial", "track_tie_early", "track_tie_late"},
        "rx": {"acquisition_canceled_by_sleep", "preamble_after_wake", "preamble_at_wake", "preamble_before_wake"},
        "ack": {"mac_ack_wait", "mac_ack_sync", "mac_ack_track", "mac_cancel_then_ack", "mac_control_cancel_then_ack", "hop_release_order"},
    }
    require(cases == expected_cases[spec["kind"]] and count == {"mac": 279, "rx": 154, "ack": 101}[spec["kind"]],
            "Native contract required cases/checkpoint coverage mismatch")
    require(count == integer(record.get("checkpoint_count"), "native checkpoint count")
            and len(cases) == integer(record.get("case_count"), "native case count"), "Native contract coverage differs from manifest")
    return {"kind": spec["kind"], "checkpoint_count": count, "case_count": len(cases),
            "manifest_sha256": sweep.digest(directory/"manifest.json"), "reference_sha256": sweep.digest(checkpoints)}


def verify_contracts(root, source_root, metadata):
    require(metadata.get("ContractDirectory") == "k" and metadata.get("ContractsExecuted") is True
            and metadata.get("ContractsPassed") is True, "T10 contract execution incomplete")
    rows = sweep.entries(metadata.get("ContractCases"), "returned contract cases")
    require(len(rows) == 3 and [row.get("Kind") for row in rows] == [row["kind"] for row in CONTRACTS],
            "T10 contract families missing, duplicated or reordered")
    observations = []
    for row, spec in zip(rows, CONTRACTS):
        native = verify_native_contract_reference(source_root, spec)
        require(row.get("Directory") == "k/"+spec["kind"] and row.get("Schema") == spec["summary_schema"]
                and row.get("Passed") is True, "Returned contract family identity mismatch")
        directory = sweep.safe_path(root, row["Directory"])
        require(sweep.digest(directory/"summary.json") == row.get("SummarySHA256"), "Contract summary hash mismatch")
        summary = sweep.json_object(directory/"summary.json")
        require(summary.get("Schema") == spec["summary_schema"] and summary.get("Passed") is True
                and integer(summary.get("UnmatchedCount"), "unmatched contracts") == 0
                and integer(summary.get("FailedCount"), "failed contracts") == 0
                and summary.get("ReferenceSHA256") == native["reference_sha256"], "Contract summary/reference binding mismatch")
        count = timing.exact_contract_rows(directory/"checkpoints.csv", source_root/spec["directory"]/"checkpoints.csv")
        require(count == integer(summary.get("CheckpointCount"), "contract count")
                == integer(row.get("CheckpointCount"), "metadata contract count") == native["checkpoint_count"],
                "Returned contract count mismatch")
        require(t7.listed_files(directory) == {"summary.json", "checkpoints.csv"}, "Unlisted contract output")
        observations.append(native)
    return {"passed": True, "families": observations, "checkpoint_count": sum(row["checkpoint_count"] for row in observations),
            "scope": "Prescribed subsystem checkpoints, including separate receiver timing; no stochastic/RF population equivalence claim."}


def verify_retained(root, source_root, metadata, source, runtime, plan):
    completed = sweep.entries(metadata.get("RetainedCases"), "retained cases")
    require(integer(metadata.get("RetainedPlannedCount"), "retained planned") == 29
            and integer(metadata.get("RetainedCompletedCount"), "retained completed") == 29
            and len(completed) == 29, "T10 retained case execution incomplete")
    observations = []
    returned_plan = sweep.json_object(root/"retained_plan.json")
    require(returned_plan.get("Schema") == "csr-matlab-retained-plan-v1" and returned_plan.get("Status") == "planned-not-executed"
            and returned_plan.get("CaseCount") == 29 and returned_plan.get("SourceCommit") == PIN
            and returned_plan.get("ConfigurationsChanged") is False and returned_plan.get("NumericalParityEstablished") is False,
            "Returned retained plan identity/scope mismatch")
    expected_rows = [{"CaseId": row["case_id"], "Kind": row["kind"], "Name": row["name"], "StorageKey": row["storage_key"],
                      "Factory": row["factory"], "Fixture": row["fixture"], "ScenarioFile": row["scenario_file"],
                      "ScenarioSHA256": sweep.digest(source_root/row["scenario_file"]) if row["scenario_file"] else ""}
                     for row in plan["retained_cases"]]
    require(returned_plan.get("Cases") == expected_rows, "Returned retained plan cases differ from fixed factories")
    summary_rows = list(t7.csv_records(root/"retained_summary.csv", ("CaseId", "Kind", "Name", *t7.COUNTS)))
    require(len(summary_rows) == 29, "Retained summary membership mismatch")
    total_seconds = 0
    with zipfile.ZipFile(source_root/timing.T7_ARCHIVE) as bundle:
        roots = timing.archive_roots(bundle)
        for item, expected, row in zip(completed, plan["retained_cases"], summary_rows):
            require(all(item.get(key) == expected[name] for key, name in (("CaseId", "case_id"), ("Kind", "kind"), ("Name", "name")))
                    and item.get("Directory") == "r/"+expected["storage_key"], "T10 retained case identity/order/path mismatch")
            directory = sweep.safe_path(root, item["Directory"])
            custom = expected["kind"] in ("foundation", "mac_hop") or expected["case_id"] == "routed_gateway"
            summary, accounting = timing.verify_case_manifest(directory, item, source, runtime,
                                                              custom=custom)
            require(all(row.get(k) == item[k] for k in ("CaseId", "Kind", "Name"))
                    and row.get("Scenario") == summary["Config"]["Name"]
                    and integer(row.get("Seed"), "retained seed") == summary["Config"]["Seed"]
                    and finite(row.get("DurationSeconds"), "retained duration") == summary["Config"]["DurationSeconds"]
                    and sweep.boolean(row.get("StructuralChecksPassed"), "retained structural checks")
                    and t7.count_balance(row, "retained summary") == accounting["counts"], "Retained summary/raw identity or counts mismatch")
            for field in ("PhysicalAttempts", "PhysicalReceived", "PhysicalDropped", "PhysicalPending", "ApplicationBytesReceived"):
                require(integer(row.get(field), field) == summary["Statistics"][field], "Retained summary raw physical/byte counts differ")
            total_seconds += summary["Config"]["DurationSeconds"]
            manifest = sweep.json_object(directory/"case_manifest.json")
            if custom:
                require(all(manifest.get(field) == expected[field] for field in
                            ("case_id", "kind", "name", "storage_key", "factory", "fixture")), "Retained legacy manifest identity mismatch")
                local = list(t7.csv_records(directory/"retained_summary.csv"))
                require(local == [row], "Retained aggregate/per-case summary mismatch")
            baseline = timing.compare_baseline(bundle, timing.baseline_path(expected, roots), directory, source_root)
            observations.append({"case_id": item["CaseId"], "kind": item["Kind"], **accounting, "accepted_tranche7": baseline})
    require(finite(returned_plan.get("TotalSimulatedSeconds"), "retained simulated seconds") == total_seconds,
            "Retained plan total duration differs from executed configurations")
    return {"status": "passed", "case_count": len(observations), "cases": observations,
            "baseline_archive_sha256": timing.T7_SHA, "scope": "Exact retained input configuration; counts and unique application outcomes reconstructed. Numerical outcomes may change."}


def verify_sweeps(root, source_root, metadata, source, runtime, plan):
    sweep_plan = sweep.json_object(root/"sweep_plan.json")
    expected, seeds = sweep.expected_plan(sweep_plan)
    names = [row["case_id"] for row in sweep_membership()]
    require(list(expected) == names and seeds == [128, 129, 130], "Default 18-case sweep plan changed")
    sweep.match_keys(expected, sweep.keyed(list(t7.csv_records(root/"sweep_cases.csv", sweep.IDENTITY)), "sweep cases"), "sweep cases")
    performance = sweep.keyed(list(t7.csv_records(root/"performance_summary.csv", sweep.IDENTITY+sweep.METRICS)), "sweep performance")
    sweep.match_keys(expected, performance, "sweep performance")
    completed = sweep.entries(metadata.get("SweepCases"), "completed sweeps")
    require(integer(metadata.get("SweepPlannedCount"), "sweep planned") == 18
            and integer(metadata.get("SweepCompletedCount"), "sweep completed") == 18
            and len(completed) == 18 and [item.get("CaseId") for item in completed] == names,
            "T10 sweeps missing, duplicated or reordered")
    observations = []
    with zipfile.ZipFile(source_root/timing.T7_ARCHIVE) as bundle:
        roots = timing.archive_roots(bundle)
        old_plan = json.loads(bundle.read(str(roots[5]/"sweep_plan.json")))
        require(sweep_plan == old_plan, "T10 sweep plan differs from accepted T7 default inputs")
        for item, planned in zip(completed, plan["sweep_cases"]):
            name, key = item["CaseId"], planned["storage_key"]
            identity, values = expected[name]
            require(sweep.identity(item, "returned sweep") == identity and item.get("Name") == name
                    and item.get("Kind") == "sweep" and item.get("Directory") == f"s/{key}/raw"
                    and item.get("DiagnosticsDirectory") == f"s/{key}/analysis", "T10 sweep identity/path mismatch")
            directory = sweep.safe_path(root, item["Directory"])
            summary, accounting = timing.verify_case_manifest(directory, item, source, runtime)
            require(sweep.identity(dict(summary["Config"]["Research"]["Sweep"], CaseId=summary["Config"]["Name"]),
                                   "sweep config") == identity, "Actual sweep configuration differs from plan")
            row = performance[name][1]
            result = sweep.metrics(row)
            require(all(result[k] == accounting["counts"][k] for k in t7.COUNTS), "Sweep performance/raw counts differ")
            diagnostics = list(t7.csv_records(sweep.safe_path(root, item["DiagnosticsDirectory"])/"performance_summary.csv"))
            require(len(diagnostics) == 1 and diagnostics[0] == row, "Sweep aggregate/per-case diagnostics differ")
            baseline = timing.compare_baseline(bundle, timing.baseline_path({"kind": "sweep", "name": name}, roots), directory, source_root)
            observations.append({"case_id": name, **accounting, "performance": result, "accepted_tranche7": baseline})
    return {"status": "passed", "case_count": len(observations), "cases": observations,
            "baseline_archive_sha256": timing.T7_SHA, "seeds": seeds}


def verify_diagnostics(root, source_root, metadata, source, runtime, source_hash, plan):
    completed = sweep.entries(metadata.get("Cases"), "completed diagnostics")
    require(integer(metadata.get("PlannedCaseCount"), "planned diagnostics") == 6
            and integer(metadata.get("CompletedCaseCount"), "completed diagnostics") == 6
            and len(completed) == 6 and [row.get("CaseId") for row in completed] == [row["case_id"] for row in plan["cases"]],
            "T10 diagnostics missing, duplicated or reordered")
    observations, paths = [], []
    with zipfile.ZipFile(source_root/timing.T9_ARCHIVE) as bundle:
        for item, case in zip(completed, plan["cases"]):
            key = case["storage_key"]
            directory, reference = root/"b"/key, source_root/case["reference_directory"]
            manifest = sweep.json_object(directory/"benchmark_manifest.json")
            require(manifest.get("storage_key") == key, "Diagnostic storage key changed")
            observed = t7.verify_case(root, item, case, source, runtime, source_hash, expected_directory=f"b/{key}")
            compare.case_input_manifest(directory, reference)
            observed.update(base_case_id=case["base_case_id"], seed=case["seed"])
            observed["matlab_applications"] = metrics.matlab_applications(directory, case)
            observed["ns3_applications"] = metrics.ns3_applications(reference, case)
            observed["matlab_feedback"] = t8.verify_matlab_feedback(directory, case)
            observed["ns3_feedback"] = t8.verify_ns3_feedback(reference, case)
            observed["matlab_service"] = service.verify_matlab_service(directory, case, plan)
            observed["ns3_service"] = service.verify_ns3_service(source_root/case["service_reference_directory"], case, plan)
            observed["accepted_tranche9"] = timing.compare_baseline(bundle, PurePosixPath(f"b/{key}/raw"),
                directory/"raw", source_root, case=case, files=t8.UNCHANGED_CSV)
            observations.append(observed)
            paths.append((directory, reference))
    t9.case_summary(root, observations)
    return observations, paths


def verify_campus(root, source_root, metadata, source, runtime, source_hash, case):
    if not metadata["Options"]["RunCampus"]:
        require(metadata.get("CampusExecuted") is False
                and metadata.get("CampusCase") == {"CaseId": "", "Directory": "", "ManifestSHA256": ""}
                and not (root/"b/campus").exists() and not (root/"campus_summary.csv").exists(),
                "Unrequested campus contains execution claims or artifacts")
        return {"status": "not_run", "requested": False}, []
    require(metadata.get("CampusExecuted") is True and isinstance(metadata.get("CampusCase"), dict),
            "Requested campus execution incomplete")
    item = metadata["CampusCase"]
    require(item.get("CaseId") == case["case_id"], "Campus identity mismatch")
    observed = t7.verify_case(root, item, case, source, runtime, source_hash, expected_directory="b/campus")
    directory, reference = root/"b/campus", source_root/case["reference_directory"]
    manifest = sweep.json_object(directory/"benchmark_manifest.json")
    summary = sweep.json_object(directory/"raw/summary.json")
    require(manifest.get("observer_enabled") is False and manifest.get("service_observer_enabled") is False
            and "LinkDiagnostics" not in summary and "ServiceDiagnostics" not in summary
            and not any((directory/"raw"/name).exists() for name in ("link_decisions.csv", "actual_feedback.csv", "service_trace.csv")),
            "Campus must execute without the diagnostic observers")
    compare.case_input_manifest(directory, reference)
    rows = list(t7.csv_records(root/"campus_summary.csv", ("CaseId", *t7.COUNTS, "Attempts", "AdmissionBlocked")))
    require(len(rows) == 1 and rows[0]["CaseId"] == case["case_id"]
            and t7.count_balance(rows[0], "campus summary") == observed["counts"]
            and integer(rows[0]["Attempts"], "campus attempts") == observed["admission"]["attempts"]
            and integer(rows[0]["AdmissionBlocked"], "campus blocked") == observed["admission"]["blocked"],
            "Campus summary differs from reconstructed outcomes")
    with zipfile.ZipFile(source_root/timing.T7_ARCHIVE) as bundle:
        observed["accepted_tranche7"] = timing.compare_baseline(bundle,
            PurePosixPath("benchmarks/campus_multihop_6000/raw"), directory/"raw", source_root, case=case)
    observed.update(status="passed", requested=True, simulated_seconds=6000, seed=128,
                    comparison_sources=["matlab", "ns3", "archived_opnet"], opnet_rerun=False,
                    scope="One full campus seed; archived OPNET aggregates are reused, not rerun.")
    return observed, [(directory, reference)]


def verify_return(root, source_root):
    root, source_root = Path(root).resolve(), Path(source_root).resolve()
    metadata = sweep.json_object(root/"validation_metadata.json")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 10, "Unsupported Tranche 10 schema")
    require(metadata.get("MatlabBaseCommit") == BASE and metadata.get("ValidatedTranche9CodeCommit") == T9_CODE,
            "T10 accepted baseline identity mismatch")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB"
            and isinstance(runtime.get("Version"), str) and runtime["Version"]
            and isinstance(runtime.get("Release"), str) and runtime["Release"], "Missing actual MATLAB runtime/release")
    verify_options(metadata)
    require(metadata.get("DiagnosticPlan") == "diagnostic_plan.json" and metadata.get("ValidationPlan") == "validation_plan.json"
            and metadata.get("NonperturbationFile") == "nonperturbation.json"
            and metadata.get("ServiceWindowSeconds") == [300, 320] and metadata.get("ServiceWindowEndExclusive") is True
            and metadata.get("CrossSimulatorComparisonExecuted") is False and metadata.get("NumericalParityEstablished") is False,
            "T10 artifact paths or comparison scope mismatch")
    source = t7.candidate_snapshot(source_root)
    t7.source_binding(metadata, source, runtime)
    t7.inventory(root, metadata.get("Artifacts"), "outer T10 artifacts", excluded=("validation_metadata.json", "tranche10_evidence.zip"),
                 local=metadata.get("LocalArtifacts", []))
    source_hash = sweep.digest(root/"source_snapshot.json")
    require(metadata.get("SourceSnapshotSHA256") == source_hash
            and sweep.snapshot(json.loads((root/"source_snapshot.json").read_text()), "source snapshot") == source,
            "T10 source snapshot file binding mismatch")
    plan, diagnostic_plan, parent = verify_plan(source_root)
    for field, actual, expected in (("DiagnosticPlanSHA256", "diagnostic_plan.json", t9.PLAN),
                                     ("ValidationPlanSHA256", "validation_plan.json", PLAN)):
        require(metadata.get(field) == sweep.digest(source_root/expected)
                and sweep.digest(root/actual) == sweep.digest(source_root/expected), "T10 returned plan hash mismatch")
    references = verify_reference_snapshot(metadata, source_root, plan)
    t7.verify_reference_suite(source_root, sweep.json_object(source_root/"scenarios/benchmarks/catalog.json"))
    t8.verify_reference_suite(source_root, parent)
    service_reference = service.verify_reference_suite(source_root, diagnostic_plan)
    contracts = verify_contracts(root, source_root, metadata)
    tests = verify_tests(root, metadata, source_root)
    retained = verify_retained(root, source_root, metadata, source, runtime, plan)
    sweeps = verify_sweeps(root, source_root, metadata, source, runtime, plan)
    cases, paths = verify_diagnostics(root, source_root, metadata, source, runtime, source_hash, diagnostic_plan)
    controls = t9.verify_nonperturbation(root, metadata, source, diagnostic_plan)
    campus, campus_paths = verify_campus(root, source_root, metadata, source, runtime, source_hash, plan["campus"])
    full = verify_gate_claims(metadata, tests=tests, campus=campus, contracts=contracts, retained=retained, sweeps=sweeps, controls=controls)
    require(t7.candidate_snapshot(source_root) == source, "Candidate changed during Python review")
    metrics_rows = [row[key] for row in cases for key in ("matlab_applications", "ns3_applications")]
    report = {"schema": REVIEW_SCHEMA, "status": "structural_review_completed", "evidence_integrity_verified": True,
              "default_structural_gate_completed": full, "diagnostic_only": not full, "matlab_runtime": runtime,
              "tests": tests, "deterministic_contracts": contracts, "retained": retained, "sweeps": sweeps,
              "cases": cases, "nonperturbation": controls, "campus": campus, "service_reference": service_reference,
              "contention_multiseed": metrics.multiseed_summary([row for row in metrics_rows if row["base_case_id"] == "three_node_contention_360"]),
              "source_files_verified": len(source), "reference_files_verified": references,
              "source_snapshot_sha256": source_hash, "metadata_sha256": sweep.digest(root/"validation_metadata.json"),
              "acceptance_established": False, "numerical_parity_established": False, "population_equivalence_established": False,
              "limitations": ["MATLAB runtime is owner-returned evidence; this reviewer executes no MATLAB.",
                              "Source-confirmed timing changes permit numerical differences; counts do not establish causality or parity.",
                              "Five contention seeds and one campus seed are descriptive; matching seed numbers do not align random streams.",
                              "PHY/ECC and radio policy are unchanged; subsystem timing contracts are scoped to their prescribed conditions.",
                              "Archived OPNET aggregate evidence is reused; OPNET and the MATLAB native backend are not executed.",
                              "Pending MATLAB work and unclassified ns-3 unmatched sends remain explicit."]}
    return report, paths+campus_paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output, created, archive_hash = args.output.resolve(), False, None
    try:
        require(not output.exists(), "Review output already exists")
        require(not output.is_relative_to(args.evidence.resolve()) and not output.is_relative_to(args.source_root.resolve()),
                "Review output must be outside evidence and candidate")
        if args.evidence.is_file():
            archive_hash = sweep.digest(args.evidence)
        output.mkdir(parents=True, exist_ok=False)
        created = True
        with t7.evidence_directory(args.evidence) as root:
            report, cases = verify_return(root, args.source_root)
            for case, reference in cases:
                compare.compare_case(case, reference, output/case.name)
            if archive_hash:
                require(sweep.digest(args.evidence) == archive_hash, "Uploaded evidence changed during review")
                report["uploaded_zip_sha256"] = archive_hash
            (output/"review.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
            flat = [row[key] for row in report["cases"] for key in ("matlab_applications", "ns3_applications")]
            fields = [name for name in flat[0] if name not in ("flows", "drop_reasons")]
            sweep.write_csv(output/"per_seed_metrics.csv", fields, [{name: row[name] for name in fields} for row in flat])
        print(f"T10 structural review completed; default gate={report['default_structural_gate_completed']}. Acceptance requires review.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error, zipfile.BadZipFile) as failure:
        if created:
            result = {"schema": REVIEW_SCHEMA, "status": "structural_review_failed", "evidence_integrity_verified": False,
                      "default_structural_gate_completed": False, "acceptance_established": False,
                      "numerical_parity_established": False, "error_type": type(failure).__name__, "error": str(failure)}
            if archive_hash:
                result["uploaded_zip_sha256"] = archive_hash
            (output/"review-failure.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        print(f"Tranche 10 review failed: {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
