"""Fail-closed checks for passive feedback evidence and unchanged app output."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tranche8_ns3_tested", ROOT / "scripts/run_tranche8_ns3_diagnostics.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class TestTranche8Ns3Diagnostics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def row(self, stage="feedback_selection", **changes):
        row = dict(schema="csr-ns3-feedback-observation-v1", stage=stage, time_s="1.0",
                   node_id="1", peer_id="2", frame_type="ACK", hop_sequence="5", decision_id="1",
                   packet_uid="10", has_ack_window="1", ack_bitmap="18446744073709551615", dack_bitmap="0",
                   selected_rate_key_kbps="128", selected_power_dbm="22", incoming_rate_key_kbps="64",
                   incoming_power_dbm="24", actual_rate_key_kbps="64", actual_power_dbm="27", aggregate_id="9",
                   min_rate_key_kbps="8", max_rate_key_kbps="128", min_power_dbm="-36", max_power_dbm="33",
                   segment_index="1", segment_count="2")
        row.update(changes)
        return row

    def summarize(self, rows):
        path = self.root / "observer.csv"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return MOD.observer_summary(path)

    def test_selection_context_and_repeated_ota_are_separate(self):
        report = self.summarize([self.row(), self.row("ack_response_context"),
                                 self.row("ota_segment"), self.row("ota_segment", aggregate_id="10")])
        self.assertEqual(report["selection_count"], 1)
        self.assertEqual(report["ota_feedback_member_count"], 2)
        self.assertEqual(report["distinct_decisions_transmitted"], 1)
        self.assertEqual(report["actual_vs_selected_power_change_count"], 2)
        self.assertEqual(report["incoming_vs_selected_rate_difference_count"], 1)

    def test_ota_without_observed_construction_fails(self):
        with self.assertRaisesRegex(ValueError, "without selection"):
            self.summarize([self.row("ota_segment")])

    def test_feedback_uid_change_fails(self):
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.summarize([self.row(), self.row("ota_segment", packet_uid="11")])

    def test_large_bitmap_change_is_not_rounded_away(self):
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.summarize([self.row(), self.row("ota_segment", ack_bitmap="18446744073709551614")])

    def test_duplicate_construction_fails(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.summarize([self.row(), self.row()])

    def test_duplicate_incoming_context_fails(self):
        with self.assertRaisesRegex(ValueError, "repeated DATA"):
            self.summarize([self.row(), self.row("ack_response_context"), self.row("ack_response_context")])

    def test_same_ota_member_is_not_counted_twice(self):
        with self.assertRaisesRegex(ValueError, "Duplicate or invalid feedback OTA"):
            self.summarize([self.row(), self.row("ota_segment"), self.row("ota_segment")])

    def test_observer_nan_power_fails(self):
        with self.assertRaisesRegex(ValueError, "Invalid selected feedback"):
            self.summarize([self.row(selected_power_dbm="NaN")])

    def test_unavailable_incoming_power_is_not_a_difference(self):
        report = self.summarize([self.row(), self.row("ack_response_context", incoming_power_dbm="")])
        self.assertEqual(report["incoming_vs_selected_power_difference_count"], 0)

    def test_absent_control_incoming_context_is_not_zero(self):
        report = self.summarize([self.row(has_ack_window="0"), self.row("ota_segment", has_ack_window="0")])
        self.assertEqual(report["ordinary_data_context_count"], 0)
        self.assertEqual(report["incoming_vs_selected_rate_difference_count"], 0)

    def test_unknown_event_schema_fails(self):
        with self.assertRaisesRegex(ValueError, "Unknown feedback observer schema"):
            self.summarize([self.row(schema="future-v9")])

    def test_observer_on_off_output_difference_fails(self):
        for name in ("ns3-trace.csv", "app-admission-diagnostics.csv"):
            (self.root / name).write_text("unchanged\n")
            (self.root / ("off-" + name)).write_text("unchanged\n")
        self.assertEqual(MOD.compare_bytes(self.root, "", "off-")["status"], "passed")
        (self.root / "off-ns3-trace.csv").write_text("altered\n")
        with self.assertRaisesRegex(ValueError, "altered simulation"):
            MOD.compare_bytes(self.root, "", "off-")

    def test_closed_compressed_control_must_match_earlier_comparison(self):
        for name in ("ns3-trace.csv", "app-admission-diagnostics.csv"):
            (self.root / name).write_text("full original\n")
            (self.root / ("observer-off-" + name)).write_text("full original\n")
        record = {"nonperturbation": MOD.compare_bytes(self.root, "", "observer-off-"),
                  "compressed_artifacts": [], "control_compressed_artifacts": []}
        (self.root / "observer-off-ns3-trace.csv").write_text("truncated\n")
        MOD.compress_outputs(self.root, record)
        with self.assertRaisesRegex(ValueError, "changed after observer comparison"):
            MOD.validate_final_control_bindings(self.root, record)

    def test_source_hook_anchor_must_be_unique(self):
        for source in ("unmatched", "repeat repeat"):
            with self.assertRaisesRegex(ValueError, "not unique"):
                MOD.replace_once(source, "repeat", "hook")


if __name__ == "__main__":
    unittest.main()
