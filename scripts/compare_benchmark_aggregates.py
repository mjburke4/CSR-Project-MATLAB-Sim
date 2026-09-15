#!/usr/bin/env python3
"""Compare hash-bound MATLAB, ns-3 and optional OPNET application buckets.

The gate is structural: exact scenario/profile provenance, eight source-defined
series, units, aggregation semantics and complete bucket grids. Numeric and
no-sample differences are reported without a tolerance-based parity claim.
Inputs are read only. A comparison manifest uses paths relative to itself::

  {"schema":"csr-benchmark-comparison-input-v1", "scenario":"campus",
   "scenario_sha256":"...", "profile_id":"...", "duration_s":6000,
   "bucket_width_s":60, "inputs":[
     {"source":"matlab", "aggregate_file":"matlab.csv",
      "aggregate_sha256":"...", "provenance_file":"matlab.json",
      "provenance_sha256":"..."}, ...]}

Each sidecar follows ``csr-benchmark-source-provenance-v1`` and binds source,
scenario, scenario_sha256, profile_id, source_file_sha256, window, and
output.sha256. Original source provenance may be retained as additional fields.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


INPUT_SCHEMA = "csr-benchmark-comparison-input-v1"
PROVENANCE_SCHEMA = "csr-benchmark-source-provenance-v1"
SERIES_SCHEMA = "csr-aggregate-series-v1"
REPORT_SCHEMA = "csr-benchmark-aggregate-comparison-v1"
CORE_SERIES = {
    "Generator.Traffic Sent (packets/sec)": ("packets/s", "bucket_sum_per_second"),
    "Generator.Traffic Sent (bits/sec)": ("bits/s", "bucket_sum_per_second"),
    "Generator.Packet Size (bits)": ("bits", "bucket_sample_mean"),
    "Sink.Traffic Received (packets/sec)": ("packets/s", "bucket_sum_per_second"),
    "Sink.Traffic Received (packets)": ("packets", "bucket_sum"),
    "Sink.Traffic Received (bits/sec)": ("bits/s", "bucket_sum_per_second"),
    "Sink.Traffic Received (bits)": ("bits", "bucket_sum"),
    "Sink.End-to-End Delay (seconds)": ("s", "bucket_sample_mean"),
}
REQUIRED_COLUMNS = {
    "schema", "scenario", "statistic", "time_s", "value", "source",
    "unit", "aggregation", "value_status", "source_file", "source_file_sha256",
}
OPTIONAL_SOURCE_SERIES = {
    "Generator.Packet Interarrival Time (secs)",
    "ECC.Traffic Dropped (packets/sec)",
    "HOP.Resend Queue Size (packets)",
    "MAC.ACK Queue Size (packets)",
    "MAC.Tx Queue Size (packets)",
    "MAC.Tx Queuing Delay (sec)",
    "NWK.Network Queue Size (packets)",
    "NWK.Network Queuing Delay (sec)",
}
HASH = re.compile(r"[0-9a-f]{64}\Z")


class BenchmarkError(ValueError):
    """A benchmark input cannot be compared without guessing."""


@dataclass(frozen=True)
class Point:
    value: float | None
    value_status: str
    raw_value: str


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchmarkError(message)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    def invalid_constant(value: str) -> None:
        raise BenchmarkError(f"non-finite JSON number {value}")

    with path.open(encoding="utf-8-sig") as stream:
        result = json.load(stream, object_pairs_hook=_unique_object,
                           parse_constant=invalid_constant)
    require(isinstance(result, dict), f"{path.name}: expected a JSON object")
    return result


def _text(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label}: expected nonempty text")
    require(value == value.strip(), f"{label}: surrounding whitespace is not canonical")
    return value


def _hash(value: Any, label: str) -> str:
    require(isinstance(value, str) and HASH.fullmatch(value) is not None,
            f"{label}: expected lowercase SHA-256")
    return value


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    require(not isinstance(value, bool), f"{label}: booleans are not numeric samples")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise BenchmarkError(f"{label}: expected finite numeric value") from error
    require(math.isfinite(number), f"{label}: value must be finite")
    require(number > 0 if positive else number >= 0, f"{label}: invalid negative/zero value")
    return number


def _integer(value: Any, label: str) -> int:
    # Match analyze_research_sweep.integer: MATLAB jsonencode emits some exact
    # integer counts in exponent notation, which json.loads decodes as floats.
    # Never round fractions or accept an ambiguous binary64 integer at 2**53.
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    if type(value) is float and math.isfinite(value) and value >= 0 and value.is_integer():
        require(value < 2**53, f"{label}: integer float exceeds exact safe range")
        return int(value)
    raise BenchmarkError(f"{label}: expected nonnegative integer")


def _bound_file(base: Path, entry: dict[str, Any], name: str) -> tuple[Path, str]:
    value = _text(entry.get(f"{name}_file"), f"{name}_file")
    path = (base / value).resolve()
    expected = _hash(entry.get(f"{name}_sha256"), f"{name}_sha256")
    require(path.is_file(), f"missing {name} file: {value}")
    require(digest(path) == expected, f"SHA-256 mismatch: {value}")
    return path, expected


def _window(manifest: dict[str, Any]) -> tuple[float, float, int]:
    duration = _number(manifest.get("duration_s"), "duration_s", positive=True)
    width = _number(manifest.get("bucket_width_s"), "bucket_width_s", positive=True)
    quotient = duration / width
    count = round(quotient)
    require(count > 0 and math.isclose(quotient, count, rel_tol=1e-12, abs_tol=1e-12),
            "duration_s must be an integer multiple of bucket_width_s")
    return duration, width, count


def _check_provenance(provenance: dict[str, Any], manifest: dict[str, Any],
                      source: str, aggregate_hash: str,
                      duration: float, width: float, count: int) -> str:
    require(provenance.get("schema") == PROVENANCE_SCHEMA,
            f"{source}: unsupported normalized provenance schema")
    for name, value in (("source", source), ("scenario", manifest["scenario"]),
                        ("scenario_sha256", manifest["scenario_sha256"]),
                        ("profile_id", manifest["profile_id"])):
        require(provenance.get(name) == value, f"{source}: provenance {name} mismatch")
    window = provenance.get("window")
    require(isinstance(window, dict), f"{source}: missing provenance window")
    for name, value in (("start_time_s", 0), ("stop_time_s", duration),
                        ("bucket_width_s", width), ("bucket_count", count),
                        ("start_endpoint", "inclusive"), ("stop_endpoint", "exclusive")):
        require(window.get(name) == value, f"{source}: provenance window {name} mismatch")
        if isinstance(value, (int, float)):
            require(not isinstance(window.get(name), bool),
                    f"{source}: provenance window {name} must be numeric, not boolean")
    require(window.get("timestamp", "bucket_end") == "bucket_end",
            f"{source}: timestamps must identify bucket ends")
    output = provenance.get("output")
    require(isinstance(output, dict) and output.get("sha256") == aggregate_hash,
            f"{source}: provenance output SHA-256 mismatch")
    if "profile" in manifest:
        require(provenance.get("profile") == manifest["profile"],
                f"{source}: detailed profile mismatch")
    return _hash(provenance.get("source_file_sha256"), f"{source} source_file_sha256")


def read_series(path: Path, source: str, scenario: str, source_hash: str,
                width: float, count: int, excluded: list[str]) -> tuple[dict[tuple[str, int], Point], dict[str, int]]:
    """Validate all rows and retain the exact eight core bucket series."""
    require(len(set(excluded)) == len(excluded), f"{source}: duplicate excluded statistic")
    require(set(excluded) <= OPTIONAL_SOURCE_SERIES,
            f"{source}: only named source-only interarrival/ECC/queue series may be excluded")
    points: dict[tuple[str, int], Point] = {}
    seen: set[tuple[str, str, str, float]] = set()
    excluded_counts = {name: 0 for name in excluded}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None, f"{path.name}: empty CSV")
        names = reader.fieldnames or []
        require(len(names) == len(set(names)), f"{path.name}: duplicate CSV columns")
        require(REQUIRED_COLUMNS <= set(names), f"{path.name}: missing canonical columns")
        for row_number, row in enumerate(reader, 2):
            label = f"{path.name}:{row_number}"
            require(None not in row and all(value is not None for value in row.values()),
                    f"{label}: malformed CSV row width")
            require(row["schema"] == SERIES_SCHEMA, f"{label}: unsupported aggregate schema")
            require(row["scenario"] == scenario, f"{label}: scenario mismatch")
            require(row["source"] == source, f"{label}: simulator source mismatch")
            require(row["source_file_sha256"] == source_hash, f"{label}: source-file SHA-256 mismatch")
            _text(row["source_file"], f"{label}: source_file")
            statistic = _text(row["statistic"], f"{label}: statistic")
            require(statistic in CORE_SERIES or statistic in excluded,
                    f"{label}: unexpected statistic {statistic!r}")
            time = _number(row["time_s"], f"{label}: time_s", positive=True)
            quotient = time / width
            bucket = round(quotient)
            require(1 <= bucket <= count and abs(quotient-bucket) <= 1e-12,
                    f"{label}: time is not on the expected bucket grid")
            unit, aggregation = row["unit"], row["aggregation"]
            if statistic in CORE_SERIES:
                require((unit, aggregation) == CORE_SERIES[statistic],
                        f"{label}: unit/aggregation mismatch for {statistic}")
            identity = (statistic, unit, aggregation, bucket)
            require(identity not in seen, f"{label}: duplicate series/bucket identity")
            seen.add(identity)
            value_text = row["value"].strip()
            status = row["value_status"]
            raw_value = row.get("raw_value", "")
            if value_text:
                require(status == "observed", f"{label}: numeric value requires observed status")
                value = _number(value_text, f"{label}: value")
                # Modeler's encoded sentinel is never a measured value.
                require(value != 2e100, f"{label}: OPNET no-sample sentinel was not decoded")
            else:
                require(status in {"missing", "no_sample"}, f"{label}: empty value lacks missing status")
                # Recovered Modeler stores 2e100 in empty bucket sums as well
                # as sample means. Preserve that source record: its paired
                # rate may be zero while its sum remains unobserved.
                opnet_sentinel = (source == "opnet" and bool(raw_value) and
                                  _number(raw_value, f"{label}: raw_value") == 2e100)
                require(aggregation == "bucket_sample_mean" or opnet_sentinel,
                        f"{label}: derived count/rate buckets cannot be missing without an OPNET sentinel")
                value = None
            if statistic in excluded:
                excluded_counts[statistic] += 1
            else:
                points[(statistic, bucket)] = Point(value, status, raw_value)
    expected = {(name, bucket) for name in CORE_SERIES for bucket in range(1, count+1)}
    missing = expected-set(points)
    require(not missing, f"{source}: missing required series/bucket positions: {sorted(missing)[:5]}")
    for name, observed in excluded_counts.items():
        require(observed == count, f"{source}: excluded series {name!r} does not have a complete bucket grid")
    return points, excluded_counts


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    # Scale before summing to avoid overflow when finite bucket values are large.
    result = math.fsum(value/len(values) for value in values)
    require(math.isfinite(result), "bucket mean is not representable as a finite value")
    return result


def _difference(candidate: float | None, reference: float | None) -> tuple[float | None, float | None]:
    if candidate is None or reference is None:
        return None, None
    delta = candidate-reference
    require(math.isfinite(delta), "bucket difference is not representable as a finite value")
    percent = (delta/reference)*100 if reference != 0 else None
    require(percent is None or math.isfinite(percent),
            "relative bucket difference is not representable as a finite value")
    return delta, percent


def _compare_pair(candidate: str, reference: str,
                   observations: dict[str, dict[tuple[str, int], Point]],
                   width: float, count: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summaries = []
    rows = []
    for name, (unit, aggregation) in CORE_SERIES.items():
        candidate_values, reference_values = [], []
        paired_candidate, paired_reference, deltas = [], [], []
        missing = {"both_missing": [], "candidate_missing_only": [], "reference_missing_only": []}
        for bucket in range(1, count+1):
            first = observations[candidate][(name, bucket)]
            second = observations[reference][(name, bucket)]
            first_value, second_value = first.value, second.value
            if first_value is not None:
                candidate_values.append(first_value)
            if second_value is not None:
                reference_values.append(second_value)
            if first_value is None or second_value is None:
                status = ("both_missing" if first_value is None and second_value is None else
                          "candidate_missing_only" if first_value is None else "reference_missing_only")
                missing[status].append(bucket*width)
            else:
                status = "both_observed"
                paired_candidate.append(first_value)
                paired_reference.append(second_value)
                deltas.append(first_value-second_value)
            delta, percent = _difference(first_value, second_value)
            rows.append({"candidate": candidate, "reference": reference, "statistic": name,
                         "unit": unit, "aggregation": aggregation, "time_s": bucket*width,
                         "candidate_value": first_value, "reference_value": second_value,
                         "candidate_value_status": first.value_status,
                         "reference_value_status": second.value_status,
                         "candidate_raw_value": first.raw_value,
                         "reference_raw_value": second.raw_value,
                         "comparison_status": status, "difference": delta,
                         "relative_difference_percent": percent})
        candidate_mean, reference_mean = _mean(candidate_values), _mean(reference_values)
        mean_delta, mean_percent = _difference(candidate_mean, reference_mean)
        paired_candidate_mean, paired_reference_mean = _mean(paired_candidate), _mean(paired_reference)
        paired_delta, paired_percent = _difference(paired_candidate_mean, paired_reference_mean)
        summaries.append({
            "statistic": name, "unit": unit, "aggregation": aggregation,
            "aligned_bucket_count": count, "numeric_pair_count": len(deltas),
            "exact_numeric_difference_count": sum(value != 0 for value in deltas),
            "candidate_observed_bucket_count": len(candidate_values),
            "reference_observed_bucket_count": len(reference_values),
            "candidate_observed_bucket_mean": candidate_mean,
            "reference_observed_bucket_mean": reference_mean,
            "observed_bucket_mean_difference": mean_delta,
            "observed_bucket_mean_relative_difference_percent": mean_percent,
            "paired_candidate_bucket_mean": paired_candidate_mean,
            "paired_reference_bucket_mean": paired_reference_mean,
            "paired_bucket_mean_difference": paired_delta,
            "paired_bucket_mean_relative_difference_percent": paired_percent,
            "maximum_absolute_bucket_difference": max(map(abs, deltas)) if deltas else None,
            "missing_bucket_ends_s": missing,
        })
    return {"candidate": candidate, "reference": reference, "series": summaries}, rows


def compare_manifest(manifest_path: Path) -> dict[str, Any]:
    """Return a structural comparison report; numerical residuals never fail it."""
    manifest_path = Path(manifest_path).resolve()
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == INPUT_SCHEMA, "unsupported comparison-input schema")
    for key in ("scenario", "profile_id"):
        _text(manifest.get(key), key)
    _hash(manifest.get("scenario_sha256"), "scenario_sha256")
    duration, width, count = _window(manifest)
    inputs = manifest.get("inputs")
    require(isinstance(inputs, list) and 2 <= len(inputs) <= 3,
            "comparison requires MATLAB, ns-3 and optionally OPNET inputs")
    observations, provenance_records = {}, {}
    paths: set[Path] = {manifest_path}
    for entry in inputs:
        require(isinstance(entry, dict), "input descriptor must be an object")
        source = entry.get("source")
        require(source in {"matlab", "ns3", "opnet"}, "unexpected simulator source")
        require(source not in observations, f"duplicate source input {source}")
        aggregate, aggregate_hash = _bound_file(manifest_path.parent, entry, "aggregate")
        sidecar, sidecar_hash = _bound_file(manifest_path.parent, entry, "provenance")
        require(aggregate not in paths and sidecar not in paths and aggregate != sidecar,
                "comparison inputs must identify distinct files")
        paths.update((aggregate, sidecar))
        provenance = read_json(sidecar)
        source_hash = _check_provenance(provenance, manifest, source, aggregate_hash,
                                        duration, width, count)
        excluded = entry.get("excluded_statistics", [])
        require(isinstance(excluded, list) and all(isinstance(name, str) for name in excluded),
                f"{source}: excluded_statistics must be a list of names")
        points, excluded_counts = read_series(aggregate, source, manifest["scenario"],
                                              source_hash, width, count, excluded)
        observations[source] = points
        provenance_records[source] = {
            "aggregate_file": str(aggregate), "aggregate_sha256": aggregate_hash,
            "provenance_file": str(sidecar), "provenance_sha256": sidecar_hash,
            "source_file_sha256": source_hash,
            "compared_series_count": len(CORE_SERIES), "compared_bucket_count": len(points),
            "excluded_source_only_statistics": excluded_counts,
            "provenance": provenance,
        }
    require({"matlab", "ns3"} <= set(observations), "MATLAB and ns-3 inputs are mandatory")
    pairs = [("matlab", "ns3")]
    if "opnet" in observations:
        pairs.extend((("matlab", "opnet"), ("ns3", "opnet")))
    comparisons, all_points = [], []
    for candidate, reference in pairs:
        summary, points = _compare_pair(candidate, reference, observations, width, count)
        comparisons.append(summary)
        all_points.extend(points)
    report = {
        "schema": REPORT_SCHEMA, "status": "structural_pass", "structural_gate_passed": True,
        "numeric_tolerance_gate_applied": False, "full_protocol_parity_established": False,
        "scenario": manifest["scenario"], "scenario_sha256": manifest["scenario_sha256"],
        "profile_id": manifest["profile_id"], "duration_s": duration, "bucket_width_s": width,
        "bucket_count": count, "input_manifest": str(manifest_path),
        "input_manifest_sha256": digest(manifest_path), "inputs": provenance_records,
        "comparisons": comparisons, "points": all_points,
        "interpretation": [
            "Pass means hash-bound profile, series, unit, aggregation and bucket coverage checks passed.",
            "Numeric residuals and unequal no-sample coverage remain descriptive results, not tolerance failures.",
            "Observed-bucket means use each source's measured buckets; paired means use only jointly observed buckets.",
            "Bucket sample means are not packet-weighted latency or time-weighted queue occupancy.",
            "OPNET aggregate data supplies no chronological packet, path, retry or PHY/ECC event truth.",
            "Source-file hashes bind the declared source artifacts; this tool verifies the provided CSVs and sidecars, not unprovided upstream binaries or traces.",
        ],
    }
    if "case_binding" in manifest:
        report["case_binding"] = manifest["case_binding"]
    return report


def _relative(base: Path, value: Any, label: str) -> Path:
    name = _text(value, label)
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and "\\" not in name and ":" not in name and
            all(part not in {"", ".", ".."} for part in name.split("/")),
            f"{label}: expected a normalized relative path")
    path = base.joinpath(*relative.parts)
    require(not path.is_symlink() and path.resolve().is_relative_to(base.resolve()),
            f"{label}: path escapes its artifact directory or names a symlink")
    return path


def _inventory(base: Path, entries: Any) -> dict[str, Path]:
    require(isinstance(entries, list) and bool(entries), f"{base.name}: missing file inventory")
    result = {}
    for entry in entries:
        require(isinstance(entry, dict), "inventory entry must be an object")
        path = _relative(base, entry.get("path"), "inventory path")
        require(entry["path"] not in result, "duplicate inventory path")
        require(path.is_file(), f"missing inventoried file: {entry['path']}")
        expected = _hash(entry.get("sha256"), f"{entry['path']} SHA-256")
        size = _integer(entry.get("bytes"), "inventory bytes")
        require(path.stat().st_size == size and digest(path) == expected,
                f"inventory size/SHA-256 mismatch: {entry['path']}")
        result[entry["path"]] = path
    return result


def _needed(inventory: dict[str, Path], name: str) -> Path:
    require(name in inventory, f"required artifact is not inventoried: {name}")
    return inventory[name]


def _matching_config(summary: dict[str, Any], raw: dict[str, Any], case: dict[str, Any],
                     source_commit: str, scenario: Path) -> None:
    config = summary.get("Config")
    require(isinstance(config, dict), "MATLAB summary is missing Config")
    with scenario.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    run = [row for row in rows if row.get("record") == "run"]
    require(len(run) == 1, "canonical scenario must contain one run record")
    run = run[0]
    for field, actual in (("scenario", config.get("Name")), ("application_profile", config.get("ApplicationProfile")),
                          ("mac_profile", config.get("Mac", {}).get("SlotProfile"))):
        require(actual == run.get(field), f"MATLAB actual Config {field} differs from canonical scenario")
    require(config.get("DurationSeconds") == case["duration_s"] and config.get("Seed") == case["seed"],
            "MATLAB Config duration/seed mismatch")
    require(_number(run.get("duration_s"), "canonical duration") == case["duration_s"] and
            _number(run.get("seed"), "canonical seed") == case["seed"],
            "canonical scenario duration/seed mismatch")
    require(config.get("ApplicationGenerator") == "historical-opnet-gated" and
            config.get("ApplicationFlowLimit") == case["flow_limit"] and
            config.get("Radio", {}).get("EnvelopeProfile") == "bare",
            "MATLAB benchmark generator/flow-limit/envelope mismatch")
    require(config.get("Nwk", {}).get("SecurityProfile") == f"behavioral-{case['profile_id']}-size-only" and
            config.get("Nwk", {}).get("AdaptiveLinkControl") is True,
            "MATLAB benchmark NWK security/link-adaptation profile mismatch")
    shared = config.get("SharedScenario")
    require(isinstance(shared, dict), "MATLAB Config is missing SharedScenario identity")
    for field, value in (("SourceSHA256", case["scenario_sha256"]), ("SourceCommit", source_commit),
                          ("HistoricalBenchmark", True), ("FlowLimit", case["flow_limit"]),
                          ("ApplicationProfile", run.get("application_profile")),
                          ("MacProfile", run.get("mac_profile")),
                          ("HopSecurityProfile", run.get("hop_security_profile")),
                          ("SourceExecutableSHA256", run.get("source_executable_sha256")),
                          ("ApplicationPayloadExclusionBytes", 15), ("BrAppExclusionBytes", 8),
                          ("NwkHeaderBytes", 7)):
        require(shared.get(field) == value, f"MATLAB SharedScenario {field} mismatch")
    expected_options = {"opnetAppGating": True, "stochasticSyncThreshold": True,
                        "dutyCycling": True, "opnetAlignedDutyCycle": True, "gatewayDiscovery": True}
    require(shared.get("RunOptions") == expected_options and raw.get("run_options") == expected_options,
            "MATLAB benchmark run options mismatch")
    for name in ("application_profile", "mac_profile", "hop_security_profile"):
        require(raw.get(name) == run.get(name), f"MATLAB raw manifest {name} mismatch")
    require(run.get("hop_security_profile") == case["profile_id"], "canonical atomic profile identity mismatch")


def case_input_manifest(matlab_case: Path, reference: Path) -> dict[str, Any]:
    """Validate returned/reference case artifacts and construct a bound input manifest.

    The outer return reviewer remains responsible for suite/test completeness,
    exact candidate source snapshots, and full application/custody reconciliation.
    """
    matlab_case, reference = Path(matlab_case).resolve(), Path(reference).resolve()
    matlab_manifest_path = matlab_case / "benchmark_manifest.json"
    reference_manifest_path = reference / "manifest.json"
    matlab = read_json(matlab_manifest_path)
    reference_manifest = read_json(reference_manifest_path)
    require(matlab.get("schema") == "csr-matlab-benchmark-case-v1" and
            matlab.get("status") == "completed" and matlab.get("structural_checks_passed") is True,
            "MATLAB benchmark case must be completed with a passed structural gate")
    require(reference_manifest.get("schema") == "csr-tranche7-benchmark-reference-case-v1" and
            reference_manifest.get("status") == "completed", "reference case must be completed")
    case = reference_manifest.get("case")
    require(isinstance(case, dict), "reference is missing its canonical case descriptor")
    for name in ("case_id", "scenario", "scenario_sha256", "profile_id", "duration_s",
                 "seed", "bucket_width_s", "source_kind", "opnet_available"):
        require(name in case and matlab.get(name) == case[name], f"MATLAB/reference case {name} mismatch")
    require(reference_manifest.get("case_id") == case["case_id"], "reference case_id is inconsistent")
    source_commit = reference_manifest.get("ns3_source_commit")
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None and
            matlab.get("ns3_source_commit") == source_commit, "ns-3 source commit mismatch")
    matlab_files = _inventory(matlab_case, matlab.get("files"))
    reference_files = _inventory(reference, reference_manifest.get("files"))
    scenario_path = _needed(matlab_files, "raw/scenario.csv")
    require(digest(scenario_path) == case["scenario_sha256"], "returned canonical scenario SHA-256 mismatch")
    # Reference case directories have the repository-owned evidence/<suite>/<case> layout.
    repository = reference.parents[2]
    canonical_scenario = _relative(repository, case.get("scenario_file"), "canonical scenario path")
    require(canonical_scenario.is_file() and digest(canonical_scenario) == case["scenario_sha256"],
            "reference canonical scenario SHA-256 mismatch")
    raw_path = _needed(matlab_files, "raw/case_manifest.json")
    raw = read_json(raw_path)
    require(raw.get("schema") == "csr-matlab-research-case-v1" and raw.get("status") == "completed" and
            raw.get("execution_completed") is True and raw.get("source_files_stable") is True and
            raw.get("structural_checks_passed") is True, "raw MATLAB case did not complete its structural gate")
    for name in ("scenario", "scenario_sha256", "duration_s", "seed", "ns3_source_commit"):
        require(raw.get(name) == matlab.get(name), f"raw MATLAB case {name} mismatch")
    require(raw.get("flow_limit") == case["flow_limit"], "raw MATLAB flow limit mismatch")
    _inventory(matlab_case / "raw", raw.get("files"))
    summary = read_json(_needed(matlab_files, "raw/summary.json"))
    _matching_config(summary, raw, case, source_commit, scenario_path)
    sidecar_path = _needed(matlab_files, "analysis/aggregate_provenance.json")
    sidecar = read_json(sidecar_path)
    trace = _needed(matlab_files, "raw/protocol_trace.csv")
    require(sidecar.get("source_file") == "raw/protocol_trace.csv" and
            sidecar.get("source_file_sha256") == digest(trace), "MATLAB aggregate source trace is not hash-bound")
    snapshot = matlab.get("source_snapshot_sha256")
    require(_hash(snapshot, "MATLAB source snapshot SHA-256") == sidecar.get("source_snapshot_sha256"),
            "MATLAB aggregate/source snapshot mismatch")
    duration, width, count = _window(case)
    output = {"schema": INPUT_SCHEMA, **{name: case[name] for name in
              ("scenario", "scenario_sha256", "profile_id", "duration_s", "bucket_width_s")}, "inputs": []}
    inputs = [("matlab", _needed(matlab_files, "analysis/aggregates.csv"), sidecar_path)]
    for source in ("ns3", "opnet") if case["opnet_available"] else ("ns3",):
        inputs.append((source, _needed(reference_files, f"{source}-aggregates.csv"),
                       _needed(reference_files, f"{source}-benchmark.provenance.json")))
    for source, aggregate, sidecar_path in inputs:
        provenance = read_json(sidecar_path)
        _check_provenance(provenance, output, source, digest(aggregate), duration, width, count)
        if source != "matlab":
            upstream = provenance.get("upstream_provenance")
            require(isinstance(upstream, dict), f"{source}: missing upstream provenance binding")
            upstream_path = _needed(reference_files, upstream.get("path"))
            require(digest(upstream_path) == upstream.get("sha256"), f"{source}: upstream provenance SHA-256 mismatch")
            original = read_json(upstream_path)
            if source == "ns3":
                require(provenance.get("source_commit") == source_commit and
                        original.get("input", {}).get("sha256") == provenance["source_file_sha256"],
                        "ns-3 original trace/source commit binding mismatch")
                compressed = [entry for entry in reference_manifest.get("compressed_artifacts", [])
                              if entry.get("original_sha256") == provenance["source_file_sha256"]]
                require(len(compressed) == 1, "ns-3 source trace is not uniquely preserved in compressed artifacts")
                descriptor = compressed[0]
                compressed_path = _needed(reference_files, descriptor["path"])
                expected_bytes = _integer(descriptor.get("original_bytes"), "ns-3 original trace bytes")
                require(expected_bytes > 0,
                        "ns-3 original trace byte count is invalid")
                trace_hash, bytes_read = hashlib.sha256(), 0
                with gzip.open(compressed_path, "rb") as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b""):
                        bytes_read += len(chunk)
                        require(bytes_read <= expected_bytes, "ns-3 compressed source trace exceeds declared size")
                        trace_hash.update(chunk)
                require(bytes_read == expected_bytes and trace_hash.hexdigest() == provenance["source_file_sha256"],
                        "ns-3 compressed source trace SHA-256 mismatch")
            else:
                opnet_path = _relative(repository, case.get("opnet_ov_file"), "OPNET archive path")
                require(opnet_path.is_file() and digest(opnet_path) == provenance["source_file_sha256"] and
                        original.get("provenance", {}).get("source_file_sha256") == provenance["source_file_sha256"],
                        "OPNET original archive SHA-256 mismatch")
        entry = {"source": source, "aggregate_file": str(aggregate), "aggregate_sha256": digest(aggregate),
                 "provenance_file": str(sidecar_path), "provenance_sha256": digest(sidecar_path)}
        if source != "matlab":
            entry["excluded_statistics"] = provenance.get("excluded_extra_statistics", [])
        output["inputs"].append(entry)
    output["case_binding"] = {
        "matlab_manifest_file": str(matlab_manifest_path), "matlab_manifest_sha256": digest(matlab_manifest_path),
        "reference_manifest_file": str(reference_manifest_path), "reference_manifest_sha256": digest(reference_manifest_path),
        "matlab_inventory_files_verified": len(matlab_files), "reference_inventory_files_verified": len(reference_files),
        "matlab_source_snapshot_sha256": snapshot, "source_trace_bytes_verified": True,
        "canonical_scenario_file": str(canonical_scenario), "canonical_scenario_sha256": digest(canonical_scenario),
        "scope": "Case identity, recorded generator/MAC/envelope settings, inventories, traces and aggregate provenance; outer suite acceptance is separate",
    }
    return output


def compare_case(matlab_case: Path, reference: Path, output: Path) -> dict[str, Any]:
    """Materialize a bound comparison input and reports outside the input cases."""
    matlab_case, reference, output = Path(matlab_case).resolve(), Path(reference).resolve(), Path(output).resolve()
    require(not output.is_relative_to(matlab_case) and not output.is_relative_to(reference),
            "comparison output must be outside the input case directories")
    manifest = case_input_manifest(matlab_case, reference)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "comparison-input.json"
    require(not manifest_path.exists() and not manifest_path.is_symlink(),
            "comparison-input.json already exists; choose a fresh output directory")
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    report = compare_manifest(manifest_path)
    write_report(report, output)
    return report


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(report: dict[str, Any], directory: Path) -> None:
    directory = Path(directory).resolve()
    protected = {Path(report["input_manifest"]).resolve()}
    for entry in report["inputs"].values():
        protected.update(Path(entry[name]).resolve() for name in ("aggregate_file", "provenance_file"))
    outputs = [directory / name for name in ("comparison.json", "bucket_comparison.csv", "series_comparison.csv")]
    for output in outputs:
        require(output.resolve() not in protected and
                not any(output.exists() and output.samefile(path) for path in protected),
                "report output aliases a protected input")
    for index, first in enumerate(outputs):
        for second in outputs[index+1:]:
            require(first.resolve() != second.resolve() and
                    not (first.exists() and second.exists() and first.samefile(second)),
                    "report outputs alias one another")
    directory.mkdir(parents=True, exist_ok=True)
    payload = dict(report)
    points = payload.pop("points")
    outputs[0].write_text(json.dumps(payload, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    _csv(outputs[1], points)
    summaries = []
    for pair in report["comparisons"]:
        for series in pair["series"]:
            row = {"candidate": pair["candidate"], "reference": pair["reference"], **series}
            missing = row.pop("missing_bucket_ends_s")
            row.update({f"{name}_count": len(values) for name, values in missing.items()})
            summaries.append(row)
    _csv(outputs[2], summaries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", type=Path)
    group.add_argument("--matlab-case", type=Path)
    parser.add_argument("--reference", type=Path,
                        help="Reference case directory, required with --matlab-case")
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    if bool(arguments.matlab_case) != bool(arguments.reference):
        parser.error("--reference must be supplied exactly with --matlab-case")
    try:
        if arguments.matlab_case:
            report = compare_case(arguments.matlab_case, arguments.reference, arguments.output)
        else:
            report = compare_manifest(arguments.manifest)
            write_report(report, arguments.output)
    except (BenchmarkError, OSError, json.JSONDecodeError, csv.Error) as error:
        print(f"benchmark comparison failed: {error}", file=sys.stderr)
        return 2
    print(f"{report['scenario']}: structural pass; {len(report['comparisons'])} pair comparisons; numeric differences descriptive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
