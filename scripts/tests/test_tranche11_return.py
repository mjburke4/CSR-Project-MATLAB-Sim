#!/usr/bin/env python3
"""Synthetic mutation tests for the return verifier, never MATLAB evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche11_return as gate


class SyntheticOnly(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="synthetic-t11-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_json(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def event_rows(self):
        # Artificial final snapshots exercise validation only; they are never
        # sent to review() and cannot establish a completed owner execution.
        rows = []
        for case in gate.CASES:
            for index, node in enumerate(gate.NODES, 1):
                row = {field: "0" for field in gate.EVENT_FIELDS}
                row.update(case=case, order=str(index), time_ns="8000000000", event="final", node=str(node))
                rows.append(row)
        return rows

    def draw_rows(self):
        rows, tape, usage = [], {}, []
        for case in gate.CASES:
            for node in gate.NODES:
                rows.append(dict(zip(gate.DRAW_FIELDS, (case, str(node), "1", "13000000", "0", "31", "3", "3", "prepare"))))
                for ordinal in range(1, 129):
                    tape[case, node, ordinal] = {"min": 0, "max": 31, "draw": 3}
                usage.append(dict(zip(gate.USAGE_FIELDS, (case, str(node), "128", "1", "127"))))
        return rows, tape, usage

    def test_safe_archive_rejects_parent_traversal_before_extraction(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as bundle:
            bundle.writestr("../outside", "no")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            with gate.evidence_directory(path):
                self.fail("Unsafe ZIP yielded")
        self.assertFalse((self.root.parent / "outside").exists())

    def test_safe_archive_rejects_case_collision(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as bundle:
            bundle.writestr("metadata.json", "{}")
            bundle.writestr("Metadata.json", "{}")
        with self.assertRaisesRegex(ValueError, "case-colliding"):
            with gate.evidence_directory(path):
                self.fail("Colliding ZIP yielded")

    def test_duplicate_json_key_is_not_silently_overwritten(self):
        path = self.root / "duplicate.json"
        path.write_text('{"passed":false,"passed":true}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            gate.json_object(path)

    def test_nonfinite_json_is_rejected(self):
        path = self.root / "bad.json"
        path.write_text('{"duration":NaN}')
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            gate.json_object(path)

    def test_inventory_rejects_unlisted_payload(self):
        path = self.write_json("reported.json", {})
        self.write_json("hidden.json", {})
        listed = [{"path": "reported.json", "sha256": gate.sha256(path), "bytes": path.stat().st_size}]
        with self.assertRaisesRegex(ValueError, "not closed"):
            gate.inventory(self.root, listed)

    def test_rehashing_metadata_cannot_hide_wrong_payload_size(self):
        path = self.write_json("payload.json", {"value": 1})
        listed = [{"path": "payload.json", "sha256": gate.sha256(path), "bytes": 1}]
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            gate.inventory(self.root, listed)

    def test_source_snapshot_cannot_omit_new_matlab_file(self):
        self.write_json("evidence/source-baseline.json", {})
        (self.root / "run.m").write_text("function run; end\n")
        expected = gate.candidate_snapshot(self.root)
        self.assertEqual(set(expected), {"run.m", "evidence/source-baseline.json"})
        (self.root / "new.m").write_text("function new; end\n")
        self.assertNotEqual(expected, gate.candidate_snapshot(self.root))

    def test_selected_tests_derive_methods_and_exclude_class_setup(self):
        directory = self.root / "tests"
        directory.mkdir()
        (directory / "TestSynthetic.m").write_text(
            "classdef TestSynthetic < matlab.unittest.TestCase\n"
            "    methods (TestClassSetup)\n        function setupCase(testCase)\n        end\n    end\n"
            "    methods (Test)\n        function exactIdentity(testCase)\n        end\n    end\nend\n")
        self.assertEqual(gate.selected_test_names(self.root, ["tests/TestSynthetic.m"]), ["TestSynthetic/exactIdentity"])

    def test_duplicate_event_order_fails_even_if_csv_is_rehashed(self):
        rows = self.event_rows()
        rows[1]["order"] = "1"
        with self.assertRaisesRegex(ValueError, "duplicate event order"):
            gate.validate_events(rows, label="synthetic")

    def test_missing_final_node_fails(self):
        rows = self.event_rows()[:-1]
        with self.assertRaisesRegex(ValueError, "incomplete final case"):
            gate.validate_events(rows, label="synthetic")

    def test_negative_and_nonfinite_time_fail(self):
        for value in ("-1", "nan", "inf"):
            with self.subTest(value=value):
                rows = self.event_rows()
                rows[0]["time_ns"] = value
                with self.assertRaises(ValueError):
                    gate.validate_events(rows, label="synthetic")

    def test_ordered_comparison_does_not_sort_away_first_divergence(self):
        native = self.event_rows()
        actual = copy.deepcopy(native)
        actual[0]["node"], actual[1]["node"] = actual[1]["node"], actual[0]["node"]
        result = gate.compare_rows(actual, native, gate.EVENT_FIELDS, family="events")
        self.assertFalse(result["matches_native"])
        self.assertEqual(result["unmatched_rows"], 2)
        self.assertEqual(result["differences"][0]["row"], 1)

    def test_one_ns_tolerance_is_explicit_but_two_ns_differs(self):
        native = self.event_rows()
        actual = copy.deepcopy(native)
        actual[0]["time_ns"] = "7999999999"
        result = gate.compare_rows(actual, native, gate.EVENT_FIELDS, family="events")
        self.assertTrue(result["matches_native"])
        self.assertEqual(result["nonzero_time_differences"], 1)
        actual[0]["time_ns"] = "7999999998"
        self.assertFalse(gate.compare_rows(actual, native, gate.EVENT_FIELDS, family="events")["matches_native"])

    def test_large_uint64_bitmap_is_compared_without_float_rounding(self):
        native = self.event_rows()
        native[0]["ack_bits"] = str(2**63)
        actual = copy.deepcopy(native)
        actual[0]["ack_bits"] = str(2**63+1)
        result = gate.compare_rows(actual, native, gate.EVENT_FIELDS, family="events")
        self.assertEqual(result["differences"][0]["fields"], ["ack_bits"])

    def test_missing_row_is_observed_as_mismatch(self):
        native = self.event_rows()
        result = gate.compare_rows(native[:-1], native, gate.EVENT_FIELDS, family="events")
        self.assertFalse(result["matches_native"])
        self.assertEqual(result["unmatched_rows"], 1)

    def test_requested_support_must_match_fixed_input(self):
        rows, tape, usage = self.draw_rows()
        rows[0]["max"] = "30"
        with self.assertRaisesRegex(ValueError, "support differs"):
            gate.validate_draws(rows, usage, tape, label="synthetic")

    def test_duplicate_draw_ordinal_fails(self):
        rows, tape, usage = self.draw_rows()
        rows.insert(1, dict(rows[0]))
        with self.assertRaisesRegex(ValueError, "duplicate or exhausted"):
            gate.validate_draws(rows, usage, tape, label="synthetic")

    def test_unresolved_draw_cannot_be_labeled_completed(self):
        rows, tape, usage = self.draw_rows()
        rows[0]["purpose"] = "unresolved"
        with self.assertRaisesRegex(ValueError, "unresolved"):
            gate.validate_draws(rows, usage, tape, label="synthetic")

    def test_unused_suffix_cannot_hide_consumption(self):
        rows, tape, usage = self.draw_rows()
        usage[0]["consumed"], usage[0]["unused"] = "2", "126"
        with self.assertRaisesRegex(ValueError, "suffix accounting"):
            gate.validate_draws(rows, usage, tape, label="synthetic")

    def test_usage_node_cannot_be_omitted(self):
        rows, tape, usage = self.draw_rows()
        with self.assertRaisesRegex(ValueError, "incomplete tape usage"):
            gate.validate_draws(rows, usage[:-1], tape, label="synthetic")


    def claims(self, matches=False):
        summary = {"DiagnosticCompleted": True, "Passed": True, "MatchesNative": matches,
                   "CaseCount": 4, "EventCount": 12, "DrawCount": 12,
                   "CheckpointCount": 56, "FailedCount": 0, "UnmatchedCount": 1}
        metadata = {"ReplayCompleted": True, "ReplayMatchesNative": matches, "ReplayCaseCount": 4,
                    "ReplayEventCount": 12, "ReplayDrawCount": 12, "ReplayUnmatchedCount": 1}
        return metadata, summary

    def test_numerical_mismatch_can_be_a_completed_diagnostic(self):
        metadata, summary = self.claims()
        matches, unmatched = gate.verify_replay_claims(metadata, summary, event_count=12, draw_count=12,
            checks=[{}] * 56, comparisons=[{"unmatched_rows": 1}])
        self.assertFalse(matches)
        self.assertEqual(unmatched, 1)

    def test_false_match_claim_cannot_override_observed_difference(self):
        metadata, summary = self.claims(matches=True)
        with self.assertRaisesRegex(ValueError, "native match claim"):
            gate.verify_replay_claims(metadata, summary, event_count=12, draw_count=12,
                checks=[{}] * 56, comparisons=[{"unmatched_rows": 1}])

    def test_summary_event_count_is_independently_computed(self):
        metadata, summary = self.claims()
        summary["EventCount"] = 11
        with self.assertRaisesRegex(ValueError, "summary EventCount"):
            gate.verify_replay_claims(metadata, summary, event_count=12, draw_count=12,
                checks=[{}] * 56, comparisons=[{"unmatched_rows": 1}])

    def test_metadata_unmatched_count_cannot_disagree_with_replay(self):
        metadata, summary = self.claims()
        metadata["ReplayUnmatchedCount"] = 0
        with self.assertRaisesRegex(ValueError, "metadata ReplayUnmatchedCount"):
            gate.verify_replay_claims(metadata, summary, event_count=12, draw_count=12,
                checks=[{}] * 56, comparisons=[{"unmatched_rows": 1}])

    def test_failed_return_never_establishes_execution_or_acceptance(self):
        self.write_json("source/" + gate.CANDIDATE, {"Schema": "csr-tranche-11-candidate-v1", "Tranche": 11,
                        "SourceCommit": gate.PIN, "Cases": list(gate.CASES), "CaseDurationSeconds": 8})
        archive = self.root / "failed.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("metadata.json", json.dumps({"Schema": gate.SCHEMA, "Tranche": 11, "Status": "failed"}))
        output = self.root / "review"
        self.assertEqual(gate.main(["--evidence", str(archive), "--source-root", str(self.root / "source"),
                                    "--output", str(output)]), 1)
        result = json.loads((output / "review.json").read_text())
        self.assertFalse(result["acceptance_established"])
        self.assertFalse(result["matlab_executed_by_reviewer"])
        self.assertFalse(result["focused_structural_gate_completed"])


if __name__ == "__main__":
    unittest.main()
