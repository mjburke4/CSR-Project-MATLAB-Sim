#!/usr/bin/env python3
"""Verify returned T9 service diagnostics, controlled contracts and regressions.

This reviewer reconstructs owner-returned MATLAB evidence. It never executes
MATLAB, establishes acceptance automatically, or treats matching seed labels as
matching pseudorandom streams. Use the exact candidate --source-root snapshot.
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import math
from pathlib import Path, PurePosixPath
import sys
import zipfile

import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import analyze_tranche8_return as t8
import compare_benchmark_aggregates as compare
import tranche8_metrics as metrics

ROOT = Path(__file__).resolve().parents[1]
PIN = t7.PIN
BASE = "d0f3c5657f9f2dcf678f32900020caf3696bf90a"
T8_CODE = "89b62e729e588f396bb919afdff522f7e9419268"
ANCHOR_SHA = "bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77"
PARENT_PLAN_SHA = "ed648ee4f54ebf14e14b98d6fcecce224590727139db83f0f4d23161ddfc7a09"
SCHEMA = "csr-matlab-tranche-9-validation-v1"
REVIEW_SCHEMA = "csr-matlab-tranche-9-return-review-v1"
PLAN = "scenarios/ack_service/plan.json"
CASE_ORDER = ["c129", "c128", "c130", "c131", "c132", "a129"]
CONTROL_KEYS = ["c129", "a129"]
CONTRACT_ROOT = "evidence/tranche-9-contract-reference"
REFERENCE_ROOT = "evidence/tranche-9-ns3-reference"
require, integer, finite = sweep.require, sweep.integer, sweep.finite


def verify_plan(source_root):
    source_root = Path(source_root)
    plan = sweep.json_object(source_root/PLAN)
    require(plan.get("schema") == "csr-ack-service-plan-v1"
            and plan.get("matlab_base_commit") == BASE
            and plan.get("accepted_tranche8_matlab_commit") == T8_CODE
            and plan.get("ns3_source_commit") == PIN, "T9 plan source/baseline identity mismatch")
    require(plan.get("case_count") == 6 and plan.get("case_order") == CASE_ORDER
            and plan.get("control_keys") == CONTROL_KEYS
            and plan.get("service_window_s") == [300, 320]
            and plan.get("service_window_end_exclusive") is True
            and plan.get("service_max_records") == 100000
            and plan.get("feedback_max_records") == 100000,
            "T9 diagnostic case order, controls, window or limits changed")
    require(plan.get("stimuli_changed") is False and plan.get("opnet_available") is False
            and plan.get("policy_changes") is True
            and plan.get("change_id") == "preserve_mac_preparation_after_queue_cancellation",
            "T9 experiment scope or declared correction is unsupported")
    require(plan.get("parent_plan") == t8.PLAN
            and plan.get("parent_plan_sha256") == PARENT_PLAN_SHA
            and sweep.digest(source_root/t8.PLAN) == PARENT_PLAN_SHA,
            "T9 plan does not preserve its accepted T8 parent")
    parent = t8.verify_plan(source_root)
    known = {t8.short_case_id(row["case_id"]): row for row in parent["cases"]}
    cases = sweep.entries(plan.get("cases"), "T9 planned cases")
    require(len(cases) == 6 and [row.get("storage_key") for row in cases] == CASE_ORDER,
            "T9 cases missing, duplicated or reordered")
    for row in cases:
        key = row["storage_key"]
        expected = dict(known[key], storage_key=key, service_reference_directory=f"{REFERENCE_ROOT}/{key}")
        require(row == expected, "T9 case changed the accepted T8 input or reference identity")
    anchor = plan.get("baseline_anchor", {})
    require(anchor.get("archive") == "evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip"
            and anchor.get("archive_sha256") == ANCHOR_SHA
            and type(anchor.get("expected_existing_traces_equal")) is bool
            and (not plan["policy_changes"] or anchor["expected_existing_traces_equal"] is False),
            "T9 accepted anchor or declared policy/equality expectation mismatch")
    return plan, parent


def verify_reference_snapshot(metadata, source_root):
    require(metadata.get("ReferenceFilesStableDuringRun") is True, "Reference stability unproven")
    before = sweep.entries(metadata.get("ReferenceFiles"), "initial reference files")
    after = sweep.entries(metadata.get("ReferenceFilesFinal"), "final reference files")
    require(before == after, "Reference files changed during MATLAB execution")
    trees = (REFERENCE_ROOT, CONTRACT_ROOT, "evidence/tranche-8-ns3-reference",
             "evidence/tranche-7-ns3-reference", "evidence/tranche-7-benchmark-inputs")
    expected = {f"{tree}/{relative}" for tree in trees for relative in t7.listed_files(source_root/tree)}
    expected.add("evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip")
    require(len(before) == len(expected) and {row.get("path") for row in before} == expected,
            "T9 reference snapshot membership mismatch")
    for row in before:
        path = sweep.safe_path(source_root, row["path"])
        require(path.stat().st_size == integer(row.get("bytes"), "reference bytes")
                and sweep.digest(path) == sweep.valid_hash(row.get("sha256"), "reference hash"),
                "Reference snapshot hash mismatch")
    return len(before)


def verify_nonperturbation(root, metadata, source, plan):
    """Independently rehash complete legacy observations for two controls."""
    record = sweep.json_object(root/"nonperturbation.json")
    require(record.get("schema") == "csr-ack-service-nonperturbation-v1"
            and record.get("status") == "completed" and record.get("passed") is True
            and record.get("planned_control_count") == 2 and record.get("completed_control_count") == 2
            and metadata.get("NonperturbationPassed") is True, "T9 observer-disabled controls did not complete")
    expected = {row["case_id"]: row for row in plan["cases"] if row["storage_key"] in CONTROL_KEYS}
    controls = sweep.entries(record.get("cases"), "T9 observer-disabled controls")
    require(len(controls) == 2 and {row.get("case_id") for row in controls} == set(expected),
            "T9 controls must contain c129 and a129 exactly once")
    for row in controls:
        key = expected[row["case_id"]]["storage_key"]
        require(row.get("observer_on_directory") == f"b/{key}/raw"
                and row.get("observer_off_directory") == f"c/{key}/raw"
                and row.get("statistics_equal") is True and row.get("config_equal") is True
                and row.get("passed") is True, "T9 observer control identity/result mismatch")
        on, off = (sweep.safe_path(root, row[name]) for name in ("observer_on_directory", "observer_off_directory"))
        enabled, disabled = (sweep.json_object(path/"case_manifest.json") for path in (on, off))
        require(disabled.get("schema") == "csr-matlab-research-case-v1" and disabled.get("status") == "completed"
                and disabled.get("execution_completed") is True and disabled.get("structural_checks_passed") is True
                and disabled.get("source_files_stable") is True and disabled.get("ns3_source_commit") == PIN
                and sweep.snapshot(disabled.get("source_files"), "control source") == source,
                "Observer-disabled raw case source/completion mismatch")
        require(all(disabled.get(field) == enabled.get(field) for field in
                    ("scenario", "scenario_sha256", "duration_s", "seed", "flow_limit", "run_options",
                     "application_profile", "mac_profile", "hop_security_profile")),
                "Observer-disabled raw case identity differs from enabled case")
        t7.inventory(off, disabled.get("files"), "T9 observer-disabled raw case",
                     excluded=("case_manifest.json",), local=disabled.get("local_files", []))
        left, right = (sweep.json_object(path/"summary.json") for path in (on, off))
        require(left["Statistics"] == right["Statistics"] and left["Config"] == right["Config"],
                "T9 observer changed statistics or configuration")
        require("LinkDiagnostics" not in right and "ServiceDiagnostics" not in right
                and not any((off/name).exists() for name in ("link_decisions.csv", "actual_feedback.csv", "service_trace.csv")),
                "Disabled T9 control contains enabled observer outputs")
        files = sweep.entries(row.get("compared_files"), "T9 nonperturbation comparisons")
        names = {*t8.UNCHANGED_CSV, "scenario.csv"}
        require(len(files) == len(names) and {entry.get("path") for entry in files} == names,
                "T9 nonperturbation comparison omitted unchanged evidence")
        for entry in files:
            require(entry.get("equal") is True
                    and sweep.digest(on/entry["path"]) == entry.get("observer_on_sha256")
                    and sweep.digest(off/entry["path"]) == entry.get("observer_off_sha256")
                    and entry["observer_on_sha256"] == entry["observer_off_sha256"],
                    "T9 observer on/off evidence differs or comparison hashes are unbound")
    return record


def csv_difference(first, second):
    """Report a bounded difference; preserve exact large integer semantics."""
    try:
        count = t8.equivalent_csv(first, second, "T8 baseline comparison")
        return {"semantic_equal": True, "semantic_records": count}
    except ValueError as failure:
        return {"semantic_equal": False, "first_difference": str(failure)}


def verify_anchor_configuration(before, after, case):
    """Bind the same input while permitting its installation root to move."""
    configs = [copy.deepcopy(before), copy.deepcopy(after)]
    paths = []
    suffix = PurePosixPath(case["scenario_file"]).parts
    for config in configs:
        shared = config.get("SharedScenario")
        require(isinstance(shared, dict) and shared.get("SourceSHA256") == case["scenario_sha256"],
                "T9 anchor configuration input hash differs from the accepted plan")
        path = shared.get("SourcePath")
        require(isinstance(path, str) and path, "T9 anchor configuration source path is missing")
        parts = PurePosixPath(path.replace("\\", "/")).parts
        require(".." not in parts and len(parts) > len(suffix) and parts[-len(suffix):] == suffix,
                "T9 anchor configuration source path does not identify the planned input")
        paths.append(shared.pop("SourcePath"))
    require(configs[0] == configs[1], "T9 changed accepted T8 experiment configuration")
    return {"field": "SharedScenario.SourcePath", "before": paths[0], "after": paths[1],
            "scenario_file": case["scenario_file"], "scenario_sha256": case["scenario_sha256"],
            "scope": "Only the installation prefix of this hash-bound input path may differ; all other configuration fields compare exactly."}


def verify_t8_anchors(root, source_root, plan):
    archive = source_root/plan["baseline_anchor"]["archive"]
    require(sweep.digest(archive) == ANCHOR_SHA, "Accepted T8 archive hash mismatch")
    cases = []
    with zipfile.ZipFile(archive) as bundle:
        for case in plan["cases"]:
            key = case["storage_key"]
            current = root/"b"/key
            prefix = f"b/{key}/"
            old_summary = json.loads(bundle.read(prefix+"raw/summary.json"))
            new_summary = sweep.json_object(current/"raw/summary.json")
            relocation = verify_anchor_configuration(old_summary["Config"], new_summary["Config"], case)
            files = []
            for name in t8.UNCHANGED_CSV:
                with bundle.open(prefix+"raw/"+name) as old, (current/"raw"/name).open(encoding="utf-8-sig", newline="") as new:
                    difference = csv_difference(io.TextIOWrapper(old, encoding="utf-8-sig", newline=""), new)
                files.append(dict(path=name, **difference))
            counts_old = t7.count_balance(old_summary["Statistics"], f"T8 {key}")
            counts_new = t7.count_balance(new_summary["Statistics"], f"T9 {key}")
            cases.append({"case_id": case["case_id"], "storage_key": key,
                          "statistics_equal": old_summary["Statistics"] == new_summary["Statistics"],
                          "configuration_equal": True,
                          "configuration_exact_equal": old_summary["Config"] == new_summary["Config"],
                          "configuration_path_relocation": relocation,
                          "before_counts": counts_old, "after_counts": counts_new,
                          "count_changes": {name: counts_new[name]-counts_old[name] for name in t7.COUNTS},
                          "files": files})
    equal = all(row["statistics_equal"] and all(file["semantic_equal"] for file in row["files"]) for row in cases)
    if plan["baseline_anchor"]["expected_existing_traces_equal"]:
        require(equal, "T9 observations changed despite a declared unchanged-behavior experiment")
    return {"archive_sha256": ANCHOR_SHA, "cases": cases, "comparison_completed": len(cases) == 6,
            "all_existing_observations_equal": equal,
            "policy_changes_declared": plan["policy_changes"],
            "equality_required": plan["baseline_anchor"]["expected_existing_traces_equal"],
            "scope": "All six accepted T8 fixtures are compared. Declared policy corrections permit differences; improvement is a separate scientific review."}


def verify_contract_rows(actual_path, reference_path):
    fields = ("case", "checkpoint", "time_seconds", "field", "actual", "expected", "pass")
    actual, reference = (list(t7.csv_records(path, fields)) for path in (actual_path, reference_path))
    require(reference and len(actual) == len(reference), "Contract checkpoint coverage mismatch")
    identity = lambda row: (row["case"], row["checkpoint"], row["field"])
    require(len({identity(row) for row in actual}) == len(actual)
            and len({identity(row) for row in reference}) == len(reference), "Duplicate contract checkpoint identity")
    require([identity(row) for row in actual] == [identity(row) for row in reference],
            "Contract checkpoint identity/order differs from pinned native execution")
    for observed, expected in zip(actual, reference):
        require(sweep.boolean(observed["pass"], "contract pass") and sweep.boolean(expected["pass"], "native contract pass"),
                "Controlled contract checkpoint failed")
        for field in ("time_seconds", "actual", "expected"):
            left, right = finite(observed[field], field), finite(expected[field], field)
            require(math.isclose(left, right, rel_tol=0, abs_tol=1e-9),
                    "Contract checkpoint differs from pinned native execution")
        require(math.isclose(finite(observed["actual"], "actual"), finite(observed["expected"], "expected"), rel_tol=0, abs_tol=1e-9)
                and math.isclose(finite(expected["actual"], "native actual"), finite(expected["expected"], "native expected"), rel_tol=0, abs_tol=1e-9),
                "Controlled contract actual/expected values disagree")
    return len(actual)


def case_summary(root, observations):
    rows = list(t7.csv_records(root/"benchmark_summary.csv", ("CaseId", "BaseCaseId", *t7.COUNTS, "Attempts", "AdmissionBlocked")))
    known = {row["case_id"]: row for row in observations}
    require(len(rows) == len(known) and {row["CaseId"] for row in rows} == set(known), "T9 summary membership mismatch")
    for row in rows:
        observed = known[row["CaseId"]]
        require(row["BaseCaseId"] == observed["base_case_id"]
                and t7.count_balance(row, row["CaseId"]) == observed["counts"]
                and integer(row["Attempts"], "attempts") == observed["admission"]["attempts"]
                and integer(row["AdmissionBlocked"], "blocked") == observed["admission"]["blocked"],
                "T9 summary differs from reconstructed application counts")


def verify_return(root, source_root):
    import tranche9_metrics as service

    root, source_root = Path(root).resolve(), Path(source_root).resolve()
    metadata = sweep.json_object(root/"validation_metadata.json")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 9, "Unsupported Tranche 9 schema")
    require(metadata.get("MatlabBaseCommit") == BASE and metadata.get("ValidatedTranche8CodeCommit") == T8_CODE,
            "Tranche 9 accepted baseline identity mismatch")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB"
            and isinstance(runtime.get("Version"), str) and runtime["Version"]
            and isinstance(runtime.get("Release"), str) and runtime["Release"], "Missing actual MATLAB runtime/release record")
    require(metadata.get("DiagnosticPlan") == "diagnostic_plan.json"
            and metadata.get("NonperturbationFile") == "nonperturbation.json"
            and metadata.get("ServiceWindowSeconds") == [300, 320]
            and metadata.get("ServiceWindowEndExclusive") is True
            and metadata.get("CrossSimulatorComparisonExecuted") is False
            and metadata.get("NumericalParityEstablished") is False, "T9 metadata artifact/window/comparison scope mismatch")
    source = t7.candidate_snapshot(source_root)
    t7.source_binding(metadata, source, runtime)
    t7.inventory(root, metadata.get("Artifacts"), "outer T9 diagnostic artifacts",
                 excluded=("validation_metadata.json", "tranche9_evidence.zip"), local=metadata.get("LocalArtifacts", []))
    source_hash = sweep.digest(root/"source_snapshot.json")
    require(metadata.get("SourceSnapshotSHA256") == source_hash
            and sweep.snapshot(json.loads((root/"source_snapshot.json").read_text()), "source snapshot") == source,
            "Source snapshot file binding mismatch")
    plan, parent_plan = verify_plan(source_root)
    require(metadata.get("DiagnosticPlanSHA256") == sweep.digest(source_root/PLAN)
            and sweep.digest(root/"diagnostic_plan.json") == sweep.digest(source_root/PLAN), "Returned T9 plan mismatch")
    reference_count = verify_reference_snapshot(metadata, source_root)
    t8.verify_reference_suite(source_root, parent_plan)
    reference = service.verify_reference_suite(source_root, plan)
    contracts = service.verify_contracts(root, source_root, metadata, verify_contract_rows)
    tests = t8.verify_tests(root, metadata, source_root)
    cases = {case["case_id"]: case for case in plan["cases"]}
    completed = sweep.entries(metadata.get("Cases"), "returned T9 diagnostic cases")
    require(len(completed) == 6 and [row.get("CaseId") for row in completed] == [row["case_id"] for row in plan["cases"]]
            and integer(metadata.get("PlannedCaseCount"), "planned cases") == 6
            and integer(metadata.get("CompletedCaseCount"), "completed cases") == 6,
            "T9 instrumented diagnostic cases missing, duplicated or reordered")
    observations, paths, metric_rows = [], [], []
    for item in completed:
        case = cases[item["CaseId"]]
        directory = sweep.safe_path(root, item["Directory"])
        reference_directory = sweep.safe_path(source_root, case["reference_directory"])
        require(sweep.json_object(directory/"benchmark_manifest.json").get("storage_key") == case["storage_key"],
                "T9 storage key differs from strict short-path mapping")
        observed = t7.verify_case(root, item, case, source, runtime, source_hash,
                                  expected_directory=f"b/{case['storage_key']}")
        compare.case_input_manifest(directory, reference_directory)
        observed["base_case_id"], observed["seed"] = case["base_case_id"], case["seed"]
        observed["matlab_applications"] = metrics.matlab_applications(directory, case)
        observed["ns3_applications"] = metrics.ns3_applications(reference_directory, case)
        observed["matlab_feedback"] = t8.verify_matlab_feedback(directory, case)
        observed["ns3_feedback"] = t8.verify_ns3_feedback(reference_directory, case)
        observed["matlab_service"] = service.verify_matlab_service(directory, case, plan)
        observed["ns3_service"] = service.verify_ns3_service(source_root/case["service_reference_directory"], case, plan)
        metric_rows.extend([observed["matlab_applications"], observed["ns3_applications"]])
        observations.append(observed)
        paths.append((directory, reference_directory))
    controls = verify_nonperturbation(root, metadata, source, plan)
    anchors = verify_t8_anchors(root, source_root, plan)
    case_summary(root, observations)
    full = tests["status"] == "passed" and controls["passed"] and contracts["passed"] and anchors["comparison_completed"]
    contention = [row for row in metric_rows if row["base_case_id"] == "three_node_contention_360"]
    report = {"schema": REVIEW_SCHEMA, "status": "structural_review_completed",
              "evidence_integrity_verified": True, "default_structural_gate_completed": full,
              "diagnostic_only": not full, "matlab_runtime": runtime, "tests": tests,
              "source_files_verified": len(source), "source_snapshot_sha256": source_hash,
              "metadata_sha256": sweep.digest(root/"validation_metadata.json"),
              "reference_files_verified": reference_count, "service_reference": reference,
              "cases": observations, "nonperturbation": controls, "deterministic_contracts": contracts,
              "accepted_tranche8_anchors": anchors, "contention_multiseed": metrics.multiseed_summary(contention),
              "admission_control_seed": 129, "acceptance_established": False,
              "numerical_parity_established": False, "population_equivalence_established": False,
              "limitations": ["MATLAB runtime is owner-returned evidence; this Python reviewer does not execute MATLAB.",
                              "No campus, retained scenario/sweep, native-backend or OPNET run is part of this gate.",
                              "Five contention seeds and one admission control are descriptive, with no statistical equivalence claim.",
                              "Pending MATLAB work and unclassified ns-3 unmatched sends remain explicit.",
                              "Early service traces cover the half-open 300 <= t < 320 second window; counts are not full-run service counts.",
                              "Matching deterministic subsystem contracts do not prove full-network protocol parity.",
                              "Feedback replacement means DATA-to-first-ACK intervals need not be residence times of one unchanged ACK."]}
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
        print(f"Reviewed six cases, two controls and deterministic contracts; default structural gate={report['default_structural_gate_completed']}. Acceptance requires review.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error, zipfile.BadZipFile) as failure:
        if created:
            result = {"schema": REVIEW_SCHEMA, "status": "structural_review_failed", "evidence_integrity_verified": False,
                      "default_structural_gate_completed": False, "acceptance_established": False,
                      "numerical_parity_established": False, "error_type": type(failure).__name__, "error": str(failure)}
            if args.evidence.is_file():
                result["uploaded_zip_sha256"] = sweep.digest(args.evidence)
            (output/"review-failure.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        print(f"Tranche 9 review failed: {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
