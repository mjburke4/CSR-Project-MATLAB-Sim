#!/usr/bin/env python3
"""Compare ordered receiver decisions. This never implies network parity."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

FIELDS = ("time_ns", "signal_id", "stage", "source", "hop_sequence",
          "result", "reason", "state_before", "state_after")
IDENTITY = ("signal_id", "stage", "source", "hop_sequence")


def read_events(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS + ("event_index",)) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = list(reader)
    last_time, last_index = -1, -1
    for row in rows:
        now, index = int(row["time_ns"]), int(row["event_index"])
        if now < last_time or index <= last_index:
            raise ValueError(f"{path}: event time/order decreases at {row}")
        if not row["stage"]:
            raise ValueError(f"{path}: empty stage")
        last_time, last_index = now, index
    return rows


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(reference, candidate, start_ns, end_ns, tolerance_ns=0):
    if start_ns >= end_ns or tolerance_ns < 0:
        raise ValueError("Require start < end and nonnegative time tolerance")
    ref = [r for r in reference if start_ns <= int(r["time_ns"]) < end_ns]
    got = [r for r in candidate if start_ns <= int(r["time_ns"]) < end_ns]
    if not ref:
        raise ValueError("Reference has no events in assessed window")
    first = None
    matched = 0
    for index in range(max(len(ref), len(got))):
        a = ref[index] if index < len(ref) else None
        b = got[index] if index < len(got) else None
        differences = {}
        if a is None or b is None:
            category = "missing_or_extra_event"
            differences["event"] = {"reference": a, "candidate": b}
        else:
            for name in FIELDS:
                equal = (abs(int(a[name]) - int(b[name])) <= tolerance_ns
                         if name == "time_ns" else a[name] == b[name])
                if not equal:
                    differences[name] = {"reference": a[name], "candidate": b[name]}
            if any(name in differences for name in IDENTITY):
                category = "event_identity_or_order"
            elif "result" in differences or "reason" in differences:
                category = "receiver_decision"
            elif "state_before" in differences or "state_after" in differences:
                category = "receiver_state"
            else:
                category = "event_time"
        if differences:
            first = {"assessed_index": index, "category": category,
                     "differences": differences, "reference": a, "candidate": b,
                     "reference_context": ref[max(0, index-3):index+4],
                     "candidate_context": got[max(0, index-3):index+4]}
            break
        matched += 1
    return {"schema": "csr.receiver-comparison.v1", "passed": first is None,
            "scope": "ordered common-input receiver events; not network parity",
            "window_start_ns_inclusive": start_ns,
            "window_end_ns_exclusive": end_ns, "time_tolerance_ns": tolerance_ns,
            "compared_columns": list(FIELDS),
            "ignored_diagnostics": "event_index numbering, raw_reason and additional columns",
            "reference_event_count": len(ref), "candidate_event_count": len(got),
            "matching_prefix_events": matched,
            "reference_stage_counts": dict(Counter(r["stage"] for r in ref)),
            "candidate_stage_counts": dict(Counter(r["stage"] for r in got)),
            "first_difference": first}


def markdown(report):
    result = "MATCH" if report["passed"] else "DIFFERENCE"
    text = [f"# Receiver replay: {result}", "",
            "This comparison covers a fixed physical input schedule; it is not a network-parity result.", "",
            f"Reference events: {report['reference_event_count']}; candidate events: {report['candidate_event_count']}; matching prefix: {report['matching_prefix_events']}.",
            f"Timestamp tolerance: {report['time_tolerance_ns']} ns.", ""]
    difference = report["first_difference"]
    if difference:
        text += [f"First difference: **{difference['category']}**, assessed row {difference['assessed_index']} (zero based).", "",
                 "```json", json.dumps(difference, indent=2), "```", ""]
    else:
        text += ["All assessed events agree in order and in the declared comparison fields.", ""]
    return "\n".join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--start-ns", type=int, default=657_000_000_000)
    parser.add_argument("--end-ns", type=int, default=669_000_000_000)
    parser.add_argument("--time-tolerance-ns", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("receiver_comparison.json"))
    args = parser.parse_args()
    report = compare(read_events(args.reference), read_events(args.candidate),
                     args.start_ns, args.end_ns, args.time_tolerance_ns)
    report["files"] = {name: {"path": str(path), "sha256": digest(path)}
                       for name, path in (("reference", args.reference), ("candidate", args.candidate))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(markdown(report))
    print(json.dumps({k: report[k] for k in ("passed", "reference_event_count", "candidate_event_count", "matching_prefix_events")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
