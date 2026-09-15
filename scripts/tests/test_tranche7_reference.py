"""Reference provenance and failure classification must remain fail-closed."""
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tranche7_reference_tested", ROOT / "scripts/run_tranche7_ns3_reference.py")
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)


class Tranche7ReferenceTests(unittest.TestCase):
    def workflow(self, comparison=1):
        return {"status": "selected_comparison_failed" if comparison else "selected_comparison_passed",
                "stages": {name: {"exit_code": comparison if name == "compare" else 0}
                           for name in ("extract_opnet", "run_ns3", "aggregate_ns3", "compare")}}

    def test_numeric_residual_is_only_accepted_after_completed_stages(self):
        REFERENCE.validate_workflow_completion(self.workflow(), 1)
        for stage in ("extract_opnet", "run_ns3", "aggregate_ns3"):
            with self.subTest(stage=stage):
                record = self.workflow()
                record["stages"][stage]["exit_code"] = 1
                with self.assertRaises(ValueError):
                    REFERENCE.validate_workflow_completion(record, 1)

    def test_failure_and_inconsistent_exit_are_not_numeric_results(self):
        for status, code in (("failed", 1), ("running", 0), ("selected_comparison_failed", 2)):
            with self.subTest(status=status, code=code):
                record = self.workflow()
                record["status"] = status
                with self.assertRaises(ValueError):
                    REFERENCE.validate_workflow_completion(record, code)
        with self.assertRaises(ValueError):
            REFERENCE.validate_workflow_completion(self.workflow(0), 1)

    def test_synthetic_recipes_reproduce_exact_bytes_and_preserve_radio(self):
        catalog = REFERENCE.load_json(REFERENCE.CATALOG)
        parent_path = ROOT / catalog["cases"][0]["scenario_file"]
        parent = REFERENCE.BASE.csv_rows(parent_path)
        original_radio = next(row for row in parent if row["record"] == "node")
        radio_fields = ("min_speed_kbps", "max_speed_kbps", "min_power_dbm", "max_power_dbm",
                        "link_margin_db", "ecc_threshold", "rx_frequency_hz", "tx_frequency_hz")
        for case in catalog["cases"]:
            if case["source_kind"] != "synthetic_diagnostic":
                continue
            recipe_path = ROOT / case["recipe_file"]
            recipe = REFERENCE.load_json(recipe_path)
            rows = REFERENCE.synthetic_rows(parent, recipe, REFERENCE.BASE.digest(recipe_path))
            self.assertEqual(rows, REFERENCE.BASE.csv_rows(ROOT / case["scenario_file"]))
            for node in (row for row in rows if row["record"] == "node"):
                self.assertEqual({key: node[key] for key in radio_fields},
                                 {key: original_radio[key] for key in radio_fields})
            self.assertFalse(case["opnet_available"])
        self.assertEqual(parent, REFERENCE.BASE.csv_rows(parent_path))

    def test_complete_raw_trace_survives_gzip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            data = b"schema,event,time\n" + b"example,delivery,1200\n" * 10000
            path.write_bytes(data)
            record = REFERENCE.compress(path)
            self.assertFalse(path.exists())
            self.assertEqual(gzip.decompress((Path(directory) / record["path"]).read_bytes()), data)
            self.assertEqual(record["original_bytes"], len(data))

    def test_sidecar_rejects_missing_series_and_mixed_source_identity(self):
        case = REFERENCE.load_json(REFERENCE.CATALOG)["cases"][0]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            rows = [{"source": "ns3", "scenario": case["scenario"], "source_file_sha256": "a" * 64,
                     "statistic": statistic} for statistic in REFERENCE.CORE]
            path = destination / "ns3-aggregates.csv"
            (destination / "ns3-aggregates.provenance.json").write_text("{}\n")
            REFERENCE.write_csv(path, rows)
            sidecar = REFERENCE.normalized_sidecar(case, destination, "ns3")
            self.assertEqual(sidecar["window"]["bucket_count"], 100)
            for mutated in (rows[:-1], [dict(rows[0], source_file_sha256="b" * 64), *rows[1:]],
                            [dict(rows[0], source="opnet"), *rows[1:]]):
                REFERENCE.write_csv(path, mutated)
                with self.assertRaises(ValueError):
                    REFERENCE.normalized_sidecar(case, destination, "ns3")


if __name__ == "__main__":
    unittest.main()
