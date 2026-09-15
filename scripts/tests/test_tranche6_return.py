"""Synthetic outcome comparisons; no MATLAB execution is implied."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche6_return as review
import analyze_research_sweep as sweep


class OutcomeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.before, self.after = self.root / "before", self.root / "after"
        self.case = "recovery_freshness_s180_seed128"
        self.config = {"Seed": 128, "LinkEvents": [405, 540], "Traffic": {"PacketCount": 3}}
        self.old = dict(CaseId=self.case, Experiment="recovery_freshness",
                        Parameter="FreshnessTimeoutSeconds", Value=180, Seed=128,
                        Generated=3, Received=2, Dropped=1, Pending=0,
                        NwkPendingCustody=0, HopPendingData=0, NeighborDeactivations=1,
                        RouteChanges=2, ControlFailures=0, HopDataRetransmissions=6)
        self.new = dict(self.old, Received=2, Dropped=0, Pending=1, NwkPendingCustody=1)
        self.old_apps = [self.packet(1, "delivered", 100), self.packet(2, "dropped"),
                         self.packet(3, "delivered", 10)]
        self.new_apps = [self.packet(1, "pending"), self.packet(2, "delivered", 2),
                         self.packet(3, "delivered", 9)]
        self.write(self.before, self.old_apps)
        self.write(self.after, self.new_apps)

    @staticmethod
    def packet(packet, outcome, latency=None):
        generated = 400+packet*36
        return dict(PacketId=packet, SourceId=3, DestinationId=1, ApplicationBytes=64, Dscp=0,
                    GeneratedSeconds=generated, LastEventSeconds=generated+(latency or 8),
                    ReceivedSeconds=generated+latency if latency is not None else "NaN",
                    LatencySeconds=latency if latency is not None else "NaN", Outcome=outcome,
                    DropReason="retry_exhausted" if outcome == "dropped" else "")

    def write(self, root, applications, config=None):
        diagnostic = root / "diagnostics" / self.case
        diagnostic.mkdir(parents=True, exist_ok=True)
        with (diagnostic / "applications.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(applications[0]))
            writer.writeheader(); writer.writerows(applications)
        case = root / "sweep" / self.case
        case.mkdir(parents=True, exist_ok=True)
        (case / "summary.json").write_text(json.dumps({"Config": config or self.config}))

    def compare(self):
        return review.compare_cases(self.after, self.before, [self.new], [self.old])

    def test_latency_uses_same_survivors_and_retains_pending(self):
        rows, applications = self.compare()
        self.assertEqual(rows[0]["BothDeliveredCount"], 1)
        self.assertEqual(rows[0]["BothDeliveredMeanLatencyDeltaSeconds"], -1)
        self.assertEqual(rows[0]["DeltaReceived"], 0)
        self.assertEqual(rows[0]["DeltaPending"], 1)
        self.assertEqual(len(applications), 3)
        self.assertEqual(applications[0]["AfterOutcome"], "pending")
        self.assertIsNone(applications[0]["BothDeliveredLatencyDeltaSeconds"])

    def test_changed_blackout_cannot_be_attributed_to_code(self):
        altered = dict(self.config, LinkEvents=[405, 450])
        self.write(self.after, self.new_apps, altered)
        with self.assertRaisesRegex(sweep.EvidenceError, "configuration changed"):
            self.compare()

    def test_changed_packet_input_is_rejected(self):
        self.new_apps[0]["ApplicationBytes"] = 32
        self.write(self.after, self.new_apps)
        with self.assertRaisesRegex(sweep.EvidenceError, "Application input changed"):
            self.compare()

    def test_duplicate_packet_identity_is_rejected(self):
        self.new_apps[1]["PacketId"] = 1
        self.write(self.after, self.new_apps)
        with self.assertRaisesRegex(sweep.EvidenceError, "Duplicate application"):
            self.compare()

    def test_aggregate_cannot_hide_pending_packet(self):
        self.new.update(Received=3, Pending=0)
        with self.assertRaisesRegex(sweep.EvidenceError, "aggregate outcomes"):
            self.compare()

    def test_undelivered_packet_cannot_have_latency(self):
        self.new_apps[0]["LatencySeconds"] = 0
        self.write(self.after, self.new_apps)
        with self.assertRaisesRegex(sweep.EvidenceError, "Undelivered application"):
            self.compare()

    def test_no_common_survivors_has_no_latency_comparison(self):
        self.new_apps[2] = self.packet(3, "pending")
        self.new.update(Received=1, Pending=2, NwkPendingCustody=2)
        self.write(self.after, self.new_apps)
        rows, _ = self.compare()
        self.assertEqual(rows[0]["BothDeliveredCount"], 0)
        self.assertIsNone(rows[0]["BothDeliveredMeanLatencyDeltaSeconds"])

    def test_baseline_archive_identity_is_required(self):
        path = self.root / "wrong.zip"
        path.write_bytes(b"not accepted evidence")
        with self.assertRaisesRegex(sweep.EvidenceError, "not the accepted"):
            review.extract_baseline(path, self.root / "extracted")


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.nested = self.root / "regression" / "run_test"
        self.nested.mkdir(parents=True)
        self.source = [{"path": "run_tranche6_validation.m", "sha256": "a"*64}]
        self.nested_record = dict(SourceFiles=self.source, TestsExecuted=True, TestsPassed=True,
            TestCount=1, PassedTests=1, FailedTests=0, IncompleteTests=0,
            CompletedCaseCount=18, PlannedCaseCount=18, Options={"RunTests": True},
            SourceCommit=review.PIN, Runtime={"Runtime": "MATLAB", "Release": "2025a"})
        self.record = dict(self.nested_record, Schema=review.SCHEMA, Status="completed", MATLABExecuted=True,
            MatlabBaseCommit=review.BASE, AcceptedTranche5CodeCommit=review.ACCEPTED_T5_CODE,
            SourceFilesStableDuringRun=True,
            SourceFilesFinal=copy.deepcopy(self.source), RegressionEvidenceDirectory="regression/run_test")
        self.refresh()

    def refresh(self):
        path = self.nested / "validation_metadata.json"
        path.write_text(json.dumps(self.nested_record))
        self.record["RegressionMetadataSHA256"] = sweep.digest(path)
        self.record["Artifacts"] = [{"path": path.relative_to(self.root).as_posix(),
                                    "sha256": sweep.digest(path), "bytes": path.stat().st_size}]
        (self.root / "validation_metadata.json").write_text(json.dumps(self.record))

    def test_wrapper_binds_nested_source_and_counts(self):
        _, path, _, _ = review.verify_wrapper(self.root)
        self.assertEqual(path, self.nested)

    def test_wrong_merge_baseline_is_rejected(self):
        self.record["MatlabBaseCommit"] = "b"*40
        self.refresh()
        with self.assertRaisesRegex(sweep.EvidenceError, "baseline/reference"):
            review.verify_wrapper(self.root)

    def test_test_counts_cannot_be_relabelled(self):
        self.record["PassedTests"] = 100
        self.refresh()
        with self.assertRaisesRegex(sweep.EvidenceError, "PassedTests mismatch"):
            review.verify_wrapper(self.root)

    def test_nested_different_source_is_rejected(self):
        self.nested_record["SourceFiles"] = [{"path": "old.m", "sha256": "c"*64}]
        self.refresh()
        with self.assertRaisesRegex(sweep.EvidenceError, "source does not match"):
            review.verify_wrapper(self.root)

    def test_uninventoried_artifact_is_rejected(self):
        (self.root / "extra.csv").write_text("x\n1\n")
        with self.assertRaisesRegex(sweep.EvidenceError, "inventory is incomplete"):
            review.verify_wrapper(self.root)

    def test_nested_reference_commit_cannot_be_relabelled(self):
        self.nested_record["SourceCommit"] = "b"*40
        self.refresh()
        with self.assertRaisesRegex(sweep.EvidenceError, "Nested reference commit"):
            review.verify_wrapper(self.root)

    def test_nested_runtime_cannot_be_relabelled(self):
        self.nested_record["Runtime"] = {"Runtime": "MATLAB", "Release": "2026a"}
        self.refresh()
        with self.assertRaisesRegex(sweep.EvidenceError, "runtime/release"):
            review.verify_wrapper(self.root)

    def test_accepted_baseline_identity_cannot_be_relabelled(self):
        self.record["AcceptedTranche5CodeCommit"] = "c"*40
        self.refresh()
        with self.assertRaisesRegex(sweep.EvidenceError, "Tranche 5 code identity"):
            review.verify_wrapper(self.root)


if __name__ == "__main__":
    unittest.main()
