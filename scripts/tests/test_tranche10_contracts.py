"""Reject damaged native timing evidence and mismatched engine libraries."""
import csv
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("t10_contract_runner", ROOT / "scripts/run_tranche10_contracts.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def native_rows(self, kind):
        directory = "tranche-10-contract-reference" if kind == "mac" else "tranche-10-receiver-reference"
        with (ROOT / "evidence" / directory / "checkpoints.csv").open(newline="") as stream:
            return list(csv.DictReader(stream))

    def save_rows(self, rows):
        path = self.root / "checkpoints.csv"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["case", "checkpoint", "time_seconds", "field", "actual", "expected", "pass"])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_actual_native_references(self):
        for kind in ("mac", "rx"):
            self.assertEqual(len(runner.validate_rows(self.save_rows(self.native_rows(kind)), runner.KINDS[kind])),
                             runner.KINDS[kind]["count"])

    def test_self_reported_pass_cannot_hide_wrong_state(self):
        rows = self.native_rows("mac")
        rows[0]["actual"] = str(int(rows[0]["expected"]) + 1)
        with self.assertRaisesRegex(ValueError, "Failed native"):
            runner.validate_rows(self.save_rows(rows), runner.KINDS["mac"])

    def test_one_nanosecond_error_rejected(self):
        from decimal import Decimal
        rows = self.native_rows("rx")
        row = next(row for row in rows if row["field"] == "time_seconds")
        row["actual"] = str(Decimal(row["expected"]) + Decimal("1e-9"))
        with self.assertRaisesRegex(ValueError, "Failed native"):
            runner.validate_rows(self.save_rows(rows), runner.KINDS["rx"])

    def test_duplicate_checkpoint_cannot_replace_coverage(self):
        rows = self.native_rows("mac")
        rows[1] = copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError, "Duplicate checkpoint"):
            runner.validate_rows(self.save_rows(rows), runner.KINDS["mac"])

    def test_missing_case_rejected(self):
        rows = self.native_rows("rx")
        for row in rows:
            if row["case"] == "preamble_at_wake":
                row["case"] = "preamble_before_wake"
        with self.assertRaisesRegex(ValueError, "coverage"):
            runner.validate_rows(self.save_rows(rows), runner.KINDS["rx"])

    def test_nonfinite_time_rejected(self):
        rows = self.native_rows("mac")
        rows[0]["time_seconds"] = "NaN"
        with self.assertRaisesRegex(ValueError, "Invalid checkpoint"):
            runner.validate_rows(self.save_rows(rows), runner.KINDS["mac"])

    def engine_record(self):
        build = self.root / "build"
        (build / "lib").mkdir(parents=True)
        record = {"schema": "csr-tranche10-native-engine-rebuild-v1", "status": "passed",
                  "engine_rebuilt": True, "source_commit": runner.BASE.PIN,
                  "engine_commit": runner.ENGINE_PIN, "engine_tracked_sources_unchanged": True,
                  "csr_tracked_sources_unchanged": True, "libraries": []}
        for module in runner.BASE.MODULES:
            path = build / "lib" / f"libns3-dev-{module}-debug.so"
            path.write_bytes(module.encode())
            record["libraries"].append({"path": str(path), "sha256": runner.BASE.digest(path)})
        path = self.root / "engine.json"
        path.write_text(json.dumps(record))
        return path, build, record

    def test_changed_library_rejected(self):
        path, build, _ = self.engine_record()
        runner.validate_engine(path, build)
        (build / "lib/libns3-dev-csr-debug.so").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "differs from build record"):
            runner.validate_engine(path, build)

    def test_old_engine_or_unrebuilt_claim_rejected(self):
        path, build, record = self.engine_record()
        for field, value in (("engine_commit", "0"*40), ("engine_rebuilt", False)):
            changed = copy.deepcopy(record)
            changed[field] = value
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "fresh-engine record"):
                runner.validate_engine(path, build)


if __name__ == "__main__":
    unittest.main()
