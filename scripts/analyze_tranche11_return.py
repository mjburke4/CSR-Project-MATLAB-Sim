#!/usr/bin/env python3
"""Verify a focused Tranche 11 owner return; this program never runs MATLAB.

Malformed or incomplete evidence fails closed. A valid completed diagnostic may
still differ from native ns-3. Such differences are reported as observations,
never converted into an acceptance or full-network numerical-parity claim.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

SCHEMA = "csr-matlab-tranche-11-validation-v1"
REVIEW_SCHEMA = "csr-matlab-tranche-11-return-review-v1"
PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
CANDIDATE = "evidence/tranche-11-candidate.json"
REFERENCE = "evidence/tranche-11-replay-reference"
SOURCE_PATTERNS = ("*.m", "+csr/**/*.m", "tests/**/*.m", "examples/**/*.m",
                   "scripts/**/*.py", "scripts/**/*.cc", "scripts/**/*.h", "data/**/*",
                   "scenarios/**/*", "evidence/tranche-*-candidate.json", "evidence/source-baseline.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def integer(value, label, minimum=0):
    require(not isinstance(value, bool), f"{label}: Boolean is not an integer")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label}: invalid integer") from None
    require(number.is_finite() and number == number.to_integral_value() and number >= minimum,
            f"{label}: expected finite integer >= {minimum}")
    return int(number)


def number(value, label, *, minimum=None):
    require(not isinstance(value, bool), f"{label}: Boolean is not numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label}: invalid number") from None
    require(result.is_finite() and (minimum is None or result >= minimum), f"{label}: invalid finite number")
    return result


def logical(value, label):
    require(value in ("0", "1", "true", "false", "True", "False"), f"{label}: invalid Boolean")
    return value in ("1", "true", "True")


def safe_name(value):
    require(isinstance(value, str) and value and "\\" not in value and ":" not in value
            and not any(ord(char) < 32 for char in value), "Unsafe relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(part not in ("", ".", "..") for part in value.split("/"))
            and str(path) == value, "Unsafe relative path")
    return value


def safe_path(root, name):
    safe_name(name)
    root = Path(root).resolve()
    path = root.joinpath(*PurePosixPath(name).parts)
    require(path.resolve().is_relative_to(root), "Path escapes its evidence root")
    require(not any(part.is_symlink() for part in (path, *path.parents) if part != root.parent), "Symlink is not evidence")
    return path


def json_value(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, f"Duplicate JSON key: {key}")
            out[key] = value
        return out
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream, object_pairs_hook=unique,
                         parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"Nonfinite JSON value: {token}")))


def json_object(path):
    result = json_value(path)
    require(isinstance(result, dict), f"Expected JSON object: {path}")
    return result


def csv_rows(path, fields=None):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames),
                f"Missing or duplicate CSV columns: {path}")
        if fields is not None:
            require(reader.fieldnames == list(fields), f"Unexpected CSV schema: {path}")
        result = []
        for row in reader:
            require(None not in row and None not in row.values(), f"Malformed CSV row: {path}")
            result.append(row)
    return result


def records(value, label, *, empty=False):
    # MATLAB jsonencode represents a scalar struct as an object, not an array.
    if isinstance(value, dict):
        value = [value]
    require(isinstance(value, list) and (empty or value) and all(isinstance(row, dict) for row in value),
            f"Invalid {label} records")
    return value


def record_map(value, label, *, sizes=False, empty=False):
    result = {}
    seen = set()
    for row in records(value, label, empty=empty):
        name = safe_name(row.get("path"))
        require(name.casefold() not in seen, f"Duplicate {label} identity: {name}")
        seen.add(name.casefold())
        digest = row.get("sha256")
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), f"Invalid {label} SHA-256")
        result[name] = {"path": name, "sha256": digest}
        if sizes:
            result[name]["bytes"] = integer(row.get("bytes"), f"{label} bytes")
    return result


def all_files(root):
    result = set()
    for path in Path(root).rglob("*"):
        require(not path.is_symlink(), f"Symlink is not evidence: {path}")
        if path.is_file():
            result.add(path.relative_to(root).as_posix())
    return result


def inventory(root, raw, *, excluded=()):
    entries = record_map(raw, "artifact", sizes=True)
    require(set(entries) == all_files(root) - set(excluded), "Artifact inventory is not closed")
    for name, row in entries.items():
        path = safe_path(root, name)
        require(path.stat().st_size == row["bytes"] and sha256(path) == row["sha256"], f"Artifact hash or size mismatch: {name}")
    return entries


@contextmanager
def evidence_directory(archive):
    """Extract only bounded regular members, checking CRC as every file reaches EOF."""
    with tempfile.TemporaryDirectory(prefix="t11-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            require(len(bundle.infolist()) <= 10000, "Evidence ZIP contains too many entries")
            seen, total = set(), 0
            for member in bundle.infolist():
                name = safe_name(member.filename[:-1] if member.is_dir() else member.filename)
                require(name.casefold() not in seen, "Duplicate or case-colliding ZIP member")
                seen.add(name.casefold())
                mode = member.external_attr >> 16
                require(not stat.S_ISLNK(mode) and not (member.flag_bits & 1), "Symlink or encrypted ZIP member")
                require(not mode or stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), "Nonregular ZIP member")
                total += member.file_size
                require(total <= 512 * 1024**2 and member.file_size <= 256 * 1024**2, "Focused evidence ZIP exceeds size limit")
                target = safe_path(root, name)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
        require((root / "metadata.json").is_file(), "ZIP has no root metadata.json")
        yield root


def candidate_snapshot(root):
    paths = {path for pattern in SOURCE_PATTERNS for path in Path(root).glob(pattern) if path.is_file()}
    require(paths, "Empty candidate source snapshot")
    for path in paths:
        safe_path(root, path.relative_to(root).as_posix())
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(paths)}


def selected_test_names(source_root, files):
    require(isinstance(files, list) and files and len(set(files)) == len(files), "Invalid selected TestFiles")
    names = []
    for name in files:
        path = safe_path(source_root, name)
        require(path.suffix == ".m" and path.parent == Path(source_root) / "tests" and path.stem.startswith("Test"),
                "Unsupported MATLAB test selection")
        code = path.read_text(encoding="utf-8")
        found = []
        for match in re.finditer(r"^    methods\s*\(([^)]*)\)(.*?)(?=^    methods\b|\Z)", code, re.M | re.S):
            if re.search(r"\bTest\b", match[1]):
                found.extend(f"{path.stem}/{method}" for method in re.findall(r"^        function\s+(\w+)\s*\(", match[2], re.M))
        require(found and len(set(found)) == len(found), f"Missing or duplicate MATLAB methods: {name}")
        names.extend(found)
    require(len(set(names)) == len(names), "Duplicate selected MATLAB tests")
    return names


def verify_tests(root, metadata, source_root, candidate):
    files = candidate.get("TestFiles")
    names = selected_test_names(source_root, files)
    require(candidate.get("ExpectedTestNames") == names and metadata.get("TestFiles") == files
            and metadata.get("ExpectedTestNames") == names, "Test selection differs from candidate source methods")
    require(metadata.get("TestResultsFile") == "tests.csv", "Unexpected test results path")
    rows = csv_rows(root / "tests.csv", ("Name", "Passed", "Failed", "Incomplete", "DurationSeconds"))
    require(len(rows) == len(names) and {row["Name"] for row in rows} == set(names), "Missing or duplicate MATLAB test identity")
    for row in rows:
        require(logical(row["Passed"], "Passed") and not logical(row["Failed"], "Failed")
                and not logical(row["Incomplete"], "Incomplete"), "MATLAB test failed or incomplete")
        number(row["DurationSeconds"], "Test duration", minimum=0)
    require(metadata.get("TestsExecuted") is True and metadata.get("TestsPassed") is True
            and all(integer(metadata.get(key), key) == expected for key, expected in
                    (("TestCount", len(names)), ("PassedTests", len(names)), ("FailedTests", 0), ("IncompleteTests", 0))),
            "MATLAB test counters disagree with results")
    return {"status": "passed", "count": len(names), "names": names, "runtime_scope": "Owner-returned MATLAB execution"}


def verify_sources(root, metadata, source_root):
    expected = candidate_snapshot(source_root)
    before = record_map(json_value(root / "source.json"), "source")
    after = record_map(metadata.get("SourceFilesFinal"), "final source")
    require({name: row["sha256"] for name, row in before.items()} == expected and before == after,
            "Source snapshot differs from candidate or changed during run")
    require(metadata.get("SourceFilesStableDuringRun") is True and metadata.get("SourceSnapshotSHA256") == sha256(root / "source.json"),
            "Source snapshot hash or stability missing")
    return {"count": len(before), "sha256": sha256(root / "source.json")}


def verify_references(root, metadata, source_root, candidate):
    roots, files = candidate.get("ReferenceRoots"), candidate.get("ReferenceFiles")
    require(isinstance(roots, list) and roots and isinstance(files, list), "Candidate reference membership missing")
    require(len(set(roots)) == len(roots) and len(set(files)) == len(files), "Duplicate reference declarations")
    expected = set()
    for name in roots:
        discovered = {f"{name}/{path}" for path in all_files(safe_path(source_root, name))}
        require(discovered and not expected.intersection(discovered), "Empty or overlapping reference roots")
        expected.update(discovered)
    require(not expected.intersection(files), "Overlapping reference files")
    expected.update(safe_name(name) for name in files)
    before = record_map(json_value(root / "references.json"), "reference", sizes=True)
    after = record_map(metadata.get("ReferenceFilesFinal"), "final reference", sizes=True)
    require(set(before) == expected and before == after, "Reference inventory differs from candidate or changed during run")
    require(metadata.get("ReferenceFilesStableDuringRun") is True
            and metadata.get("ReferenceSnapshotSHA256") == sha256(root / "references.json"), "Reference snapshot hash or stability missing")
    for name, row in before.items():
        path = safe_path(source_root, name)
        require(path.is_file() and sha256(path) == row["sha256"] and path.stat().st_size == row["bytes"],
                f"Reference hash or size mismatch: {name}")
    return {"count": len(before), "sha256": sha256(root / "references.json")}


EVENT_FIELDS = ("case", "order", "time_ns", "event", "node", "peer", "app_source", "app_id", "hop_seq",
                "ack_bits", "dack_bits", "mac_state", "ack_queue", "data_queue", "prep", "counter", "opportunity",
                "advertised", "hop_pending", "neighbor_outstanding", "neighbor_threshold", "resend_queue", "admitted",
                "rate_kbps", "power_dbm")
DRAW_FIELDS = ("case", "node", "ordinal", "time_ns", "min", "max", "draw", "resolved", "purpose")
USAGE_FIELDS = ("case", "node", "supplied", "consumed", "unused")
EVENT_NAMES = {"offer", "admit", "blocked", "tx_start", "ingress_before", "ingress_after", "release", "wake", "busy", "final"}
CASES = ("ab", "ba", "slow", "track")
NODES = (1, 2, 3)


def verify_plan(source_root, candidate):
    name = candidate.get("FixturePlan")
    require(name == "scenarios/replay/plan.json", "Unexpected replay plan path")
    path = safe_path(source_root, name)
    require(sha256(path) == candidate.get("FixturePlanSHA256"), "Replay plan hash mismatch")
    plan = json_object(path)
    require(plan.get("schema") == "csr-tranche11-replay-input-v1" and plan.get("source_pin") == PIN,
            "Replay plan schema or source pin mismatch")
    require(plan.get("cases") == list(CASES) and plan.get("nodes") == list(NODES)
            and plan.get("sources") == [2, 3] and plan.get("gateway") == 1,
            "Replay case/node membership changed")
    require(plan.get("events_schema") == list(EVENT_FIELDS) and plan.get("draws_output_schema") == list(DRAW_FIELDS),
            "Replay plan output schema changed")
    require(plan.get("applications_per_source") == 4 and plan.get("tape_entries_per_node") == 128
            and plan.get("slot_range") == 31 and plan.get("slot_reduction") == 0
            and plan.get("rate_kbps") == 128 and plan.get("power_dbm") == 33
            and plan.get("duty_cycle") is False, "Replay support or scope changed")
    cases_path = source_root / "scenarios/replay/cases.csv"
    rows = csv_rows(cases_path, ("case", "duration_seconds", "node2_a", "node2_b", "node3_a", "node3_b", "gateway_draw",
                                "track_start_seconds", "track_stop_seconds"))
    require([row["case"] for row in rows] == list(CASES), "Replay case input membership/order changed")
    expected = [(3, 7, 9, 1, 1, -1, -1), (9, 1, 3, 7, 1, -1, -1),
                (3, 7, 9, 1, 28, -1, -1), (3, 7, 9, 1, 1, Decimal(".25"), Decimal(".65"))]
    for row, values in zip(rows, expected):
        require(number(row["duration_seconds"], "Case duration") == 8, "Replay duration changed")
        require(tuple(number(row[field], field) for field in list(row)[2:]) == values, "Replay prescribed case changed")
    tape_path = source_root / "scenarios/replay/draws.csv"
    tape = csv_rows(tape_path, ("case", "node", "ordinal", "min", "max", "draw"))
    tape_map = {}
    for row in tape:
        key = (row["case"], integer(row["node"], "Tape node"), integer(row["ordinal"], "Tape ordinal", 1))
        require(key[0] in CASES and key[1] in NODES and key not in tape_map, "Duplicate or unknown tape identity")
        require(integer(row["min"], "Tape minimum") == 0 and integer(row["max"], "Tape maximum") == 31
                and 0 <= integer(row["draw"], "Tape draw") <= 31, "Tape support mismatch")
        tape_map[key] = {field: integer(row[field], field) for field in ("min", "max", "draw")}
    require(set(tape_map) == {(case, node, ordinal) for case in CASES for node in NODES for ordinal in range(1, 129)},
            "Tape is incomplete or contains excess ordinals")
    return plan, tape_map


def validate_events(rows, *, label):
    require(rows, f"{label}: empty events")
    previous_case, next_order, last_time, final_nodes = -1, 1, Decimal(0), set()
    admissions = set()
    case_counts = {case: 0 for case in CASES}
    for row in rows:
        require(tuple(row) == EVENT_FIELDS, f"{label}: unexpected event fields")
        case = row["case"]
        require(case in CASES, f"{label}: unknown event case")
        case_index = CASES.index(case)
        if case_index != previous_case:
            require(case_index == previous_case + 1 and (previous_case < 0 or final_nodes == set(NODES)),
                    f"{label}: missing, repeated or reordered event case")
            previous_case, next_order, last_time, final_nodes = case_index, 1, Decimal(0), set()
        order = integer(row["order"], "Event order", 1)
        require(order == next_order, f"{label}: missing or duplicate event order")
        next_order += 1
        when = number(row["time_ns"], "Event time", minimum=0)
        require(last_time <= when <= 8_000_000_000, f"{label}: event time is unordered or outside fixture")
        last_time = when
        event = row["event"]
        require(event in EVENT_NAMES, f"{label}: unsupported event kind")
        node = integer(row["node"], "Event node", 1)
        peer = integer(row["peer"], "Event peer")
        require(node in NODES and peer in (0, *NODES), f"{label}: unknown event node")
        for field in EVENT_FIELDS[6:]:
            if field == "power_dbm":
                number(row[field], field)
            else:
                integer(row[field], field, -1 if field in ("counter", "opportunity", "advertised", "neighbor_threshold") else 0)
        require(integer(row["mac_state"], "MAC state") <= 3 and integer(row["prep"], "Preparation flag") <= 1,
                f"{label}: invalid MAC state or preparation flag")
        require(integer(row["admitted"], "Admission counter") <= 4, f"{label}: impossible admission counter")
        require(integer(row["ack_bits"], "ACK bitmap") <= 2**64-1 and integer(row["dack_bits"], "DACK bitmap") <= 2**64-1,
                f"{label}: invalid bitmap")
        if event in ("offer", "admit", "blocked"):
            require(node in (2, 3) and integer(row["app_source"], "Application source") == node
                    and 1 <= integer(row["app_id"], "Application ID") <= 4, f"{label}: invalid offered application identity")
        if event == "admit":
            key = (case, node, integer(row["app_id"], "Application ID"))
            require(key not in admissions, f"{label}: duplicate admitted application")
            admissions.add(key)
        if event == "final":
            require(when == 8_000_000_000 and node not in final_nodes, f"{label}: duplicate or early final observation")
            final_nodes.add(node)
        case_counts[case] += 1
    require(previous_case == len(CASES)-1 and final_nodes == set(NODES), f"{label}: incomplete final case")
    return case_counts


def validate_draws(rows, usage, tape, *, label):
    require(rows, f"{label}: empty draws")
    counts = {(case, node): 0 for case in CASES for node in NODES}
    previous_case, when_previous = -1, Decimal(0)
    for row in rows:
        require(tuple(row) == DRAW_FIELDS, f"{label}: unexpected draw fields")
        case, node = row["case"], integer(row["node"], "Draw node", 1)
        require(case in CASES and node in NODES, f"{label}: unknown draw identity")
        case_index = CASES.index(case)
        require(case_index >= previous_case, f"{label}: reordered draw case")
        if case_index != previous_case:
            previous_case, when_previous = case_index, Decimal(0)
        when = number(row["time_ns"], "Draw time", minimum=0)
        require(when_previous <= when <= 8_000_000_000, f"{label}: draw time is unordered or outside fixture")
        when_previous = when
        key = (case, node)
        counts[key] += 1
        ordinal = integer(row["ordinal"], "Draw ordinal", 1)
        require(ordinal == counts[key] and (case, node, ordinal) in tape, f"{label}: missing, duplicate or exhausted draw ordinal")
        require({field: integer(row[field], field) for field in ("min", "max", "draw")} == tape[case, node, ordinal],
                f"{label}: draw value or requested support differs from tape")
        require(row["purpose"] in ("prepare", "advertise") and 0 <= integer(row["resolved"], "Resolved slot") <= 255,
                f"{label}: unresolved or invalid production slot observation")
    seen = set()
    for row in usage:
        require(tuple(row) == USAGE_FIELDS, f"{label}: unexpected usage fields")
        key = (row["case"], integer(row["node"], "Usage node", 1))
        require(key in counts and key not in seen, f"{label}: missing or duplicate usage identity")
        seen.add(key)
        supplied, consumed, unused = (integer(row[field], field) for field in ("supplied", "consumed", "unused"))
        require(supplied == 128 and consumed == counts[key] and supplied == consumed + unused,
                f"{label}: unused tape suffix accounting mismatch")
    require(seen == set(counts), f"{label}: incomplete tape usage inventory")
    return counts


def compare_rows(actual, reference, fields, *, family):
    """Retain ordered row identity; a shifted event is never matched by sorting."""
    differences, timing_nonzero, paired = [], 0, min(len(actual), len(reference))
    max_time_difference = Decimal(0)
    for index in range(max(len(actual), len(reference))):
        left = actual[index] if index < len(actual) else None
        right = reference[index] if index < len(reference) else None
        unequal = []
        if left is None or right is None:
            unequal = ["missing_row"]
        else:
            for field in fields:
                if field in ("case", "event", "purpose"):
                    same = left[field] == right[field]
                else:
                    delta = abs(number(left[field], field) - number(right[field], field))
                    same = delta <= 1 if field == "time_ns" else delta == 0
                    if field == "time_ns":
                        max_time_difference = max(max_time_difference, delta)
                        if delta != 0:
                            timing_nonzero += 1
                if not same:
                    unequal.append(field)
        if unequal:
            differences.append({"family": family, "row": index+1, "fields": unequal,
                                "matlab": left, "ns3": right})
    return {"family": family, "matches_native": not differences, "matlab_rows": len(actual),
            "native_rows": len(reference), "paired_rows": paired, "unmatched_rows": len(differences),
            "nonzero_time_differences": timing_nonzero, "maximum_time_difference_ns": str(max_time_difference), "differences": differences}


CHECK_FIELDS = ("case", "checkpoint", "node", "actual", "expected", "pass")


def compute_checks(events, draws):
    checks = []
    def add(case, checkpoint, node, actual, expected):
        checks.append({"case": case, "checkpoint": checkpoint, "node": node,
                       "actual": actual, "expected": expected, "pass": actual == expected})
    for case in CASES:
        selected = [row for row in events if row["case"] == case]
        for node in (2, 3):
            own = [row for row in selected if integer(row["node"], "node") == node]
            releases = [row for row in own if row["event"] == "release"]
            received = {integer(row["app_id"], "app_id") for row in selected if row["event"] == "ingress_after"
                        and integer(row["node"], "node") == 1 and integer(row["app_source"], "app_source") == node
                        and integer(row["app_id"], "app_id") > 0}
            final = [row for row in own if row["event"] == "final"]
            require(len(final) == 1, "Missing or duplicate final node observation")
            add(case, "admitted", node, sum(row["event"] == "admit" for row in own), 4)
            add(case, "delivered", node, len(received), 4)
            add(case, "released", node, len(releases), 4)
            add(case, "pending", node, integer(final[0]["hop_pending"], "final pending"), 0)
            failures = sum(integer(row["hop_pending"], "pending") != integer(row["neighbor_outstanding"], "outstanding")
                           or integer(row["resend_queue"], "resend queue") <= integer(row["hop_pending"], "pending") for row in releases)
            add(case, "release_order_failures", node, failures, 0)
            add(case, "blocked_seen", node, int(any(row["event"] == "blocked" for row in own)), 1)
        add(case, "ack_transmissions_seen", 1, int(any(row["event"] == "tx_start" and integer(row["node"], "node") == 1
            and integer(row["app_source"], "app_source") == 0 for row in selected)), 1)
        add(case, "draw_resolution_failures", 0, sum(row["purpose"] not in ("prepare", "advertise")
            or integer(row["resolved"], "resolved", -1) < 0 for row in draws if row["case"] == case), 0)
    return checks


def verify_checks(root, events, draws):
    actual = csv_rows(root / "check.csv", CHECK_FIELDS)
    expected = compute_checks(events, draws)
    require(len(actual) == len(expected), "Replay checkpoint inventory incomplete")
    for row, computed in zip(actual, expected):
        require((row["case"], row["checkpoint"], integer(row["node"], "check node")) ==
                (computed["case"], computed["checkpoint"], computed["node"]), "Missing, duplicate or reordered replay checkpoint")
        require(integer(row["actual"], "check actual") == computed["actual"]
                and integer(row["expected"], "check expected") == computed["expected"]
                and logical(row["pass"], "check pass") is computed["pass"], "Replay checkpoint contradicts raw observations")
    require(all(row["pass"] for row in expected), "Replay structural checkpoint failed")
    return expected


def verify_bindings(value, source_root, expected, label):
    rows = records(value, label)
    require(len(rows) == len(expected) and {row.get("Path") for row in rows} == set(expected), f"{label} membership mismatch")
    for row in rows:
        path = safe_path(source_root, row["Path"])
        require(row.get("SHA256") == sha256(path), f"{label} hash mismatch")


def verify_replay_claims(metadata, summary, *, event_count, draw_count, checks, comparisons):
    unmatched = sum(row["unmatched_rows"] for row in comparisons)
    matches = unmatched == 0
    require(summary.get("DiagnosticCompleted") is True and summary.get("Passed") is True,
            "Replay diagnostic structural completion missing")
    require(summary.get("MatchesNative") is matches and metadata.get("ReplayMatchesNative") is matches,
            "Replay native match claim contradicts independently compared rows")
    for field, expected in (("CaseCount", 4), ("EventCount", event_count), ("DrawCount", draw_count),
                            ("CheckpointCount", len(checks)), ("FailedCount", 0), ("UnmatchedCount", unmatched)):
        require(integer(summary.get(field), field) == expected, f"Replay summary {field} contradicts raw evidence")
    for field, expected in (("ReplayCaseCount", 4), ("ReplayEventCount", event_count), ("ReplayDrawCount", draw_count),
                            ("ReplayUnmatchedCount", unmatched)):
        require(integer(metadata.get(field), field) == expected, f"Replay metadata {field} contradicts raw evidence")
    require(metadata.get("ReplayCompleted") is True, "Replay completion metadata missing")
    return matches, unmatched


def verify_native(source_root, plan):
    native = source_root / REFERENCE
    manifest = json_object(native / "manifest.json")
    require(manifest.get("schema") == "csr-tranche11-reference-files-v1" and isinstance(manifest.get("files"), dict),
            "Native reference manifest schema mismatch")
    require(set(manifest["files"]) == all_files(native) - {"manifest.json"}, "Native reference manifest is not closed")
    for name, digest in manifest["files"].items():
        require(sha256(safe_path(native, name)) == digest, f"Native reference manifest hash mismatch: {name}")
    summary = json_object(native / "summary.json")
    require(summary.get("schema") == "csr-tranche11-native-reference-v1" and summary.get("status") == "completed"
            and summary.get("source_pin") == PIN and summary.get("scope") == plan["scope"]
            and summary.get("native_source_unchanged") is True and summary.get("native_libraries_unchanged") is True
            and summary.get("matlab_execution") is False and summary.get("cross_simulator_parity_established") is False,
            "Native reference source, execution or scope mismatch")
    input_hashes = {name: sha256(source_root / "scenarios/replay" / name) for name in ("cases.csv", "draws.csv", "plan.json")}
    fixture_paths = ["scripts/run_tranche11_ns3_reference.py", "scripts/build_tranche11_overlay.py",
                     "scripts/ns3/tranche11_replay.cc", "scripts/ns3/tranche11-replay-hooks.h"]
    fixture_hashes = {Path(name).name: sha256(source_root / name) for name in fixture_paths}
    require(summary.get("input_hashes") == input_hashes and summary.get("fixture_hashes") == fixture_hashes,
            "Native reference input or fixture source binding mismatch")
    commands = records(summary.get("commands"), "native execution commands")
    require(all(integer(row.get("exit_code"), "native command exit") == 0 for row in commands), "Native reference command failed")
    controls = summary.get("disabled_seam_controls")
    require(isinstance(controls, dict) and set(controls) == {"ack", "receiver"}, "Native disabled-seam controls missing")
    for family, count, digest in (("ack", 101, "2991bbc93e5ba2c64d06a93cee278160cd9baf2fdc11b052ee5b0cb561fe4b73"),
                                  ("receiver", 154, "a3562a3f23e5603359610b150e20551f5a671298d7db529e037d842ce7206c1a")):
        paths = [native / "controls" / f"{family}-{mode}.csv" for mode in ("clean", "off")]
        observed = csv_rows(paths[0])
        require(len(observed) == count and all(logical(row["pass"], "control pass") for row in observed)
                and all(sha256(path) == digest for path in paths), "Native disabled seam changed a retained contract")
        require(controls[family] == {"checkpoints": count, "passed": True, "clean_and_disabled_byte_equal": True, "sha256": digest},
                "Native disabled-seam summary contradicts raw files")
    build = json_object(source_root / "evidence/tranche-11-native-build.json")
    require(build.get("schema") == "csr-tranche11-native-control-build-v1" and build.get("status") == "passed"
            and build.get("source_commit") == PIN and build.get("engine_commit") == "6b5cd24ea80713ce16d88575869aedd6f432bdae"
            and build.get("engine_rebuilt") is True and build.get("reused_historical_libraries") is False
            and build.get("csr_tracked_sources_unchanged") is True and build.get("engine_tracked_sources_unchanged") is True
            and build.get("build_record", {}).get("exit_code") == 0
            and build.get("build_record", {}).get("output_captured_after_process_closed") is True,
            "Native reference clean build provenance missing")
    built = {Path(row["path"]).name.removeprefix("libns3-dev-").removesuffix("-debug.so"): row["sha256"]
             for row in records(build.get("libraries"), "native libraries")}
    require(summary.get("shared_libraries") == built, "Native replay libraries differ from audited clean build")
    events = csv_rows(native / "events.csv", EVENT_FIELDS)
    draws = csv_rows(native / "draws.csv", DRAW_FIELDS)
    raw_events, raw_draws = [], []
    for case in CASES:
        raw_events.extend(csv_rows(native / "raw" / case / "events.csv", EVENT_FIELDS))
        raw_draws.extend(csv_rows(native / "raw" / case / "raw.csv", (*DRAW_FIELDS[:-1], "probes")))
    require(raw_events == events, "Native merged events differ from raw execution order")
    require(len(raw_draws) == len(draws) and all(all(left[field] == right[field] for field in DRAW_FIELDS[:-1])
            for left, right in zip(raw_draws, draws)), "Native merged draws differ from raw execution")
    require(integer(summary.get("event_count"), "native event count") == len(events)
            and integer(summary.get("draw_count"), "native draw count") == len(draws)
            and integer(summary.get("self_tests"), "native fixture self-tests") == 6,
            "Native summary count mismatch")
    require(all(row["pass"] for row in compute_checks(events, draws)), "Native reference structural chain did not finish")
    return {"event_count": len(events), "draw_count": len(draws), "disabled_seam_checkpoints": 255,
            "source_pin": PIN, "controlled_transport": True}


def verify_replay(root, metadata, source_root, candidate):
    plan, tape = verify_plan(source_root, candidate)
    require(metadata.get("ReplayDirectory") == "replay", "Unexpected replay directory")
    replay = root / "replay"
    native = source_root / REFERENCE
    require(candidate.get("ReferenceManifest") == REFERENCE + "/manifest.json", "Unexpected native reference manifest")
    require(candidate.get("ReferenceManifestSHA256") == sha256(native / "manifest.json"), "Candidate native manifest hash mismatch")
    native_provenance = verify_native(source_root, plan)
    files = [("events", EVENT_FIELDS), ("draws", DRAW_FIELDS), ("usage", USAGE_FIELDS)]
    loaded = {}
    for label, directory in (("matlab", replay), ("ns3", native)):
        loaded[label] = {family: csv_rows(directory / (family + ".csv"), fields) for family, fields in files}
        validate_events(loaded[label]["events"], label=label)
        validate_draws(loaded[label]["draws"], loaded[label]["usage"], tape, label=label)
    comparisons = [compare_rows(loaded["matlab"][family], loaded["ns3"][family], fields, family=family) for family, fields in files]
    checks = verify_checks(replay, loaded["matlab"]["events"], loaded["matlab"]["draws"])
    summary = json_object(replay / "summary.json")
    require(summary.get("Schema") == "csr-tranche11-replay-contract-v1", "Replay summary schema mismatch")
    verify_bindings(summary.get("InputBindings"), source_root,
                    ["scenarios/replay/" + name for name in ("plan.json", "cases.csv", "draws.csv")], "Replay inputs")
    verify_bindings(summary.get("ReferenceBindings"), source_root,
                    [REFERENCE + "/" + name for name in ("events.csv", "draws.csv", "usage.csv")], "Replay references")
    for field, comparison in zip(("EventsCompared", "DrawsCompared", "UsageCompared"), comparisons):
        require(integer(summary.get(field), field) == max(comparison["matlab_rows"], comparison["native_rows"]),
                f"Replay summary {field} disagrees with independently compared rows")
    require(summary.get("Runtime") == metadata.get("Runtime", {}).get("Version"), "Replay runtime differs from owner runtime")
    require(summary.get("ComparedEntireTrajectories") is True and summary.get("TimeToleranceNanoseconds") == 1
            and summary.get("Scope") == plan["scope"], "Replay comparison scope or timing tolerance changed")
    for field, comparison in zip(("EventComparison", "DrawComparison", "UsageComparison"), comparisons):
        declared = summary.get(field, {})
        expected = {"ReferencePresent": True, "SchemaMatches": True, "ActualRows": comparison["matlab_rows"],
                    "ReferenceRows": comparison["native_rows"], "ComparedRows": max(comparison["matlab_rows"], comparison["native_rows"]),
                    "UnmatchedCount": comparison["unmatched_rows"],
                    "FirstUnmatchedRow": comparison["differences"][0]["row"] if comparison["differences"] else 0}
        require(all(type(declared.get(key)) is bool and declared[key] is value if type(value) is bool else
                    integer(declared.get(key), key) == value for key, value in expected.items()),
                f"{field} contradicts independently compared rows")
        require(number(declared.get("MaximumTimeDifferenceNanoseconds"), "maximum timing difference") ==
                number(comparison["maximum_time_difference_ns"], "computed maximum timing difference"),
                f"{field} maximum timing difference contradicts raw observations")
    case_results = records(summary.get("CaseResults"), "replay case results")
    require([row.get("Case") for row in case_results] == list(CASES) and
            all(row.get("Completed") is True and row.get("ErrorIdentifier") == "" and row.get("ErrorMessage") == ""
                for row in case_results), "Replay cases have errors or incomplete/duplicate identities")
    for result in case_results:
        selected = [row for row in loaded["matlab"]["events"] if row["case"] == result["Case"]]
        observed = {"Admitted": [], "Delivered": [], "Released": [], "WakeCount": []}
        for node in NODES:
            own = [row for row in selected if integer(row["node"], "event node") == node]
            observed["Admitted"].append(sum(row["event"] == "admit" for row in own))
            observed["Released"].append(sum(row["event"] == "release" for row in own))
            observed["WakeCount"].append(sum(row["event"] == "wake" for row in own))
            observed["Delivered"].append(len({integer(row["app_id"], "application ID") for row in selected
                if row["event"] == "ingress_after" and integer(row["node"], "event node") == 1
                and integer(row["app_source"], "app source") == node and integer(row["app_id"], "app ID") > 0}))
        require(all(isinstance(result.get(field), list) and
                    [integer(value, field) for value in result[field]] == values for field, values in observed.items()),
                "Replay per-case counters contradict complete raw observations")
    matches, unmatched = verify_replay_claims(metadata, summary, event_count=len(loaded["matlab"]["events"]),
                                             draw_count=len(loaded["matlab"]["draws"]), checks=checks, comparisons=comparisons)
    return {"structural_complete": True, "matches_native": matches, "unmatched_rows": unmatched,
            "case_count": 4, "event_count": len(loaded["matlab"]["events"]), "draw_count": len(loaded["matlab"]["draws"]),
            "checkpoint_count": len(checks), "comparisons": comparisons, "scope": plan["scope"], "native_provenance": native_provenance}


def verify_baseline(metadata, source_root, candidate):
    path = safe_path(source_root, candidate.get("BaselineSourceSnapshot"))
    require(candidate.get("BaseSourceSnapshotSHA256") == sha256(path)
            == "9be444b0fb1ffbfe818cab86502a287b19e3da83467d210ef426ec3b19e183da"
            and candidate.get("BaseArchiveSHA256") == "df3ad517708fccc9e4c85d8e38c3492b97aff8d2d5236b3f05249da3cd15b900",
            "Accepted T10 baseline provenance hash mismatch")
    expected = record_map(json_value(path), "accepted T10 source")
    require(len(expected) == 225 and sum(name.endswith(".m") for name in expected) == 124,
            "Accepted T10 baseline identity/count changed")
    for name, row in expected.items():
        require(sha256(safe_path(source_root, name)) == row["sha256"], f"Accepted T10 baseline changed: {name}")
    require(integer(metadata.get("BaselineSourceFilesVerified"), "Baseline source count") == 225
            and integer(metadata.get("BaselineMatlabFilesVerified"), "Baseline MATLAB count") == 124,
            "Baseline verification counters disagree")
    return {"source_files": 225, "matlab_files": 124, "unchanged": True}


def review(evidence, source_root, output):
    evidence, source_root, output = Path(evidence).resolve(), Path(source_root).resolve(), Path(output).resolve()
    candidate = json_object(source_root / CANDIDATE)
    require(candidate.get("Schema") == "csr-tranche-11-candidate-v1" and candidate.get("Tranche") == 11
            and candidate.get("SourceCommit") == PIN and candidate.get("Cases") == list(CASES)
            and candidate.get("CaseDurationSeconds") == 8, "Candidate schema, source or case scope mismatch")
    with evidence_directory(evidence) as root:
        metadata = json_object(root / "metadata.json")
        require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 11 and metadata.get("Status") == "completed",
                "Return is not a completed Tranche 11 diagnostic")
        require(metadata.get("MATLABExecuted") is True and metadata.get("NativeExecuted") is False and metadata.get("SourceCommit") == PIN,
                "MATLAB execution or source identity missing")
        runtime = metadata.get("Runtime")
        require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB"
                and isinstance(runtime.get("Version"), str) and runtime["Version"]
                and runtime.get("DefaultBackend") == "portable", "Unsupported or missing MATLAB runtime provenance")
        require(metadata.get("CandidateFile") == CANDIDATE and metadata.get("CandidateSHA256") == sha256(source_root / CANDIDATE),
                "Candidate identity mismatch")
        from datetime import datetime
        started, completed = (datetime.fromisoformat(metadata.get(field, "").replace("Z", "+00:00"))
                              for field in ("StartedUTC", "CompletedUTC"))
        require(started.tzinfo is not None and completed.tzinfo is not None and completed >= started,
                "Invalid owner execution timestamps")
        require(metadata.get("InventoryExcludedPaths") == ["metadata.json"] and metadata.get("EvidenceArchive") == "t11.zip",
                "Evidence inventory exclusion or archive identity changed")
        local = record_map(metadata.get("LocalArtifacts", []), "local artifacts", sizes=True, empty=True)
        require(all(name.endswith(".mat") and name not in all_files(root) for name in local), "Invalid local-only artifacts")
        artifacts = inventory(root, metadata.get("Artifacts"), excluded=("metadata.json",))
        require({"run.log", "source.json", "references.json", "tests.csv", "replay/events.csv", "replay/draws.csv",
                 "replay/usage.csv", "replay/check.csv", "replay/summary.json"} <= set(artifacts), "Required focused evidence missing")
        source = verify_sources(root, metadata, source_root)
        baseline = verify_baseline(metadata, source_root, candidate)
        references = verify_references(root, metadata, source_root, candidate)
        tests = verify_tests(root, metadata, source_root, candidate)
        replay = verify_replay(root, metadata, source_root, candidate)
        require(metadata.get("FocusedGateExecuted") is True and metadata.get("DiagnosticOnly") is True
                and all(metadata.get(field) is False for field in ("FullAcceptanceGateExecuted", "AcceptanceEstablished", "NumericalParityEstablished")),
                "Focused diagnostic scope or acceptance claim contradicts authorized gate")
        result = {"schema": REVIEW_SCHEMA, "status": "focused_diagnostic_review_completed",
                  "evidence_integrity_verified": True, "focused_structural_gate_completed": True,
                  "matched_replay": replay["matches_native"], "acceptance_established": False,
                  "numerical_parity_established": False, "matlab_executed_by_reviewer": False,
                  "runtime": runtime, "evidence": {"path": evidence.name, "sha256": sha256(evidence), "bytes": evidence.stat().st_size},
                  "source": source, "baseline": baseline, "references": references, "tests": tests, "replay": replay}
    output.mkdir(parents=True, exist_ok=True)
    (output / "review.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = review(args.evidence, args.source_root, args.output)
    except (ValueError, OSError, csv.Error, zipfile.BadZipFile, KeyError, TypeError) as error:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {"schema": REVIEW_SCHEMA, "status": "review_failed", "evidence_integrity_verified": False,
                   "focused_structural_gate_completed": False, "acceptance_established": False,
                   "numerical_parity_established": False, "matlab_executed_by_reviewer": False, "error": str(error)}
        (args.output / "review.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(f"T11 evidence rejected: {error}")
        return 1
    print(f"T11 focused structural review complete; matched replay={result['matched_replay']}. MATLAB runtime is owner-returned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
