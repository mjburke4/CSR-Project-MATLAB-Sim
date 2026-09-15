#!/usr/bin/env python3
"""Verify a Tranche 6 return and compare identical cases with accepted Tranche 5.

Standard library only. Comparisons retain every application, including drops
and pending custody. Neither source hashes nor these reports establish runtime
authenticity, improved performance, or full ns-3 equivalence on their own.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import zipfile

import analyze_research_sweep as sweep

SCHEMA = "csr-matlab-tranche-6-validation-v1"
BASE = "243ed8610df807e47d3b0be36d4ce2eae0527898"
ACCEPTED_T5_CODE = "536b288d765a7b18007ff7898eaf3f2e173d9e58"
PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
BASELINE_SHA256 = "824cf0f5cb6a735ee896ebc5431be5c72f69d9d95135c8e03311238bd0ca75c1"
REPO = Path(__file__).resolve().parents[1]


def verify_wrapper(directory):
    root = Path(directory).resolve()
    metadata_path = root / "validation_metadata.json"
    metadata = sweep.json_object(metadata_path)
    sweep.require(metadata.get("Schema") == SCHEMA, "Unsupported Tranche 6 schema")
    sweep.require(metadata.get("Status") == "completed" and metadata.get("MATLABExecuted") is True,
                  "Completed MATLAB Tranche 6 execution was not recorded")
    sweep.require(metadata.get("MatlabBaseCommit") == BASE and metadata.get("SourceCommit") == PIN,
                  "Tranche 6 baseline/reference mismatch")
    sweep.require(metadata.get("AcceptedTranche5CodeCommit") == ACCEPTED_T5_CODE,
                  "Accepted Tranche 5 code identity mismatch")
    sweep.require(metadata.get("SourceFilesStableDuringRun") is True,
                  "Tranche 6 source stability is unproven")
    source = sweep.snapshot(metadata.get("SourceFiles"), "T6 source")
    sweep.require(source == sweep.snapshot(metadata.get("SourceFilesFinal"), "T6 final source"),
                  "Tranche 6 source snapshots disagree")
    files = sweep.inventory(root, metadata.get("Artifacts"), "T6 artifacts")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and p != metadata_path and p.suffix in (".csv", ".json", ".log")}
    sweep.require(set(files) == actual, "Tranche 6 artifact inventory is incomplete")
    nested = sweep.safe_path(root, metadata.get("RegressionEvidenceDirectory"))
    nested_metadata = sweep.json_object(nested / "validation_metadata.json")
    sweep.require(nested_metadata.get("SourceCommit") == PIN,
                  "Nested reference commit differs from the pinned source")
    sweep.require(isinstance(metadata.get("Runtime"), dict) and metadata["Runtime"]
                  and nested_metadata.get("Runtime") == metadata["Runtime"],
                  "Nested runtime/release identity differs from Tranche 6")
    sweep.require(sweep.digest(nested / "validation_metadata.json") ==
                  metadata.get("RegressionMetadataSHA256"), "Nested metadata hash mismatch")
    sweep.require(sweep.snapshot(nested_metadata.get("SourceFiles"), "nested source") == source,
                  "Nested regression source does not match Tranche 6")
    for field in ("TestsExecuted", "TestsPassed", "TestCount", "PassedTests", "FailedTests",
                  "IncompleteTests", "CompletedCaseCount", "PlannedCaseCount", "Options"):
        sweep.require(metadata.get(field) == nested_metadata.get(field),
                      f"Tranche 6/nested {field} mismatch")
    return root, nested, metadata, source


def extract_baseline(archive, directory):
    sweep.require(sweep.digest(archive) == BASELINE_SHA256,
                  "Baseline ZIP is not the accepted Tranche 5 return")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        sweep.require(len(names) == len(set(names)), "Duplicate baseline ZIP members")
        for name in names:
            target = sweep.safe_path(directory, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))


def application_rows(root, case, generated, received, dropped, pending):
    rows = sweep.csv_rows(root / "diagnostics" / case / "applications.csv", (
        "PacketId", "SourceId", "DestinationId", "ApplicationBytes", "Dscp", "GeneratedSeconds",
        "LastEventSeconds", "ReceivedSeconds", "LatencySeconds", "Outcome", "DropReason"))
    found = {}
    for row in rows:
        packet = sweep.integer(row["PacketId"], "PacketId")
        sweep.require(packet not in found, f"Duplicate application identity {case}/{packet}")
        for field in ("SourceId", "DestinationId", "ApplicationBytes", "Dscp"):
            row[field] = sweep.integer(row[field], field)
        row["PacketId"] = packet
        row["GeneratedSeconds"] = sweep.finite(row["GeneratedSeconds"], "GeneratedSeconds")
        last = sweep.finite(row["LastEventSeconds"], "LastEventSeconds")
        sweep.require(last >= row["GeneratedSeconds"], "Application outcome predates generation")
        row["LastEventSeconds"] = last
        sweep.require(row["Outcome"] in ("delivered", "dropped", "pending"), "Unknown application outcome")
        if row["Outcome"] == "delivered":
            when = sweep.finite(row["ReceivedSeconds"], "ReceivedSeconds")
            latency = sweep.finite(row["LatencySeconds"], "LatencySeconds")
            sweep.require(when >= row["GeneratedSeconds"] and abs(when-row["GeneratedSeconds"]-latency) < 1e-8,
                          "Application delivery time/latency mismatch")
            sweep.require(not row["DropReason"], "Delivered application retains drop reason")
            row["ReceivedSeconds"], row["LatencySeconds"] = when, latency
        else:
            for field in ("ReceivedSeconds", "LatencySeconds"):
                sweep.require(row[field] in ("", "NaN", "nan"), "Undelivered application has delivery timing")
                row[field] = None
            sweep.require(bool(row["DropReason"]) == (row["Outcome"] == "dropped"),
                          "Drop reason disagrees with terminal outcome")
        found[packet] = row
    counts = Counter(r["Outcome"] for r in found.values())
    sweep.require(len(found) == generated and counts["delivered"] == received
                  and counts["dropped"] == dropped and counts["pending"] == pending,
                  f"Application diagnostics disagree with aggregate outcomes: {case}")
    return found


def compare_cases(current_root, baseline_root, current_rows, baseline_rows):
    baseline = {r["CaseId"]: r for r in baseline_rows}
    comparisons, applications = [], []
    for row in current_rows:
        case = row["CaseId"]
        sweep.require(case in baseline, f"No accepted baseline for {case}")
        old = baseline[case]
        current_config = sweep.json_object(current_root / "sweep" / case / "summary.json")["Config"]
        old_config = sweep.json_object(baseline_root / "sweep" / case / "summary.json")["Config"]
        sweep.require(current_config == old_config, f"Scenario/configuration changed: {case}")
        records = []
        for root, item in ((baseline_root, old), (current_root, row)):
            records.append(application_rows(root, case, *[item[k] for k in
                           ("Generated", "Received", "Dropped", "Pending")]))
        before, after = records
        sweep.require(before.keys() == after.keys(), f"Application identities changed: {case}")
        both = []
        for packet in before:
            a, b = before[packet], after[packet]
            identity = ("SourceId", "DestinationId", "ApplicationBytes", "Dscp", "GeneratedSeconds")
            sweep.require(all(a[k] == b[k] for k in identity), f"Application input changed: {case}/{packet}")
            delta = None
            if a["Outcome"] == b["Outcome"] == "delivered":
                delta = b["LatencySeconds"]-a["LatencySeconds"]
                both.append(delta)
            applications.append(dict(CaseId=case, PacketId=packet,
                **{k: a[k] for k in identity}, BeforeOutcome=a["Outcome"], AfterOutcome=b["Outcome"],
                BeforeLatencySeconds=a["LatencySeconds"], AfterLatencySeconds=b["LatencySeconds"],
                BothDeliveredLatencyDeltaSeconds=delta,
                BeforeDropReason=a["DropReason"], AfterDropReason=b["DropReason"]))
        item = {k: row[k] for k in sweep.IDENTITY}
        for metric in ("Generated", "Received", "Dropped", "Pending", "NwkPendingCustody", "HopPendingData",
                       "NeighborDeactivations", "RouteChanges", "ControlFailures", "HopDataRetransmissions"):
            item.update({"Before"+metric: old[metric], "After"+metric: row[metric],
                         "Delta"+metric: row[metric]-old[metric]})
        item.update(BothDeliveredCount=len(both),
                    BothDeliveredMeanLatencyDeltaSeconds=sum(both)/len(both) if both else None)
        comparisons.append(item)
    return comparisons, applications


def analyze(evidence, baseline_archive):
    root, nested, metadata, source = verify_wrapper(evidence)
    regression, current, _ = sweep.analyze(nested)
    with tempfile.TemporaryDirectory(prefix="csr-t6-baseline-") as temporary:
        baseline_root = Path(temporary)
        extract_baseline(baseline_archive, baseline_root)
        baseline_report, baseline, _ = sweep.analyze(baseline_root)
        old_metadata = sweep.json_object(baseline_root / "validation_metadata.json")
        old_source = sweep.snapshot(old_metadata["SourceFiles"], "accepted T5 source")
        protected = [name for name in old_source if name.startswith(("+csr/+phy/", "data/", "+csr/+hop/", "+csr/+mac/"))]
        sweep.require(protected and all(source.get(name) == old_source[name] for name in protected),
                      "PHY/ECC, DATA HOP or MAC source changed from the accepted baseline")
        comparisons, applications = compare_cases(nested, baseline_root, current, baseline)
    full_gate = (len(current) == 18 and {r["CaseId"] for r in current} == {r["CaseId"] for r in baseline}
                 and metadata["TestsPassed"] is True)
    report = dict(schema="csr-matlab-tranche-6-comparison-v1", status="review_completed",
        candidate_runtime=metadata["Runtime"], default_regression_gate_completed=full_gate,
        candidate_metadata_sha256=sweep.digest(root / "validation_metadata.json"),
        accepted_tranche5_archive_sha256=BASELINE_SHA256, ns3_source_commit=PIN,
        protected_source_files_unchanged=len(protected), current_source_file_count=len(source),
        tests=regression["tests"], cases=len(comparisons), applications=len(applications),
        baseline_cases=baseline_report["case_count"], comparison_scope="Identical MATLAB configurations and application identities",
        acceptance_established=False, cross_simulator_equivalence_established=False,
        limitations=["Acceptance requires review of structural failures and measured regressions, not delivery alone.",
                     "Latency deltas include only applications delivered in both runs; all other outcomes remain in application_comparison.csv.",
                     "Repeated seeds identify configurations, not identical random draws after event ordering changes.",
                     "Recovery includes explicit rediscovery stimuli and a two-endpoint post-PHY blackout; it does not measure autonomous convergence.",
                     "Compare pinned ns-3 results separately with their documented receive-gate and security-profile differences."])
    return report, comparisons, applications


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True, help="Extracted Tranche 6 run directory")
    parser.add_argument("--baseline-zip", type=Path,
                        default=REPO / "evidence/tranche-5-r2025a-accepted/tranche5_evidence.zip")
    parser.add_argument("--output", type=Path, required=True, help="New directory outside the evidence")
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        sweep.require(not output.is_relative_to(args.evidence.resolve()), "Output must be outside immutable evidence")
        report, comparisons, applications = analyze(args.evidence, args.baseline_zip)
        output.mkdir(parents=True, exist_ok=False)
        (output / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        sweep.write_csv(output / "case_comparison.csv", list(comparisons[0]), comparisons)
        sweep.write_csv(output / "application_comparison.csv", list(applications[0]), applications)
        print(f"Reviewed {len(comparisons)} identical cases and {len(applications)} application identities; acceptance requires review.")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as failure:
        print(f"Tranche 6 review failed: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
