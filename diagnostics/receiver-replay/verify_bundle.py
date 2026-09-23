#!/usr/bin/env python3
"""Verify the delivered files and physical-input consistency without MATLAB."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "comparison"))
from validate_inputs import validate
from compare_receiver import read_events


def hash_file(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify_entries(entries, prefix=ROOT):
    count = 0
    for entry in entries:
        path = (prefix / entry["path"]).resolve()
        assert path.is_relative_to(ROOT), ("Unsafe manifest path", entry["path"])
        assert path.is_file(), ("Missing file", entry["path"])
        assert hash_file(path) == entry["sha256"], ("File hash differs", entry["path"])
        count += 1
    return count


def main():
    package = json.loads((ROOT / "PACKAGE_FILES.json").read_text())
    sealed = json.loads((ROOT / "RUN_FILES.json").read_text())
    binding = json.loads((ROOT / "baseline_binding.json").read_text())
    counts = {
        "package_files": verify_entries(package["files"]),
        "run_files": verify_entries(sealed["files"]),
        "accepted_matlab_core_files": verify_entries(binding["matlab_baseline_files"], ROOT / "core")}
    inputs = validate(ROOT / "inputs")
    reference = read_events(ROOT / "reference" / "events.csv")
    assert reference, "Empty native reference"
    fidelity = json.loads((ROOT / "reference" / "native_fidelity.json").read_text())
    assert fidelity["native_original_timeline_exact"] and fidelity["ordered_events"] == 90
    assessed = [r for r in reference if fidelity["comparison_start_ns"] <= int(r["time_ns"]) < fidelity["comparison_end_ns"]]
    assert len(assessed) == 90
    for name, expected in fidelity["input_hashes"].items():
        assert hash_file(ROOT / "inputs" / name) == expected, ("Fidelity input changed", name)
    receipt = json.loads((ROOT / "native" / "capture" / "prefix-equality.json").read_text())
    assert receipt["exact_prefix"] and receipt["rows"] == 373815 and len(receipt["fields"]) == 30
    print(json.dumps({"verified": True, **counts, "native_reference_events_total": len(reference),
                      "native_assessed_events": len(assessed),
                      "input_checks": inputs, "matlab_executed_by_this_verifier": False}, indent=2))


if __name__ == "__main__":
    main()
