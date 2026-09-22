"""Regression checks for boundaries, lifecycle reopening, and censoring."""
import tempfile
import unittest
from pathlib import Path

from analyze_drain import (QueueAudit, admit_record, analyze, app_record,
                           digest, outcome_at, qualify, quantile,
                           read_matlab, summarize_apps, validate_admissions, write_csv, write_json)


class DrainAccountingTests(unittest.TestCase):
    def test_stop_snapshot_includes_events_at_stop_and_drain_area(self):
        queue = QueueAudit(10, 20, 40)
        queue.update("enqueue", "a", 12)
        queue.update("enqueue", "b", 15)
        queue.update("admit", "a", 20)
        queue.update("admit", "b", 25)
        result = queue.finish(0)
        self.assertEqual(result["waiting_at_traffic_stop"], 1)
        self.assertEqual(result["waiting_at_end"], 0)
        self.assertAlmostEqual(result["mean_waiting_during_traffic"], 1.3)
        self.assertAlmostEqual(result["mean_waiting_during_drain"], .25)

    def test_queue_censored_owner_is_not_completed_wait(self):
        queue = QueueAudit(10, 20, 40)
        queue.update("enqueue", "a", 12)
        queue.update("enqueue", "b", 13)
        queue.update("release", "a", 25)
        result = queue.finish(1)
        self.assertEqual(result["completed_nwk_wait"]["n"], 0)
        self.assertEqual(result["released_without_admit"], 1)
        self.assertEqual(result["pending_nwk_wait_age"]["max_s"], 27)
        with self.assertRaisesRegex(ValueError, "without NWK enqueue"):
            QueueAudit(10, 20, 40).update("admit", "unknown", 15)

    def test_custody_reopen_means_final_drop_time_cannot_infer_cutoff_state(self):
        app = app_record("a", 2, 1, 11)
        app.update(events=[(11, "pending"), (15, "dropped"), (19, "pending"), (30, "delivered")],
                   outcome="delivered", terminal_s=30, received_s=30, latency_s=19)
        self.assertEqual(outcome_at(app, 16), "dropped")
        self.assertEqual(outcome_at(app, 20), "pending")
        result = summarize_apps([app], 1, 20, 40)
        self.assertEqual(result["outstanding_at_traffic_stop"], 1)
        self.assertEqual(result["delivered_during_drain"], 1)
        self.assertEqual(result["drain_time_to_last_terminal_s"], 10)

    def test_native_unresolved_never_invented_pending_or_drop(self):
        app = app_record("a", 2, 1, 11)
        app.update(outcome="unresolved", events=[(11, "unresolved")])
        result = summarize_apps([app], 1, 20, 40, native=True)
        self.assertIsNone(result["pending"])
        self.assertIsNone(result["explicit_dropped"])
        self.assertEqual(result["native_unresolved"], 1)
        self.assertFalse(result["all_terminal_by_end"])
        self.assertIsNone(result["drain_time_to_last_terminal_s"])
        self.assertEqual(result["delivered_latency"]["n"], 0)

    def test_attempt_cap_counts_blocked_attempts_and_forbids_cutoff_attempt(self):
        case = {"traffic_start_s": 10, "traffic_stop_s": 30, "duration_s": 40,
                "interval_s": 10, "expected_attempts": 2,
                "source_starts": [{"source": 2, "start_s": 11}]}
        apps = {"a": app_record("a", 2, 1, 11)}
        accepted = admit_record(2, 1, 0, 1, 11, True, "admitted", "a", 0, 0)
        blocked = admit_record(2, 1, 0, 2, 21, False, "nsdp_full", None, 16, 0)
        self.assertTrue(validate_admissions(apps, [accepted, blocked], case))
        blocked["time_s"] = 30
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_admissions(apps, [accepted, blocked], case)

    def test_per_source_failure_cannot_be_hidden_by_pooling(self):
        good = {"blocked_fraction": 0, "delivery_fraction": 1, "all_terminal_by_end": True}
        bad = {"source": 7, "blocked_fraction": .1, "delivery_fraction": 1, "all_terminal_by_end": True}
        policy = {"max_blocked_fraction": .01, "max_waiting_queue_depth": 4, "min_delivered_fraction": .95}
        result = qualify(good, [bad], {2: {"peak_waiting": 1, "waiting_at_end": 0}}, policy)
        self.assertFalse(result["qualified"])
        self.assertFalse(result["criteria"]["each_source_passes"])

    def test_linear_quantiles_include_single_and_empty_samples(self):
        self.assertIsNone(quantile([], .95))
        self.assertEqual(quantile([7], .95), 7)
        self.assertAlmostEqual(quantile([0, 10], .95), 9.5)

    def test_matlab_reader_uses_exported_raw_nodes_and_actual_csv_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            raw.mkdir()
            write_csv(raw / "nodes.csv", [{"Id": 1, "WaitingForHop": 0}, {"Id": 2, "WaitingForHop": 0}])
            events = [{"TimeSeconds": 2, "Event": "app_generate", "NodeId": 2, "PeerId": 1, "PacketId": 1, "ApplicationBytes": 185},
                      {"TimeSeconds": 2, "Event": "network_enqueue", "NodeId": 2, "PeerId": 1, "PacketId": 1, "ApplicationBytes": 185},
                      {"TimeSeconds": 3, "Event": "hop_admit", "NodeId": 2, "PeerId": 1, "PacketId": 1, "ApplicationBytes": 185},
                      {"TimeSeconds": 10, "Event": "app_receive", "NodeId": 1, "PeerId": 2, "PacketId": 1, "ApplicationBytes": 185}]
            write_csv(raw / "protocol_trace.csv", events)
            write_csv(root / "applications.csv", [{"PacketId": 1, "SourceId": 2, "DestinationId": 1,
                                                   "GeneratedSeconds": 2, "Outcome": "delivered", "LatencySeconds": 8}])
            write_csv(raw / "application_admission_trace.csv", [{"SourceId": 2, "ConfiguredDestinationId": 1,
                        "FlowIndex": 1, "AttemptIndex": 1, "TimeSeconds": 2, "Accepted": 1, "Reason": "admitted",
                        "PacketId": 1, "NsdpCount": 0, "NwkQueueSize": 0}])
            write_csv(raw / "application_admission_statistics.csv", [{"FlowIndex": 1, "Attempts": 1,
                                                                     "Admitted": 1, "BlockedNsdp": 0}])
            apps, admissions, queues, _ = read_matlab(root, {"traffic_start_s": 0, "traffic_stop_s": 10, "duration_s": 20})
            self.assertEqual(len(admissions), 1)
            self.assertEqual(apps["1"]["latency_s"], 8)
            self.assertEqual(queues[2]["completed_nwk_wait"]["mean_s"], 1)
            summary = summarize_apps(list(apps.values()), 1, 10, 20)
            self.assertEqual(summary["delivered_during_drain"], 0)

    def test_missing_failed_cases_preserve_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "native"
            root.mkdir()
            plan = {"cases": [{"id": "a", "seed": 128, "traffic_start_s": 10,
                              "traffic_stop_s": 20, "duration_s": 40,
                              "interval_s": 10, "expected_attempts": 1}]}
            write_json(root / "plan.json", plan)
            write_json(root / "files.json", {"plan.json": digest(root / "plan.json")})
            output = Path(temp) / "review"
            result = analyze(plan, {"native": root}, output)
            self.assertEqual(result["status"], "incomplete-review-required")
            self.assertFalse(result["cases"][0]["integrity_passed"])
            self.assertTrue((output / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
