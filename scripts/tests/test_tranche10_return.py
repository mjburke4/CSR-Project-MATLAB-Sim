#!/usr/bin/env python3
"""Mutation checks for T10 gate scope, timing precision and raw provenance."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche10_return as review
import tranche10_metrics as timing

REPO = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)


class PlanAndGate(TemporaryCase):
    def source(self):
        source = self.root/"source"
        shutil.copytree(REPO/"scenarios", source/"scenarios")
        return source

    def test_fixed_plan_preserves_all_workloads_and_campus(self):
        plan, diagnostics, _ = review.verify_plan(REPO)
        self.assertEqual((len(plan["retained_cases"]), len(plan["sweep_cases"]), len(diagnostics["cases"])), (29, 18, 6))
        self.assertEqual((plan["campus"]["duration_s"], plan["campus"]["seed"]), (6000, 128))

    def mutate_plan(self, mutation, message):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        mutation(plan)
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, message):
            review.verify_plan(source)

    def test_duplicate_retained_identity_cannot_be_rehashed_away(self):
        self.mutate_plan(lambda plan: plan["retained_cases"].__setitem__(1, dict(plan["retained_cases"][0])), "retained cases")

    def test_changed_retained_factory_fails(self):
        self.mutate_plan(lambda plan: plan["retained_cases"][1].update(factory="csr.scenario.smallNetwork"), "retained cases")

    def test_reordered_sweep_seed_fails(self):
        self.mutate_plan(lambda plan: plan["sweep_cases"].reverse(), "sweep cases")

    def test_campus_cannot_be_shortened_under_the_same_label(self):
        self.mutate_plan(lambda plan: plan["campus"].update(duration_s=600), "campus fixture")

    def test_service_window_cannot_be_silently_extended(self):
        self.mutate_plan(lambda plan: plan.update(service_window_end_exclusive=False), "observer limits or boundaries")

    def test_numeric_logicals_are_not_execution_options(self):
        metadata = {"Options": {"RunTests": 1, "RunCampus": True}}
        with self.assertRaisesRegex(ValueError, "options"):
            review.verify_options(metadata)

    def test_requested_flags_must_match_actual_options(self):
        metadata = {"Options": {"RunTests": True, "RunCampus": False}, "TestsRequested": True, "CampusRequested": True}
        with self.assertRaisesRegex(ValueError, "request flags"):
            review.verify_options(metadata)

    def gate(self, *, full, tests="passed", campus="passed"):
        return review.verify_gate_claims({"FullAcceptanceGateExecuted": full, "DiagnosticOnly": not full},
            tests={"status": tests}, campus={"status": campus}, contracts={"passed": True},
            retained={"case_count": 29}, sweeps={"case_count": 18}, controls={"passed": True})

    def test_full_default_gate_requires_campus(self):
        with self.assertRaisesRegex(ValueError, "default gate"):
            self.gate(full=True, campus="not_run")

    def test_full_default_gate_requires_tests(self):
        with self.assertRaisesRegex(ValueError, "default gate"):
            self.gate(full=True, tests="not_run")

    def test_skipped_campus_is_diagnostic_only(self):
        self.assertFalse(self.gate(full=False, campus="not_run"))

    def test_all_phases_can_complete_structural_gate(self):
        self.assertTrue(self.gate(full=True))

    def test_blank_campus_struct_is_the_real_no_campus_runner_schema(self):
        metadata = {"Options": {"RunCampus": False}, "CampusExecuted": False,
                    "CampusCase": {"CaseId": "", "Directory": "", "ManifestSHA256": ""}}
        result, paths = review.verify_campus(self.root, REPO, metadata, {}, {}, "", {})
        self.assertEqual(result["status"], "not_run")
        self.assertFalse(paths)
        (self.root/"campus_summary.csv").write_text("hidden campus outcome")
        with self.assertRaisesRegex(ValueError, "Unrequested campus"):
            review.verify_campus(self.root, REPO, metadata, {}, {}, "", {})

    def test_skipped_tests_cannot_have_csv_or_execution_claim(self):
        source = self.root/"source"
        (source/"tests").mkdir(parents=True)
        metadata = {"Options": {"RunTests": False, "RunCampus": True}, "TestsRequested": False,
                    "TestsExecuted": False, "TestsPassed": False, "TestResultsFile": "tests/test_results.csv",
                    **{name: 0 for name in review.t7.TEST_COUNTS}}
        self.assertEqual(review.verify_tests(self.root, metadata, source)["status"], "not_run")
        (self.root/"tests").mkdir()
        (self.root/"tests/test_results.csv").write_text("stale test evidence")
        with self.assertRaisesRegex(ValueError, "Unrequested tests"):
            review.verify_tests(self.root, metadata, source)

    def test_test_membership_is_every_current_method_exactly_once(self):
        source = self.root/"source"
        (source/"tests").mkdir(parents=True)
        (source/"tests/TestA.m").write_text("classdef TestA\n    methods (Test)\n        function alpha(testCase)\n        end\n        function beta(testCase)\n        end\n    end\nend\n")
        rows = [dict(Name="TestA/"+name, Passed="1", Failed="0", Incomplete="0", DurationSeconds="0.1") for name in ("alpha", "beta")]
        write_csv(self.root/"tests/test_results.csv", rows)
        metadata = {"Options": {"RunTests": True, "RunCampus": True}, "TestsRequested": True, "TestsExecuted": True,
                    "TestsPassed": True, "TestCount": 2, "PassedTests": 2, "FailedTests": 0, "IncompleteTests": 0,
                    "TestResultsFile": "tests/test_results.csv"}
        self.assertEqual(review.verify_tests(self.root, metadata, source)["count"], 2)
        rows[1] = dict(rows[0])
        write_csv(self.root/"tests/test_results.csv", rows)
        with self.assertRaisesRegex(ValueError, "every candidate portable test"):
            review.verify_tests(self.root, metadata, source)


class ContractPrecision(TemporaryCase):
    def test_all_native_families_pass_complete_reference_checks(self):
        results = [review.verify_native_contract_reference(REPO, spec) for spec in review.CONTRACTS]
        self.assertEqual([row["checkpoint_count"] for row in results], [279, 154, 101])

    def mutate(self, mutation, message):
        reference = REPO/review.CONTRACTS[0]["directory"]/"checkpoints.csv"
        rows = list(review.t7.csv_records(reference))
        mutation(rows)
        write_csv(self.root/"actual.csv", rows)
        with self.assertRaisesRegex(ValueError, message):
            timing.exact_contract_rows(self.root/"actual.csv", reference)

    def test_one_nanosecond_time_shift_is_rejected(self):
        self.mutate(lambda rows: rows[0].update(time_seconds=str(timing.Decimal(rows[0]["time_seconds"])+timing.Decimal("1e-9"))), "differs")

    def test_claimed_pass_cannot_hide_changed_state(self):
        self.mutate(lambda rows: rows[0].update(actual=str(timing.Decimal(rows[0]["actual"])+1), **{"pass": "1"}), "differs")

    def test_reordered_rows_are_rejected(self):
        self.mutate(lambda rows: rows.reverse(), "identity/order")

    def test_relabelled_checkpoint_is_rejected(self):
        self.mutate(lambda rows: rows[0].update(checkpoint="replacement"), "identity/order")

    def test_deleted_row_is_rejected(self):
        self.mutate(lambda rows: rows.pop(), "coverage")

    def test_nonfinite_contract_value_is_rejected(self):
        self.mutate(lambda rows: rows[0].update(actual="NaN"), "finite")

    def test_large_integer_values_do_not_round_through_double(self):
        row = dict(case="uint64", checkpoint="exact", time_seconds="0.1", field="identity",
                   actual="9007199254740992", expected="9007199254740992", **{"pass": "1"})
        write_csv(self.root/"reference.csv", [row])
        altered = dict(row, actual="9007199254740993", expected="9007199254740993")
        write_csv(self.root/"actual.csv", [altered])
        with self.assertRaisesRegex(ValueError, "differs"):
            timing.exact_contract_rows(self.root/"actual.csv", self.root/"reference.csv")

    def test_decimal_printing_difference_below_picosecond_passes(self):
        row = dict(case="fractional", checkpoint="boundary", time_seconds="0.30000000000000004", field="delay_seconds",
                   actual="0.10000000000000001", expected="0.1", **{"pass": "1"})
        write_csv(self.root/"reference.csv", [row])
        write_csv(self.root/"actual.csv", [dict(row, time_seconds="0.3", actual="0.1")])
        self.assertEqual(timing.exact_contract_rows(self.root/"actual.csv", self.root/"reference.csv"), 1)

    def test_all_contract_families_must_be_present(self):
        metadata = {"ContractDirectory": "k", "ContractsExecuted": True, "ContractsPassed": True,
                    "ContractCases": [{"Kind": "mac"}, {"Kind": "ack"}]}
        with self.assertRaisesRegex(ValueError, "families missing"):
            review.verify_contracts(self.root, REPO, metadata)


class NativeBuildProvenance(TemporaryCase):
    def source(self):
        source = self.root/"source"
        for tree in (review.BUILD_ROOT, review.t9.CONTRACT_ROOT):
            shutil.copytree(REPO/tree, source/tree)
        (source/"scripts/ns3").mkdir(parents=True)
        shutil.copy2(REPO/"scripts/ns3/tranche9_ack_contract.cc", source/"scripts/ns3/tranche9_ack_contract.cc")
        shutil.copy2(REPO/review.NATIVE_BUILD, source/review.NATIVE_BUILD)
        return source

    def test_current_fresh_build_and_original_record_are_bound(self):
        self.assertEqual(review.verify_native_build(REPO)["status"], "passed")

    def test_unlisted_build_artifact_fails(self):
        source = self.source()
        (source/review.BUILD_ROOT/"unexpected.log").write_text("extra")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            review.verify_native_build(source)

    def test_rehashed_summary_cannot_claim_different_original_build(self):
        source = self.source()
        record = json.loads((source/review.NATIVE_BUILD).read_text())
        record["build_jobs"] += 1
        write_json(source/review.NATIVE_BUILD, record)
        with self.assertRaisesRegex(ValueError, "differs from the original"):
            review.verify_native_build(source)

    def test_reference_snapshot_uses_published_build_paths_and_covers_original_manifest(self):
        plan = json.loads((REPO/review.PLAN).read_text())
        entries = []
        for tree in plan["reference_directories"]:
            for name in review.t7.listed_files(REPO/tree):
                path = REPO/tree/name
                entries.append(dict(path=tree+"/"+name, sha256=review.sweep.digest(path), bytes=path.stat().st_size))
        entries.extend(plan["accepted_anchors"])
        entries.extend(plan["reference_files"])
        metadata = {"ReferenceFilesStableDuringRun": True, "ReferenceFiles": entries, "ReferenceFilesFinal": entries}
        self.assertEqual(review.verify_reference_snapshot(metadata, REPO, plan), 332)
        altered = copy.deepcopy(entries)
        entry = next(row for row in altered if row["path"].startswith(review.BUILD_ROOT+"/engine-logs/"))
        entry["path"] = entry["path"].removeprefix(review.BUILD_ROOT+"/")
        metadata.update(ReferenceFiles=altered, ReferenceFilesFinal=altered)
        with self.assertRaisesRegex(ValueError, "membership mismatch"):
            review.verify_reference_snapshot(metadata, REPO, plan)


class RetainedRawEvidence(TemporaryCase):
    def accepted(self, kind, name):
        with zipfile.ZipFile(REPO/timing.T7_ARCHIVE) as bundle:
            roots = timing.archive_roots(bundle)
            prefix = timing.baseline_path({"kind": kind, "name": name}, roots)
            root = self.root/"raw"
            root.mkdir(exist_ok=True)
            for filename in bundle.namelist():
                if PurePosixPath(filename).parent == prefix and filename.endswith((".json", ".csv")):
                    (root/PurePosixPath(filename).name).write_bytes(bundle.read(filename))
        return root, json.loads((root/"summary.json").read_text())

    def test_gateway_destination_rewrite_is_source_defined(self):
        directory, summary = self.accepted("routed", "gateway")
        self.assertEqual(timing.verify_raw_accounting(directory, summary)["counts"]["Received"], 3)
        summary["Config"]["Nwk"]["SendOnlyToGateway"] = False
        with self.assertRaisesRegex(ValueError, "delivery endpoint"):
            timing.verify_raw_accounting(directory, summary)

    def test_gateway_flag_does_not_permit_an_arbitrary_delivery_node(self):
        directory, summary = self.accepted("routed", "gateway")
        rows = list(review.t7.csv_records(directory/"protocol_trace.csv"))
        next(row for row in rows if row["Event"] == "app_receive")["NodeId"] = "3"
        write_csv(directory/"protocol_trace.csv", rows)
        with self.assertRaisesRegex(ValueError, "delivery endpoint"):
            timing.verify_raw_accounting(directory, summary)

    def test_nodeid_protocol_tables_are_distinct_from_id_summary(self):
        directory, summary = self.accepted("mac_hop", "reliable")
        self.assertEqual(timing.verify_raw_accounting(directory, summary)["counts"]["Received"], 6)
        rows = list(review.t7.csv_records(directory/"hop_nodes.csv"))
        rows[1]["NodeId"] = rows[0]["NodeId"]
        write_csv(directory/"hop_nodes.csv", rows)
        with self.assertRaisesRegex(ValueError, "protocol node membership"):
            timing.verify_raw_accounting(directory, summary)

    def test_missing_protocol_table_cannot_be_hidden_by_a_new_inventory(self):
        directory, summary = self.accepted("mac_hop", "reliable")
        (directory/"hop_nodes.csv").unlink()
        with self.assertRaisesRegex(ValueError, "required protocol outputs"):
            timing.verify_raw_accounting(directory, summary)

    def test_network_protocol_trace_is_required_even_if_trace_csv_survives(self):
        directory, summary = self.accepted("routed", "autonomous")
        (directory/"protocol_trace.csv").unlink()
        with self.assertRaisesRegex(ValueError, "required protocol outputs"):
            timing.verify_raw_accounting(directory, summary)

    def test_generated_unknown_node_is_rejected(self):
        directory, summary = self.accepted("foundation", "default")
        rows = list(review.t7.csv_records(directory/"trace.csv"))
        next(row for row in rows if row["Event"] == "app_generate")["NodeId"] = "99"
        write_csv(directory/"trace.csv", rows)
        with self.assertRaisesRegex(ValueError, "unconfigured node"):
            timing.verify_raw_accounting(directory, summary)

    def test_configured_count_counters_cannot_hide_missing_admission(self):
        directory, summary = self.accepted("shared", "two_node_8")
        rows = list(review.t7.csv_records(directory/"application_admission_statistics.csv"))
        rows[0].update(Attempts="2", Admitted="2")
        write_csv(directory/"application_admission_statistics.csv", rows)
        with self.assertRaisesRegex(ValueError, "counters disagree with generation"):
            timing.verify_raw_accounting(directory, summary)

    def test_duplicate_delivery_fails_even_if_counts_are_relabelled(self):
        directory, summary = self.accepted("foundation", "default")
        rows = list(review.t7.csv_records(directory/"trace.csv"))
        index = next(i for i, row in enumerate(rows) if row["Event"] == "app_receive")
        rows.insert(index+1, dict(rows[index]))
        write_csv(directory/"trace.csv", rows)
        with self.assertRaisesRegex(ValueError, "Duplicate delivery"):
            timing.verify_raw_accounting(directory, summary)

    def test_hash_bound_input_installation_prefix_may_move(self):
        directory, summary = self.accepted("shared", "two_node_8")
        before = summary["Config"]
        after = copy.deepcopy(before)
        after["SharedScenario"]["SourcePath"] = "D:\\csr10\\scenarios\\shared\\two_node_8.csv"
        result = timing.same_configuration(before, after, REPO)
        self.assertTrue(result["configuration_equal"])
        self.assertFalse(result["configuration_exact_equal"])
        self.assertIn("SourcePath", before["SharedScenario"])

    def test_changed_hash_or_other_path_cannot_hide_as_relocation(self):
        _, summary = self.accepted("shared", "two_node_8")
        before = summary["Config"]
        after = copy.deepcopy(before)
        after["SharedScenario"]["SourceSHA256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "input hash differs"):
            timing.same_configuration(before, after, REPO)
        after = copy.deepcopy(before)
        after["Seed"] = 129
        with self.assertRaisesRegex(ValueError, "experiment configuration"):
            timing.same_configuration(before, after, REPO)


class SafeReturn(TemporaryCase):
    def test_failure_cli_preserves_failure_report_and_original_upload(self):
        archive = self.root/"return.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("validation_metadata.json", json.dumps({"Schema": review.SCHEMA, "Tranche": 10, "Status": "failed"}))
        before = archive.read_bytes()
        output = self.root/"review"
        self.assertEqual(review.main(["--evidence", str(archive), "--source-root", str(REPO), "--output", str(output)]), 1)
        result = json.loads((output/"review-failure.json").read_text())
        self.assertFalse(result["acceptance_established"])
        self.assertFalse(result["default_structural_gate_completed"])
        self.assertEqual(archive.read_bytes(), before)

    def test_zip_path_traversal_fails_before_extracting(self):
        archive = self.root/"return.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.txt", "not evidence")
        with self.assertRaisesRegex(ValueError, "path"):
            with review.t7.evidence_directory(archive):
                self.fail("Unsafe archive was accepted")


if __name__ == "__main__":
    unittest.main()
