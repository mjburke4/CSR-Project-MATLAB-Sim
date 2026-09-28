#!/usr/bin/env python3
"""Reproduce a read-only J owner-return audit against the captured native tape.

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
DATA = ROOT / "autonomous_eighth/data"
KIT = ROOT / "autonomous_seventh/kit/autocase"
NATIVE = ROOT / "autonomous/native_capture/fixture"
OUT = Path(__file__).resolve().parent
CASES = ("J_discovery_identity",)


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
    ):
        result = read_json(DATA / path)
        assert result["passed"] and len(result["checks"]) == count
        assert all(row["passed"] for row in result["checks"])
        preflights[name] = dict(passed=True, checks=count)
    assert read_json(DATA / "import_preflight/preflight.json")["passed"]

    folder = DATA / "J_discovery_identity"
    events = records(folder / "ordered_events.jsonl")
    requests = records(folder / "random_requests.jsonl")
    stop = read_json(folder / "first_divergence.json")
    cutoff = int(stop["expected"]["event_order"])
    all_draws = list(csv.DictReader((NATIVE / "random_draws.csv").open()))
    native_draws = [row for row in all_draws if int(row["event_order"]) <= cutoff]
    tx_by_id = {}
    for row in csv.DictReader((NATIVE / "tx_signatures.csv").open()):
        tx_by_id.setdefault(int(row["tx_id"]), []).append(row)
    native_txs = sorted([rows for rows in tx_by_id.values() if int(rows[0]["event_order"]) <= cutoff],
                        key=lambda rows: int(rows[0]["event_order"]))
    assert list(map(draw_key, requests)) == list(map(draw_key, native_draws))
    assert len(requests) == 759
    assert [row["context_matched"] for row in requests] == [True]*758+[False]
    request_table, ignored = [], []
    for index, (actual, expected) in enumerate(zip(requests, native_draws), 1):
        assert round(actual["time_s"]*1e9) == int(expected["time_ns"])
        assert actual["value"] == (float(expected["value"]) if index < 759 else None)
        differences = [field for field, value in actual["actual"].items() if not equal(value, expected[field], field)]
        diagnostic = "reported_nodes" in differences
        if diagnostic:
            assert actual["actual"]["profile"] == 4
            ignored.append(dict(request=index, actual=actual["actual"]["reported_nodes"], native=int(expected["reported_nodes"])))
        controlling = [field for field in differences if field != "reported_nodes"]
        assert controlling == (["bits"] if index == 759 else [])
        request_table.append(dict(global_request_index=index, node=actual["node"], purpose=actual["purpose"],
            ordinal=actual["ordinal"], native_event_order=int(expected["event_order"]), native_time_ns=int(expected["time_ns"]),
            matlab_time_s=actual["time_s"], global_order_equal=True, rounded_time_equal=True,
            controlling_context_differences=";".join(controlling), value_consumed=actual["context_matched"],
            ignored_profile4_reported_nodes_difference=diagnostic))
    txs = [row for row in events if row["kind"] == "physical_tx_context"]
    assert len(txs) == len(native_txs) == 129
    raw_mac_txs = {}
    for event in events:
        if event["kind"] == "protocol" and event["details"]["event"] == "mac_transmit":
            key = (event["node"], round(event["time_s"]*1e9))
            assert key not in raw_mac_txs
            raw_mac_txs[key] = event["details"]["frame"]
    tx_table, annotations = [], []
    for index, (actual, expected) in enumerate(zip(txs, native_txs), 1):
        detail, parent = actual["details"], expected[0]
        assert int(detail["native_semantic_tx_id"]) == int(parent["tx_id"])
        assert round(actual["time_s"]*1e9) == int(parent["time_ns"])
        assert not detail["mismatches"]
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
        assert differences == permitted
        tx_table.append(dict(global_tx_index=index, source=int(parent["source"]), source_tx_ordinal=int(parent["source_tx_ordinal"]),
            tx_id=int(parent["tx_id"]), native_event_order=int(parent["event_order"]), native_time_ns=int(parent["time_ns"]),
            matlab_time_s=actual["time_s"], child_count=detail["actual"]["child_count"], wire_bytes=detail["actual"]["total_wire_bytes"],
            semantic_context_passed=True, independently_allowed_trace_identity_differences=";".join(permitted)))
    assert len(annotations) == 7 and sum(row["raw_difference"] for row in annotations) == 4
    wanted = sorted([(int(row["event_order"]), "random", *draw_key(row)) for row in native_draws] +
        [(int(rows[0]["event_order"]), "tx", int(rows[0]["source"]), "physical_tx", int(rows[0]["source_tx_ordinal"])) for rows in native_txs])
    merged, merged_table = [], []
    for event in events:
        if event["kind"] == "random_request":
            row = event["details"]
            merged.append((int(row["expected"]["event_order"]), "random", *draw_key(row)))
        elif event["kind"] == "physical_tx_context":
            row = tx_by_id[int(event["details"]["native_semantic_tx_id"])][0]
            merged.append((int(row["event_order"]), "tx", int(row["source"]), "physical_tx", int(row["source_tx_ordinal"])))
        else:
            continue
        merged_table.append(dict(index=len(merged), matlab_observation_order=event["observation_order"],
            native_event_order=merged[-1][0], kind=merged[-1][1], node=merged[-1][2], purpose=merged[-1][3], ordinal=merged[-1][4],
            matlab_time_s=event["time_s"], rounded_time_ns=round(event["time_s"]*1e9)))
    assert merged == wanted and len(merged) == 888
    assert [row["details"] for row in events if row["kind"] == "random_request"] == requests
    identities = [row for row in events if row["kind"] == "physical_tx_identity"]
    assert len(identities) == 129
    assert [int(row["details"]["native_semantic_tx_id"]) for row in identities] == [int(row["details"]["native_semantic_tx_id"]) for row in txs]
    verified_boundaries = []
    for identity, count, size in ((21474836483,4,82),(4294967303,7,215),(4294967314,3,63),(12884901905,3,109)):
        actual = next(row for row in txs if int(row["details"]["native_semantic_tx_id"]) == identity)
        assert actual["details"]["actual"]["child_count"] == count and actual["details"]["actual"]["total_wire_bytes"] == size
        verified_boundaries.append(dict(tx_id=identity,time_s=actual["time_s"],children=count,wire_bytes=size))
    assert next(row for row in requests if draw_key(row)==(4,"phy_binomial",2))["actual"]["bits"] == 183
    population = next(row for row in requests if draw_key(row)==(1,"mac_slot",8))
    assert population["actual"]["active_nodes"] == 2 and population["value"] == 13
    assert stop["actual"]["bits"] == 52 and stop["expected"]["bits"] == 51
    for field in ("tx_id","interval_ordinal","interval_start_ns","interval_end_ns","component_start_ns","component_end_ns","probability","component"):
        assert stop["actual"][field] == stop["expected"][field]
    summary = read_json(folder / "random_summary.json")
    observer = read_json(folder / "observer_status.json")
    assert summary["first_time_difference"] == [] and summary["native_transmissions_checked"] == 129
    assert sum(row["consumed"] for row in summary["counts"]) == 758
    assert observer["Complete"] and observer["OmittedServiceRecords"] == 0 and observer["CancellationPairsComplete"]
    assert observer["CancellationPairErrors"] == 0
    native_no_path = sum(row["check_subtype"] == "no_path" for rows in tx_by_id.values() for row in rows)
    assert native_no_path == 0
    for name, rows in (("global_random_comparison.csv",request_table),("global_tx_comparison.csv",tx_table),
                       ("merged_random_tx_order.csv",merged_table),("discovery_identity_annotations.csv",annotations)):
        csv_out(name,rows)
    inputs = [NATIVE / "random_draws.csv",NATIVE / "tx_signatures.csv",KIT / "FILES.json",DATA / "provenance.json",DATA / "report.json",
              folder / "random_requests.jsonl",folder / "ordered_events.jsonl",folder / "first_divergence.json"]
    result = dict(schema="csr-eighth-owner-j-independent-audit-v1",requests=759,consumed=758,
        requested_by_purpose=dict(Counter(row["purpose"] for row in requests)),
        consumed_by_purpose=dict(Counter(row["purpose"] for row in requests if row["context_matched"])),
        tx_verified=129,merged_events=888,native_cutoff_event_order=cutoff,cutoff_time_ns=int(stop["expected"]["time_ns"]),
        global_order_equal=True,rounded_ns_times_equal=True,prior758_controlling_contexts_equal=True,
        all_recorded_phy_interval_component_ns_equal=True,ignored_profile4_reported_nodes_differences=ignored,
        stopped_request_value_not_consumed=True,stop=stop,
        previous_physical_boundaries_verified=verified_boundaries,earlier_phy183_and_population2_guards_pass=True,
        discovery_identity_annotations=annotations,normalization_scope_independently_verified=True,
        native_no_path_children_in_full_fixture=0,no_path_network_effect_exercised=False,preflights=preflights,
        provenance=dict(manifest_equal=True,bound_files_verified=len(files),resolved_matlab_files_verified=len(provenance["resolved_matlab_files"]),
            source_candidate_transforms_equal=True,runtime=provenance["runtime"],accepted_natural_reused=True,
            fresh_natural_run=False,natural_trace_rows=natural_rows,natural_trace_bytes_equal=True,configuration_equal_except_source_path=True),
        service_capture_complete_through_stop=True,no_new_simulation_executed_by_auditor=True,no_kit_or_guard_edits=True,
        scope="Unconditional logged request/TX prefix through rejected draw only. Rounded-ns equality does not establish raw floating-point endpoint equality or every internal state. No full-network/6000-second/15-percent parity claim.",
        input_hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs})
    (OUT / "j_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({key:result[key] for key in ("requests","consumed","requested_by_purpose","consumed_by_purpose","tx_verified",
        "merged_events","native_cutoff_event_order","global_order_equal","rounded_ns_times_equal","provenance","preflights")},indent=2))


if __name__ == "__main__":
    main()
