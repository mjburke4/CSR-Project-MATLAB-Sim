#!/usr/bin/env python3
"""Validate two-case native capture provenance and truthful replay status.

No simulation is run here. A prepared capture is a valid *pending* result;
--require-complete asks for a finished acceptance gate and fails on pending.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys

SCHEMA = "csr-two-case-capture-v1"
CASE = {"discovery131": (131, 25_000_000_000, 85_000_000_000),
        "source5_132": (132, 300_000_000_000, 330_000_000_000)}
TAPE_FIELDS = {
    "inputs": "time_ns event_order node kind peer sequence frame_id value value2 value3 ack_bitmap dack_bitmap".split(),
    "draws": "event_order time_ns node ordinal min max draw".split(),
    "frames": "frame_id node source destination sequence type dscp ackable is_ack is_dack has_ack_window ack_bitmap dack_bitmap rate has_link_control tx_power_dbm rx_power_dbm wirebytes envelope_format compatibility_payload_bytes destination_sequences packet_hex".split(),
    "tx": "time_ns node consumed_slot next_slot wirebytes rate power preamble_bits duration_ns frame_ids".split(),
    "tx_frames": "time_ns node child_index source destination sequence type wirebytes frame_id".split(),
}
REQUIRED_COVERAGE = ("aggregate_children", "receiver_state", "competing_signals",
                     "mac_integer_draws", "phy_random_tape", "nwk_hop_capacity")


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def resolve(base: Path, raw: str) -> Path:
    need(isinstance(raw, str) and bool(raw), "path must be a nonempty string")
    p = Path(raw)
    return p if p.is_absolute() else base / p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def open_csv(path: Path):
    return gzip.open(path, "rt", newline="") if path.suffix == ".gz" else path.open("r", newline="")


def read_tape(path: Path, name: str) -> list[dict]:
    with open_csv(path) as f:
        reader = csv.DictReader(f)
        need(reader.fieldnames == TAPE_FIELDS[name], f"{name} CSV fields/order differ from accepted converter")
        rows = list(reader)
    need(all(None not in r for r in rows), f"{name} has irregular CSV rows")
    return rows


def parse_int(raw: str, label: str) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{label} must be an integer: {raw!r}") from e
    need(str(n) == str(raw), f"{label} not canonical integer: {raw!r}")
    return n


def verify_tapes(base: Path, tape_paths: dict, coverage: dict) -> dict:
    need(set(tape_paths) == set(TAPE_FIELDS), "mac_tape_paths must name all five accepted CSVs")
    rows = {}
    for name in TAPE_FIELDS:
        p = resolve(base, tape_paths[name])
        need(p.is_file(), f"missing {name} tape: {p}")
        rows[name] = read_tape(p, name)
    input_order = [parse_int(x["event_order"], "input event_order") for x in rows["inputs"]]
    draw_order = [parse_int(x["event_order"], "draw event_order") for x in rows["draws"]]
    need(len(input_order) == len(set(input_order)), "duplicate MAC input event_order")
    need(len(draw_order) == len(set(draw_order)), "duplicate MAC draw event_order")
    need(len(set(input_order + draw_order)) == len(input_order + draw_order),
         "MAC input and draw event orders overlap")
    ids = [parse_int(x["frame_id"], "frame_id") for x in rows["frames"]]
    need(len(ids) == len(set(ids)), "duplicate frame_id")
    for r in rows["inputs"]:
        need(parse_int(r["time_ns"], "input time_ns") >= 0, "negative input time")
        if r["kind"] == "enqueue":
            need(parse_int(r["frame_id"], "enqueue frame_id") in ids, "unbound enqueued frame_id")
    seen_draw = {}
    for r in rows["draws"]:
        node = parse_int(r["node"], "draw node")
        ordinal = parse_int(r["ordinal"], "draw ordinal")
        need(ordinal == seen_draw.get(node, 0) + 1, f"noncontiguous MAC draw ordinal node {node}")
        seen_draw[node] = ordinal
        lo, hi, v = (parse_int(r[c], "draw " + c) for c in ("min", "max", "draw"))
        need(lo <= v <= hi, "draw outside support")
    tx_keys = {(r["time_ns"], r["node"]) for r in rows["tx"]}
    need(len(tx_keys) == len(rows["tx"]), "duplicate same-time/node physical TX")
    tx_child_keys = set()
    for r in rows["tx_frames"]:
        key = (r["time_ns"], r["node"])
        need(key in tx_keys, "TX child without physical TX")
        ck = (*key, r["child_index"])
        need(ck not in tx_child_keys, "duplicate TX child index")
        tx_child_keys.add(ck)
    for name, count in (("mac_inputs", len(rows["inputs"])),
                        ("mac_draws", len(rows["draws"])),
                        ("tx", len(rows["tx"])),
                        ("tx_children", len(rows["tx_frames"]))):
        if name in coverage.get("counts", {}):
            need(coverage["counts"][name] == count, f"{name} count does not match captured tape")
    return {name: len(rows[name]) for name in TAPE_FIELDS}


def exact_prefix(reference: Path, captured: Path, stop_ns: int) -> int:
    """Compare every canonical differential trace row in half-open prefix."""
    limit = stop_ns / 1e9
    with open_csv(reference) as a, open_csv(captured) as b:
        ra, rb = csv.DictReader(a), csv.DictReader(b)
        need(ra.fieldnames == rb.fieldnames and ra.fieldnames is not None,
             "native canonical trace CSV columns differ")
        def prefix(reader):
            for row in reader:
                if float(row["time_s"]) >= limit:
                    return
                yield row
        count = 0
        for x, y in itertools.zip_longest(prefix(ra), prefix(rb)):
            need(x == y, f"native canonical prefix differs at row {count}")
            count += 1
    need(count > 0, "empty native trace prefix")
    return count


def reference_rows(path: Path, stop_ns: int) -> int:
    limit = stop_ns / 1e9
    with open_csv(path) as f:
        reader = csv.DictReader(f)
        need(reader.fieldnames is not None and "time_s" in reader.fieldnames,
             "native reference does not contain canonical time_s")
        n = 0
        for row in reader:
            need(float(row["time_s"]) < limit, "reference contains event outside declared prefix")
            n += 1
    need(n > 0, "native reference prefix is empty")
    return n


def verify_observations(path: Path, case_id: str, stop_ns: int) -> tuple[int, dict[str, int]]:
    need(path.is_file(), f"missing native observations: {path}")
    if path.suffix == ".jsonl":
        with path.open() as f:
            records = (json.loads(line) for line in f if line.strip())
            rows = list(records)
    else:
        with path.open(newline="") as f:
            sample = f.readline()
            f.seek(0)
            rows = list(csv.DictReader(f, delimiter="\t" if "\t" in sample else ","))
    keys = {"time_ns", "event_order", "case_id", "node", "layer", "event",
            "peer", "frame_id", "tx_id", "reason", "state_before", "state_after"}
    need(bool(rows) and all(keys <= set(r) for r in rows),
         "native observation stream missing required event/identity fields")
    counts: dict[str, int] = {}
    orders = []
    for r in rows:
        need(r["case_id"] == case_id, "mixed case IDs in observer events")
        t = parse_int(r["time_ns"], "observer time_ns")
        need(0 <= t < stop_ns, "observer event outside captured prefix")
        orders.append(parse_int(r["event_order"], "observer event_order"))
        need(r["layer"] in {"PHY", "MAC", "NWK", "HOP", "APP"}, "unknown observer layer")
        event = r["event"]
        need(isinstance(event, str) and bool(event), "empty observer event name")
        counts[event] = counts.get(event, 0) + 1
    need(orders == sorted(set(orders)), "observer event_order not unique and increasing")
    return len(rows), counts


def validate(path: Path, require_complete: bool = False) -> dict:
    m = json.loads(path.read_text())
    base = path.parent
    need(m.get("schema") == SCHEMA, "unknown manifest schema")
    case = m.get("case_id")
    need(case in CASE, "unknown case_id")
    seed, lo, hi = CASE[case]
    need(m.get("seed") == seed, "case/seed mismatch")
    need(m.get("window_ns") == [lo, hi], "case/window mismatch")
    sources = m.get("source_files")
    need(isinstance(sources, list), "source_files must list bound sources")
    roles = {}
    for s in sources:
        role, digest = s.get("role"), s.get("sha256")
        need(isinstance(role, str) and role not in roles, "duplicate/missing source role")
        need(isinstance(digest, str) and len(digest) == 64 and
             all(c in "0123456789abcdef" for c in digest), "invalid source SHA-256")
        p = resolve(base, s.get("path"))
        need(p.is_file() and sha256(p) == digest, f"source hash mismatch or missing: {p}")
        roles[role] = p
    need({"scenario", "native_reference", "instrumentation_generator"} <= set(roles),
         "required source roles: scenario, native_reference, instrumentation_generator")
    lineage = m.get("reference_lineage", {})
    need(lineage.get("strict_stop_ns") == hi, "reference cutoff is not target window end")
    parent_digest = lineage.get("original_full_trace_sha256")
    need(isinstance(parent_digest, str) and len(parent_digest) == 64 and
         all(c in "0123456789abcdef" for c in parent_digest),
         "invalid parent full-trace SHA-256 lineage")
    known_rows = reference_rows(roles["native_reference"], hi)
    need(lineage.get("rows") == known_rows, "reference prefix row count mismatches lineage")
    if lineage.get("original_full_trace_path"):
        parent = resolve(base, lineage["original_full_trace_path"])
        need(parent.is_file() and sha256(parent) == parent_digest,
             "original full native trace hash mismatch")
        need(exact_prefix(parent, roles["native_reference"], hi) == known_rows,
             "reference prefix was not derived from declared original")
    capture = m.get("capture", {})
    cs = capture.get("status")
    need(cs in {"capture_pending", "captured", "verified"}, "unknown capture status")
    obs = m.get("coverage", {}).get("observability", {})
    need(set(REQUIRED_COVERAGE) <= set(obs), "coverage lacks required observability fields")
    need(all(obs[v] in {"observed", "unavailable"} for v in REQUIRED_COVERAGE),
         "observability must be observed/unavailable")
    result = {"case_id": case, "capture_status": cs, "source_hashes_verified": len(roles),
              "exact_prefix_rows": None, "tape_counts": None}
    if cs == "capture_pending":
        need(capture.get("prefix_fidelity") == "pending", "uncaptured prefix cannot pass fidelity")
        need(not capture.get("trace_path") and not capture.get("mac_tape_paths"),
             "pending capture must not point to purported completed traces")
    else:
        need(capture.get("prefix_end_ns") >= hi,
             "native capture must include zero-to-end history and target window")
        actual = resolve(base, capture.get("trace_path"))
        need(actual.is_file(), "captured canonical trace missing")
        if cs == "verified":
            need({"native_capture_source", "native_overlay"} <= set(roles),
                 "verified capture must hash-bind actual generated overlay and runner source")
            need(capture.get("prefix_fidelity") == "passed", "verified capture needs passed fidelity")
            result["exact_prefix_rows"] = exact_prefix(
                roles["native_reference"], actual, capture["prefix_end_ns"])
            if "prefix_rows" in capture:
                need(capture["prefix_rows"] == result["exact_prefix_rows"], "prefix row-count mismatch")
            result["tape_counts"] = verify_tapes(
                base, capture.get("mac_tape_paths", {}), m["coverage"])
            observed_count, event_counts = verify_observations(
                resolve(base, capture.get("observations_path")), case, capture["prefix_end_ns"])
            result["observation_rows"] = observed_count
            if "observer_events" in m["coverage"].get("counts", {}):
                need(m["coverage"]["counts"]["observer_events"] == observed_count,
                     "observer event count differs from declaration")
            for event, declared in m["coverage"].get("event_counts", {}).items():
                need(declared == event_counts.get(event, 0),
                     f"observer {event} event count differs from declaration")
        else:
            need(capture.get("prefix_fidelity") in {"pending", "failed"},
                 "captured-but-unverified prefix cannot pass fidelity")
    replay = m.get("replay", {})
    rs = replay.get("status")
    need(rs in {"replay_pending", "conditional", "verified"}, "unknown replay status")
    if rs != "replay_pending":
        need(cs == "verified", "replay result needs a verified native source capture")
        usage_path = resolve(base, replay.get("draw_usage_path"))
        need(usage_path.is_file(), "replay missing draw usage evidence")
        with usage_path.open(newline="") as f:
            usage = list(csv.DictReader(f))
        need(bool(usage) and {"node", "supplied", "consumed", "unused"} <= set(usage[0]),
             "invalid draw usage table")
        supplied = sum(parse_int(u["supplied"], "supplied") for u in usage)
        consumed = sum(parse_int(u["consumed"], "consumed") for u in usage)
        unused = sum(parse_int(u["unused"], "unused") for u in usage)
        need(supplied == result["tape_counts"]["draws"] and supplied == consumed + unused,
             "replay draw usage does not account for captured draws")
        need(replay.get("draws_supplied") == supplied and replay.get("draws_consumed") == consumed,
             "replay draw summary differs from usage rows")
        if rs == "verified":
            need(unused == 0, "verified replay has unused random draws")
            need(all(obs[k] == "observed" for k in REQUIRED_COVERAGE),
                 "verified full decision replay needs observed complete receiver/capacity inputs")
    need(m.get("claims", {}).get("full_network_parity") is False,
         "short replay cannot establish 6000-second network parity")
    need(not (rs == "verified" and cs != "verified"), "verified replay needs verified capture")
    if require_complete:
        need(cs == "verified" and rs in {"conditional", "verified"},
             "two-case acceptance is still pending")
    result.update(replay_status=rs, accepted_manifest=True,
                  behavioral_verdict="pending" if cs != "verified" or rs == "replay_pending"
                  else ("conditional" if rs == "conditional" else "bounded_verified"),
                  full_network_parity_claim=False)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", type=Path)
    p.add_argument("--require-complete", action="store_true")
    args = p.parse_args()
    try:
        result = validate(args.manifest, args.require_complete)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"accepted_manifest": False, "error": str(error)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
