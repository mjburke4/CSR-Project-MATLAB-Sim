#!/usr/bin/env python3
"""Mutation tests for T12 return verification, never MATLAB execution evidence.

Tests mutate in-memory copies of the genuine native fixture or tiny hostile
inputs. They never construct, label or accept a successful MATLAB owner ZIP.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche12_return as gate

SOURCE = Path(__file__).resolve().parents[2]


class MutationsOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = gate.csv_rows(SOURCE / gate.RELAY_REFERENCE / "events.csv", gate.RELAY_FIELDS)
        cls.draws = gate.csv_rows(SOURCE / gate.RELAY_REFERENCE / "draws.csv", gate.DRAW_FIELDS)
        cls.usage = gate.csv_rows(SOURCE / gate.RELAY_REFERENCE / "usage.csv", gate.USAGE_FIELDS)
        cls.candidate = gate.json_object(SOURCE / gate.CANDIDATE)
        _, cls.tape = gate.verify_relay_plan(SOURCE, cls.candidate)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t12-mutation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_real_native_capacity_holds_are_accounted_at_sixteen_seconds(self):
        gate.validate_relay_events(self.events, label="real native")
        checks = gate.compute_relay_checks(self.events, self.draws)
        self.assertEqual(len(checks), 164)
        self.assertTrue(all(row["pass"] for row in checks))
        holds = {case: sum(int(row["dack_holds"]) for row in self.events
                          if row["case"] == case and row["event"] == "checkpoint") for case in gate.RELAY_CASES}
        self.assertEqual(holds, {"relay": 0, "local": 0, "mix": 4, "sw": 1})

    def test_ack_release_callback_offset_is_distinct_from_stable_capacity(self):
        offsets = [int(row["resend_queue"]) + int(row["dack_holds"]) - int(row["hop_pending"])
                   for row in self.events if row["event"] == "release"]
        self.assertEqual(offsets.count(1), 175)
        self.assertEqual(offsets.count(0), 5)
        self.assertTrue(all(row["pass"] for row in gate.compute_relay_checks(self.events, self.draws)))

    def test_mutated_stable_capacity_cannot_hide_behind_valid_final_delivery(self):
        events = copy.deepcopy(self.events)
        next(row for row in events if row["event"] == "checkpoint" and row["case"] == "mix" and row["node"] == "4")["dack_holds"] = "0"
        with self.assertRaisesRegex(ValueError, "Stable HOP"):
            gate.compute_relay_checks(events, self.draws)

    def test_unexpired_final_dack_hold_does_not_pass_structural_checks(self):
        events = copy.deepcopy(self.events)
        row = next(row for row in events if row["event"] == "final" and row["case"] == "mix" and row["node"] == "4")
        row["hop_pending"] = row["dack_holds"] = "1"
        failed = [row["checkpoint"] for row in gate.compute_relay_checks(events, self.draws) if not row["pass"]]
        self.assertIn("dack_holds", failed)
        self.assertIn("hop_pending", failed)

    def test_missing_checkpoint_node_is_rejected(self):
        events = copy.deepcopy([row for row in self.events if not (row["event"] == "checkpoint" and row["node"] == "5" and row["case"] == "sw")])
        for case in gate.RELAY_CASES:
            for order, row in enumerate([row for row in events if row["case"] == case], 1):
                row["order"] = str(order)
        with self.assertRaisesRegex(ValueError, "incomplete final relay case"):
            gate.validate_relay_events(events, label="mutated")

    def test_duplicate_event_order_rejects_rehashed_trace(self):
        events = copy.deepcopy(self.events)
        events[1]["order"] = events[0]["order"]
        with self.assertRaisesRegex(ValueError, "duplicate relay event order"):
            gate.validate_relay_events(events, label="mutated")

    def test_wrong_source_identity_cannot_turn_relayed_into_local_delivery(self):
        events = copy.deepcopy(self.events)
        next(row for row in events if row["event"] == "deliver" and row["case"] == "relay")["app_source"] = "5"
        with self.assertRaisesRegex(ValueError, "delivery"):
            gate.validate_relay_events(events, label="mutated")

    def test_duplicate_delivered_identity_is_rejected(self):
        events = copy.deepcopy(self.events)
        delivered = [row for row in events if row["event"] == "deliver" and row["case"] == "relay"]
        delivered[1]["app_id"] = delivered[0]["app_id"]
        with self.assertRaisesRegex(ValueError, "duplicate, unadmitted"):
            gate.validate_relay_events(events, label="mutated")

    def test_missing_last_case_cannot_be_compared_as_a_complete_run(self):
        with self.assertRaisesRegex(ValueError, "incomplete final relay case"):
            gate.validate_relay_events([row for row in self.events if row["case"] != "sw"], label="mutated")

    def test_nonfinite_and_negative_times_are_rejected(self):
        for value in ("NaN", "Inf", "-1"):
            events = copy.deepcopy(self.events)
            events[0]["time_ns"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.validate_relay_events(events, label="mutated")

    def test_raw_draw_cannot_change_even_if_resolved_slot_matches(self):
        draws = copy.deepcopy(self.draws)
        draws[0]["draw"] = str((int(draws[0]["draw"]) + 1) % 32)
        with self.assertRaisesRegex(ValueError, "prescribed tape"):
            gate.validate_relay_draws(draws, self.usage, self.tape, label="mutated")

    def test_wrong_draw_support_is_rejected(self):
        draws = copy.deepcopy(self.draws)
        draws[0]["max"] = "32"
        with self.assertRaisesRegex(ValueError, "prescribed tape"):
            gate.validate_relay_draws(draws, self.usage, self.tape, label="mutated")

    def test_duplicate_draw_ordinal_is_rejected(self):
        draws = copy.deepcopy(self.draws)
        row = next(row for row in draws if row["ordinal"] == "2")
        row["ordinal"] = "1"
        with self.assertRaisesRegex(ValueError, "draw ordinal"):
            gate.validate_relay_draws(draws, self.usage, self.tape, label="mutated")

    def test_unused_tape_suffix_must_reconcile_with_actual_consumption(self):
        usage = copy.deepcopy(self.usage)
        usage[0]["unused"] = str(int(usage[0]["unused"]) + 1)
        with self.assertRaisesRegex(ValueError, "unused suffix"):
            gate.validate_relay_draws(self.draws, usage, self.tape, label="mutated")

    def test_unobserved_node_still_requires_tape_accounting(self):
        with self.assertRaisesRegex(ValueError, "incomplete raw tape"):
            gate.validate_relay_draws(self.draws, self.usage[:-1], self.tape, label="mutated")

    def test_comparison_retains_full_unmatched_suffix(self):
        result = gate.compare_rows(self.events[:-3], self.events, gate.RELAY_FIELDS, family="relay")
        self.assertEqual(result["unmatched_rows"], 3)
        self.assertFalse(result["matches_native"])
        self.assertTrue(all(row["fields"] == ["missing_row"] for row in result["differences"]))

    def test_uint64_bitmaps_are_not_rounded_through_float(self):
        actual = copy.deepcopy(self.events[:1]); native = copy.deepcopy(actual)
        actual[0]["ack_bits"] = str(2**63 + 1); native[0]["ack_bits"] = str(2**63)
        result = gate.compare_rows(actual, native, gate.RELAY_FIELDS, family="relay")
        self.assertEqual(result["differences"][0]["fields"], ["ack_bits"])

    def test_clock_continuous_residual_is_not_rounded_or_waived(self):
        native, matlab = gate.clock_expected_events(matlab=False), gate.clock_expected_events(matlab=True)
        comparison = gate.compare_rows(matlab, native, gate.CLOCK_FIELDS, family="clock", time_tolerance_ns=0)
        self.assertEqual(comparison["unmatched_rows"], 3)
        self.assertEqual(sum(len(row["fields"]) for row in comparison["differences"]), 4)
        self.assertTrue(all(row["matlab"]["case"] == "continuous" for row in comparison["differences"]))

    def test_clock_counter_mismatch_cannot_hide_behind_equal_timestamps(self):
        events = gate.clock_expected_events(matlab=True)
        events[0]["local_counter"] = "15"
        with self.assertRaisesRegex(ValueError, "local_counter"):
            gate.validate_clock_events(events, matlab=True, label="mutated")

    def test_clock_case_reordering_is_rejected(self):
        events = gate.clock_expected_events(matlab=True)
        events[0], events[1] = events[1], events[0]
        with self.assertRaisesRegex(ValueError, "reordered clock"):
            gate.validate_clock_events(events, matlab=True, label="mutated")

    def test_clock_integer_time_requires_exact_nanoseconds(self):
        events = gate.clock_expected_events(matlab=True)
        events[0]["time_ns"] = str(int(events[0]["time_ns"]) + 1)
        with self.assertRaisesRegex(ValueError, "time_ns"):
            gate.validate_clock_events(events, matlab=True, label="mutated")

    def test_clock_check_cannot_report_pass_for_a_failed_value(self):
        events = gate.clock_expected_events(matlab=False)
        checks = gate.csv_rows(SOURCE / gate.CLOCK_REFERENCE / "checks.csv", gate.CLOCK_CHECK_FIELDS)
        checks[0]["actual"] = "15"
        with self.assertRaisesRegex(ValueError, "contradicts independently"):
            gate.verify_clock_checks(checks, events, matlab=False)

    def boundary_vectors(self):
        # Independently fixed IEEE754 endpoint from the reviewed native/MATLAB
        # operation sequence; do not derive the duration with the gate helper.
        tick = struct.unpack(">d", bytes.fromhex("4000178dd616f86a"))[0]
        continuous = struct.unpack(">d", bytes.fromhex("4000178dd616f86b"))[0]
        rows = []
        for case in gate.CLOCK_CASES:
            arrival = continuous if case == "continuous" else (2011501000 + {"before": -1, "after": 1}.get(case, 0)) / 1e9
            rows.append({"case": case, "arrival_seconds_hex": struct.pack(">d", arrival).hex(),
                         "tick_seconds_hex": "4000178dd616f86a", "arrival_minus_tick_seconds": str(arrival - tick),
                         "transport_quantized": str(int(case == "quantized")), "late_insertion": str(int(case == "tie_late"))})
        return rows

    def test_binary64_reconstruction_uses_operational_rate_not_128000(self):
        offsets = gate.verify_boundaries(self.boundary_vectors())
        self.assertEqual(offsets["continuous"], "4.440892098500626E-16")
        self.assertEqual(offsets["quantized"], "0.0")

    def test_rounding_continuous_boundary_cannot_erase_clock_residual(self):
        rows = self.boundary_vectors()
        rows[4]["arrival_seconds_hex"] = rows[4]["tick_seconds_hex"]
        rows[4]["arrival_minus_tick_seconds"] = "0"
        with self.assertRaisesRegex(ValueError, "binary64 arrival"):
            gate.verify_boundaries(rows)

    def test_clock_transport_quantization_cannot_be_applied_globally(self):
        rows = self.boundary_vectors()
        rows[0]["transport_quantized"] = "1"
        with self.assertRaisesRegex(ValueError, "transport/FIFO scope"):
            gate.verify_boundaries(rows)

    def test_candidate_selects_exact_72_methods_including_retained_52(self):
        selected = gate.selected_test_names(SOURCE, self.candidate["TestFiles"])
        self.assertEqual(selected, self.candidate["ExpectedTestNames"])
        self.assertEqual(len(selected), 72)
        previous = gate.json_object(SOURCE / "evidence/tranche-11-candidate.json")["ExpectedTestNames"]
        self.assertEqual(len(previous), 52)
        self.assertTrue(set(previous) <= set(selected))

    def test_native_manifest_must_exclude_itself(self):
        folder = self.root / "native"; folder.mkdir()
        path = folder / "manifest.json"
        path.write_text(json.dumps({"schema": "test", "files": {"manifest.json": "0" * 64}}))
        with self.assertRaisesRegex(ValueError, "not closed"):
            gate.verify_manifest(self.root, "native/manifest.json", gate.sha256(path), "test")

    def test_native_manifest_cannot_hide_unlisted_output(self):
        folder = self.root / "native"; folder.mkdir()
        path = folder / "manifest.json"
        path.write_text(json.dumps({"schema": "test", "files": {}}))
        (folder / "unlisted.csv").write_text("extra\n")
        with self.assertRaisesRegex(ValueError, "not closed"):
            gate.verify_manifest(self.root, "native/manifest.json", gate.sha256(path), "test")

    def test_zip_parent_traversal_is_rejected(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../outside", "hostile")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            with gate.evidence_directory(path):
                self.fail("Hostile archive was yielded")

    def test_zip_symlink_is_rejected(self):
        path = self.root / "bad.zip"; link = zipfile.ZipInfo("link")
        link.create_system = 3; link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(link, "outside")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            with gate.evidence_directory(path):
                self.fail("Symlink archive was yielded")

    def test_duplicate_json_cannot_rewrite_completion_claim(self):
        path = self.root / "claims.json"
        path.write_text('{"Passed":false,"Passed":true}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            gate.json_object(path)

    def test_false_exact_comparison_claim_is_rejected(self):
        comparison = gate.compare_rows(self.events[:-1], self.events, gate.RELAY_FIELDS, family="relay")
        claim = {"ReferencePresent": True, "SchemaMatches": True, "ActualRows": len(self.events) - 1,
                 "ReferenceRows": len(self.events), "ComparedRows": len(self.events),
                 "UnmatchedCount": 0, "FirstUnmatchedRow": 0, "MaximumTimeDifferenceNanoseconds": 0}
        with self.assertRaisesRegex(ValueError, "UnmatchedCount"):
            gate.verify_comparison_claim(claim, comparison, "mutated")

    def test_false_timing_maximum_is_rejected(self):
        actual = copy.deepcopy(self.events[:1]); actual[0]["time_ns"] = "1"
        comparison = gate.compare_rows(actual, self.events[:1], gate.RELAY_FIELDS, family="relay")
        claim = {"ReferencePresent": True, "SchemaMatches": True, "ActualRows": 1, "ReferenceRows": 1,
                 "ComparedRows": 1, "UnmatchedCount": 0, "FirstUnmatchedRow": 0, "MaximumTimeDifferenceNanoseconds": 0}
        with self.assertRaisesRegex(ValueError, "maximum timing"):
            gate.verify_comparison_claim(claim, comparison, "mutated")

    def test_nonfinite_csv_numbers_and_boolean_integers_are_rejected(self):
        for value in ("NaN", "Infinity", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.integer(value, "mutated")


if __name__ == "__main__":
    unittest.main()
