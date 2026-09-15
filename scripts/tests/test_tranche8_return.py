#!/usr/bin/env python3
"""Integrity and scientific-reporting failure cases for Tranche 8 diagnostics."""
from __future__ import annotations

import copy
import csv
import gzip
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche8_return as review
import tranche8_metrics as metrics

REPO = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class PlanAndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self):
        target = self.root/"source"
        shutil.copytree(REPO/"scenarios", target/"scenarios")
        return target

    def test_candidate_plan_preserves_parent_fixture(self):
        plan = review.verify_plan(REPO)
        self.assertEqual(len(plan["cases"]), 10)
        self.assertEqual(review.short_case_id("two_node_admission_1200_s128"), "a128")
        self.assertEqual(review.short_case_id("three_node_contention_360_s132"), "c132")
        with self.assertRaises(ValueError):
            review.short_case_id("campus_multihop_6000_s128")

    def test_rehashed_scenario_geometry_mutation_fails_derivation(self):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        item = plan["cases"][0]
        path = source/item["scenario_file"]
        rows = list(review.t7.csv_records(path))
        next(row for row in rows if row["record"] == "node")["x_m"] = "999"
        write_csv(path, rows)
        item["scenario_sha256"] = review.sweep.digest(path)
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, "beyond declared"):
            review.verify_plan(source)

    def nonrun_scenario_mutation(self, record):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        item = plan["cases"][0]
        path = source/item["scenario_file"]
        rows = list(review.t7.csv_records(path))
        row = next(row for row in rows if row["record"] == record)
        self.assertEqual(row["scenario"], "")
        row["scenario"] = item["scenario"]
        write_csv(path, rows)
        item["scenario_sha256"] = review.sweep.digest(path)
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, "beyond declared run-row"):
            review.verify_plan(source)

    def test_rehashed_scenario_on_node_row_is_rejected(self):
        self.nonrun_scenario_mutation("node")

    def test_rehashed_scenario_on_flow_row_is_rejected(self):
        self.nonrun_scenario_mutation("flow")

    def test_inputs_obey_actual_matlab_allowed_field_contract(self):
        # Read the consumer's declarations rather than reproducing the CSV
        # derivation or calling verify_plan. A generator and verifier sharing
        # the same mistake must still fail this independent compatibility gate.
        # This is a static preflight, not a claim of MATLAB execution.
        importer = (REPO/"+csr/+scenario/importNs3.m").read_text()

        def fields(pattern):
            matches = re.findall(pattern, importer, flags=re.DOTALL)
            self.assertEqual(len(matches), 1, "MATLAB field declaration changed; update contract preflight")
            return set(re.findall(r"'([^']+)'", matches[0]))

        common = fields(r"(?m)^common\s*=\s*\{([^}]+)\};")
        allowed = {
            record: common | fields(r"(?m)^" + record + r"Fields\s*=\s*\[common,\{([^}]+)\}\];")
            for record in ("run", "node", "flow")
        }
        allowed["node"] |= fields(r"if historical, nodeFields\s*=\s*\[nodeFields,\{([^}]+)\}\]; end")
        self.assertIn("scenario", allowed["run"])
        self.assertNotIn("scenario", allowed["node"])
        self.assertNotIn("scenario", allowed["flow"])
        plan = json.loads((REPO/review.PLAN).read_text())
        self.assertEqual(len(plan["cases"]), 10)
        seen_records = set()
        for item in plan["cases"]:
            with (REPO/item["scenario_file"]).open(newline="", encoding="utf-8") as stream:
                for row_number, row in enumerate(csv.DictReader(stream), 2):
                    with self.subTest(case=item["case_id"], row=row_number):
                        record = row["record"]
                        self.assertIn(record, allowed)
                        seen_records.add(record)
                        populated = {key for key, value in row.items() if value != ""}
                        self.assertFalse(populated - allowed[record],
                                         f"MATLAB rejects populated fields on {record} row: "
                                         f"{sorted(populated - allowed[record])}")
        self.assertEqual(seen_records, {"run", "node", "flow"})

    def test_missing_and_duplicate_seed_plan_is_rejected(self):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        plan["cases"][-1] = plan["cases"][0]
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, "complete two-fixture"):
            review.verify_plan(source)

    def test_snapshot_binds_new_cpp_header(self):
        path = self.root/"scripts/ns3/observer.h"
        path.parent.mkdir(parents=True)
        path.write_text("// passive helper\n")
        before = review.t7.candidate_snapshot(self.root)
        self.assertIn("scripts/ns3/observer.h", before)
        path.write_text("// changed helper\n")
        self.assertNotEqual(before, review.t7.candidate_snapshot(self.root))

    def test_test_result_actual_duration_column_and_exact_membership(self):
        path = self.root/"tests/TestFixture.m"
        path.parent.mkdir()
        path.write_text("classdef TestFixture < matlab.unittest.TestCase\n    methods (Test)\n"
                        "        function one(testCase)\n        end\n    end\nend\n")
        metadata = dict(Options={"RunTests": True}, TestsRequested=True, TestsExecuted=True,
                        TestsPassed=True, TestCount=1, PassedTests=1, FailedTests=0, IncompleteTests=0,
                        TestResultsFile="tests/test_results.csv")
        row = dict(Name="TestFixture/one", Passed="1", Failed="0", Incomplete="0", DurationSeconds="0.01")
        write_csv(self.root/"tests/test_results.csv", [row])
        self.assertEqual(review.verify_tests(self.root, metadata, self.root)["count"], 1)
        write_csv(self.root/"tests/test_results.csv", [row, row])
        with self.assertRaisesRegex(ValueError, "exactly once"):
            review.verify_tests(self.root, metadata, self.root)

    def test_unrequested_tests_cannot_claim_pass(self):
        metadata = dict(Options={"RunTests": False}, TestsRequested=False, TestsExecuted=False,
                        TestsPassed=True, TestCount=0, PassedTests=0, FailedTests=0, IncompleteTests=0,
                        TestResultsFile="tests/test_results.csv")
        with self.assertRaisesRegex(ValueError, "Unrequested tests"):
            review.verify_tests(self.root, metadata, self.root)

    def test_semantic_csv_comparison_handles_newlines_without_losing_integers(self):
        self.assertEqual(review.equivalent_csv(io.StringIO("x,y\r\n1,NaN\r\n"), io.StringIO("x,y\n1.0,nan\n"), "sample"), 1)
        with self.assertRaises(ValueError):
            review.equivalent_csv(io.StringIO("bitmap\n18446744073709551614\n"),
                                  io.StringIO("bitmap\n18446744073709551615\n"), "bitmap")
        with self.assertRaises(ValueError):
            review.equivalent_csv(io.StringIO("bitmap\n18446744073709551614\n"),
                                  io.StringIO("bitmap\n18446744073709551615.0\n"), "mixed-format bitmap")

    def test_failure_report_is_preserved_without_success_claim(self):
        evidence, output = self.root/"partial", self.root/"review"
        write_json(evidence/"validation_metadata.json", {"Schema": review.SCHEMA, "Tranche": 8, "Status": "failed"})
        self.assertEqual(review.main(["--evidence", str(evidence), "--source-root", str(REPO), "--output", str(output)]), 1)
        result = json.loads((output/"review-failure.json").read_text())
        self.assertEqual(result["status"], "structural_review_failed")
        self.assertFalse(result["acceptance_established"])


class ScientificMetrics(unittest.TestCase):
    def setUp(self):
        self.case = dict(case_id="test_s128", base_case_id="test", seed=128, duration_s=20, bucket_width_s=10)
        self.sent = {1: (0, 2, 1, 592), 2: (1, 2, 1, 592), 3: (1, 3, 1, 592), 4: (19, 3, 1, 592)}
        self.delivered = [(1, 1, 592), (2, 2, 592), (3, 10, 592)]

    def summary(self):
        return metrics.application_summary(self.sent, self.delivered, self.case, simulator="ns3", attempts=6)

    def test_packet_weighted_and_bucket_means_are_not_conflated(self):
        result = self.summary()
        self.assertAlmostEqual(result["mean_packet_latency_s"], 11/3)
        self.assertEqual(result["mean_populated_bucket_latency_s"], 5)
        self.assertEqual(result["flows"][0]["mean_packet_latency_s"], 1)
        self.assertEqual(result["flows"][1]["mean_packet_latency_s"], 9)

    def test_unmatched_ns3_sends_remain_unclassified(self):
        result = self.summary()
        self.assertEqual(result["unmatched_sends"], 1)
        self.assertIsNone(result["explicit_drops"])
        self.assertIsNone(result["pending"])

    def test_duplicate_delivery_is_explicit_and_kept_in_traffic(self):
        self.delivered.append((1, 2, 592))
        result = self.summary()
        self.assertEqual((result["delivered"], result["delivered_unique"], result["duplicate_delivery_events"]), (4, 3, 1))

    def test_identity_size_and_window_failures_block_metrics(self):
        for record in ((99, 2, 592), (1, 1, 591), (1, 20, 592), (3, 0, 592)):
            with self.subTest(record=record), self.assertRaises(ValueError):
                metrics.application_summary(self.sent, [record], self.case, simulator="ns3", attempts=6)

    def test_five_seed_pooled_latency_uses_packet_sample_weights(self):
        rows = []
        for seed in range(128, 133):
            row = self.summary()
            row["seed"] = seed
            if seed == 132:
                row.update(delay_samples=1, delay_sum_s=20, mean_packet_latency_s=20)
            rows.append(row)
        result = metrics.multiseed_summary(rows)
        self.assertAlmostEqual(result["groups"][0]["pooled"]["mean_packet_latency_s"], 64/13)
        self.assertFalse(result["population_equivalence_established"])
        with self.assertRaisesRegex(ValueError, "each of the five"):
            metrics.multiseed_summary(rows[:-1])

    def test_zero_reference_does_not_invent_relative_difference(self):
        rows = []
        for simulator in ("matlab", "ns3"):
            for seed in range(128, 133):
                row = self.summary()
                row.update(seed=seed, simulator=simulator, delivered=0 if simulator == "ns3" else 1,
                           explicit_drops=0 if simulator == "matlab" else None, pending=1 if simulator == "matlab" else None)
                rows.append(row)
        result = metrics.multiseed_summary(rows)
        self.assertIsNone(result["paired_by_seed"][0]["delivered"]["relative_difference_percent"])

    def test_missing_numbers_and_operational_rate(self):
        self.assertIsNone(metrics.optional_number("NaN", "missing"))
        self.assertEqual(metrics.optional_number("0", "observed zero"), 0)
        self.assertAlmostEqual(review.rate_bps("8"), 7843.13725490196)
        with self.assertRaisesRegex(ValueError, "operational bps"):
            review.check_rate({"key": "8", "bps": "8000"}, "key", "bps")


class MatlabFeedback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = dict(base_case_id="two_node_admission_1200", duration_s=1200,
                         trace_limits={"link_decisions": 100000, "protocol": 1500000, "phy": 1500000, "admission": 100000})
        self.diagnostic = dict(SchemaVersion="csr-matlab-link-diagnostics-v1", Enabled=True, Complete=True, Passive=True,
                              MaxRecords=100000, AckTransmissionsPerRetainedFrame=5, DecisionCount=2, ActualFeedbackCount=2,
                              OmittedDecisionRecords=0, OmittedActualFeedbackRecords=0, UnmatchedActualFeedbackRecords=0,
                              CorrelationErrors=0, ScheduledEvents=0, RandomDraws=0, LinkControlApplied=False,
                              PeerS0Available=False, HopFailureCountAvailable=False)
        self.summary = {"Config": {"Nodes": [{"Id": 1, "RadioProfile": {"TxPowerDbm": 33}},
                                               {"Id": 2, "RadioProfile": {"TxPowerDbm": 33}}],
                                   "Mac": {"AckTransmissions": 5}, "Trace": {"MaxRecords": 1500000, "MaxPhyRecords": 1500000,
                                                                              "MaxApplicationAdmissionRecords": 100000},
                                   "MaxEvents": 12000000}, "LinkDiagnostics": self.diagnostic}
        self.decision = dict(DecisionId="1", TimeSeconds="1", Stage="feedback_mac_admission", NodeId="1", PeerId="2",
                             FrameKind="ACK", Sequence="1", HasAckWindow="1", AckBitmap="18446744073709551615", DackBitmap="0",
                             InputContextAvailable="1", InputFrameKind="DATA", InputRateKeyKbps="128", InputRateBps=str(review.rate_bps(128)),
                             InputPowerDbm="33", InputReceivedPowerDbm="-90", PathlossDb="123", SelectedRateKeyKbps="128",
                             SelectedRateBps=str(review.rate_bps(128)), SelectedPowerDbm="33", ConfiguredNodePowerDbm="33",
                             PowerDefaulted="1", PeerS0Dbm="NaN", HopFailureCount="NaN", NwkFailureCount="0", LinkControlApplied="0",
                             QueueAccepted="1", QueueDisposition="enqueued", RetainedDecisionId="1")
        # The exact ACK is absorbed by the existing cumulative ACK for the same
        # peer/sequence; the actual frame keeps the original full identity.
        self.decisions = [self.decision, dict(self.decision, DecisionId="2", TimeSeconds="1.1", HasAckWindow="0", AckBitmap="0",
                                              QueueDisposition="duplicate_retained")]
        row = {field: self.decision[field] for field in ("NodeId", "PeerId", "FrameKind", "Sequence", "HasAckWindow", "AckBitmap", "DackBitmap",
                                                       "SelectedRateKeyKbps", "SelectedRateBps", "SelectedPowerDbm")}
        row.update(ObservationId="1", DecisionId="1", DecisionMatched="1", TimeSeconds="2", Stage="ota_feedback", AggregateId="10",
                   SegmentIndex="1", SegmentCount="1", RateKeyKbps="8", RateBps=str(review.rate_bps(8)), TxPowerDbm="30")
        self.actual = [row, dict(row, ObservationId="2", TimeSeconds="3", AggregateId="11")]
        self.hop = [dict(NodeId="1", AckGenerated="2", DackGenerated="0", FeedbackQueueDrops="0"),
                    dict(NodeId="2", AckGenerated="0", DackGenerated="0", FeedbackQueueDrops="0")]
        self.mac = [dict(NodeId="1", AckTransmissions="2", AckEnqueued="1", AckQueueDrops="0", AckReplacements="0"),
                    dict(NodeId="2", AckTransmissions="0", AckEnqueued="0", AckQueueDrops="0", AckReplacements="0")]
        self.save()

    def save(self):
        write_json(self.root/"raw/summary.json", self.summary)
        write_json(self.root/"benchmark_manifest.json", dict(observer_enabled=True, observer_diagnostics=self.diagnostic,
                                                            base_case_id=self.case["base_case_id"]))
        write_csv(self.root/"raw/link_decisions.csv", self.decisions)
        write_csv(self.root/"raw/actual_feedback.csv", self.actual)
        write_csv(self.root/"raw/hop_nodes.csv", self.hop)
        write_csv(self.root/"raw/mac_nodes.csv", self.mac)
        write_csv(self.root/"raw/protocol_trace.csv", [dict(Event="tx_start", TimeSeconds="2", NodeId="1", PacketId="10"),
                                                     dict(Event="tx_start", TimeSeconds="3", NodeId="1", PacketId="11")])

    def check(self):
        return review.verify_matlab_feedback(self.root, self.case)

    def test_retained_duplicate_repeats_and_actual_radio_override(self):
        result = self.check()
        self.assertEqual(result["distinct_decisions_transmitted"], 1)
        self.assertEqual(result["actual_vs_selected_rate_change_count"], 2)
        self.assertEqual(result["actual_vs_selected_power_change_count"], 2)
        self.assertEqual(result["queue_dispositions"]["duplicate_retained"], 1)
        self.assertEqual(result["feedback_forms"][0]["ota_feedback_member_count"], 0)
        self.assertEqual(result["feedback_forms"][1]["actual_vs_selected_rate_change_count"], 2)

    def test_observer_omission_is_separate_blocking_failure(self):
        self.diagnostic["OmittedDecisionRecords"] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, "Incomplete or perturbing"):
            self.check()

    def test_actual_requires_original_retained_identity(self):
        self.actual[0]["DecisionId"] = "2"
        self.save()
        with self.assertRaisesRegex(ValueError, "retained decision"):
            self.check()

    def test_duplicate_actual_row_or_missing_original_tx_is_rejected(self):
        self.actual[1]["AggregateId"] = "10"
        self.save()
        with self.assertRaisesRegex(ValueError, "Duplicate/invalid"):
            self.check()
        self.actual[1]["AggregateId"] = "12"
        self.save()
        with self.assertRaisesRegex(ValueError, "original protocol"):
            self.check()

    def test_self_consistent_trace_counts_still_checked_against_original_mac(self):
        self.mac[0]["AckTransmissions"] = "3"
        self.save()
        with self.assertRaisesRegex(ValueError, "original per-node counters"):
            self.check()

    def test_unknown_input_cannot_be_filled_with_zero(self):
        self.decisions[0]["PeerS0Dbm"] = "0"
        self.save()
        with self.assertRaisesRegex(ValueError, "fabricated"):
            self.check()

    def test_uint64_bitmap_is_compared_exactly(self):
        self.actual[0]["AckBitmap"] = "18446744073709551614"
        self.save()
        with self.assertRaisesRegex(ValueError, "retained decision"):
            self.check()

    def test_fabricated_rate_policy_change_is_rejected(self):
        self.decisions[0]["SelectedRateKeyKbps"] = "8"
        self.decisions[0]["SelectedRateBps"] = str(review.rate_bps(8))
        self.save()
        with self.assertRaisesRegex(ValueError, "preserve received frame rate"):
            self.check()


class Ns3Evidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_observed_link_control_inputs_determine_source_rate_and_power(self):
        row = dict(min_rate_key_kbps="8", max_rate_key_kbps="128", min_power_dbm="-36", max_power_dbm="33",
                   link_margin_db="12", peer_known="1", path_loss_db="123.167249841905", peer_s0_dbm="-103",
                   hop_failure_count="99", advertised_rx_power_dbm="-103", selected_rate_key_kbps="128", selected_power_dbm="33")
        review.check_ns3_selection(row)
        # HOP failures affect cost, not this selected rate/power calculation.
        row["path_loss_db"] = "135.208"
        row["selected_rate_key_kbps"] = "8"
        review.check_ns3_selection(row)
        row["selected_rate_key_kbps"] = "128"
        with self.assertRaisesRegex(ValueError, "source HOP"):
            review.check_ns3_selection(row)

    def test_compressed_control_proof_binds_final_bytes(self):
        data = b"original event trace\n"
        zipped = self.root/"observer-off-ns3-trace.csv.gz"
        zipped.write_bytes(gzip.compress(data, mtime=0))
        record = dict(path=zipped.name, bytes=zipped.stat().st_size, sha256=review.sweep.digest(zipped),
                      original_name="observer-off-ns3-trace.csv", original_bytes=len(data),
                      original_sha256=review.hashlib.sha256(data).hexdigest())
        review.check_compressed(self.root, record)
        zipped.write_bytes(gzip.compress(b"changed event trace!\n", mtime=0))
        record.update(bytes=zipped.stat().st_size, sha256=review.sweep.digest(zipped))
        with self.assertRaisesRegex(ValueError, "roundtrip mismatch|exceeds declared"):
            review.check_compressed(self.root, record)


class AcceptedReturnContractReplay(unittest.TestCase):
    """Replay already accepted raw bytes through new anchor/control contracts.

    This fixture does not execute MATLAB or represent a T8 MATLAB return. It
    catches directory, inventory, singleton-JSON, and evidence-comparison drift
    using the actual MATLAB exporter records from the immutable T7 archive.
    """
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.plan = review.verify_plan(REPO)
        rows = []
        with zipfile.ZipFile(REPO/cls.plan["baseline_anchor"]["archive"]) as bundle:
            cls.source = review.sweep.snapshot(json.loads(bundle.read("source_snapshot.json")), "accepted source")
            for case in cls.plan["cases"]:
                if case["seed"] != 128:
                    continue
                token = review.short_case_id(case["case_id"])
                on, off = cls.root/"b"/token/"raw", cls.root/"c"/token/"raw"
                prefix = f"benchmarks/{case['base_case_id']}/raw/"
                for member in bundle.infolist():
                    if member.filename.startswith(prefix) and not member.is_dir():
                        relative = member.filename[len(prefix):]
                        target = on/relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(bundle.read(member))
                shutil.copytree(on, off)
                files = [{"path": name, "observer_on_sha256": review.sweep.digest(on/name),
                          "observer_off_sha256": review.sweep.digest(off/name), "equal": True}
                         for name in (*review.UNCHANGED_CSV, "scenario.csv")]
                rows.append(dict(case_id=case["case_id"], observer_on_directory=f"b/{token}/raw",
                                 observer_off_directory=f"c/{token}/raw", statistics_equal=True, config_equal=True,
                                 compared_files=files, passed=True))
        cls.record = dict(schema="csr-link-diagnostic-nonperturbation-v1", status="completed", planned_control_count=2,
                          completed_control_count=2, passed=True, cases=rows)
        write_json(cls.root/"nonperturbation.json", cls.record)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_accepted_matlab_anchor_passes_semantic_short_layout_replay(self):
        result = review.verify_t7_anchor(self.root, REPO, self.plan)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["cases"]), 2)

    def test_two_control_contracts_accept_actual_matlab_export_shapes(self):
        result = review.verify_nonperturbation(self.root, {"NonperturbationPassed": True}, self.source, self.plan)
        self.assertTrue(result["passed"])

    def test_claimed_equal_control_cannot_omit_comparison_file(self):
        changed = copy.deepcopy(self.record)
        changed["cases"][0]["compared_files"].pop()
        write_json(self.root/"nonperturbation.json", changed)
        try:
            with self.assertRaisesRegex(ValueError, "omitted unchanged"):
                review.verify_nonperturbation(self.root, {"NonperturbationPassed": True}, self.source, self.plan)
        finally:
            write_json(self.root/"nonperturbation.json", self.record)


if __name__ == "__main__":
    unittest.main()
