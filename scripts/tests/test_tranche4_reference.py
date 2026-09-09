"""Focused failure and provenance gates for the standalone reference utility."""

import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tranche4_reference", ROOT / "scripts/run_tranche4_ns3_reference.py")
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)


class TestReferenceContract(unittest.TestCase):
    def scenario(self, directory, changes):
        source = ROOT / "scenarios/shared/two_node_8.csv"
        rows = REFERENCE.csv_rows(source)
        for row_index, field, value in changes:
            rows[row_index][field] = str(value)
        path = Path(directory) / "scenario.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_catalog_cases_have_explicit_fixed_profile(self):
        catalog = json.loads((ROOT / "scenarios/shared/catalog.json").read_text())
        self.assertEqual(len(catalog["cases"]), 5)
        for case in catalog["cases"]:
            scenario = REFERENCE.validate_scenario(ROOT / "scenarios/shared" / case["path"], case["flow_limit"])
            self.assertEqual(scenario["run"]["hop_security_profile"], "production-pairwise16")

    def test_crlf_is_rejected_without_altering_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.csv"
            content = (ROOT / "scenarios/shared/two_node_8.csv").read_bytes().replace(b"\n", b"\r\n")
            path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "LF line endings"):
                REFERENCE.validate_scenario(path, 3)
            self.assertEqual(path.read_bytes(), content)

    def test_profile_mixing_and_dynamic_destination_rejected(self):
        for changes in [[(0, "ack_envelope_profile", "hist-adb97c54-bare")],
                        [(0, "application_profile", "legacy-send-only-no-dscp")],
                        [(3, "flow_destination_mode", "random_route_or_neighbor")]]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    REFERENCE.validate_scenario(self.scenario(directory, changes), 3)

    def test_unequal_heights_and_rate_ranges_rejected(self):
        for changes in [[(2, "height_m", 2)], [(1, "max_speed_kbps", 128), (2, "max_speed_kbps", 128)]]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    REFERENCE.validate_scenario(self.scenario(directory, changes), 3)

    def test_stop_boundary_and_invalid_size_rejected(self):
        for changes in [[(0, "duration_s", 150)], [(3, "flow_packet_bytes", 14)]]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    REFERENCE.validate_scenario(self.scenario(directory, changes), 3)

    def test_cmake_include_shim_resolves_to_checked_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            actual = path / "actual.h"
            actual.write_text("#pragma once\n")
            shim = path / "shim.h"
            shim.write_text('#include "actual.h"\n')
            self.assertEqual(REFERENCE.resolved_header(shim), actual)
            self.assertEqual(REFERENCE.resolved_header(actual), actual)

    def test_missing_trace_writes_failed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            runner = output / "runner"
            runner.write_bytes(b"test executable stand-in")
            case = {"name": "two_node_8", "path": "two_node_8.csv", "flow_limit": 3, "extension": False}
            result = subprocess.CompletedProcess([], 0, "CSR differential scenario complete: test\n", "")
            with patch.object(REFERENCE.subprocess, "run", return_value=result):
                with self.assertRaises(FileNotFoundError):
                    REFERENCE.execute_case(case, ROOT / "scenarios/shared", output, runner, output, output, {}, "0" * 64)
            manifest = json.loads((output / "two_node_8/manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertFalse(manifest["execution_completed"])
            self.assertFalse(manifest["source_files_stable"])

    def test_malformed_failure_csv_remains_hashable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            path.write_text("a,b\n1,2,3\n")
            record = REFERENCE.file_record(path, Path(directory))
            self.assertIn("csv_error", record)
            self.assertEqual(record["sha256"], REFERENCE.digest(path))


if __name__ == "__main__":
    unittest.main()
