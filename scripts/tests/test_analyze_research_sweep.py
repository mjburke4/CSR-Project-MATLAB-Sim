"""Synthetic analyzer fixtures. These tests are not MATLAB execution evidence."""

import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_research_sweep as analyzer


class IntegerParsingTests(unittest.TestCase):
    def test_real_matlab_scientific_json_byte_counts(self):
        # Exact numeric tokens from the returned R2025a Tranche 5 inventory.
        for token, expected in (("2.485837E+6", 2485837), ("1.01088E+6", 1010880)):
            with self.subTest(token=token):
                value = json.loads(token)
                self.assertIs(type(value), float)
                self.assertEqual(analyzer.integer(value, "bytes"), expected)

    def test_safe_integral_floats_and_exact_large_integer_identifiers(self):
        for value in (0.0, 1.0, float(2**53-1)):
            with self.subTest(value=value):
                self.assertEqual(analyzer.integer(value, "count"), int(value))
        # Digit strings and Python JSON integers retain every digit beyond
        # binary64 precision and must not pass through float conversion.
        for value in (2**53+1, 2**64-1):
            self.assertEqual(analyzer.integer(value, "id"), value)
            self.assertEqual(analyzer.integer(str(value), "id"), value)

    def test_invalid_counts_and_ambiguous_large_floats_are_rejected(self):
        for value in (True, False, -1, -1.0, 1.5, float("nan"), float("inf"),
                      -float("inf"), None, [], {}, "1.0", "1E3", "-1", " 1 ", ""):
            with self.subTest(value=value):
                with self.assertRaisesRegex(analyzer.EvidenceError, "nonnegative integer"):
                    analyzer.integer(value, "count")
        for value in (float(2**53), float(2**53+1), float(2**54)):
            with self.subTest(value=value):
                with self.assertRaisesRegex(analyzer.EvidenceError, "exact safe range"):
                    analyzer.integer(value, "count")


class SweepAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "evidence"
        self.root.mkdir()
        self.output = self.root.parent / "analysis"
        self.source = [{"path": "run_tranche5_validation.m", "sha256": "a"*64}]
        self.options = dict(Seeds=[128, 129, 130], Experiments=["offered_load"],
                            IncludeLongRun=False, LoadMultipliers=[1, 2], FreshnessTimeoutSeconds=[180])
        self.rows = []
        for value in self.options["LoadMultipliers"]:
            for seed in self.options["Seeds"]:
                name = f"offered_load_x{value}_seed{seed}"
                row = dict.fromkeys(analyzer.COUNT_METRICS, 0)
                row.update(dict.fromkeys(analyzer.BOOL_METRICS, True))
                row.update(CaseId=name, Scenario=name, Experiment="offered_load", Parameter="LoadMultiplier",
                           Value=value, Seed=seed, DurationSeconds=480, Generated=10, Received=10,
                           PhysicalTransmissions=20, DeliveryRatio=1, LatencyP95Seconds=seed-127,
                           MaxLatencySeconds=seed-126, MetricsSchema="csr-performance-summary-v1",
                           StructuralChecksPassed=True)
                self.rows.append(row)
        self.metadata = dict(Schema=analyzer.SCHEMA, Status="completed", MATLABExecuted=True,
                             SourceFilesStableDuringRun=True, SourceFiles=self.source,
                             SourceFilesFinal=copy.deepcopy(self.source), SourceCommit="b"*40,
                             SweepPlan="sweep_plan.json", TestsRequested=False, TestsExecuted=False,
                             TestsPassed=False, TestCount=0, PassedTests=0, FailedTests=0,
                             IncompleteTests=0, NativeRequested=False, NativeAttempted=False,
                             NativeExecuted=False, NativeStatus="not_run", RegressionStatus="not_run")
        self.refresh()

    @staticmethod
    def write_json(path, data):
        path.write_text(json.dumps(data)+"\n", encoding="utf-8")

    @staticmethod
    def write_csv(path, rows, fields=None):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
            writer.writeheader()
            for row in rows:
                # MATLAB writes logical table variables as numeric 0/1.
                writer.writerow({key: int(value) if type(value) is bool else value for key, value in row.items()})

    @staticmethod
    def file_entry(root, path):
        entry = dict(path=path.relative_to(root).as_posix(), sha256=analyzer.digest(path), bytes=path.stat().st_size)
        if path.suffix == ".csv":
            entry["row_count"] = len(analyzer.csv_rows(path))
        return entry

    def rehash_run(self):
        self.metadata["Artifacts"] = [self.file_entry(self.root, path)
                                      for path in sorted(self.root.rglob("*")) if path.is_file()
                                      and path != self.root / "validation_metadata.json"]
        self.write_json(self.root / "validation_metadata.json", self.metadata)

    def refresh(self):
        cases, descriptors = [], []
        for row in self.rows:
            name = row["CaseId"]
            descriptor = {field: row[field] for field in analyzer.IDENTITY}
            descriptors.append(descriptor)
            case_root = self.root / "sweep" / name
            case_root.mkdir(parents=True, exist_ok=True)
            diagnostic_root = self.root / "diagnostics" / name
            diagnostic_root.mkdir(parents=True, exist_ok=True)
            config = dict(Name=name, Seed=row["Seed"], DurationSeconds=row["DurationSeconds"],
                          Research=dict(Sweep={k: v for k, v in descriptor.items() if k != "CaseId"}))
            stats = {field: row[field] for field in ("Generated", "Received", "Dropped", "Pending", "PhysicalTransmissions")}
            stats.update(OmittedTraceRecords=0, OmittedPhyTraceRecords=0)
            self.write_json(case_root / "summary.json", dict(Config=config, Statistics=stats,
                            Metadata=dict(SourceCommit=self.metadata["SourceCommit"])))
            self.write_csv(case_root / "research_summary.csv", [row])
            self.write_csv(case_root / "protocol_trace.csv", [], ["TimeSeconds", "Event"])
            self.write_csv(case_root / "phy_trace.csv", [], ["TimeSeconds", "Event"])
            self.write_csv(diagnostic_root / "performance_summary.csv", [row])
            self.write_csv(diagnostic_root / "applications.csv", [], ["PacketId", "Outcome"])
            manifest = dict(schema="csr-matlab-research-case-v1", status="completed", execution_completed=True,
                            source_files_stable=True, structural_checks_passed=True, source_files=self.source,
                            ns3_source_commit=self.metadata["SourceCommit"], scenario=name, seed=row["Seed"],
                            duration_s=row["DurationSeconds"], files=[])
            manifest["files"] = [self.file_entry(case_root, path) for path in sorted(case_root.iterdir())
                                 if path.name != "case_manifest.json"]
            self.write_json(case_root / "case_manifest.json", manifest)
            cases.append(dict(descriptor, Name=name, Directory=f"sweep/{name}", DiagnosticsDirectory=f"diagnostics/{name}",
                              ManifestSHA256=analyzer.digest(case_root / "case_manifest.json")))
        self.plan = dict(Schema="csr-matlab-research-sweep-plan-v1", Status="planned-not-executed",
                         Options=self.options, CaseCount=len(descriptors), Cases=descriptors,
                         LongRunCaseCount=len(descriptors) if self.options["IncludeLongRun"] else 0)
        self.write_json(self.root / "sweep_plan.json", self.plan)
        self.write_csv(self.root / "sweep_cases.csv", descriptors)
        self.write_csv(self.root / "performance_summary.csv", self.rows)
        (self.root / "validation.log").write_text("Synthetic Python fixture, no MATLAB was run.\n")
        self.metadata.update(Cases=cases, Options=dict(self.options, RunTests=self.metadata["TestsRequested"],
                                                      IncludeNative=self.metadata["NativeRequested"]),
                             PlannedCaseCount=len(cases), CompletedCaseCount=len(cases))
        self.rehash_run()

    def analyze(self):
        return analyzer.analyze(self.root)

    def assert_invalid(self, pattern):
        with self.assertRaisesRegex(analyzer.EvidenceError, pattern):
            self.analyze()

    def test_descriptive_means_and_sample_std_across_equal_seed_sets(self):
        report, rows, groups = self.analyze()
        self.assertEqual(report["tests"]["status"], "not_run")
        self.assertFalse(report["matlab_acceptance_established"])
        self.assertFalse(report["cross_simulator_equivalence_established"])
        self.assertEqual(len(rows), 6)
        latency = report["groups"][0]["metrics"]["LatencyP95Seconds"]
        self.assertEqual(latency, dict(SeedCount=3, FiniteCount=3, MissingCount=0, Mean=2, SampleStd=1, Min=1, Max=3))
        self.assertEqual(len(groups), 2*len(analyzer.METRICS))

    def test_matlab_singleton_structs_seed_and_long_only_plan(self):
        # Use a new evidence directory so removed multi-case files cannot linger.
        self.root = self.root.parent / "singleton"
        self.root.mkdir()
        self.options.update(Seeds=128, Experiments=[], IncludeLongRun=True)
        self.rows = [self.rows[0]]
        self.rows[0].update(CaseId="long_run_s6000_seed128", Scenario="long_run_s6000_seed128",
                            Experiment="long_run", Parameter="DurationSeconds", Value=6000, DurationSeconds=6000)
        self.refresh()
        self.plan["Cases"] = self.plan["Cases"][0]
        self.write_json(self.root / "sweep_plan.json", self.plan)
        self.metadata["Cases"] = self.metadata["Cases"][0]
        self.metadata["SourceFiles"] = self.source[0]
        self.metadata["SourceFilesFinal"] = self.source[0]
        self.rehash_run()
        report, _, _ = self.analyze()
        self.assertEqual(report["seeds"], [128])
        self.assertIsNone(report["groups"][0]["metrics"]["DeliveryRatio"]["SampleStd"])

    def test_scalar_experiment_string_is_supported(self):
        self.options["Experiments"] = "offered_load"
        self.refresh()
        self.assertEqual(self.analyze()[0]["case_count"], 6)

    def test_unrequested_tests_cannot_claim_passed(self):
        self.metadata["TestsPassed"] = True
        self.rehash_run()
        self.assert_invalid("Unrequested tests")

    def test_real_test_csv_counts_and_status_are_bound(self):
        path = self.root / "regression" / "tests" / "test_results.csv"
        path.parent.mkdir(parents=True)
        self.write_csv(path, [dict(Name="SyntheticTest/one", Passed=1, Failed=0, Incomplete=0)])
        self.metadata.update(TestsRequested=True, TestsExecuted=True, TestsPassed=True,
                             TestCount=1, PassedTests=1, RegressionStatus="completed",
                             TestResultsFile="regression/tests/test_results.csv", TestResultsSHA256=analyzer.digest(path))
        self.refresh()
        self.assertEqual(self.analyze()[0]["tests"]["status"], "passed")
        self.metadata["PassedTests"] = 0
        self.rehash_run()
        self.assert_invalid("Requested tests")

    def test_nonfinite_latency_becomes_null_and_missing_count_not_zero(self):
        for row in self.rows[:3]:
            row["LatencyP95Seconds"] = "NaN"
            row["MaxLatencySeconds"] = "Inf"
        self.refresh()
        report, rows, _ = self.analyze()
        metric = report["groups"][0]["metrics"]["LatencyP95Seconds"]
        self.assertEqual(metric["MissingCount"], 3)
        self.assertEqual(metric["FiniteCount"], 0)
        self.assertIsNone(metric["Mean"])
        self.assertIsNone(rows[0]["LatencyP95Seconds"])

    def test_missing_metrics_do_not_pool_different_number_of_seeds(self):
        self.rows[0]["MaxLatencySeconds"] = ""
        self.refresh()
        metric = self.analyze()[0]["groups"][0]["metrics"]["MaxLatencySeconds"]
        self.assertEqual((metric["SeedCount"], metric["FiniteCount"], metric["MissingCount"]), (3, 2, 1))

    def test_corrupt_file_is_rejected(self):
        (self.root / "performance_summary.csv").write_text("broken\n")
        self.assert_invalid("byte count mismatch|SHA-256 mismatch")

    def test_bad_hash_is_rejected_independently_of_bytes(self):
        self.metadata["Artifacts"][0]["sha256"] = "f"*64
        self.write_json(self.root / "validation_metadata.json", self.metadata)
        self.assert_invalid("SHA-256 mismatch")

    def test_scientific_json_byte_count_keeps_size_and_hash_checks(self):
        entry = self.metadata["Artifacts"][0]
        entry["bytes"] = float(entry["bytes"])
        self.write_json(self.root / "validation_metadata.json", self.metadata)
        self.assertEqual(self.analyze()[0]["case_count"], 6)
        entry["bytes"] += 1.0
        self.write_json(self.root / "validation_metadata.json", self.metadata)
        self.assert_invalid("byte count mismatch")
        entry["bytes"] -= 1.0
        entry["sha256"] = "f"*64
        self.write_json(self.root / "validation_metadata.json", self.metadata)
        self.assert_invalid("SHA-256 mismatch")

    def test_missing_file_is_rejected(self):
        (self.root / "performance_summary.csv").unlink()
        self.assert_invalid("missing file")

    def test_unlisted_exported_artifact_is_rejected(self):
        (self.root / "extra.json").write_text("{}")
        self.assert_invalid("exact exported file set")

    def test_duplicate_inventory_entry_is_rejected(self):
        self.metadata["Artifacts"].append(self.metadata["Artifacts"][0])
        self.write_json(self.root / "validation_metadata.json", self.metadata)
        self.assert_invalid("duplicate inventory")

    def test_unsafe_inventory_path_is_rejected(self):
        self.metadata["Artifacts"][0]["path"] = "../escape.csv"
        self.write_json(self.root / "validation_metadata.json", self.metadata)
        self.assert_invalid("Unsafe relative path")

    def test_incomplete_status_is_rejected(self):
        for status in ("running", "failed"):
            self.metadata["Status"] = status
            self.rehash_run()
            self.assert_invalid("not completed")

    def test_stability_requires_matching_final_snapshot(self):
        self.metadata["SourceFilesFinal"][0]["sha256"] = "f"*64
        self.rehash_run()
        self.assert_invalid("source snapshots differ")

    def test_duplicate_case_is_rejected(self):
        self.metadata["Cases"].append(self.metadata["Cases"][0])
        self.rehash_run()
        self.assert_invalid("duplicate CaseId")

    def test_missing_seed_from_rows_cannot_be_success(self):
        self.write_csv(self.root / "performance_summary.csv", self.rows[:-1])
        self.rehash_run()
        self.assert_invalid("missing or unexpected cases")

    def test_truncated_plan_cannot_hide_missing_seed(self):
        self.plan["Cases"] = self.plan["Cases"][:-1]
        self.plan["CaseCount"] -= 1
        self.write_json(self.root / "sweep_plan.json", self.plan)
        self.rehash_run()
        self.assert_invalid("CaseCount mismatch")

    def test_metadata_counts_and_options_must_agree_with_plan(self):
        self.metadata["CompletedCaseCount"] -= 1
        self.rehash_run()
        self.assert_invalid("case counts disagree")
        self.metadata["CompletedCaseCount"] += 1
        self.metadata["Options"]["Seeds"] = [128]
        self.rehash_run()
        self.assert_invalid("options disagree")

    def test_archived_config_cannot_claim_different_parameter(self):
        name = self.rows[0]["CaseId"]
        path = self.root / "sweep" / name / "summary.json"
        summary = analyzer.json_object(path)
        summary["Config"]["Research"]["Sweep"]["Value"] = 8
        self.write_json(path, summary)
        manifest_path = path.parent / "case_manifest.json"
        manifest = analyzer.json_object(manifest_path)
        manifest["files"] = [self.file_entry(path.parent, path.parent / entry["path"]) for entry in manifest["files"]]
        self.write_json(manifest_path, manifest)
        self.metadata["Cases"][0]["ManifestSHA256"] = analyzer.digest(manifest_path)
        self.rehash_run()
        self.assert_invalid("config identity mismatch")

    def test_counter_and_drain_metrics_reject_nonfinite_or_contradictory_values(self):
        self.rows[0]["HopControlFailures"] = "NaN"
        self.refresh()
        self.assert_invalid("nonnegative integer")
        self.rows[0]["HopControlFailures"] = 0
        self.rows[0]["ControlPending"] = 1
        self.refresh()
        self.assert_invalid("Drain flags")

    def test_native_requested_cannot_be_incomplete(self):
        self.metadata["NativeRequested"] = True
        self.metadata["RegressionStatus"] = "completed"
        self.refresh()
        self.assert_invalid("native execution did not pass")

    def test_cli_writes_valid_json_and_clears_only_own_stale_tables_on_failure(self):
        args = ["--evidence", str(self.root), "--output", str(self.output)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(analyzer.main(args), 0)
            sentinel = self.output / "keep.txt"
            sentinel.write_text("unrelated")
            self.metadata["Status"] = "failed"
            self.rehash_run()
            self.assertEqual(analyzer.main(args), 2)
        report = analyzer.json_object(self.output / "sweep_analysis.json")
        self.assertEqual(report["status"], "invalid_evidence")
        self.assertEqual(analyzer.csv_rows(self.output / "seed_observations.csv"), [])
        self.assertEqual(analyzer.csv_rows(self.output / "group_statistics.csv"), [])
        self.assertEqual(sentinel.read_text(), "unrelated")

    def test_output_inside_evidence_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(analyzer.main(["--evidence", str(self.root), "--output", str(self.root / "analysis")]), 2)
        self.assertFalse((self.root / "analysis").exists())


if __name__ == "__main__":
    unittest.main()
