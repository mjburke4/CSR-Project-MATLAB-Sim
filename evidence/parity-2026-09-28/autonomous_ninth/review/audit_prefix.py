#!/usr/bin/env python3
"""Reproduce a read-only K owner-return audit against the captured native tape.

Audits unconditional global request/TX order (including the rejected TX),
rounded-nanosecond time, independently compared logged contexts and provenance.
Does not simulate, alter inputs, or equate guarded-prefix agreement to parity.
"""
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "autonomous_ninth/data"
KIT = ROOT / "autonomous_eighth/kit/autocase"
NATIVE = ROOT / "autonomous/native_capture/fixture"
OUT = Path(__file__).resolve().parent
CASES = ("K_receiver_timers",)


def read_json(path):
    return json.loads(path.read_text())


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_out(name, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_key(row):
    return int(row["node"]), row["purpose"], int(row["ordinal"])


def equal(value, text, field):
    if isinstance(value, str):
        if field == "discover_active_peers":
            return sorted(value.split(";")) == sorted(text.split(";"))
        return value == text
    if value is None:
        return text == ""
    number = float(text)
    return (math.isclose(value, number, rel_tol=1e-12, abs_tol=0)
            if field == "probability" else value == number)


def tx_differences(actual, native):
    differences = []
    for field, value in actual.items():
        if field == "children":
            continue
        if not equal(value, native[0][field], field):
            differences.append("parent." + field)
    if actual["child_count"] != len(native):
        differences.append("ordered_child_count")
        return differences
    for index, (child, expected) in enumerate(zip(actual["children"], native), 1):
        for field, value in child.items():
            # These diagnostic payload fields have no native column. Their
            # encoded semantic fields are independently compared below.
            if field not in expected or field.endswith("_ns"):
                continue
            if not equal(value, expected[field], field):
                differences.append(f"child{index}.{field}")
    return differences


def main():
    manifest = read_json(KIT / "FILES.json")
    provenance = read_json(DATA / "provenance.json")
    assert manifest == provenance["manifest"]
    files = {row["path"]: row for row in manifest["files"]}
    for path, row in files.items():
        assert digest(KIT / path) == row["sha256"]
        assert (KIT / path).stat().st_size == row["bytes"]
    for row in provenance["resolved_matlab_files"]:
        relative = row["path"].split("\\autocase\\", 1)[1].replace("\\", "/")
        assert row["sha256"] == files[relative]["sha256"]
    for key in ("source_transform", "candidate_transform"):
        assert provenance[key] == read_json(KIT / (key + ".json"))
    natural = read_json(DATA / "A_natural/accepted_reuse.json")["reuse"]
    assert natural["reused"] and natural["runtime_matches"] and natural["configuration_matches"]
    assert natural["prefix_gate_recomputed"] and not natural["fresh_natural_simulation_executed"]
    cfg = read_json(DATA / "configuration.json")
    previous = read_json(KIT / "ref/accepted/configuration.json")
    cfg["SharedScenario"]["SourcePath"] = previous["SharedScenario"]["SourcePath"] = "metadata-only"
    assert cfg == previous
    natural_rows = {}
    for name in ("protocol_trace.csv", "phy_trace.csv", "application_admission_trace.csv"):
        assert digest(DATA / "A_natural" / name) == digest(KIT / "ref/accepted" / name)
        natural_rows[name] = sum(1 for _ in csv.DictReader((DATA / "A_natural" / name).open()))
    assert read_json(DATA / "A_natural/prefix_gate.json")["passed"]
    preflights = {}
    for name, path, count in (
        ("key", "key_preflight/key_request_preflight.json", 7),
        ("neighbor", "check_preflight/check_gate_preflight.json", 8),
        ("population", "population_preflight/population_preflight.json", 6),
        ("route", "route_preflight/route_admission_preflight.json", 8),
        ("request_wire", "request_preflight/request_wire_preflight.json", 6),
        ("no_path_wire", "no_path_preflight/no_path_wire_preflight.json", 3),
        ("discovery_identity", "identity_preflight/discovery_identity_preflight.json", 7),
        ("receiver_timer", "timer_preflight/receiver_timer_preflight.json", 8),
    ):
        result = read_json(DATA / path)
        assert result["passed"] and len(result["checks"]) == count
        assert all(row["passed"] for row in result["checks"])
        preflights[name] = dict(passed=True, checks=count)
    assert read_json(DATA / "import_preflight/preflight.json")["passed"]

    folder = DATA / "K_receiver_timers"
    events = records(folder / "ordered_events.jsonl")
    requests = records(folder / "random_requests.jsonl")
    stop = read_json(folder / "first_divergence.json")
    cutoff = int(stop["expected"][0]["event_order"])
    all_draws = list(csv.DictReader((NATIVE / "random_draws.csv").open()))
    native_draws = [row for row in all_draws if int(row["event_order"]) <= cutoff]
    draws_by_key = {draw_key(row):row for row in native_draws}
    tx_by_id = {}
    for row in csv.DictReader((NATIVE / "tx_signatures.csv").open()):
        tx_by_id.setdefault(int(row["tx_id"]), []).append(row)
    native_txs = sorted([rows for rows in tx_by_id.values() if int(rows[0]["event_order"]) <= cutoff],
                        key=lambda rows: int(rows[0]["event_order"]))
    assert len(requests) == len(native_draws) == 1450
    assert set(map(draw_key, requests)) == set(draws_by_key)
    assert all(row["context_matched"] for row in requests)
    request_table, ignored = [], []
    for index, actual in enumerate(requests, 1):
        expected = draws_by_key[draw_key(actual)]
        assert actual["value"] == float(expected["value"])
        differences = [field for field, value in actual["actual"].items() if not equal(value, expected[field], field)]
        diagnostic = "reported_nodes" in differences
        if diagnostic:
            assert actual["actual"]["profile"] == 4
            ignored.append(dict(request=index, actual=actual["actual"]["reported_nodes"], native=int(expected["reported_nodes"])))
        controlling = [field for field in differences if field != "reported_nodes" and not field.endswith("_ns")]
        assert not controlling
        delta = round(actual["time_s"]*1e9)-int(expected["time_ns"])
        request_table.append(dict(global_request_index=index, node=actual["node"], purpose=actual["purpose"],
            ordinal=actual["ordinal"], native_event_order=int(expected["event_order"]), native_time_ns=int(expected["time_ns"]),
            matlab_time_s=actual["time_s"], rounded_time_delta_ns=delta,
            guarded_context_equal=True, endpoint_context_differences=";".join(f for f in differences if f.endswith("_ns")),
            value_consumed=True, ignored_profile4_reported_nodes_difference=diagnostic))
    txs = [row for row in events if row["kind"] == "physical_tx_context"]
    assert len(txs) == len(native_txs) == 244
    assert [int(row["details"]["native_semantic_tx_id"]) for row in txs] == [int(rows[0]["tx_id"]) for rows in native_txs]
    # Rejected TX does not reach mac_transmit. Its actual raw frame remains
    # in the immediately preceding public mac_state(Tx) observation.
    raw_mac_txs = {}
    for event in events:
        if event["kind"] == "protocol" and event["details"]["event"] in ("mac_transmit", "mac_state"):
            frame = event["details"]["frame"]
            if frame.get("Kind") != "IDLE" and frame.get("WirePayloadBytes",0):
                raw_mac_txs[(event["node"], round(event["time_s"]*1e9))] = frame
    tx_table, annotations = [], []
    for index, (actual, expected) in enumerate(zip(txs, native_txs), 1):
        detail, parent = actual["details"], expected[0]
        differences = tx_differences(detail["actual"], expected)
        permitted = []
        raw_frame = raw_mac_txs[(actual["node"], round(actual["time_s"]*1e9))]
        raw_children = raw_frame.get("Segments") or [raw_frame]
        for child_index, (child, wanted, raw) in enumerate(zip(detail["actual"]["children"], expected, raw_children), 1):
            eligibility = (child["kind"] == 4 and child["hop_destination"] == 16777215 and
                child["ackable"] == 0 and child["has_ack_window"] == 0 and child.get("discover_subtype") == "broadcast" and
                raw.get("DestinationIds") in (16777215, [16777215]) and
                int(wanted["kind"]) == 4 and int(wanted["hop_destination"]) == 16777215 and
                int(wanted["ackable"]) == 0 and int(wanted["has_ack_window"]) == 0 and wanted["discover_subtype"] == "broadcast" and
                int(wanted["destination_type"]) == 1 and int(wanted["flags"]) & 128 and
                wanted["security_count"] != "" and math.isfinite(float(wanted["security_count"])))
            assert ("discovery_outer_sequence_identity" in child) == bool(eligibility)
            if not eligibility:
                continue
            annotation = child["discovery_outer_sequence_identity"]
            assert annotation["actual"] == child["hop_sequence"] == raw["Sequence"]
            assert annotation["native"] == int(wanted["hop_sequence"])
            assert annotation["policy"] == "trace_only_broadcast_discover_identifier" and annotation["reason"]
            assert child["discover_sequence"] == int(wanted["discover_sequence"])
            if annotation["actual"] != annotation["native"]:
                permitted.append(f"child{child_index}.hop_sequence")
            annotations.append(dict(global_tx_index=index, time_s=actual["time_s"], source=actual["node"],
                source_tx_ordinal=int(parent["source_tx_ordinal"]), child_index=child_index,
                actual_outer_sequence=annotation["actual"], native_outer_sequence=annotation["native"],
                payload_discovery_sequence=child["discover_sequence"], raw_difference=annotation["actual"] != annotation["native"],
                independently_verified_eligibility=True, policy=annotation["policy"], reason=annotation["reason"]))
        remaining = [field for field in differences if field not in permitted]
        assert remaining == ([] if index<244 else ["child3.hop_destination", "child3.snmp_destination"])
        assert detail["mismatches"] == remaining
        tx_table.append(dict(global_tx_index=index, source=int(parent["source"]), source_tx_ordinal=int(parent["source_tx_ordinal"]),
            tx_id=int(parent["tx_id"]), native_event_order=int(parent["event_order"]), native_time_ns=int(parent["time_ns"]),
            matlab_time_s=actual["time_s"], rounded_time_delta_ns=round(actual["time_s"]*1e9)-int(parent["time_ns"]),
            child_count=detail["actual"]["child_count"], wire_bytes=detail["actual"]["total_wire_bytes"],
            semantic_context_passed=not remaining, semantic_differences=";".join(remaining),
            independently_allowed_trace_identity_differences=";".join(permitted)))
    wanted = sorted([(int(row["event_order"]), "random", *draw_key(row)) for row in native_draws] +
        [(int(rows[0]["event_order"]), "tx", int(rows[0]["source"]), "physical_tx", int(rows[0]["source_tx_ordinal"])) for rows in native_txs])
    merged, merged_table = [], []
    for event in events:
        if event["kind"] == "random_request":
            row = event["details"]
            expected = draws_by_key[draw_key(row)]
            merged.append((int(expected["event_order"]), "random", *draw_key(row)))
        elif event["kind"] == "physical_tx_context":
            expected = tx_by_id[int(event["details"]["native_semantic_tx_id"])][0]
            merged.append((int(expected["event_order"]), "tx", int(expected["source"]), "physical_tx", int(expected["source_tx_ordinal"])))
        else:
            continue
        position = len(merged)-1
        merged_table.append(dict(index=position+1, matlab_observation_order=event["observation_order"],
            native_event_order=merged[-1][0], native_expected_order_at_position=wanted[position][0],
            global_position_equal=merged[-1]==wanted[position], kind=merged[-1][1], node=merged[-1][2], purpose=merged[-1][3], ordinal=merged[-1][4],
            matlab_time_s=event["time_s"], rounded_time_delta_ns=round(event["time_s"]*1e9)-int(expected["time_ns"])))
    assert sorted(merged) == wanted and len(merged) == 1694
    assert [row["details"] for row in events if row["kind"] == "random_request"] == requests
    identities = [row for row in events if row["kind"] == "physical_tx_identity"]
    assert len(identities) == 243
    assert [int(row["details"]["native_semantic_tx_id"]) for row in identities] == [int(row["details"]["native_semantic_tx_id"]) for row in txs[:-1]]
    boundary = next(row for row in requests if draw_key(row)==(3,"phy_binomial",75))
    assert boundary["actual"]["bits"] == boundary["expected"]["bits"] == 51
    assert boundary["time_s"] == 45.662638077 and boundary["context_matched"]
    verified_boundaries = []
    for identity, count, size in ((21474836483,4,82),(4294967303,7,215),(4294967314,3,63),(12884901905,3,109)):
        actual = next(row for row in txs if int(row["details"]["native_semantic_tx_id"]) == identity)
        assert actual["details"]["actual"]["child_count"] == count and actual["details"]["actual"]["total_wire_bytes"] == size
        verified_boundaries.append(dict(tx_id=identity,time_s=actual["time_s"],children=count,wire_bytes=size))
    assert next(row for row in requests if draw_key(row)==(4,"phy_binomial",2))["actual"]["bits"] == 183
    assert next(row for row in requests if draw_key(row)==(1,"mac_slot",8))["actual"]["active_nodes"] == 2
    summary = read_json(folder / "random_summary.json")
    observer = read_json(folder / "observer_status.json")
    assert summary["native_transmissions_checked"] == 243
    assert sum(row["consumed"] for row in summary["counts"]) == 1450
    assert observer["Complete"] and observer["OmittedServiceRecords"] == 0 and observer["CancellationPairsComplete"]
    assert observer["CancellationPairErrors"] == 0
    time_diffs = [row for row in request_table if row["rounded_time_delta_ns"]]
    tx_time_diffs = [row for row in tx_table if row["rounded_time_delta_ns"]]
    order_diffs = [row for row in merged_table if not row["global_position_equal"]]
    prefix_count=next(i for i,row in enumerate(merged_table) if not row["global_position_equal"] or row["rounded_time_delta_ns"])
    assert len(time_diffs)==341 and len(tx_time_diffs)==58 and len(order_diffs)==3 and prefix_count==1281
    for name, rows in (("global_random_comparison.csv",request_table),("global_tx_comparison.csv",tx_table),
                       ("merged_random_tx_order.csv",merged_table),("discovery_identity_annotations.csv",annotations)):
        csv_out(name,rows)
    raw_failed = raw_mac_txs[(5,71942000000)]["Segments"][2]
    expected_failed = tx_by_id[21474836548][2]
    assert raw_failed["DestinationId"]==4 and raw_failed["Control"]["Payload"]["DestinationId"]==2
    packet = bytes.fromhex(expected_failed["packet_hex"])
    payload = bytes.fromhex(expected_failed["payload_hex"])
    assert int.from_bytes(packet[3:6],"big")==1 and int.from_bytes(payload[3:6],"big")==1
    (OUT/"stopped_snmp_raw_evidence.json").write_text(json.dumps(dict(actual_raw_child=raw_failed,
        native_signature=expected_failed,native_outer_destination_from_packet_hex=int.from_bytes(packet[3:6],"big"),
        native_payload_destination_from_payload_hex=int.from_bytes(payload[3:6],"big")),indent=2)+"\n")
    inputs = [NATIVE / "random_draws.csv",NATIVE / "tx_signatures.csv",KIT / "FILES.json",DATA / "provenance.json",DATA / "report.json",
              folder / "random_requests.jsonl",folder / "ordered_events.jsonl",folder / "first_divergence.json"]
    result = dict(schema="csr-ninth-owner-k-independent-audit-v1",requests=1450,consumed=1450,
        requested_by_purpose=dict(Counter(row["purpose"] for row in requests)),tx_contexts_checked=244,tx_verified=243,
        tx_rejected=1,merged_events=1694,native_cutoff_event_order=cutoff,cutoff_time_ns=71942000000,
        global_order_equal=False,rounded_ns_times_equal=False,first_fully_matched_merged_events=prefix_count,
        strict_prefix_event_split=dict(Counter(row["kind"] for row in merged_table[:prefix_count])),
        last_strict_prefix_event=merged_table[prefix_count-1],
        global_order_differing_positions=order_diffs,request_timing_difference_count=len(time_diffs),
        tx_timing_difference_count=len(tx_time_diffs),first_request_time_difference=time_diffs[0],
        request_time_deltas_ns=dict(Counter(row["rounded_time_delta_ns"] for row in time_diffs)),
        tx_time_deltas_ns=dict(Counter(row["rounded_time_delta_ns"] for row in tx_time_diffs)),
        request_endpoint_diagnostic_difference_count=sum(bool(row["endpoint_context_differences"]) for row in request_table),
        all1450_guarded_contexts_equal=True,ignored_profile4_reported_nodes_differences=ignored,
        rejected_TX_not_registered_or_physically_emitted=True,stop=stop,
        previous_physical_boundaries_verified=verified_boundaries,earlier_phy183_and_population2_guards_pass=True,
        previous_timer_boundary=dict(time_s=boundary["time_s"],node=3,ordinal=75,bits=51,consumed=True),
        discovery_identity_annotations=annotations,normalization_scope_independently_verified=True,
        native_no_path_children_in_full_fixture=sum(row["check_subtype"]=="no_path" for rows in tx_by_id.values() for row in rows),
        preflights=preflights,component_checks=sum(row["checks"] for row in preflights.values()),
        provenance=dict(manifest_equal=True,bound_files_verified=len(files),resolved_matlab_files_verified=len(provenance["resolved_matlab_files"]),
            source_candidate_transforms_equal=True,runtime=provenance["runtime"],accepted_natural_reused=True,
            fresh_natural_run=False,natural_trace_rows=natural_rows,natural_trace_bytes_equal=True,configuration_equal_except_source_path=True),
        receiver_timing_summary=read_json(folder/"receiver_timing_summary.json"),
        service_capture_complete_through_stop=True,no_new_simulation_executed_by_auditor=True,no_kit_or_guard_edits=True,
        scope="1,281-event strict merged prefix only. Later local semantic guards pass despite timing and cross-stream order differences. No full-network/6000-second/15-percent parity claim.",
        input_hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs})
    (OUT / "k_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({key:result[key] for key in ("requests","consumed","requested_by_purpose","tx_verified","tx_rejected",
        "merged_events","first_fully_matched_merged_events","request_timing_difference_count","tx_timing_difference_count",
        "component_checks","provenance")},indent=2))


if __name__ == "__main__":
    main()
