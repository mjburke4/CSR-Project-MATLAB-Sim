#!/usr/bin/env python3
"""Reproduce a read-only I owner-return audit against the captured native tape.

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
DATA = ROOT / "autonomous_seventh/data"
KIT = ROOT / "autonomous_sixth/kit/autocase"
NATIVE = ROOT / "autonomous/native_capture/fixture"
OUT = Path(__file__).resolve().parent
CASES = ("I_control_wire",)


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
    ):
        result = read_json(DATA / path)
        assert result["passed"] and len(result["checks"]) == count
        assert all(row["passed"] for row in result["checks"])
        preflights[name] = dict(passed=True, checks=count)
    assert read_json(DATA / "import_preflight/preflight.json")["passed"]

    folder = DATA / "I_control_wire"
    events = records(folder / "ordered_events.jsonl")
    requests = records(folder / "random_requests.jsonl")
    stop = read_json(folder / "first_divergence.json")
    cutoff = int(stop["expected"][0]["event_order"])
    all_draws = list(csv.DictReader((NATIVE / "random_draws.csv").open()))
    native_draws = [row for row in all_draws if int(row["event_order"]) <= cutoff]
    tx_by_id = {}
    for row in csv.DictReader((NATIVE / "tx_signatures.csv").open()):
        tx_by_id.setdefault(int(row["tx_id"]), []).append(row)
    native_txs = sorted([rows for rows in tx_by_id.values() if int(rows[0]["event_order"]) <= cutoff],
                        key=lambda rows: int(rows[0]["event_order"]))
    assert list(map(draw_key, requests)) == list(map(draw_key, native_draws))
    assert len(requests) == 290 and all(row["context_matched"] for row in requests)
    request_table, ignored = [], []
    for index, (actual, expected) in enumerate(zip(requests, native_draws), 1):
        assert round(actual["time_s"] * 1e9) == int(expected["time_ns"])
        assert actual["value"] == float(expected["value"])
        differences = [field for field, value in actual["actual"].items() if not equal(value, expected[field], field)]
        diagnostic = "reported_nodes" in differences
        if diagnostic:
            assert actual["actual"]["profile"] == 4
            ignored.append(dict(request=index, actual=actual["actual"]["reported_nodes"], native=int(expected["reported_nodes"])))
        assert all(field == "reported_nodes" for field in differences)
        request_table.append(dict(global_request_index=index, node=actual["node"], purpose=actual["purpose"],
            ordinal=actual["ordinal"], native_event_order=int(expected["event_order"]), native_time_ns=int(expected["time_ns"]),
            matlab_time_s=actual["time_s"], global_order_equal=True, rounded_time_equal=True,
            controlling_context_equal=True, value_consumed=True, ignored_profile4_reported_nodes_difference=diagnostic))
    txs = [row for row in events if row["kind"] == "physical_tx_context"]
    assert len(txs) == len(native_txs) == 50
    tx_table = []
    for index, (actual, expected) in enumerate(zip(txs, native_txs), 1):
        detail, parent = actual["details"], expected[0]
        assert int(detail["native_semantic_tx_id"]) == int(parent["tx_id"])
        assert round(actual["time_s"] * 1e9) == int(parent["time_ns"])
        differences = tx_differences(detail["actual"], expected)
        assert differences == detail["mismatches"]
        assert differences == (["child3.hop_sequence"] if index == 50 else [])
        tx_table.append(dict(global_tx_index=index, source=int(parent["source"]), source_tx_ordinal=int(parent["source_tx_ordinal"]),
            tx_id=int(parent["tx_id"]), native_event_order=int(parent["event_order"]), native_time_ns=int(parent["time_ns"]),
            matlab_time_s=actual["time_s"], child_count=detail["actual"]["child_count"], wire_bytes=detail["actual"]["total_wire_bytes"],
            semantic_context_passed=not differences, independently_recomputed_differences=";".join(differences)))
    wanted = sorted([(int(row["event_order"]), "random", *draw_key(row)) for row in native_draws] +
        [(int(rows[0]["event_order"]), "tx", int(rows[0]["source"]), "physical_tx", int(rows[0]["source_tx_ordinal"])) for rows in native_txs])
    merged, merged_table, broadcasts = [], [], []
    for event in events:
        if event["kind"] == "random_request":
            row = event["details"]
            merged.append((int(row["expected"]["event_order"]), "random", *draw_key(row)))
        elif event["kind"] == "physical_tx_context":
            row = tx_by_id[int(event["details"]["native_semantic_tx_id"])][0]
            merged.append((int(row["event_order"]), "tx", int(row["source"]), "physical_tx", int(row["source_tx_ordinal"])))
        elif event["kind"] == "protocol" and event["details"]["event"] == "mac_enqueue":
            frame = event["details"].get("frame", {})
            control = frame.get("Control", {})
            if control.get("Type") == "DISCOVER":
                broadcasts.append(dict(time_s=event["time_s"], node=event["node"], outer_hop_sequence=frame["Sequence"],
                    payload_discovery_sequence=control["Payload"]["Sequence"], subtype=control["Payload"]["Subtype"]))
            continue
        else:
            continue
        merged_table.append(dict(index=len(merged), matlab_observation_order=event["observation_order"],
            native_event_order=merged[-1][0], kind=merged[-1][1], node=merged[-1][2], purpose=merged[-1][3], ordinal=merged[-1][4],
            matlab_time_s=event["time_s"], rounded_time_ns=round(event["time_s"] * 1e9)))
    assert merged == wanted and len(merged) == 340
    assert [row["details"] for row in events if row["kind"] == "random_request"] == requests
    identities = [row for row in events if row["kind"] == "physical_tx_identity"]
    assert len(identities) == 49
    assert [int(row["details"]["native_semantic_tx_id"]) for row in identities] == [
        int(row["details"]["native_semantic_tx_id"]) for row in txs[:-1]]
    wire_fix = next(row for row in txs if int(row["details"]["native_semantic_tx_id"]) == 4294967314)
    assert not wire_fix["details"]["mismatches"] and wire_fix["details"]["actual"]["total_wire_bytes"] == 63
    assert [child["wire_bytes"] for child in wire_fix["details"]["actual"]["children"]] == [16,16,31]
    earlier_phy = next(row for row in requests if draw_key(row) == (4, "phy_binomial", 2))
    assert earlier_phy["actual"]["bits"] == 183
    for identity, count, size in ((21474836483,4,82),(4294967303,7,215)):
        actual = next(row["details"]["actual"] for row in txs if int(row["details"]["native_semantic_tx_id"]) == identity)
        assert actual["child_count"] == count and actual["total_wire_bytes"] == size
    population = next(row for row in requests if draw_key(row) == (1, "mac_slot", 8))
    assert population["actual"]["active_nodes"] == 2 and population["value"] == 13
    child = stop["actual"]["children"][2]
    assert child["kind"] == 4 and child["hop_destination"] == 16777215 and child["ackable"] == 0
    assert child["hop_sequence"] == 1 and stop["expected"][2]["hop_sequence"] == 4
    assert child["discover_sequence"] == stop["expected"][2]["discover_sequence"] == 1
    assert [(r["node"],r["outer_hop_sequence"]) for r in broadcasts] == [(1,1),(1,2),(1,3),(3,1)]
    summary = read_json(folder / "random_summary.json")
    observer = read_json(folder / "observer_status.json")
    assert summary["first_time_difference"] == [] and summary["native_transmissions_checked"] == 49
    assert observer["Complete"] and observer["OmittedServiceRecords"] == 0 and observer["CancellationPairsComplete"]
    assert observer["CancellationPairErrors"] == 0
    native_no_path = sum(row["check_subtype"] == "no_path" for rows in tx_by_id.values() for row in rows)
    assert native_no_path == 0
    for name, rows in (("global_random_comparison.csv",request_table),("global_tx_comparison.csv",tx_table),
                       ("merged_random_tx_order.csv",merged_table),("discover_enqueue_sequences.csv",broadcasts)):
        csv_out(name, rows)
    inputs = [NATIVE / "random_draws.csv", NATIVE / "tx_signatures.csv", KIT / "FILES.json", DATA / "provenance.json",
        DATA / "report.json", folder / "random_requests.jsonl", folder / "ordered_events.jsonl", folder / "first_divergence.json"]
    result = dict(schema="csr-seventh-owner-i-independent-audit-v1", requests=290, consumed=290,
        requests_by_purpose=dict(Counter(row["purpose"] for row in requests)), tx_verified=49, rejected_tx_attempt=50,
        rejected_tx_not_transmitted=True, merged_events=340, native_cutoff_event_order=cutoff, cutoff_time_ns=25740000000,
        global_order_equal=True, rounded_ns_times_equal=True, controlling_request_contexts_equal=True,
        recorded_phy_interval_component_ns_equal=True, ignored_profile4_reported_nodes_differences=ignored,
        final_tx_independent_differences=["child3.hop_sequence"], request_wire_fix_actual_tx=wire_fix["details"]["actual"],
        earlier_phy183_fourchild82_population2_sevenchild215_guards_pass=True, broadcasts=broadcasts,
        native_no_path_children_in_full_fixture=0, no_path_network_effect_exercised=False, preflights=preflights,
        provenance=dict(manifest_equal=True, bound_files_verified=len(files), resolved_matlab_files_verified=len(provenance["resolved_matlab_files"]),
            source_candidate_transforms_equal=True, runtime=provenance["runtime"], accepted_natural_reused=True,
            fresh_natural_run=False, natural_trace_rows=natural_rows, natural_trace_bytes_equal=True,
            configuration_equal_except_source_path=True), service_capture_complete_through_stop=True,
        no_new_simulation_executed_by_auditor=True, no_kit_or_guard_edits=True,
        scope="Unconditional logged request/TX prefix through rejected attempt only. Does not prove all internal state equality or full-network/6000-second/15-percent parity.",
        input_hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs})
    (OUT / "i_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({key:result[key] for key in ("requests","consumed","requests_by_purpose","tx_verified","merged_events",
        "native_cutoff_event_order","global_order_equal","rounded_ns_times_equal","provenance","preflights")},indent=2))


if __name__ == "__main__":
    main()

