#!/usr/bin/env python3
"""Fail on malformed, incomplete, or internally inconsistent replay inputs."""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def validate(folder):
    profile = json.loads((folder / "profile.json").read_text())
    inputs = read(folder / "inputs.csv")
    children = read(folder / "children.csv")
    draws = read(folder / "draws.csv")
    controls = read(folder / "controls.csv")
    assert inputs, "No physical inputs"
    by_id = {}
    last_time, last_order = -1, -1
    for row in inputs:
        sid = int(row["signal_id"])
        assert sid not in by_id, ("Duplicate signal identity", sid)
        by_id[sid] = row
        now, order = int(row["time_ns"]), int(row["event_order"])
        assert now >= last_time and order > last_order, ("Input order", row)
        last_time, last_order = now, order
        assert row["kind"] in ("signal", "own_tx"), row
        assert int(row["end_ns"]) > now, ("Nonpositive duration", row)
        assert now < int(row["preamble_end_ns"]) < int(row["end_ns"]), row
        assert float(row["start_s"]) < float(row["preamble_end_s"]) < float(row["end_s"]), row
        assert int(row["preamblebits"]) in (104, 7888), row
        assert int(row["packetbits"]) == int(row["preamblebits"]) + 48 + 8*int(row["wirebytes"]) + 32, row
        for field in ("start_s", "end_s", "preamble_end_s", "tx_dbm"):
            assert math.isfinite(float(row[field])), (field, row)
        if row["kind"] == "signal":
            for field in ("rx_dbm", "noise_watts", "sync_threshold_db"):
                assert math.isfinite(float(row[field])), (field, row)
            assert float(row["noise_watts"]) > 0, row
            if "channel_matched" in row:
                assert int(row["channel_matched"]) == 1, ("Fixture assumes matched channels", row)
        else:
            assert int(row["source"]) == int(profile["receiver_id"]), row
            if "queues_empty_at_end" in row:
                assert int(row["queues_empty_at_end"]) in (0, 1), row
    global_orders = [int(r["event_order"]) for r in inputs]
    for control in controls:
        assert control["kind"] in ("prep_tx", "cancel_post_tx_wait"), control
        assert int(control["value"]) in (0, 1), control
        assert int(control["time_ns"]) >= int(profile["warmup_start_ns"]), control
        global_orders.append(int(control["event_order"]))
    assert len(set(global_orders)) == len(global_orders), "RF/control event order is not globally unique"
    grouped = defaultdict(list)
    for child in children:
        sid = int(child["signal_id"])
        assert sid in by_id, ("Unbound child", child)
        grouped[sid].append(child)
        assert bytes.fromhex(child["packet_hex"]), ("Empty packet", child)
    for sid, row in by_id.items():
        group = grouped[sid]
        assert group, ("Missing aggregate children", sid)
        assert [int(c["child_index"]) for c in group] == list(range(len(group))), sid
        assert sum(int(c["wirebytes"]) for c in group) == int(row["wirebytes"]), ("Incomplete aggregate wire size", sid)
    keys = set()
    for draw in draws:
        sid = int(draw["signal_id"])
        assert sid in by_id and by_id[sid]["kind"] == "signal", ("Unbound draw", draw)
        key = (sid, int(draw["interval_start_ns"]), int(draw["interval_end_ns"]), draw["phase"])
        assert key not in keys, ("Duplicate semantic draw", key)
        keys.add(key)
        assert key[1] <= key[2] and draw["phase"] in ("header", "payload"), draw
        assert 0 <= float(draw["uniform"]) < 1, draw
        assert int(draw["bits"]) > 0 and 0 < float(draw["probability"]) < 1, draw
    start, stop = int(profile["comparison_start_ns"]), int(profile["comparison_stop_ns"])
    targets = [r for r in inputs if r["kind"] == "signal" and int(r["source"]) == 8
               and int(r["sequence"]) == 174 and start <= int(r["time_ns"]) < stop]
    assert len(targets) == 3, ("Expected three target physical attempts", len(targets))
    return {"schema": "csr.receiver-input-validation.v1", "passed": True,
            "counts": {"physical_inputs": len(inputs), "children": len(children),
                       "semantic_draws": len(draws), "receiver_controls": len(controls),
                       "kinds": dict(Counter(r["kind"] for r in inputs))},
            "target_signal_ids": [r["signal_id"] for r in targets],
            "coverage_note": "Structural checks; original-capture and native-replay fidelity are separate gates."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.inputs)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
