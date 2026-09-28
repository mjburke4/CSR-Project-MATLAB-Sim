#!/usr/bin/env python3
"""Read-only unconditional E/F prefix audit, including the stopping request."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "autonomous_fifth/data"
NATIVE = ROOT / "autonomous/native_capture/fixture"
OUT = Path(__file__).resolve().parent


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def key(row):
    return int(row["node"]), row["purpose"], int(row["ordinal"])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_out(name, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    stop = json.loads((DATA / "E_check_gate/first_divergence.json").read_text())
    cutoff_order = int(stop["expected"]["event_order"])
    cutoff_ns = int(stop["expected"]["time_ns"])
    all_draws = list(csv.DictReader((NATIVE / "random_draws.csv").open()))
    native_draws = [r for r in all_draws if int(r["event_order"]) <= cutoff_order]
    all_txs = {}
    for row in csv.DictReader((NATIVE / "tx_signatures.csv").open()):
        all_txs.setdefault(int(row["tx_id"]), row)
    native_txs = {uid: row for uid, row in all_txs.items() if int(row["event_order"]) <= cutoff_order}
    same_time_after_stop = [row for row in all_txs.values() if int(row["event_order"]) > cutoff_order
                            and int(row["time_ns"]) == cutoff_ns]
    assert len(native_draws) == 97 and len(native_txs) == 16
    assert len(same_time_after_stop) == 1
    summaries = {}
    request_table = []
    tx_table = []
    previous_fixed = {}
    event_records = {}
    inputs = [NATIVE / "random_draws.csv", NATIVE / "tx_signatures.csv"]
    for case in ("E_check_gate", "F_message_flag"):
        folder = DATA / case
        requests = records(folder / "random_requests.jsonl")
        events = records(folder / "ordered_events.jsonl")
        event_records[case] = events
        inputs += [folder / "random_requests.jsonl", folder / "ordered_events.jsonl", folder / "first_divergence.json"]
        assert len(requests) == len(native_draws)
        assert list(map(key, requests)) == list(map(key, native_draws))
        assert [r["context_matched"] for r in requests] == [True] * 96 + [False]
        differences = []
        for index, (actual, native) in enumerate(zip(requests, native_draws), 1):
            assert round(actual["time_s"] * 1e9) == int(native["time_ns"])
            found = []
            for field, value in actual["actual"].items():
                if field == "reported_nodes":
                    continue  # Fixed profile4 does not consume this diagnostic field.
                expected = native[field]
                if isinstance(value, str):
                    equal = value == expected
                elif field == "probability":
                    equal = math.isclose(value, float(expected), rel_tol=1e-12, abs_tol=0)
                else:
                    equal = value == float(expected)
                if not equal:
                    found.append(field)
            if index < 97:
                assert not found and actual["value"] == float(native["value"])
            else:
                assert found == ["active_nodes"] and actual["value"] is None
                differences = found
            request_table.append(dict(case=case, global_request_index=index, node=actual["node"],
                                       purpose=actual["purpose"], ordinal=actual["ordinal"],
                                       native_event_order=int(native["event_order"]), native_time_ns=int(native["time_ns"]),
                                       matlab_time_s=actual["time_s"], global_order_equal=True,
                                       rounded_time_equal=True, consumed=actual["context_matched"],
                                       independent_context_differences=";".join(found)))
        txs = [r for r in events if r["kind"] == "physical_tx_context"]
        assert len(txs) == 16
        for index, (actual, (tx_id, expected)) in enumerate(zip(txs, native_txs.items()), 1):
            detail = actual["details"]
            assert int(detail["native_semantic_tx_id"]) == tx_id
            assert not detail["mismatches"]
            assert round(actual["time_s"] * 1e9) == int(expected["time_ns"])
            tx_table.append(dict(case=case, global_tx_index=index, source=int(expected["source"]),
                                 source_tx_ordinal=int(expected["source_tx_ordinal"]), tx_id=tx_id,
                                 native_event_order=int(expected["event_order"]), native_time_ns=int(expected["time_ns"]),
                                 matlab_time_s=actual["time_s"], child_count=detail["actual"]["child_count"],
                                 total_wire_bytes=detail["actual"]["total_wire_bytes"], semantic_context_passed=True))
            if tx_id == 21474836483:
                previous_fixed[case] = detail["actual"]
                assert detail["actual"]["child_count"] == 4 and detail["actual"]["total_wire_bytes"] == 82
                assert [r.get("check_subtype", "ack") for r in detail["actual"]["children"]] == [
                    "ack", "ack", "discovery", "overheard"]
        purposes = Counter(r["purpose"] for r in requests)
        consumed = Counter(r["purpose"] for r in requests if r["context_matched"])
        summaries[case] = dict(requests=len(requests), consumed=sum(consumed.values()),
                               requested_by_purpose=dict(purposes), consumed_by_purpose=dict(consumed),
                               global_order_and_rounded_times_equal=True, recorded_interval_component_ns_equal=True,
                               transmitted_contexts_verified=len(txs), rejected_fields=differences,
                               last_request_value_consumed=False)

    files = ["random_requests.jsonl", "ordered_events.jsonl", "protocol_trace.csv", "phy_trace.csv",
             "transport_timing.csv", "actual_feedback.csv", "link_decisions.csv", "service_trace.csv",
             "application_admission_trace.csv", "observer_status.json", "random_summary.json"]
    equality = {}
    for filename in files:
        first, second = DATA / "E_check_gate" / filename, DATA / "F_message_flag" / filename
        equality[filename] = first.read_bytes() == second.read_bytes()
    assert all(equality.values())
    active = set()
    discovery_outstanding = set()
    received_overheard = []
    controls = []
    for row in event_records["E_check_gate"]:
        if row["kind"] != "protocol":
            continue
        detail = row["details"]
        event = detail["event"]
        frame = detail.get("frame", {})
        control = frame.get("Control", {})
        if event == "neighbor_control_send":
            sent = detail["details"]
            subtype = sent["Payload"].get("Subtype", "")
            controls.append(dict(time_s=row["time_s"], node=row["node"], kind=sent["Kind"], subtype=subtype))
            if sent["Kind"] == "NEIGHBOR_CHECK" and subtype == "discovery":
                discovery_outstanding.add((row["node"], frame["DestinationId"]))
        if event == "neighbor_active":
            active.add((row["node"], frame["DestinationId"]))
        if event == "hop_control_ack" and control.get("Type") == "NEIGHBOR_CHECK" and control["Payload"]["Subtype"] == "discovery":
            discovery_outstanding.discard((row["node"], frame["DestinationId"]))
        if event == "hop_control_receive" and control.get("Type") == "NEIGHBOR_CHECK" and control["Payload"]["Subtype"] == "overheard":
            pair = row["node"], frame["SourceId"]
            if pair in active:
                blocker = "peer already active"
            elif pair in discovery_outstanding:
                blocker = "Discovery proof still outstanding"
            else:
                blocker = "Message-only flag might distinguish variants"
            received_overheard.append(dict(time_s=row["time_s"], node=row["node"], peer=frame["SourceId"],
                                           observation_order=row["observation_order"], sufficient_existing_blocker=blocker))
    assert len(received_overheard) == 3
    assert all(r["sufficient_existing_blocker"] != "Message-only flag might distinguish variants" for r in received_overheard)
    assert not any(r["kind"] == "NEIGHBOR_CHECK" and r["subtype"] == "message" for r in controls)
    csv_out("global_random_comparison.csv", request_table)
    csv_out("global_tx_comparison.csv", tx_table)
    csv_out("received_overheard_gate_history.csv", received_overheard)
    report = dict(schema="csr-fifth-owner-ef-independent-audit-v1", cutoff_native_event_order=cutoff_order,
                  cutoff_time_ns=cutoff_ns, cases=summaries, traces_byte_identical=equality,
                  observed_events_per_case=len(event_records["E_check_gate"]), neighbor_control_requests_per_case=len(controls),
                  previous_82byte_tx_resolved=previous_fixed,
                  native_same_timestamp_after_failed_request=same_time_after_stop,
                  F_role=dict(network_outputs_distinguished=False, message_requests=0,
                              received_overheard_contexts=received_overheard,
                              inference="Public control/ACK/activation order supplies an independent Message-blocking gate for every incoming Overheard. Internal flag states are not directly logged; no additional F network effect is observed."),
                  stop=stop, new_simulations_executed=False, kit_or_model_edited=False,
                  scope="Causal prefix through rejected random request97, native event3402. Native same-time TX17 follows that guard and is not an unexplained earlier omission. No full-network or15percent performance-parity claim.",
                  input_hashes={str(path.relative_to(ROOT)): digest(path) for path in inputs})
    (OUT / "ef_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(cases=summaries, byte_identical=all(equality.values()),
                         received_overheard_gate_history=received_overheard), indent=2))


if __name__ == "__main__":
    main()
