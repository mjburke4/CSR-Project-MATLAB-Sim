#!/usr/bin/env python3
"""Compare returned C/D evidence unconditionally against the native prefix."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "autonomous_fourth/data"
OUT = Path(__file__).resolve().parent
NATIVE = ROOT / "autonomous/native_capture/fixture"
STOP_NS = 12402000000


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def key(row):
    return int(row["node"]), row["purpose"], int(row["ordinal"])


def save_csv(name, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    native_draws = [r for r in csv.DictReader((NATIVE / "random_draws.csv").open())
                    if int(r["time_ns"]) <= STOP_NS]
    native_by_key = {key(r): r for r in native_draws}
    native_txs = {}
    for row in csv.DictReader((NATIVE / "tx_signatures.csv").open()):
        if int(row["time_ns"]) <= STOP_NS:
            native_txs.setdefault(int(row["tx_id"]), row)
    cases = {}
    draw_table = []
    tx_table = []
    controls = {}
    decisions = {}
    all_input_paths = [NATIVE / "random_draws.csv", NATIVE / "tx_signatures.csv"]
    for case in ("C_timing", "D_inline_key"):
        folder = DATA / case
        requests = read_jsonl(folder / "random_requests.jsonl")
        events = read_jsonl(folder / "ordered_events.jsonl")
        txs = [r for r in events if r["kind"] == "physical_tx_context"]
        mismatch = json.loads((folder / "first_divergence.json").read_text())
        all_input_paths += [folder / "random_requests.jsonl", folder / "ordered_events.jsonl", folder / "first_divergence.json"]
        assert all(r["context_matched"] for r in requests)
        assert len(requests) == len(native_draws) == 40
        assert set(map(key, requests)) == set(native_by_key)
        assert len(txs) == len(native_txs) == 7
        timing_deltas = []
        ns_field_deltas = []
        order_mismatches = []
        for index, request in enumerate(requests):
            expected = native_by_key[key(request)]
            assert request["value"] == float(expected["value"])
            # Independently repeat the declared semantic checks. Reported
            # population is diagnostic only for this fixed MAC profile 4.
            for name, actual in request["actual"].items():
                if name.endswith("_ns"):
                    if actual != int(expected[name]):
                        ns_field_deltas.append(dict(key=key(request), field=name,
                                                    delta_ns=actual-int(expected[name])))
                    continue
                if name == "reported_nodes":
                    continue
                wanted = expected[name]
                if isinstance(actual, str):
                    assert actual == wanted, (case, key(request), name)
                elif name == "probability":
                    assert math.isclose(actual, float(wanted), rel_tol=1e-12, abs_tol=0)
                else:
                    assert actual == float(wanted), (case, key(request), name)
            delta = round(request["time_s"] * 1e9) - int(expected["time_ns"])
            if delta:
                timing_deltas.append(dict(key=key(request), delta_ns=delta))
            if key(request) != key(native_draws[index]):
                order_mismatches.append(dict(global_index=index+1, actual=key(request),
                                             native=key(native_draws[index])))
            draw_table.append(dict(case=case, matlab_global_index=index+1,
                                   native_global_index=next(i+1 for i, r in enumerate(native_draws) if key(r)==key(request)),
                                   node=request["node"], purpose=request["purpose"], ordinal=request["ordinal"],
                                   native_time_ns=int(expected["time_ns"]), matlab_time_s=request["time_s"],
                                   rounded_delta_ns=delta, semantic_context_passed=True))
        for index, tx in enumerate(txs):
            tx_id = int(tx["details"]["native_semantic_tx_id"])
            assert tx_id == list(native_txs)[index]
            expected = native_txs[tx_id]
            tx_table.append(dict(case=case, global_tx_index=index+1, tx_id=tx_id,
                                 source=int(expected["source"]), source_tx_ordinal=int(expected["source_tx_ordinal"]),
                                 native_time_ns=int(expected["time_ns"]), matlab_time_s=tx["time_s"],
                                 rounded_delta_ns=round(tx["time_s"]*1e9)-int(expected["time_ns"]),
                                 context_passed=not tx["details"]["mismatches"],
                                 mismatches=";".join(tx["details"]["mismatches"])))
        assert all(not tx["details"]["mismatches"] for tx in txs[:6])
        assert txs[-1]["details"]["mismatches"] == mismatch["fields"]
        previous = next(r for r in requests if key(r) == (4, "phy_binomial", 2))
        assert previous["actual"]["bits"] == 183
        assert previous["actual"]["component"] == "payload"
        assert previous["value"] == 0.45559117029490032
        control_rows = []
        decision_rows = {}
        admission = []
        for row in events:
            detail = row["details"]
            if row["kind"] == "protocol" and detail["event"] == "neighbor_control_send":
                control_rows.append(dict(time_s=row["time_s"], node=row["node"],
                                         kind=detail["details"]["Kind"], peer=detail["frame"]["DestinationId"],
                                         payload=detail["details"]["Payload"]))
            if row["kind"] == "phy" and detail["event"] == "phy_signal_end":
                values = dict(detail["details"])
                values.pop("TimeSeconds", None)
                decision_rows[(row["node"], detail["frame"]["Id"])] = values
            if row["node"] in (3, 5) and 11.5002 < row["time_s"] < 11.506:
                selected = None
                if row["kind"] == "protocol" and detail["event"] in ("mac_enqueue", "hop_control_admit", "neighbor_control_send"):
                    selected = detail["event"]
                elif row["kind"] == "phy_state_transition":
                    selected = "phy_" + detail["Previous"] + "_to_" + detail["Current"]
                elif row["kind"] == "mac_boundary" and detail["Cause"] == "prepare_after":
                    selected = "mac_prepare_counter_" + str(detail["ReservationCounter"])
                if selected:
                    admission.append(dict(order=row["observation_order"], time_s=row["time_s"], node=row["node"], event=selected))
        controls[case] = control_rows
        decisions[case] = decision_rows
        cases[case] = dict(requests=len(requests), requests_by_purpose=dict(Counter(r["purpose"] for r in requests)),
                           global_order_mismatches=order_mismatches, request_timing_differences=timing_deltas,
                           interval_component_ns_differences=ns_field_deltas,
                           missing_or_extra_request_keys=False, matched_tx_contexts=6, attempted_tx_contexts=7,
                           previous_phy_request=previous, control_admission_order=admission,
                           stop=dict(node=mismatch["node"], time_s=mismatch["actual_time_s"], ordinal=mismatch["ordinal"],
                                     fields=mismatch["fields"], actual_children=mismatch["actual"]["child_count"],
                                     native_children=mismatch["expected"][0]["child_count"],
                                     actual_wire_bytes=mismatch["actual"]["total_wire_bytes"],
                                     native_wire_bytes=mismatch["expected"][0]["total_wire_bytes"]))
    semantic = lambda rows: [{k: v for k, v in r.items() if k != "time_s"} for r in rows]
    assert semantic(controls["C_timing"]) == semantic(controls["D_inline_key"])
    assert decisions["C_timing"] == decisions["D_inline_key"]
    control_compare = []
    for index, (c, d) in enumerate(zip(controls["C_timing"], controls["D_inline_key"]), 1):
        control_compare.append(dict(index=index, node=c["node"], kind=c["kind"], peer=c["peer"],
                                    C_time_s=c["time_s"], D_time_s=d["time_s"],
                                    D_minus_C_ns=round(d["time_s"]*1e9)-round(c["time_s"]*1e9),
                                    semantic_payload=json.dumps(c["payload"], sort_keys=True)))
    save_csv("global_random_comparison.csv", draw_table)
    save_csv("global_tx_comparison.csv", tx_table)
    save_csv("control_request_comparison.csv", control_compare)
    report = dict(schema="csr-fourth-owner-cd-independent-audit-v1", stop_ns=STOP_NS,
                  native_requests_through_stop=len(native_draws), native_txs_through_stop=len(native_txs),
                  cases=cases, C_D_control_semantic_sequence_equal=True, control_requests_per_case=len(controls["C_timing"]),
                  C_D_signal_end_decisions_equal_except_time=True, signal_end_decisions_per_case=len(decisions["C_timing"]),
                  local_effect="D admits initial KEY_REQUESTs before Track-to-Search; first node3/5 transmissions move one13ms slot earlier and match native.",
                  scope="Unconditional comparison through actual12.402s stop. No missing/extra sampled requests within this prefix; physical TX7 still differs. No full receiver-history or15percent performance-parity claim.",
                  new_simulations_executed=False, kit_or_model_edited=False,
                  input_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in all_input_paths})
    (OUT / "cd_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: {"requests": item["requests"], "global_order_mismatches": len(item["global_order_mismatches"]),
                             "timing_differences": len(item["request_timing_differences"]), "stop": item["stop"]}
                      for name, item in cases.items()}, indent=2))


if __name__ == "__main__":
    main()
