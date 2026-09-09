#!/usr/bin/env python3
"""Validate Tranche 5 evidence and describe variation across distinct seeds.

Python standard library only. The inputs are completed MATLAB exports, not
simulator execution, cross-simulator equivalence or statistical acceptance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import sys
from collections import defaultdict


SCHEMA = "csr-matlab-tranche-5-validation-v1"
REPORT_SCHEMA = "csr-matlab-research-sweep-analysis-v1"
IDENTITY = ("CaseId", "Experiment", "Parameter", "Value", "Seed")
GROUP_FIELDS = ("Experiment", "Parameter", "Value")
STAT_FIELDS = ("Metric", "SeedCount", "FiniteCount", "MissingCount", "Mean",
               "SampleStd", "Min", "Max")
COUNT_METRICS = (
    "Generated", "Received", "Dropped", "Pending", "PhysicalTransmissions",
    "HopDataRetransmissions", "HopControlRetransmissions", "ControlFailures",
    "HopControlFailures", "NeighborDeactivations", "RouteChanges", "ControlPending",
    "ControlPendingTargets", "NwkPendingControlMessages", "HopPendingData",
    "NwkPendingCustody", "ResendQueueDepth", "DackHoldCount", "PhysicalPending",
)
BOOL_METRICS = ("DataDrained", "ControlsDrained", "OwnershipDrained")
OPTIONAL_METRICS = ("DeliveryRatio", "LatencyP95Seconds", "MaxLatencySeconds")
METRICS = OPTIONAL_METRICS + COUNT_METRICS + BOOL_METRICS


class EvidenceError(ValueError):
    """An input cannot support an internally consistent descriptive report."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def json_object(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"{path.name}: duplicate JSON key {key}")
            result[key] = value
        return result

    def constant(value):
        raise EvidenceError(f"{path.name}: nonfinite JSON literal {value}")

    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"),
                            object_pairs_hook=pairs, parse_constant=constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Cannot read {path}: {exc}") from exc
    require(isinstance(result, dict), f"{path.name}: expected JSON object")
    return result


def csv_rows(path, fields=()):
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            names = reader.fieldnames
            require(names and len(names) == len(set(names)),
                    f"{path.name}: missing header or duplicate columns")
            require(set(fields) <= set(names), f"{path.name}: missing CSV columns")
            rows = []
            for index, row in enumerate(reader, 2):
                require(None not in row and all(v is not None for v in row.values()),
                        f"{path.name}:{index}: malformed or truncated row")
                rows.append(row)
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise EvidenceError(f"Cannot read {path}: {exc}") from exc


def integer(value, label):
    require(not isinstance(value, bool) and re.fullmatch(r"[0-9]+", str(value)),
            f"{label}: expected nonnegative integer")
    return int(value)


def finite(value, label):
    require(not isinstance(value, bool), f"{label}: Boolean is not numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceError(f"{label}: invalid numeric value {value!r}") from exc
    require(math.isfinite(number), f"{label}: expected finite number")
    return number


def boolean(value, label):
    if type(value) is bool:
        return value
    require(value in ("true", "false", "1", "0"), f"{label}: expected Boolean")
    return value in ("true", "1")


def entries(value, label, *, nonempty=True):
    # MATLAB jsonencode writes scalar structs as objects, arrays as lists.
    if isinstance(value, dict):
        value = [value]
    require(isinstance(value, list) and (bool(value) or not nonempty)
            and all(isinstance(entry, dict) for entry in value),
            f"{label}: expected {'nonempty ' if nonempty else ''}object array")
    return value


def safe_path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative
            and ":" not in relative and "\x00" not in relative,
            f"Unsafe relative path: {relative!r}")
    part = PurePosixPath(relative)
    require(not part.is_absolute() and all(p not in (".", "..", "") for p in relative.split("/")),
            f"Unsafe relative path: {relative}")
    path = root.joinpath(*part.parts)
    require(path.resolve().is_relative_to(root.resolve()), f"Path escapes evidence: {relative}")
    return path


def valid_hash(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            f"{label}: invalid SHA-256")
    return value


def inventory(root, raw, label):
    found = {}
    for entry in entries(raw, label):
        name = entry.get("path")
        path = safe_path(root, name)
        require(name not in found, f"{label}: duplicate inventory path {name}")
        require(path.is_file(), f"{label}: missing file {name}")
        require(path.stat().st_size == integer(entry.get("bytes"), f"{name} bytes"),
                f"{label}: byte count mismatch for {name}")
        require(digest(path) == valid_hash(entry.get("sha256"), name),
                f"{label}: SHA-256 mismatch for {name}")
        if entry.get("row_count") not in (None, []):
            require(path.suffix == ".csv", f"{name}: row_count on non-CSV file")
            require(len(csv_rows(path)) == integer(entry["row_count"], f"{name} row_count"),
                    f"{name}: row_count mismatch")
        found[name] = entry
    return found


def snapshot(raw, label):
    result = {}
    for entry in entries(raw, label):
        name = entry.get("path")
        # Reuse path validation without requiring the source tree on disk.
        safe_path(Path("/snapshot"), name)
        require(name not in result, f"{label}: duplicate source path {name}")
        result[name] = valid_hash(entry.get("sha256"), name)
    require(any(name.endswith(".m") for name in result), f"{label}: no MATLAB source files")
    return result


def identity(row, label):
    require(all(field in row for field in IDENTITY), f"{label}: missing case identity")
    for field in ("CaseId", "Experiment", "Parameter"):
        require(isinstance(row[field], str) and re.fullmatch(r"[A-Za-z0-9_-]+", row[field]),
                f"{label}: invalid {field}")
    seed = integer(row["Seed"], f"{label} Seed")
    require(seed <= 2**32 - 1, f"{label}: seed outside MATLAB uint32 range")
    return (row["CaseId"], row["Experiment"], row["Parameter"],
            finite(row["Value"], f"{label} Value"), seed)


def keyed(rows, label):
    found = {}
    observations = set()
    for row in rows:
        key = identity(row, label)
        require(key[0] not in found, f"{label}: duplicate CaseId {key[0]}")
        require(key[1:] not in observations, f"{label}: duplicate parameter/seed observation")
        found[key[0]] = (key, row)
        observations.add(key[1:])
    require(found, f"{label}: no cases")
    return found


def match_keys(expected, actual, label):
    require(set(expected) == set(actual), f"{label}: missing or unexpected cases")
    for name in expected:
        require(expected[name][0] == actual[name][0], f"{label}: case identity mismatch {name}")


def descriptive(values):
    observed = [value for value in values if value is not None]
    return dict(SeedCount=len(values), FiniteCount=len(observed),
                MissingCount=len(values)-len(observed),
                Mean=statistics.mean(observed) if observed else None,
                SampleStd=statistics.stdev(observed) if len(observed) > 1 else None,
                Min=min(observed) if observed else None, Max=max(observed) if observed else None)


def choices(value, label, minimum, maximum, limit):
    if not isinstance(value, list):
        value = [value]
    require(0 < len(value) <= limit, f"{label}: invalid number of choices")
    values = [integer(item, label) for item in value]
    require(len(values) == len(set(values)) and all(minimum <= v <= maximum for v in values),
            f"{label}: duplicate or out-of-range choices")
    return values


def expected_plan(plan):
    require(plan.get("Schema") == "csr-matlab-research-sweep-plan-v1"
            and plan.get("Status") == "planned-not-executed", "Unsupported sweep plan")
    options = plan.get("Options")
    require(isinstance(options, dict), "Plan missing Options")
    seeds = choices(options.get("Seeds"), "Seeds", 0, 2**32-1, 20)
    loads = choices(options.get("LoadMultipliers"), "LoadMultipliers", 1, 8, 8)
    freshness = choices(options.get("FreshnessTimeoutSeconds"), "FreshnessTimeoutSeconds", 30, 600, 8)
    experiments = options.get("Experiments")
    if isinstance(experiments, str):
        experiments = [experiments]
    require(isinstance(experiments, list) and all(isinstance(e, str) for e in experiments)
            and len(experiments) == len(set(experiments))
            and set(experiments) <= {"offered_load", "recovery_freshness"},
            "Plan invalid Experiments")
    require(type(options.get("IncludeLongRun")) is bool, "Plan invalid IncludeLongRun")
    include_long = options["IncludeLongRun"]
    rows = []
    selected = [(e, "LoadMultiplier" if e == "offered_load" else "FreshnessTimeoutSeconds",
                 "x" if e == "offered_load" else "s", loads if e == "offered_load" else freshness)
                for e in experiments]
    if include_long:
        selected.append(("long_run", "DurationSeconds", "s", [6000]))
    for experiment, parameter, token, values in selected:
        for value in values:
            for seed in seeds:
                rows.append(dict(CaseId=f"{experiment}_{token}{value}_seed{seed}",
                                 Experiment=experiment, Parameter=parameter, Value=value, Seed=seed))
    require(0 < len(rows) <= 200 and integer(plan.get("CaseCount"), "CaseCount") == len(rows),
            "Plan CaseCount mismatch or empty/oversized plan")
    require(integer(plan.get("LongRunCaseCount"), "LongRunCaseCount") == int(include_long)*len(seeds),
            "Plan LongRunCaseCount mismatch")
    expected = keyed(rows, "reconstructed plan")
    match_keys(expected, keyed(entries(plan.get("Cases"), "plan Cases"), "plan Cases"), "plan Cases")
    return expected, seeds


def optional_metric(value, label):
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "null", "nan")):
        return None
    require(not isinstance(value, bool), f"{label}: Boolean is not numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceError(f"{label}: invalid numeric value") from exc
    # Do not turn absent/nonfinite measurements into zero-valued observations.
    if not math.isfinite(number):
        return None
    require(number >= 0, f"{label}: negative metric")
    return number


def metrics(row):
    require(all(name in row for name in METRICS), "Performance summary missing metrics")
    require(row.get("MetricsSchema") == "csr-performance-summary-v1", "Wrong performance metric schema")
    require(boolean(row.get("StructuralChecksPassed"), "StructuralChecksPassed"),
            "Performance structural checks failed")
    values = {name: integer(row[name], name) for name in COUNT_METRICS}
    values.update({name: int(boolean(row[name], name)) for name in BOOL_METRICS})
    values.update({name: optional_metric(row[name], name) for name in OPTIONAL_METRICS})
    require(values["Generated"] == values["Received"]+values["Dropped"]+values["Pending"],
            "Application accounting mismatch")
    ratio = values["DeliveryRatio"]
    if values["Generated"]:
        require(ratio is not None and math.isclose(ratio, values["Received"]/values["Generated"],
                                                 rel_tol=1e-5, abs_tol=1e-8),
                "DeliveryRatio disagrees with application counts")
    else:
        require(ratio is None, "Zero generated applications require missing DeliveryRatio")
    if not values["Received"]:
        require(all(values[name] is None for name in ("LatencyP95Seconds", "MaxLatencySeconds")),
                "No delivered applications require missing latency")
    if values["LatencyP95Seconds"] is not None and values["MaxLatencySeconds"] is not None:
        require(values["LatencyP95Seconds"] <= values["MaxLatencySeconds"], "Latency p95 exceeds maximum")
    data_drained = all(values[name] == 0 for name in (
        "Pending", "HopPendingData", "NwkPendingCustody", "ResendQueueDepth", "DackHoldCount"))
    controls_drained = all(values[name] == 0 for name in (
        "ControlPending", "ControlPendingTargets", "NwkPendingControlMessages"))
    require(bool(values["DataDrained"]) == data_drained
            and bool(values["ControlsDrained"]) == controls_drained
            and bool(values["OwnershipDrained"]) == (data_drained and controls_drained),
            "Drain flags disagree with ownership counts")
    return values


def test_status(metadata, root, files):
    requested, executed = metadata.get("TestsRequested"), metadata.get("TestsExecuted")
    require(type(requested) is bool and type(executed) is bool, "Invalid test execution flags")
    totals = {key: integer(metadata.get(key), key) for key in (
        "TestCount", "PassedTests", "FailedTests", "IncompleteTests")}
    if not requested:
        require(not executed and metadata.get("TestsPassed") is False and not any(totals.values()),
                "Unrequested tests have execution counts or pass claim")
        return dict(status="not_run", requested=False, executed=False, **totals)
    require(executed and totals["TestCount"] > 0 and totals["PassedTests"] == totals["TestCount"]
            and totals["FailedTests"] == 0 and totals["IncompleteTests"] == 0,
            "Requested tests did not complete successfully")
    test_hash = valid_hash(metadata.get("TestResultsSHA256"), "TestResultsSHA256")
    test_file = metadata.get("TestResultsFile")
    require(isinstance(test_file, str) and test_file in files
            and files[test_file]["sha256"] == test_hash, "Missing hash-bound test CSV")
    require(metadata.get("TestsPassed") is True and metadata.get("RegressionStatus") == "completed",
            "Requested regression did not pass")
    rows = csv_rows(safe_path(root, test_file), ("Name", "Passed", "Failed", "Incomplete"))
    require(len(rows) == totals["TestCount"], "Test CSV count mismatch")
    require(len({row["Name"] for row in rows}) == len(rows), "Duplicate test names")
    for column, key in (("Passed", "PassedTests"), ("Failed", "FailedTests"), ("Incomplete", "IncompleteTests")):
        require(sum(boolean(row[column], column) for row in rows) == totals[key],
                f"Test CSV {column} count mismatch")
    return dict(status="passed", requested=True, executed=True, **totals)


def analyze(directory):
    root = Path(directory).resolve()
    require(root.is_dir(), "Evidence input must be an extracted directory")
    metadata_path = root / "validation_metadata.json"
    metadata = json_object(metadata_path)
    require(metadata.get("Schema") == SCHEMA, "Unsupported Tranche 5 metadata schema")
    require(metadata.get("Status") == "completed", "Run status is not completed")
    require(metadata.get("MATLABExecuted") is True, "MATLAB execution was not recorded")
    require(metadata.get("SourceFilesStableDuringRun") is True, "Source files changed or stability is unproven")
    initial = snapshot(metadata.get("SourceFiles"), "SourceFiles")
    require(snapshot(metadata.get("SourceFilesFinal"), "SourceFilesFinal") == initial,
            "Initial and final source snapshots differ")
    source_commit = metadata.get("SourceCommit")
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit),
            "Invalid ns-3 source commit")
    files = inventory(root, metadata.get("Artifacts"), "Artifacts")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
              and p != metadata_path and p.suffix in (".csv", ".json", ".log")}
    require(set(files) == actual, "Artifacts inventory does not cover the exact exported file set")
    for name in ("sweep_plan.json", "sweep_cases.csv", "performance_summary.csv", "validation.log"):
        require(name in files, f"Missing required artifact {name}")
    require(metadata.get("SweepPlan") == "sweep_plan.json", "Unsupported SweepPlan location")
    plan = json_object(root / "sweep_plan.json")
    expected, seeds = expected_plan(plan)
    require(integer(metadata.get("PlannedCaseCount"), "PlannedCaseCount") == len(expected)
            and integer(metadata.get("CompletedCaseCount"), "CompletedCaseCount") == len(expected),
            "Run planned/completed case counts disagree with plan")
    require(isinstance(metadata.get("Options"), dict)
            and all(metadata["Options"].get(key) == value for key, value in plan["Options"].items()),
            "Run options disagree with plan")
    match_keys(expected, keyed(csv_rows(root / "sweep_cases.csv", IDENTITY), "sweep_cases.csv"), "sweep_cases.csv")
    observed = keyed(csv_rows(root / "performance_summary.csv", IDENTITY + METRICS), "performance_summary.csv")
    match_keys(expected, observed, "performance_summary.csv")
    cases = keyed(entries(metadata.get("Cases"), "Cases"), "Cases")
    match_keys(expected, cases, "Cases")
    tests = test_status(metadata, root, files)
    require(metadata["Options"].get("RunTests") is metadata["TestsRequested"],
            "RunTests option disagrees with test request flag")
    native_requested = metadata.get("NativeRequested")
    require(type(native_requested) is bool and metadata["Options"].get("IncludeNative") is native_requested,
            "Native request flags disagree")
    if metadata["TestsRequested"] or native_requested:
        require(metadata.get("RegressionStatus") == "completed", "Requested regression incomplete")
    else:
        require(metadata.get("RegressionStatus") == "not_run", "Unrequested regression has execution status")
    if native_requested:
        require(metadata.get("NativeAttempted") is True and metadata.get("NativeExecuted") is True
                and metadata.get("NativeStatus") == "passed", "Requested native execution did not pass")
    else:
        require(metadata.get("NativeAttempted") is False and metadata.get("NativeExecuted") is False
                and metadata.get("NativeStatus") == "not_run", "Unrequested native execution has outcome")
    rows = []
    for name, (key, row) in observed.items():
        case = cases[name][1]
        require(case.get("Name") == name and case.get("Directory") == f"sweep/{name}"
                and case.get("DiagnosticsDirectory") == f"diagnostics/{name}",
                f"Case directory/name mismatch {name}")
        case_root = safe_path(root, case["Directory"])
        manifest_path = case_root / "case_manifest.json"
        require(digest(manifest_path) == valid_hash(case.get("ManifestSHA256"), name),
                f"Case manifest SHA-256 mismatch {name}")
        manifest = json_object(manifest_path)
        require(manifest.get("schema") == "csr-matlab-research-case-v1"
                and manifest.get("status") == "completed"
                and manifest.get("execution_completed") is True
                and manifest.get("source_files_stable") is True
                and manifest.get("structural_checks_passed") is True,
                f"Incomplete or failed case manifest {name}")
        require(snapshot(manifest.get("source_files"), f"{name} source_files") == initial,
                f"Case source snapshot mismatch {name}")
        require(manifest.get("ns3_source_commit") == source_commit
                and manifest.get("scenario") == name
                and integer(manifest.get("seed"), f"{name} seed") == key[-1],
                f"Case manifest identity mismatch {name}")
        case_files = inventory(case_root, manifest.get("files"), f"{name} files")
        for filename in ("summary.json", "research_summary.csv", "protocol_trace.csv", "phy_trace.csv"):
            require(filename in case_files, f"Case missing required artifact {filename}")
        for filename, entry in case_files.items():
            require(files.get(f"sweep/{name}/{filename}", {}).get("sha256") == entry["sha256"],
                    f"Case inventory disagrees with run inventory {name}/{filename}")
        summary = json_object(case_root / "summary.json")
        config = summary.get("Config", {})
        sweep = config.get("Research", {}).get("Sweep", {})
        declared = dict(sweep, CaseId=config.get("Name"))
        require(identity(declared, f"{name} Config") == key
                and integer(config.get("Seed"), f"{name} config seed") == key[-1]
                and summary.get("Metadata", {}).get("SourceCommit") == source_commit,
                f"Archived config identity mismatch {name}")
        require(finite(config.get("DurationSeconds"), "DurationSeconds") ==
                finite(manifest.get("duration_s"), "duration_s") and
                finite(row.get("DurationSeconds"), "row DurationSeconds") ==
                finite(config.get("DurationSeconds"), "DurationSeconds"), f"Case duration mismatch {name}")
        require(row.get("Scenario") == name, f"Performance scenario mismatch {name}")
        diagnostics = csv_rows(safe_path(root, f"diagnostics/{name}/performance_summary.csv"), IDENTITY + METRICS)
        require(len(diagnostics) == 1 and diagnostics[0] == row,
                f"Per-case and aggregate performance rows differ {name}")
        require(f"diagnostics/{name}/applications.csv" in files, f"Missing application diagnostics {name}")
        values = metrics(row)
        stats = summary.get("Statistics", {})
        for field in ("Generated", "Received", "Dropped", "Pending", "PhysicalTransmissions"):
            require(integer(stats.get(field), f"{name} {field}") == values[field],
                    f"Archived counters disagree with performance summary {name} {field}")
        for field in ("OmittedTraceRecords", "OmittedPhyTraceRecords"):
            require(integer(stats.get(field), field) == 0, f"Truncated trace evidence {name}")
        rows.append(dict(zip(IDENTITY, key), **values))
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in GROUP_FIELDS)].append(row)
    groups, statistics_rows = [], []
    for key, observations in sorted(grouped.items()):
        group_seeds = sorted(row["Seed"] for row in observations)
        require(group_seeds == sorted(seeds), "Unequal or duplicate seed sets cannot be pooled")
        group = dict(zip(GROUP_FIELDS, key), Seeds=group_seeds, metrics={})
        for name in METRICS:
            summary = descriptive([row[name] for row in observations])
            group["metrics"][name] = summary
            statistics_rows.append(dict(zip(GROUP_FIELDS, key), Metric=name, **summary))
        groups.append(group)
    report = dict(schema=REPORT_SCHEMA, status="descriptive_summary_completed",
                  evidence_integrity_verified=True, validation_metadata_sha256=digest(metadata_path),
                  source_files_stable=True, source_file_count=len(initial), ns3_source_commit=source_commit,
                  case_count=len(rows), seeds=sorted(seeds), tests=tests,
                  native_status=metadata["NativeStatus"], groups=groups,
                  matlab_acceptance_established=False, cross_simulator_equivalence_established=False,
                  limitations=["Descriptive statistics across equally weighted seed observations; no confidence interval or equivalence claim.",
                               "A group latency mean is the mean of per-run latency metrics, not a pooled packet quantile.",
                               "Missing/nonfinite observations are null, excluded from finite statistics, and counted explicitly.",
                               "Sample standard deviation uses n-1 and is null for fewer than two finite observations.",
                               "Repeated seed identities do not guarantee paired random draws after event ordering changes.",
                               "Control draining covers exported HOP/NWK ownership; current MAC feedback queue depth is unavailable.",
                               "Hashes verify internal artifact consistency, not independent proof of runtime execution."])
    return report, rows, statistics_rows


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True, help="Extracted completed Tranche 5 run directory")
    parser.add_argument("--output", type=Path, required=True, help="Report directory outside the evidence directory")
    args = parser.parse_args(argv)
    if args.output.resolve().is_relative_to(args.evidence.resolve()):
        print("Output directory must be outside the evidence directory", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        report, rows, summaries = analyze(args.evidence)
        code = 0
    except (EvidenceError, OSError, KeyError, TypeError) as exc:
        report = dict(schema=REPORT_SCHEMA, status="invalid_evidence", error=str(exc),
                      evidence_integrity_verified=False, matlab_acceptance_established=False,
                      cross_simulator_equivalence_established=False)
        rows, summaries, code = [], [], 2
        print(f"invalid_evidence: {exc}", file=sys.stderr)
    write_csv(args.output / "seed_observations.csv", IDENTITY + METRICS, rows)
    write_csv(args.output / "group_statistics.csv", GROUP_FIELDS + STAT_FIELDS, summaries)
    (args.output / "sweep_analysis.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    if code == 0:
        print(f"Descriptive report: {len(rows)} cases; MATLAB tests {report['tests']['status']}. No acceptance or equivalence claim.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
