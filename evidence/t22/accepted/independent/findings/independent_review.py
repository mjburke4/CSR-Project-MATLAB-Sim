#!/usr/bin/env python3
"""Independent numeric T22 comparison; does not import the issued checker."""
import collections
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "csr22"
ARCHIVE = ROOT / "upload/t22.zip"
OUT = Path(__file__).parent


def csv_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    with zipfile.ZipFile(ARCHIVE) as z:
        states = csv_rows(z.read("contract/checkpoints.csv"))
        actions = csv_rows(z.read("contract/actions.csv"))
        tests = csv_rows(z.read("tests.csv"))
        metadata = json.loads(z.read("metadata.json"))
        inputs_identical = all(z.read("contract/" + name) ==
            (SOURCE / "scenarios/t22" / name).read_bytes()
            for name in ["actions.csv", "cases.csv"])
    native_path = SOURCE / "evidence/t22/native/checkpoints.csv"
    native = csv_rows(native_path.read_bytes())
    contract = json.loads((SOURCE / "scenarios/t22/contract.json").read_bytes())
    assert inputs_identical
    assert len(states) == len(actions) == len(native) == 364
    assert list(states[0]) == list(native[0]) == contract["state_columns"]
    mismatches = []
    max_time_delta = Decimal(0)
    integer_fields = contract["state_columns"][6:]
    accepted = collections.Counter()
    case_sizes = collections.Counter()
    by_key = {}
    invariants = 0
    for index, (actual, reference, action) in enumerate(zip(states, native, actions)):
        key = (actual["case_id"], int(actual["step"]))
        assert key not in by_key
        by_key[key] = actual
        case_sizes[actual["case_id"]] += 1
        for field in ["case_id", "step", "action", "packet", "peer"]:
            assert actual[field] == action[field]
        for field in actual:
            if field == "time_s":
                delta = abs(Decimal(actual[field]) - Decimal(reference[field]))
                max_time_delta = max(max_time_delta, delta)
                match = delta <= Decimal("1e-9")
                assert abs(Decimal(actual[field]) - Decimal(action[field])) <= Decimal("1e-9")
            elif field in integer_fields or field in ["step", "peer"]:
                match = int(actual[field]) == int(reference[field])
            else:
                match = actual[field] == reference[field]
            if not match:
                mismatches.append({"row": index + 1, "case_id": key[0],
                    "step": key[1], "field": field,
                    "matlab": actual[field], "native": reference[field]})
        n = {field: int(actual[field]) for field in integer_fields}
        if actual["action"] == "SEND" and n["accepted"] == 1:
            accepted[key[0]] += 1
        assert n["global_pending"] == n["resend"] + n["dack_holds"]
        assert accepted[key[0]] == n["ack_total"] + n["dack_total"] + n["fail_total"] + n["resend"]
        assert n["nsdp_release_total"] == n["ack_total"] + n["dack_total"] + n["fail_total"]
        assert 0 <= n["threshold"] <= 16
        assert 0 <= n["ack_count"] <= 2
        invariants += 5
    milestone_fields = 0
    for milestone in contract["milestones"]:
        actual = by_key[(milestone["case_id"], milestone["step"])]
        for field, expected in milestone["equals"].items():
            assert int(actual[field]) == expected, (milestone, actual)
            milestone_fields += 1
    assert len(tests) == 89
    assert all(row["Passed"] == "1" and row["Failed"] == "0" and row["Incomplete"] == "0" for row in tests)
    expected_names = metadata["ExpectedTestNames"]
    assert len({row["Name"] for row in tests}) == 89
    assert sorted(row["Name"] for row in tests) == sorted(expected_names)
    assert not mismatches
    result = {
        "schema": "csr-tranche22-independent-findings-v1",
        "passed": True,
        "owner_sha256": sha(ARCHIVE.read_bytes()),
        "native_checkpoints_sha256": sha(native_path.read_bytes()),
        "issued_inputs_equal_returned_inputs": inputs_identical,
        "cases": len(case_sizes),
        "case_checkpoint_counts": dict(case_sizes),
        "matched_checkpoints": len(states),
        "discrete_state_fields_per_checkpoint": len(integer_fields),
        "discrete_state_field_comparisons": len(states) * len(integer_fields),
        "max_time_delta_seconds": str(max_time_delta),
        "milestones_checked": len(contract["milestones"]),
        "milestone_field_checks": milestone_fields,
        "conservation_and_range_checks": invariants,
        "test_count": len(tests),
        "test_classes": dict(collections.Counter(row["Name"].split("/")[0] for row in tests)),
        "runtime": metadata["Runtime"],
        "started_utc": metadata["StartedUTC"],
        "completed_utc": metadata["CompletedUTC"],
        "mismatches": mismatches,
        "scope": "Independent analysis of owner MATLAB evidence and retained native reference; no simulation executed by reviewer.",
    }
    (OUT / "independent-checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
