#!/usr/bin/env python3
"""Hostile/mutation tests using genuine native T13 output, never owner evidence.

These tests do not construct or accept a purported successful MATLAB archive.
Small in-memory counterfactuals exercise failure classification only.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche13_return as gate

SOURCE = Path(__file__).resolve().parents[2]


class ReturnedEvidenceMutations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = gate.json_object(SOURCE / gate.CANDIDATE)
        cls.plan, cls.tape, cls.offers = gate.verify_plan(SOURCE, cls.candidate)
        cls.actual = {name: gate.csv_rows(SOURCE / gate.REFERENCE / (name + ".csv"), fields)
                      for name, fields in gate.FAMILIES}
        cls.events = cls.actual["events"]
        cls.draws = cls.actual["draws"]
        cls.transport = cls.actual["transport"]
        cls.terminals = cls.actual["terminal"]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t13-mutation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_actual_native_reference_provenance_and_264_checks(self):
        _, record = gate.verify_native(SOURCE, self.candidate, self.plan, self.tape, self.offers)
        self.assertEqual(record["checkpoint_count"], 264)
        self.assertEqual(record["artifact_count"], 47)
        self.assertEqual(record["disabled_seam_checkpoints"], 255)
        self.assertEqual(record["self_tests"], 25)
        self.assertEqual(record["outcomes"]["delivered"], 384)

    def test_actual_generation_fifo_and_all_continued_polls_reconcile(self):
        record = gate.validate_events(self.events, self.offers, label="actual native")
        self.assertEqual(record, {"generated": 384, "admitted": 384, "delivered": 384, "remaining_demand": 0})

    def test_generation_cannot_be_silently_replaced_by_admission_time(self):
        events = copy.deepcopy(self.events)
        row = next(row for row in events if row["event"] == "generate" and row["app_id"] == "48")
        row["time_ns"] = str(int(row["time_ns"]) + 20_000_000)
        with self.assertRaises(ValueError):
            gate.validate_events(events, self.offers, label="mutated")

    def test_missing_generated_identity_is_rejected(self):
        offers = copy.deepcopy(self.offers[:-1])
        with self.assertRaisesRegex(ValueError, "generation differs"):
            gate.validate_events(self.events, offers, label="mutated")

    def test_duplicate_admitted_identity_is_rejected(self):
        events = copy.deepcopy(self.events)
        admits = [row for row in events if row["case"] == "ok" and row["event"] == "admit" and row["node"] == "4"]
        admits[1]["app_id"] = admits[0]["app_id"]
        with self.assertRaisesRegex(ValueError, "FIFO|duplicate"):
            gate.validate_events(events, self.offers, label="mutated")

    def test_duplicate_delivery_cannot_hide_behind_equal_total(self):
        events = copy.deepcopy(self.events)
        deliveries = [row for row in events if row["case"] == "ok" and row["event"] == "deliver" and row["app_source"] == "5"]
        deliveries[1]["app_id"] = deliveries[0]["app_id"]
        with self.assertRaisesRegex(ValueError, "duplicate/unadmitted delivery"):
            gate.validate_events(events, self.offers, label="mutated")

    def test_nsdp_admission_decision_requires_real_capacity(self):
        events = copy.deepcopy(self.events)
        row = next(row for row in events if row["event"] == "offer")
        row["nsdp4"] = "16"
        with self.assertRaisesRegex(ValueError, "NSDP16"):
            gate.validate_events(events, self.offers, label="mutated")

    def test_blocked_demand_poll_cannot_be_omitted_and_reindexed(self):
        events = copy.deepcopy(self.events)
        index = next(i for i, row in enumerate(events) if row["event"] == "blocked")
        del events[index - 1:index + 1]
        for case in gate.CASES:
            for order, row in enumerate([r for r in events if r["case"] == case], 1):
                row["order"] = str(order)
        with self.assertRaisesRegex(ValueError, "poll coverage"):
            gate.validate_events(events, self.offers, label="mutated")

    def test_missing_final_case_cannot_be_reviewed_as_complete(self):
        with self.assertRaisesRegex(ValueError, "incomplete final"):
            gate.validate_events([row for row in self.events if row["case"] != "out"], self.offers, label="mutated")

    def test_nonfinite_or_fractional_nanosecond_event_is_rejected(self):
        for value in ("NaN", "Inf", "-1", "0.5"):
            events = copy.deepcopy(self.events)
            events[0]["time_ns"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.validate_events(events, self.offers, label="mutated")

    def test_exact_full_width_bitmaps_survive_comparison(self):
        self.assertEqual(max(int(row["ack_bits"]) for row in self.events), 2**64 - 1)
        left = copy.deepcopy(self.events[:1]); right = copy.deepcopy(left)
        left[0]["ack_bits"], right[0]["ack_bits"] = str(2**63 + 1), str(2**63)
        result = gate.compare_rows(left, right, gate.EVENT_FIELDS, family="events")
        self.assertEqual(result["differences"][0]["fields"], ["ack_bits"])

    def test_float_rounded_uint64_max_is_rejected(self):
        events = copy.deepcopy(self.events)
        next(row for row in events if row["ack_bits"] == str(2**64 - 1))["ack_bits"] = str(int(float(2**64 - 1)))
        with self.assertRaisesRegex(ValueError, "uint64"):
            gate.validate_events(events, self.offers, label="mutated")

    def test_exact_raw_draw_cannot_be_replaced_by_resolved_slot(self):
        draws = copy.deepcopy(self.draws)
        draws[0]["draw"] = str((int(draws[0]["draw"]) + 1) % 32)
        with self.assertRaisesRegex(ValueError, "prescribed tape"):
            gate.validate_draws(draws, self.actual["usage"], self.tape, label="mutated")

    def test_unused_tape_suffix_requires_closed_accounting(self):
        usage = copy.deepcopy(self.actual["usage"])
        usage[0]["unused"] = str(int(usage[0]["unused"]) + 1)
        with self.assertRaisesRegex(ValueError, "unused tape suffix"):
            gate.validate_draws(self.draws, usage, self.tape, label="mutated")

    def test_resolved_slot_must_remain_in_fixed_support(self):
        draws = copy.deepcopy(self.draws)
        draws[0]["resolved"] = "32"
        with self.assertRaisesRegex(ValueError, "invalid draw resolution"):
            gate.validate_draws(draws, self.actual["usage"], self.tape, label="mutated")

    def test_unknown_or_duplicate_raw_draw_ordinal_is_rejected(self):
        draws = copy.deepcopy(self.draws)
        next(row for row in draws if row["ordinal"] == "2")["ordinal"] = "1"
        with self.assertRaisesRegex(ValueError, "duplicate, missing"):
            gate.validate_draws(draws, self.actual["usage"], self.tape, label="mutated")

    def test_actual_group_loss_and_ingress_are_independently_closed(self):
        self.assertEqual(gate.validate_transport(self.transport, self.events, label="native"),
                         {"ok": 0, "data": 2, "ack": 2, "out": 2})

    def test_first_data_policy_cannot_be_disabled_in_the_log(self):
        transport = copy.deepcopy(self.transport)
        row = next(row for row in transport if row["case"] == "data" and row["decision"] == "drop")
        row["decision"], row["reason"] = "pass", "none"
        with self.assertRaisesRegex(ValueError, "independent policy"):
            gate.validate_transport(transport, self.events, label="mutated")

    def test_second_feedback_group_cannot_be_dropped_as_first(self):
        transport = copy.deepcopy(self.transport)
        row = next(row for row in transport if row["case"] == "ack" and row["sender"] == "1" and row["decision"] == "pass")
        row["decision"], row["reason"] = "drop", "first_feedback"
        with self.assertRaisesRegex(ValueError, "independent policy"):
            gate.validate_transport(transport, self.events, label="mutated")

    def test_companion_segment_cannot_escape_whole_group_decision(self):
        transport = copy.deepcopy(self.transport)
        row = next(row for row in transport if int(row["group_segments"]) > 1)
        row["decision"] = "drop"
        with self.assertRaisesRegex(ValueError, "independent policy"):
            gate.validate_transport(transport, self.events, label="mutated")

    def test_aggregate_segment_cannot_be_omitted(self):
        transport = copy.deepcopy(self.transport[1:])
        with self.assertRaisesRegex(ValueError, "aggregate|receiver group"):
            gate.validate_transport(transport, self.events, label="mutated")

    def test_dropped_segment_cannot_be_injected_into_ingress(self):
        events = copy.deepcopy(self.events)
        row = next(row for row in events if row["event"] == "loss")
        row["event"] = "ingress_before"
        with self.assertRaisesRegex(ValueError, "loss ingress evidence"):
            gate.validate_transport(self.transport, events, label="mutated")

    def test_boundary_ambiguity_cannot_be_rounded_into_loss(self):
        transport = copy.deepcopy(self.transport)
        first = next(row for row in transport if row["case"] == "out")
        tx_id = first["tx_id"]
        for row in transport:
            if row["case"] == "out" and row["tx_id"] == tx_id:
                row["tx_time_ns"], row["arrival_ns"] = "8000000000", "8100000000"
        with self.assertRaisesRegex(ValueError, "ambiguous loss boundary"):
            gate.validate_transport(transport, self.events, label="mutated")

    def test_lost_ack_does_not_require_a_data_retransmission(self):
        rows = [r for r in self.transport if r["case"] == "ack" and r["kind"] == "DATA"]
        identities = [(r["sender"], r["app_source"], r["app_id"]) for r in rows]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertTrue(all(row["pass"] for row in gate.compute_checks(self.events, self.draws, self.transport, self.terminals)))

    def test_real_terminal_owners_are_distinct_from_app_delivery(self):
        result = gate.validate_terminals(self.terminals, self.events, label="native")
        self.assertEqual(result["terminal_owners"], 576)
        self.assertEqual(result["delivered"], 384)

    def test_undelivered_identity_requires_an_actual_failed_terminal(self):
        events = [row for row in self.events if not (row["case"] == "data" and row["event"] == "deliver"
                  and row["app_source"] == "5" and row["app_id"] == "1")]
        with self.assertRaisesRegex(ValueError, "no real terminal failure"):
            gate.validate_terminals(self.terminals, events, label="mutated")

    def test_fault_delivery_and_failed_retirement_may_legitimately_overlap(self):
        terminals = copy.deepcopy(self.terminals)
        row = next(row for row in terminals if row["case"] == "ack" and row["app_source"] == "5")
        row["success"], row["reason"] = "0", "retry_exhausted"
        result = gate.validate_terminals(terminals, self.events, label="in-memory failure classification")
        self.assertEqual(result["delivered_with_failed_retirement"], 1)
        self.assertEqual(result["genuine_undelivered_identities"], 0)

    def test_genuine_fault_loss_is_reported_instead_of_forcing_all_delivery(self):
        events = [row for row in self.events if not (row["case"] == "data" and row["event"] == "deliver"
                  and row["app_source"] == "5" and row["app_id"] == "1")]
        terminals = copy.deepcopy(self.terminals)
        row = next(row for row in terminals if row["case"] == "data" and row["app_source"] == "5" and row["app_id"] == "1")
        row["success"], row["reason"] = "0", "retry_exhausted"
        result = gate.validate_terminals(terminals, events, label="in-memory failure classification")
        self.assertEqual(result["genuine_undelivered_identities"], 1)
        self.assertEqual(result["unexplained"], 0)

    def test_no_loss_control_cannot_pass_as_all_retry_failures(self):
        events = [row for row in self.events if not (row["case"] == "ok" and row["event"] == "deliver")]
        terminals = copy.deepcopy(self.terminals)
        for row in terminals:
            if row["case"] == "ok":
                row["success"], row["reason"] = "0", "retry_exhausted"
        failed = [row for row in gate.compute_checks(events, self.draws, self.transport, terminals) if not row["pass"]]
        self.assertIn("control_delivery_failures", [row["checkpoint"] for row in failed])

    def test_success_cannot_be_relabelled_as_retry_exhaustion(self):
        terminals = copy.deepcopy(self.terminals)
        terminals[0]["reason"] = "retry_exhausted"
        with self.assertRaisesRegex(ValueError, "reason/success"):
            gate.validate_terminals(terminals, self.events, label="mutated")

    def test_terminal_requires_a_real_relay_owner(self):
        terminals = copy.deepcopy(self.terminals)
        row = next(row for row in terminals if row["app_source"] == "5")
        row["node"] = "4"
        with self.assertRaisesRegex(ValueError, "ownership"):
            gate.validate_terminals(terminals, self.events, label="mutated")

    def test_native_dack_normalization_requires_exact_raw_pair(self):
        raw = gate.csv_rows(SOURCE / gate.REFERENCE / "raw/ok/native.csv")
        raw = copy.deepcopy(raw)
        next(row for row in raw if row["event"] == "hop_completion" and row["reason"] == "dack")["success"] = "1"
        with self.assertRaisesRegex(ValueError, "reason/success pair"):
            gate.native_terminals(raw, "ok")

    def test_stable_capacity_cannot_hide_behind_successful_delivery(self):
        events = copy.deepcopy(self.events)
        row = next(row for row in events if row["event"] == "checkpoint" and row["dack_holds"] != "0")
        row["dack_holds"] = str(int(row["dack_holds"]) + 1)
        failed = [row["checkpoint"] for row in gate.compute_checks(events, self.draws, self.transport, self.terminals) if not row["pass"]]
        self.assertIn("stable_capacity_failures", failed)

    def test_queued_mac_feedback_at_stop_blocks_completion(self):
        events = copy.deepcopy(self.events)
        next(row for row in events if row["event"] == "final")["ack_queue"] = "1"
        failed = [row["checkpoint"] for row in gate.compute_checks(events, self.draws, self.transport, self.terminals) if not row["pass"]]
        self.assertIn("mac_ack_queue", failed)

    def test_comparison_retains_every_missing_suffix_row(self):
        result = gate.compare_rows(self.events[:-3], self.events, gate.EVENT_FIELDS, family="events")
        self.assertEqual(result["unmatched_rows"], 3)
        self.assertTrue(all(row["fields"] == ["missing_row"] for row in result["differences"]))

    def test_transport_timestamps_share_one_ns_tolerance_but_are_retained(self):
        left = copy.deepcopy(self.transport[:1]); right = copy.deepcopy(left)
        left[0]["tx_time_ns"] = str(int(left[0]["tx_time_ns"]) + 28)
        left[0]["arrival_ns"] = str(int(left[0]["arrival_ns"]) + 28)
        result = gate.compare_rows(left, right, gate.TRANSPORT_FIELDS, family="transport")
        self.assertEqual(result["differences"][0]["fields"], ["tx_time_ns", "arrival_ns"])
        self.assertEqual(result["maximum_time_difference_ns"], "28")

    def test_candidate_selects_88_real_methods_including_retained_72(self):
        names = gate.selected_test_names(SOURCE, self.candidate["TestFiles"])
        self.assertEqual(names, self.candidate["ExpectedTestNames"])
        self.assertEqual(len(names), 88)
        previous = gate.json_object(SOURCE / "evidence/t12/candidate.json")["ExpectedTestNames"]
        self.assertEqual(len(previous), 72)
        self.assertTrue(set(previous) <= set(names))

    def test_all_259_reviewed_sources_and_135_matlab_files_are_unchanged(self):
        snapshot = gate.record_map(gate.json_value(SOURCE / gate.BASELINE), "baseline")
        self.assertEqual(len(snapshot), 259)
        self.assertEqual(sum(name.endswith(".m") for name in snapshot), 135)
        for name, record in snapshot.items():
            self.assertEqual(gate.sha256(SOURCE / name), record["sha256"], name)

    def test_manifest_cannot_hide_an_unlisted_artifact(self):
        directory = self.root / "native"; directory.mkdir()
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps({"schema": "test", "files": {}}))
        (directory / "unlisted.csv").write_text("extra\n")
        with self.assertRaisesRegex(ValueError, "not closed"):
            gate.verify_manifest(self.root, "native/manifest.json", gate.sha256(manifest), "test")

    def test_native_manifest_cannot_include_itself(self):
        directory = self.root / "native"; directory.mkdir()
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps({"schema": "test", "files": {"manifest.json": "0" * 64}}))
        with self.assertRaisesRegex(ValueError, "not closed"):
            gate.verify_manifest(self.root, "native/manifest.json", gate.sha256(manifest), "test")

    def test_duplicate_json_keys_are_rejected(self):
        path = self.root / "bad.json"; path.write_text('{"Passed":true,"Passed":false}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            gate.json_object(path)

    def test_zip_parent_traversal_is_rejected(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../escape", "bad")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            with gate.evidence_directory(path):
                self.fail("Hostile archive yielded")

    def test_zip_case_collision_is_rejected(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("rows.csv", "bad"); archive.writestr("ROWS.csv", "bad")
        with self.assertRaisesRegex(ValueError, "case-colliding"):
            with gate.evidence_directory(path):
                self.fail("Hostile archive yielded")

    def test_zip_symlink_is_rejected(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as archive:
            member = zipfile.ZipInfo("link"); member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, "outside")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            with gate.evidence_directory(path):
                self.fail("Hostile archive yielded")


if __name__ == "__main__":
    unittest.main()
