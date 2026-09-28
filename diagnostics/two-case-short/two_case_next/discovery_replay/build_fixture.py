#!/usr/bin/env python3
"""Extract a bounded observational replay tape from immutable native traces.

The tape preserves all native TXs and MAC states, including competing nodes.
It does not invent aggregate children, receiver draws, or native PHY states.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "fixture"
INPUTS = {
    131: ROOT / "routing_work/grfix/native/s131/window-0-200.csv.gz",
    132: ROOT / "routing_recovery/t25/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz",
}
SCENARIOS = {
    131: ROOT / "routing_work/grfix/native/s131/scenario.csv",
    132: ROOT / "routing_work/grfix/native/s132/scenario.csv",
}
START_NS = 25_000_000_000
END_NS = 85_000_000_000


def tick(value: str) -> int:
    return round(float(value) * 1e9)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fields: list[str], entries: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(entries)


def extract(seed: int) -> dict:
    source = INPUTS[seed]
    active: list[dict] = []
    with gzip.open(source, "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            if tick(row["time_s"]) >= END_NS:
                break
            if row["event"] in ("tx_start", "mac_state", "rx_drop", "rx_accept"):
                active.append(row)
    # A 25-second reset is safe only for a PHY history replay when no earlier
    # native on-air packet remains active at the boundary. Higher MAC/NWK
    # queues and timers are supplied as external history, not reconstructed.
    for prior in (r for r in active if r["event"] == "tx_start" and
                  tick(r["time_s"]) < START_NS):
        assert int(prior["rate_kbps"]) == 8
        bits = 7888 if prior["detail"] == "long" else 104
        duration_ns = round((bits + 48 + 8 * int(prior["size_bytes"]) + 32) *
                            .000510 / 4 * 1e9)
        assert tick(prior["time_s"]) + duration_ns + 100_000 < START_NS, (
            seed, prior["event_index"], "signal overlaps 25-s boundary")
    tx = [r for r in active if r["event"] == "tx_start" and
          tick(r["time_s"]) >= START_NS]
    all_states = [r for r in active if r["event"] == "mac_state"]
    latest: dict[int, dict] = {}
    for row in all_states:
        if tick(row["time_s"]) <= START_NS:
            latest[int(row["node"])] = row
    states = [r for r in all_states if tick(r["time_s"]) >= START_NS]
    receptions = [r for r in active if r["event"] in ("rx_accept", "rx_drop")]
    assert tx and states

    case = OUT / f"s{seed}"
    case.mkdir(parents=True, exist_ok=True)
    with SCENARIOS[seed].open(newline="") as stream:
        points = {int(r["node_id"]): (float(r["x_m"]), float(r["y_m"]),
                                       float(r["height_m"]))
                  for r in csv.DictReader(stream) if r["record"] == "node"}

    def duration_ns(sent):
        assert int(sent["rate_kbps"]) == 8
        bits = 7888 if sent["detail"] == "long" else 104
        return round((bits + 48 + 8 * int(sent["size_bytes"]) + 32) *
                     .000510 / 4 * 1e9)

    def matching_receptions(sent):
        sent_ns=tick(sent["time_s"])
        return [r for r in receptions if r["pathloss_db"] and r["rx_power_dbm"]
                and r["peer"] == sent["node"] and
                r["packet_type"] == sent["packet_type"] and
                r["sequence"] == sent["sequence"] and
                r["size_bytes"] == sent["size_bytes"] and
                abs(tick(r["time_s"]) - (sent_ns + duration_ns(sent) +
                    round(math.dist(points[int(sent["node"])],
                                        points[int(r["node"])]) / 3e8 * 1e9))) <= 2]

    rows_tx=[]
    power_observations=0
    for sent in tx:
        matches=matching_receptions(sent)
        assert matches, (seed,sent["event_index"],"TX has no measured receive power")
        powers=[float(r["rx_power_dbm"])+float(r["pathloss_db"]) for r in matches]
        assert max(powers)-min(powers)<1e-8, (seed,sent["event_index"],"inconsistent TX power")
        power=round(powers[0],9)
        assert -36 <= power <= 33
        power_observations+=len(matches)
        rows_tx.append({"time_ns":tick(sent["time_s"]),
                        "event_order":int(sent["event_index"]),
                        "tx_id":int(sent["event_index"]),"node":int(sent["node"]),
                        "peer":int(sent["peer"]),"packet_type":sent["packet_type"],
                        "sequence":int(sent["sequence"]),
                        "wire_bytes":int(sent["size_bytes"]),
                        "rate_kbps":int(sent["rate_kbps"]),
                        "preamble":sent["detail"],"tx_power_dbm":power})
    rows_states = [{"time_ns": tick(r["time_s"]),
                    "event_order": int(r["event_index"]),
                    "node": int(r["node"]), "state": r["detail"]} for r in states]
    initial_states = [{"time_ns": START_NS, "node": node,
                       "state": latest[node]["detail"],
                       "source_event_order": int(latest[node]["event_index"])}
                      for node in sorted(latest)]
    assert len(initial_states) == 7
    assert all(r["state"] in ("idle", "search") for r in initial_states)

    # Only the identified decisions are a control. Full-window receiver
    # outcomes remain available in the immutable source but are not asserted.
    targets = [(r, 5) for r in tx if seed == 131 and
               r["node"] == "4" and r["packet_type"] == "key_request"]
    targets += [(r, 2) for r in tx if seed == 131 and r["node"] == "4"]
    targets += [(r, 2) for r in tx if seed == 132 and
                r["node"] == "4" and r["detail"] == "long"]
    expected: list[dict] = []
    for sent, receiver in targets:
        sent_ns = tick(sent["time_s"])
        preamble_bits = 7888 if sent["detail"] == "long" else 104
        assert int(sent["rate_kbps"]) == 8
        duration_ns = round(1e9 * ((preamble_bits + 48) / 4 * .000510 +
                              (int(sent["size_bytes"]) * 8 + 32) * .000510 / 4))
        distance = math.dist(points[int(sent["node"])], points[receiver])
        predicted = sent_ns + duration_ns + round(distance / 3e8 * 1e9)
        # Propagation and source airtime use the full wire payload. Restrict
        # candidates to the exact tuple and first physical completion.
        candidates = [r for r in receptions if int(r["node"]) == receiver
                      and int(r["peer"] or -1) == int(sent["node"])
                      and r["packet_type"] == sent["packet_type"]
                      and r["sequence"] == sent["sequence"]
                      and r["size_bytes"] == sent["size_bytes"]
                      and sent_ns < tick(r["time_s"]) < sent_ns + 1_300_000_000]
        # Verify the reported physical size against exact source modulation
        # time at a measured receiving node; unlike the aggregate's child
        # list, its total on-air byte count is present in this trace.
        ordered = sorted(candidates, key=lambda r: abs(tick(r["time_s"]) - predicted))
        assert ordered and abs(tick(ordered[0]["time_s"]) - predicted) <= 2, (
            seed, sent["event_index"], receiver, len(ordered))
        received = ordered[0]
        expected.append({"tx_id": int(sent["event_index"]),
                         "receiver": receiver, "source": int(sent["node"]),
                         "packet_type": sent["packet_type"],
                         "preamble": sent["detail"],
                         "tx_time_ns": sent_ns,
                         "receive_time_ns": tick(received["time_s"]),
                         "receive_event_order": int(received["event_index"]),
                         "success": int(received["event"] == "rx_accept"),
                         "reason": received["reason"],
                         "collision_count": int(received["detail"].removeprefix("collisions=")
                                                or -1),
                         "total_errors": int(received["total_errors"] or -1)})
    expected.sort(key=lambda r: (r["tx_time_ns"], r["receiver"]))
    assert len(expected) == (22 if seed == 131 else 3)
    if seed == 131:
        assert sum(r["receiver"] == 5 and r["success"] for r in expected) == 1
        assert all(r["success"] == 0 for r in expected if r["receiver"] == 2)
    else:
        assert all(r["success"] == 1 for r in expected)

    write_csv(case / "tx.csv", list(rows_tx[0]), rows_tx)
    write_csv(case / "states.csv", list(rows_states[0]), rows_states)
    write_csv(case / "initial_states.csv", list(initial_states[0]), initial_states)
    write_csv(case / "expected.csv", list(expected[0]), expected)
    (case / "scenario.csv").write_bytes(SCENARIOS[seed].read_bytes())
    return {"seed": seed, "source_path": str(source.relative_to(ROOT)),
            "source_sha256": digest(source), "scenario_sha256": digest(SCENARIOS[seed]),
            "tx_count": len(rows_tx), "state_count": len(rows_states),
            "power_source":"measured_rx_power_plus_pathloss_for_every_tx",
            "power_observation_count":power_observations,
            "initial_states": {str(r["node"]): r["state"] for r in initial_states},
            "target_count": len(expected),
            "target_successes": sum(r["success"] for r in expected),
            "fixture_sha256": {name.replace(".", "_"): digest(case / name) for name in
                               ("tx.csv", "states.csv", "initial_states.csv",
                                "expected.csv", "scenario.csv")}}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = [extract(seed) for seed in INPUTS]
    manifest = {"schema": "csr-discovery-observed-history-v1", "window_ns": [START_NS, END_NS],
                "scope": "recorded native TX and MAC state input; independent MATLAB PHY draws; no aggregate children", 
                "cases": cases, "complete_common_input": False}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": [{k: c[k] for k in
                                 ("seed", "tx_count", "state_count", "target_count",
                                  "target_successes")} for c in cases]}))


if __name__ == "__main__":
    main()
