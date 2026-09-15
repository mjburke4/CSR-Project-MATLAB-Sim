"""Semantic and evidence-boundary tests for benchmark aggregate comparison."""

from __future__ import annotations

import copy
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "compare_benchmark_aggregates.py"
SPEC = importlib.util.spec_from_file_location("compare_benchmark_aggregates", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
benchmark = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark
SPEC.loader.exec_module(benchmark)


class BenchmarkComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = {
            "schema": benchmark.INPUT_SCHEMA,
            "scenario": "synthetic-test-input",
            "scenario_sha256": "a"*64,
            "profile_id": "synthetic-explicit-profile",
            "duration_s": 120,
            "bucket_width_s": 60,
            "inputs": [],
        }
        for source in ("matlab", "ns3", "opnet"):
            self.add_source(source)
        self.path = self.root / "comparison-input.json"
        self.save_manifest()

    def rows(self, source):
        rows = []
        for name, (unit, aggregation) in benchmark.CORE_SERIES.items():
            for time in (60, 120):
                is_mean = aggregation == "bucket_sample_mean"
                value = "" if is_mean and time == 60 else "1"
                rows.append({
                    "schema": benchmark.SERIES_SCHEMA,
                    "scenario": self.manifest["scenario"], "statistic": name,
                    "time_s": str(time), "value": value, "source": source,
                    "unit": unit, "aggregation": aggregation,
                    "raw_value": "2e+100" if source == "opnet" and not value else "",
                    "value_status": "observed" if value else "missing",
                    "source_file": f"{source}-source.csv", "source_file_sha256": "b"*64,
                })
        return rows

    def add_source(self, source):
        rows = self.rows(source)
        aggregate = self.root / f"{source}-aggregate.csv"
        self.write_csv(aggregate, rows)
        provenance = {
            "schema": benchmark.PROVENANCE_SCHEMA, "source": source,
            "scenario": self.manifest["scenario"],
            "scenario_sha256": self.manifest["scenario_sha256"],
            "profile_id": self.manifest["profile_id"],
            "source_file_sha256": "b"*64,
            "window": {"start_time_s": 0, "stop_time_s": 120,
                       "bucket_width_s": 60, "bucket_count": 2,
                       "start_endpoint": "inclusive", "stop_endpoint": "exclusive"},
            "output": {"sha256": benchmark.digest(aggregate)},
        }
        sidecar = self.root / f"{source}-provenance.json"
        sidecar.write_text(json.dumps(provenance), encoding="utf-8")
        self.manifest["inputs"].append({
            "source": source, "aggregate_file": aggregate.name,
            "aggregate_sha256": benchmark.digest(aggregate),
            "provenance_file": sidecar.name,
            "provenance_sha256": benchmark.digest(sidecar),
        })

    @staticmethod
    def write_csv(path, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def save_manifest(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def descriptor(self, source="matlab"):
        return next(entry for entry in self.manifest["inputs"] if entry["source"] == source)

    def modify_rows(self, change, source="matlab"):
        entry = self.descriptor(source)
        aggregate = self.root / entry["aggregate_file"]
        with aggregate.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        change(rows)
        self.write_csv(aggregate, rows)
        entry["aggregate_sha256"] = benchmark.digest(aggregate)
        self.modify_provenance(lambda value: value["output"].update(sha256=entry["aggregate_sha256"]), source)

    def modify_provenance(self, change, source="matlab"):
        entry = self.descriptor(source)
        path = self.root / entry["provenance_file"]
        content = json.loads(path.read_text(encoding="utf-8"))
        change(content)
        path.write_text(json.dumps(content), encoding="utf-8")
        entry["provenance_sha256"] = benchmark.digest(path)
        self.save_manifest()

    def compare(self):
        return benchmark.compare_manifest(self.path)

    def test_three_way_structure_pass_preserves_missing_sentinel(self):
        result = self.compare()
        self.assertTrue(result["structural_gate_passed"])
        self.assertFalse(result["numeric_tolerance_gate_applied"])
        self.assertFalse(result["full_protocol_parity_established"])
        self.assertEqual(len(result["comparisons"]), 3)
        self.assertEqual(result["inputs"]["opnet"]["compared_bucket_count"], 16)
        point = next(row for row in result["points"] if row["reference"] == "opnet"
                     and row["statistic"] == "Generator.Packet Size (bits)" and row["time_s"] == 60)
        self.assertEqual(point["reference_raw_value"], "2e+100")
        self.assertIsNone(point["difference"])
        self.assertEqual(point["comparison_status"], "both_missing")

    def test_numerical_regression_remains_descriptive(self):
        self.modify_rows(lambda rows: rows[0].update(value="7"))
        result = self.compare()
        summary = result["comparisons"][0]["series"][0]
        self.assertTrue(result["structural_gate_passed"])
        self.assertEqual(summary["exact_numeric_difference_count"], 1)
        self.assertEqual(summary["maximum_absolute_bucket_difference"], 6)
        self.assertEqual(summary["candidate_observed_bucket_mean"], 4)
        self.assertEqual(summary["observed_bucket_mean_relative_difference_percent"], 300)

    def test_missing_coverage_does_not_become_zero_or_change_paired_mean(self):
        def change(rows):
            for row in rows:
                if row["statistic"] == "Generator.Packet Size (bits)":
                    row.update(value="9" if row["time_s"] == "60" else "3", value_status="observed")
        self.modify_rows(change)
        summary = self.compare()["comparisons"][0]["series"][2]
        self.assertEqual(summary["candidate_observed_bucket_mean"], 6)
        self.assertEqual(summary["reference_observed_bucket_mean"], 1)
        self.assertEqual(summary["paired_candidate_bucket_mean"], 3)
        self.assertEqual(summary["numeric_pair_count"], 1)
        self.assertEqual(summary["missing_bucket_ends_s"]["reference_missing_only"], [60])

    def test_zero_reference_has_no_invented_relative_percentage(self):
        self.modify_rows(lambda rows: rows[0].update(value="0"), "ns3")
        point = self.compare()["points"][0]
        self.assertEqual(point["difference"], 1)
        self.assertIsNone(point["relative_difference_percent"])

    def test_opnet_is_optional_but_ns3_required(self):
        self.manifest["inputs"] = self.manifest["inputs"][:2]
        self.save_manifest()
        self.assertEqual(len(self.compare()["comparisons"]), 1)
        self.descriptor("ns3")["source"] = "opnet"
        self.save_manifest()
        with self.assertRaisesRegex(benchmark.BenchmarkError, "source mismatch"):
            self.compare()

    def test_payload_hash_and_sidecar_hash_are_enforced(self):
        entry = self.descriptor()
        aggregate = self.root / entry["aggregate_file"]
        aggregate.write_text(aggregate.read_text()+"\n", encoding="utf-8")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "SHA-256 mismatch"):
            self.compare()
        entry["aggregate_sha256"] = benchmark.digest(aggregate)
        self.save_manifest()
        with self.assertRaisesRegex(benchmark.BenchmarkError, "output SHA-256 mismatch"):
            self.compare()

    def test_source_trace_hash_must_match_normalized_provenance(self):
        self.modify_rows(lambda rows: rows[0].update(source_file_sha256="c"*64))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "source-file SHA-256 mismatch"):
            self.compare()

    def test_scenario_and_profile_mismatches_fail(self):
        self.modify_provenance(lambda value: value.update(profile_id="different-MAC-profile"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "profile_id mismatch"):
            self.compare()
        self.modify_provenance(lambda value: value.update(profile_id=self.manifest["profile_id"],
                                                          scenario_sha256="c"*64))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "scenario_sha256 mismatch"):
            self.compare()

    def test_optional_detailed_profile_cannot_be_silently_ignored(self):
        self.manifest["profile"] = {"application": "historical", "seed": 128}
        self.save_manifest()
        with self.assertRaisesRegex(benchmark.BenchmarkError, "detailed profile mismatch"):
            self.compare()
        for source in ("matlab", "ns3", "opnet"):
            self.modify_provenance(lambda value: value.update(profile=copy.deepcopy(self.manifest["profile"])), source)
        self.assertTrue(self.compare()["structural_gate_passed"])

    def test_half_open_window_and_width_are_bound(self):
        self.modify_provenance(lambda value: value["window"].update(stop_endpoint="inclusive"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "stop_endpoint mismatch"):
            self.compare()
        self.modify_provenance(lambda value: value["window"].update(stop_endpoint="exclusive", bucket_width_s=12))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "bucket_width_s mismatch"):
            self.compare()

    def test_missing_entire_series_or_bucket_fails(self):
        self.modify_rows(lambda rows: rows.pop(0))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "missing required series/bucket"):
            self.compare()

    def test_duplicate_identity_and_wrong_time_fail(self):
        self.modify_rows(lambda rows: rows.append(copy.deepcopy(rows[0])))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate series/bucket"):
            self.compare()
        self.modify_rows(lambda rows: (rows.pop(), rows[0].update(time_s="60.0001")))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "bucket grid"):
            self.compare()

    def test_semantic_units_and_aggregation_are_not_display_labels(self):
        self.modify_rows(lambda rows: rows[0].update(unit="packets/ms"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "unit/aggregation mismatch"):
            self.compare()
        self.modify_rows(lambda rows: rows[0].update(unit="packets/s", aggregation="bucket_sample_mean"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "unit/aggregation mismatch"):
            self.compare()

    def test_no_sample_rate_bucket_and_undecoded_opnet_sentinel_fail(self):
        self.modify_rows(lambda rows: rows[0].update(value="", value_status="missing"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "count/rate buckets cannot be missing"):
            self.compare()
        self.modify_rows(lambda rows: rows[0].update(value="2e+100", value_status="observed"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "sentinel was not decoded"):
            self.compare()

    def test_archived_opnet_empty_bucket_sum_remains_missing(self):
        name = "Sink.Traffic Received (packets)"
        def change(rows):
            for row in rows:
                if row["statistic"] == name and row["time_s"] == "60":
                    row.update(value="", value_status="missing", raw_value="2e+100")
        self.modify_rows(change, "opnet")
        pair = self.compare()["comparisons"][1]
        summary = next(row for row in pair["series"] if row["statistic"] == name)
        self.assertEqual(summary["numeric_pair_count"], 1)
        self.assertEqual(summary["missing_bucket_ends_s"]["reference_missing_only"], [60])
        self.modify_rows(lambda rows: [row.update(raw_value="") for row in rows if row["statistic"] == name], "opnet")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "without an OPNET sentinel"):
            self.compare()

    def test_nonfinite_or_negative_values_fail(self):
        self.modify_rows(lambda rows: rows[0].update(value="nan"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "must be finite"):
            self.compare()
        self.modify_rows(lambda rows: rows[0].update(value="-1"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "negative/zero"):
            self.compare()

    def test_unexpected_statistic_fails_instead_of_silent_filtering(self):
        self.modify_rows(lambda rows: rows.append(dict(rows[0], statistic="Unknown queue statistic")))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "unexpected statistic"):
            self.compare()

    def test_genuine_source_only_ecc_series_is_explicitly_excluded(self):
        name = "ECC.Traffic Dropped (packets/sec)"
        self.modify_rows(lambda rows: rows.extend([dict(rows[0], statistic=name), dict(rows[1], statistic=name)]), "ns3")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "unexpected statistic"):
            self.compare()
        self.descriptor("ns3")["excluded_statistics"] = [name]
        self.save_manifest()
        result = self.compare()
        self.assertEqual(result["inputs"]["ns3"]["excluded_source_only_statistics"], {name: 2})
        self.assertEqual(len(result["comparisons"][0]["series"]), 8)

    def test_fractional_bucket_width_uses_same_grid_tolerance(self):
        self.manifest.update(duration_s=7.2, bucket_width_s=3.6)
        for source in ("matlab", "ns3", "opnet"):
            self.modify_rows(lambda rows: [row.update(time_s="3.6" if row["time_s"] == "60" else "7.2") for row in rows], source)
            self.modify_provenance(lambda value: value["window"].update(stop_time_s=7.2, bucket_width_s=3.6), source)
        self.assertEqual(self.compare()["bucket_count"], 2)

    def test_report_cannot_overwrite_a_bound_input(self):
        result = self.compare()
        output = self.root / "report"
        output.mkdir()
        (output / "comparison.json").symlink_to(self.root / "matlab-provenance.json")
        original = (self.root / "matlab-provenance.json").read_bytes()
        with self.assertRaisesRegex(benchmark.BenchmarkError, "aliases a protected input"):
            benchmark.write_report(result, output)
        self.assertEqual((self.root / "matlab-provenance.json").read_bytes(), original)

    def test_cli_emits_reusable_json_and_two_csv_tables(self):
        output = self.root / "report"
        self.assertEqual(benchmark.main(["--manifest", str(self.path), "--output", str(output)]), 0)
        report = json.loads((output / "comparison.json").read_text())
        self.assertEqual(report["status"], "structural_pass")
        self.assertNotIn("points", report)
        with (output / "bucket_comparison.csv").open(newline="") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 48)
        with (output / "series_comparison.csv").open(newline="") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 24)

    def test_duplicate_json_fields_are_rejected(self):
        self.path.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate JSON field"):
            self.compare()

    def make_case_pair(self):
        """Synthetic parser fixtures only; these are not claimed simulator runs."""
        repository = self.root / "fixture_repository"
        reference = repository / "evidence" / "reference" / "test_case"
        matlab = self.root / "returned_test_case"
        for path in (reference, matlab / "raw", matlab / "analysis", repository / "scenarios"):
            path.mkdir(parents=True)
        source_commit = "4"*40
        profile = "hist-adb97c54-bare"
        source_executable = "e"*64
        run = {"record": "run", "scenario": self.manifest["scenario"], "duration_s": "120", "seed": "128",
               "application_profile": "legacy-send-only-no-dscp", "mac_profile": "hist-2014-next-tslot-modulo-probe",
               "hop_security_profile": profile, "source_executable_sha256": source_executable}
        scenario_path = repository / "scenarios" / "test.csv"
        self.write_csv(scenario_path, [run])
        (matlab / "raw" / "scenario.csv").write_bytes(scenario_path.read_bytes())
        scenario_hash = benchmark.digest(scenario_path)
        case = {"case_id": "test_case", "scenario": self.manifest["scenario"], "scenario_sha256": scenario_hash,
                "scenario_file": "scenarios/test.csv", "profile_id": profile, "duration_s": 120,
                "seed": 128, "bucket_width_s": 60, "flow_limit": 0, "source_kind": "synthetic_diagnostic",
                "opnet_available": False}
        options = {"opnetAppGating": True, "stochasticSyncThreshold": True, "dutyCycling": True,
                   "opnetAlignedDutyCycle": True, "gatewayDiscovery": True}
        shared = {"SourceSHA256": scenario_hash, "SourceCommit": source_commit, "HistoricalBenchmark": True,
                  "FlowLimit": 0, "ApplicationProfile": run["application_profile"], "MacProfile": run["mac_profile"],
                  "HopSecurityProfile": profile, "SourceExecutableSHA256": source_executable,
                  "ApplicationPayloadExclusionBytes": 15, "BrAppExclusionBytes": 8, "NwkHeaderBytes": 7,
                  "RunOptions": options}
        summary = {"Config": {"Name": case["scenario"], "DurationSeconds": 120, "Seed": 128,
                              "ApplicationProfile": run["application_profile"], "Mac": {"SlotProfile": run["mac_profile"]},
                              "ApplicationGenerator": "historical-opnet-gated", "ApplicationFlowLimit": 0,
                              "Radio": {"EnvelopeProfile": "bare"}, "SharedScenario": shared,
                              "Nwk": {"SecurityProfile": f"behavioral-{profile}-size-only", "AdaptiveLinkControl": True}}}
        (matlab / "raw" / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        trace_bytes = b"synthetic unit-test source identity,not runtime evidence\n"
        (matlab / "raw" / "protocol_trace.csv").write_bytes(trace_bytes)
        source_hash = benchmark.digest(matlab / "raw" / "protocol_trace.csv")
        raw = {"schema": "csr-matlab-research-case-v1", "status": "completed", "execution_completed": True,
               "source_files_stable": True, "structural_checks_passed": True, "scenario": case["scenario"],
               "scenario_sha256": scenario_hash, "duration_s": 120, "seed": 128,
               "ns3_source_commit": source_commit, "flow_limit": 0, "run_options": options,
               **{key: run[key] for key in ("application_profile", "mac_profile", "hop_security_profile")},
               "files": self.file_inventory(matlab / "raw")}
        (matlab / "raw" / "case_manifest.json").write_text(json.dumps(raw), encoding="utf-8")
        for source, directory, csv_name, sidecar_name in (
                ("matlab", matlab / "analysis", "aggregates.csv", "aggregate_provenance.json"),
                ("ns3", reference, "ns3-aggregates.csv", "ns3-benchmark.provenance.json")):
            rows = self.rows(source)
            for row in rows:
                row["source_file_sha256"] = source_hash
            aggregate = directory / csv_name
            self.write_csv(aggregate, rows)
            provenance = {"schema": benchmark.PROVENANCE_SCHEMA, "source": source, "scenario": case["scenario"],
                          "scenario_sha256": scenario_hash, "profile_id": profile, "source_file_sha256": source_hash,
                          "source_file": "raw/protocol_trace.csv", "source_snapshot_sha256": "d"*64,
                          "window": {"start_time_s": 0, "stop_time_s": 120, "bucket_width_s": 60, "bucket_count": 2,
                                     "start_endpoint": "inclusive", "stop_endpoint": "exclusive"},
                          "output": {"sha256": benchmark.digest(aggregate)}}
            if source == "ns3":
                upstream = reference / "ns3-original-provenance.json"
                upstream.write_text(json.dumps({"input": {"sha256": source_hash}}), encoding="utf-8")
                provenance.update(source_commit=source_commit, excluded_extra_statistics=[],
                                  upstream_provenance={"path": upstream.name, "sha256": benchmark.digest(upstream)})
            (directory / sidecar_name).write_text(json.dumps(provenance), encoding="utf-8")
        compressed = reference / "ns3-trace.csv.gz"
        compressed.write_bytes(gzip.compress(trace_bytes))
        reference_manifest = {"schema": "csr-tranche7-benchmark-reference-case-v1", "status": "completed",
                              "case_id": case["case_id"], "case": case, "ns3_source_commit": source_commit,
                              "files": self.file_inventory(reference),
                              "compressed_artifacts": [{"path": compressed.name, "original_sha256": source_hash,
                                                        "original_bytes": len(trace_bytes)}]}
        (reference / "manifest.json").write_text(json.dumps(reference_manifest), encoding="utf-8")
        matlab_manifest = {"schema": "csr-matlab-benchmark-case-v1", "status": "completed",
                           "structural_checks_passed": True, **case, "ns3_source_commit": source_commit,
                           "source_snapshot_sha256": "d"*64, "files": self.file_inventory(matlab)}
        (matlab / "benchmark_manifest.json").write_text(json.dumps(matlab_manifest), encoding="utf-8")
        return matlab, reference

    @staticmethod
    def file_inventory(directory):
        return [{"path": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size,
                 "sha256": benchmark.digest(path)} for path in sorted(directory.rglob("*")) if path.is_file()]

    @staticmethod
    def update_json(path, change):
        content = json.loads(path.read_text(encoding="utf-8"))
        change(content)
        path.write_text(json.dumps(content), encoding="utf-8")

    def refresh_case_inventories(self, matlab):
        raw_manifest = matlab / "raw" / "case_manifest.json"
        entries = [entry for entry in self.file_inventory(matlab / "raw") if entry["path"] != "case_manifest.json"]
        self.update_json(raw_manifest, lambda data: data.update(files=entries))
        entries = [entry for entry in self.file_inventory(matlab) if entry["path"] != "benchmark_manifest.json"]
        self.update_json(matlab / "benchmark_manifest.json", lambda data: data.update(files=entries))

    def test_convenience_mode_materializes_hash_bound_input_and_verifies_trace_bytes(self):
        matlab, reference = self.make_case_pair()
        output = self.root / "case_comparison"
        result = benchmark.compare_case(matlab, reference, output)
        self.assertTrue(result["structural_gate_passed"])
        self.assertTrue(result["case_binding"]["source_trace_bytes_verified"])
        self.assertTrue((output / "comparison-input.json").is_file())
        self.assertEqual(result["case_binding"]["matlab_source_snapshot_sha256"], "d"*64)

    def test_convenience_mode_rejects_failed_case_and_swapped_identity(self):
        matlab, reference = self.make_case_pair()
        path = matlab / "benchmark_manifest.json"
        self.update_json(path, lambda value: value.update(status="failed"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "must be completed"):
            benchmark.case_input_manifest(matlab, reference)
        self.update_json(path, lambda value: value.update(status="completed", case_id="different-case"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "case_id mismatch"):
            benchmark.case_input_manifest(matlab, reference)

    def test_convenience_mode_rejects_modified_inventory_and_snapshot(self):
        matlab, reference = self.make_case_pair()
        trace = matlab / "raw" / "protocol_trace.csv"
        original = trace.read_bytes()
        trace.write_bytes(original+b"changed\n")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "inventory size/SHA-256 mismatch"):
            benchmark.case_input_manifest(matlab, reference)
        trace.write_bytes(original)
        self.update_json(matlab / "benchmark_manifest.json", lambda value: value.update(source_snapshot_sha256="a"*64))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "source snapshot mismatch"):
            benchmark.case_input_manifest(matlab, reference)

    def test_convenience_mode_checks_actual_config_after_rehashed_artifacts(self):
        matlab, reference = self.make_case_pair()
        self.update_json(matlab / "raw" / "summary.json",
                         lambda data: data["Config"].update(ApplicationGenerator="configured-count"))
        self.refresh_case_inventories(matlab)
        with self.assertRaisesRegex(benchmark.BenchmarkError, "generator/flow-limit/envelope mismatch"):
            benchmark.case_input_manifest(matlab, reference)

    def test_convenience_mode_does_not_trust_wrong_canonical_scenario_bytes(self):
        matlab, reference = self.make_case_pair()
        canonical = reference.parents[2] / "scenarios" / "test.csv"
        canonical.write_bytes(canonical.read_bytes()+b"\n")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "reference canonical scenario SHA-256 mismatch"):
            benchmark.case_input_manifest(matlab, reference)

    def test_convenience_mode_binds_gzip_plaintext_to_declared_source_hash(self):
        matlab, reference = self.make_case_pair()
        compressed = reference / "ns3-trace.csv.gz"
        original = gzip.decompress(compressed.read_bytes())
        compressed.write_bytes(gzip.compress(b"X"+original[1:]))
        self.update_json(reference / "manifest.json", lambda value: value.update(
            files=[entry for entry in self.file_inventory(reference) if entry["path"] != "manifest.json"]))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "compressed source trace SHA-256 mismatch"):
            benchmark.case_input_manifest(matlab, reference)

    def test_convenience_mode_rejects_inventory_traversal_and_input_output_overlap(self):
        matlab, reference = self.make_case_pair()
        with self.assertRaisesRegex(benchmark.BenchmarkError, "outside the input case"):
            benchmark.compare_case(matlab, reference, matlab / "report")
        self.update_json(matlab / "benchmark_manifest.json", lambda value: value["files"][0].update(path="../outside"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "normalized relative path"):
            benchmark.case_input_manifest(matlab, reference)

    def test_convenience_cli_uses_same_validation_and_fresh_output_rule(self):
        matlab, reference = self.make_case_pair()
        output = self.root / "convenience_output"
        args = ["--matlab-case", str(matlab), "--reference", str(reference), "--output", str(output)]
        self.assertEqual(benchmark.main(args), 0)
        self.assertEqual(benchmark.main(args), 2)

    def test_matlab_scientific_notation_inventory_bytes_are_exact(self):
        artifact = self.root / "scientific-byte-count.bin"
        artifact.write_bytes(b"x"*1_234_000)
        inventory = self.root / "scientific-inventory.json"
        inventory.write_text('{"files":[{"path":"scientific-byte-count.bin",'
                             '"bytes":1.234e6,"sha256":"'+benchmark.digest(artifact)+'"}]}',
                             encoding="utf-8")
        entries = benchmark.read_json(inventory)["files"]
        self.assertIs(type(entries[0]["bytes"]), float)
        self.assertEqual(benchmark._inventory(self.root, entries), {artifact.name: artifact})

    def test_inventory_byte_counts_reject_fractional_boolean_and_ambiguous_values(self):
        artifact = self.root / "one-byte.bin"
        artifact.write_bytes(b"x")
        invalid = (True, False, -1, 1.25, float("inf"), float("nan"), float(2**53), "1e0", "1.0", "")
        for value in invalid:
            with self.subTest(value=value):
                entries = [{"path": artifact.name, "bytes": value, "sha256": benchmark.digest(artifact)}]
                with self.assertRaises(benchmark.BenchmarkError):
                    benchmark._inventory(self.root, entries)

    def test_convenience_mode_accepts_integral_float_inventory_and_trace_byte_counts(self):
        matlab, reference = self.make_case_pair()
        raw_manifest = matlab / "raw" / "case_manifest.json"
        self.update_json(raw_manifest, lambda value: [entry.update(bytes=float(entry["bytes"]))
                                                     for entry in value["files"]])
        entries = [entry for entry in self.file_inventory(matlab) if entry["path"] != "benchmark_manifest.json"]
        for entry in entries:
            entry["bytes"] = float(entry["bytes"])
        self.update_json(matlab / "benchmark_manifest.json", lambda value: value.update(files=entries))
        self.update_json(reference / "manifest.json", lambda value: [entry.update(original_bytes=float(entry["original_bytes"]))
                                                                     for entry in value["compressed_artifacts"]])
        result = benchmark.compare_case(matlab, reference, self.root / "float_counts_report")
        self.assertTrue(result["structural_gate_passed"])


if __name__ == "__main__":
    unittest.main()
