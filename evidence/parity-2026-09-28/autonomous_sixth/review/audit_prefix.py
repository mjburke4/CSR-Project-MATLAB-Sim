#!/usr/bin/env python3
"""Reproduce a read-only G/H owner-return audit against the captured native tape.

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
DATA = ROOT / "autonomous_sixth/data"
KIT = ROOT / "autonomous_fifth/kit/autocase"
NATIVE = ROOT / "autonomous/native_capture/fixture"
OUT = Path(__file__).resolve().parent
CASES = ("G_population", "H_admission_route")


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
    assert provenance["manifest"] == manifest
    manifest_files = {row["path"]: row for row in manifest["files"]}
    for path, row in manifest_files.items():
        assert digest(KIT / path) == row["sha256"]
        assert (KIT / path).stat().st_size == row["bytes"]
    for row in provenance["resolved_matlab_files"]:
        path = row["path"].split("\\autocase\\", 1)[1].replace("\\", "/")
        assert row["sha256"] == manifest_files[path]["sha256"]
    for key in ("source_transform", "candidate_transform"):
        assert provenance[key] == read_json(KIT / (key + ".json"))
    natural = read_json(DATA / "A_natural/accepted_reuse.json")["reuse"]
    assert natural["reused"] and not natural["fresh_natural_simulation_executed"]
    assert natural["runtime_matches"] and natural["configuration_matches"]
    assert natural["prefix_gate_recomputed"]
    cfg = read_json(DATA / "configuration.json")
    accepted_cfg = read_json(KIT / "ref/accepted/configuration.json")
    cfg["SharedScenario"]["SourcePath"] = "metadata-only"
    accepted_cfg["SharedScenario"]["SourcePath"] = "metadata-only"
    assert cfg == accepted_cfg
    natural_rows = {}
    for name in ("protocol_trace.csv", "phy_trace.csv", "application_admission_trace.csv"):
        assert digest(DATA / "A_natural" / name) == digest(KIT / "ref/accepted" / name)
        with (DATA / "A_natural" / name).open() as handle:
            natural_rows[name] = sum(1 for _ in csv.DictReader(handle))
    gate = read_json(DATA / "A_natural/prefix_gate.json")
    assert gate["passed"] and all(row["passed"] for row in gate["checks"])
    preflights = {}
    for name, path, count in (
        ("key", "key_preflight/key_request_preflight.json", 7),
        ("neighbor", "check_preflight/check_gate_preflight.json", 8),
        ("population", "population_preflight/population_preflight.json", 6),
        ("route", "route_preflight/route_admission_preflight.json", 8),
    ):
        result = read_json(DATA / path)
        assert result["passed"] and len(result["checks"]) == count
        assert all(row["passed"] for row in result["checks"])
        preflights[name] = {"passed": True, "checks": count}
    assert read_json(DATA / "import_preflight/preflight.json")["passed"]

    all_draws = list(csv.DictReader((NATIVE / "random_draws.csv").open()))
    tx_by_id = {}
    for row in csv.DictReader((NATIVE / "tx_signatures.csv").open()):
        tx_by_id.setdefault(int(row["tx_id"]), []).append(row)
    all_txs = sorted(tx_by_id.values(), key=lambda rows: int(rows[0]["event_order"]))
    request_table, tx_table, merged_table, routing_table = [], [], [], []
    summaries, case_requests, events_by_case = {}, {}, {}
    inputs = [NATIVE / "random_draws.csv", NATIVE / "tx_signatures.csv", KIT / "FILES.json",
              DATA / "report.json", DATA / "provenance.json"]
    for case in CASES:
        folder = DATA / case
        requests = records(folder / "random_requests.jsonl")
        events = records(folder / "ordered_events.jsonl")
        case_requests[case], events_by_case[case] = requests, events
        stop = read_json(folder / "first_divergence.json")
        cutoff = int(stop["expected"][0]["event_order"])
        native_draws = [row for row in all_draws if int(row["event_order"]) <= cutoff]
        native_txs = [rows for rows in all_txs if int(rows[0]["event_order"]) <= cutoff]
        assert list(map(draw_key, requests)) == list(map(draw_key, native_draws))
        assert all(row["context_matched"] for row in requests)
        reported_differences = []
        for index, (actual, expected) in enumerate(zip(requests, native_draws), 1):
            assert round(actual["time_s"] * 1e9) == int(expected["time_ns"])
            assert actual["value"] == float(expected["value"])
            mismatch = [field for field, value in actual["actual"].items()
                        if not equal(value, expected[field], field)]
            diagnostic = [field for field in mismatch if field == "reported_nodes"]
            mismatch = [field for field in mismatch if field != "reported_nodes"]
            assert not mismatch
            if diagnostic:
                assert actual["actual"]["profile"] == 4
                reported_differences.append({"request": index, "actual": actual["actual"]["reported_nodes"],
                                             "native": int(expected["reported_nodes"])})
            request_table.append(dict(case=case, global_request_index=index, node=actual["node"],
                purpose=actual["purpose"], ordinal=actual["ordinal"], native_event_order=int(expected["event_order"]),
                native_time_ns=int(expected["time_ns"]), matlab_time_s=actual["time_s"], global_order_equal=True,
                rounded_time_equal=True, context_matched=True, value_consumed=True,
                profile4_ignored_reported_nodes_difference=bool(diagnostic)))
        txs = [row for row in events if row["kind"] == "physical_tx_context"]
        assert len(txs) == len(native_txs)
        for index, (actual, expected) in enumerate(zip(txs, native_txs), 1):
            detail, parent = actual["details"], expected[0]
            assert int(detail["native_semantic_tx_id"]) == int(parent["tx_id"])
            assert round(actual["time_s"] * 1e9) == int(parent["time_ns"])
            differences = tx_differences(detail["actual"], expected)
            assert differences == detail["mismatches"]
            assert bool(differences) == (index == len(txs))
            tx_table.append(dict(case=case, global_tx_index=index, source=int(parent["source"]),
                source_tx_ordinal=int(parent["source_tx_ordinal"]), tx_id=int(parent["tx_id"]),
                native_event_order=int(parent["event_order"]), native_time_ns=int(parent["time_ns"]),
                matlab_time_s=actual["time_s"], actual_child_count=detail["actual"]["child_count"],
                native_child_count=int(parent["child_count"]), actual_wire_bytes=detail["actual"]["total_wire_bytes"],
                native_wire_bytes=int(parent["total_wire_bytes"]), semantic_context_passed=not differences,
                independently_recomputed_differences=";".join(differences)))
        native_merged = sorted([(int(row["event_order"]), "random", *draw_key(row)) for row in native_draws] +
            [(int(rows[0]["event_order"]), "tx", int(rows[0]["source"]), "physical_tx",
              int(rows[0]["source_tx_ordinal"])) for rows in native_txs])
        merged = []
        for event in events:
            if event["kind"] == "random_request":
                row = event["details"]
                merged.append((int(row["expected"]["event_order"]), "random", *draw_key(row)))
            elif event["kind"] == "physical_tx_context":
                row = tx_by_id[int(event["details"]["native_semantic_tx_id"])][0]
                merged.append((int(row["event_order"]), "tx", int(row["source"]), "physical_tx", int(row["source_tx_ordinal"])))
            else:
                continue
            merged_table.append(dict(case=case, merged_index=len(merged), matlab_observation_order=event["observation_order"],
                native_event_order=merged[-1][0], kind=merged[-1][1], node=merged[-1][2], purpose=merged[-1][3],
                ordinal=merged[-1][4], matlab_time_s=event["time_s"], rounded_time_ns=round(event["time_s"]*1e9)))
        assert merged == native_merged
        assert [row["details"] for row in events if row["kind"] == "random_request"] == requests
        identities = [row for row in events if row["kind"] == "physical_tx_identity"]
        assert len(identities) == len(txs)-1
        assert [int(row["details"]["native_semantic_tx_id"]) for row in identities] == [
            int(row["details"]["native_semantic_tx_id"]) for row in txs[:-1]]
        earlier_phy = next(row for row in requests if draw_key(row) == (4, "phy_binomial", 2))
        assert earlier_phy["actual"]["bits"] == 183
        earlier_tx = next(row for row in txs if int(row["details"]["native_semantic_tx_id"]) == 21474836483)
        assert not earlier_tx["details"]["mismatches"]
        assert earlier_tx["details"]["actual"]["child_count"] == 4
        assert earlier_tx["details"]["actual"]["total_wire_bytes"] == 82
        earlier_population = next(row for row in requests if draw_key(row) == (1, "mac_slot", 8))
        assert earlier_population["actual"]["active_nodes"] == 2 and earlier_population["value"] == 13
        for event in events:
            if event["kind"] != "protocol" or event["node"] != 1 or not 14.4 < event["time_s"] < 14.5:
                continue
            detail = event["details"]
            frame = detail.get("frame", {})
            control = frame.get("Control", {})
            if detail["event"] != "hop_control_admit" or control.get("Type") != "ROUTING":
                continue
            routing_table.append(dict(case=case, time_s=event["time_s"], observation_order=event["observation_order"],
                wire_bytes=frame["WirePayloadBytes"], targets=json.dumps(detail["details"]["Targets"]),
                routing_section_hex=bytes(control["Payload"]["Bytes"]).hex()))
        summary = read_json(folder / "random_summary.json")
        observer = read_json(folder / "observer_status.json")
        assert summary["first_time_difference"] == []
        assert summary["native_transmissions_checked"] == len(txs)-1
        assert observer["Complete"] and observer["OmittedServiceRecords"] == 0
        assert observer["CancellationPairsComplete"] and observer["CancellationPairErrors"] == 0
        parent = native_txs[-1][0]
        summaries[case] = dict(requests=len(requests), values_consumed=len(requests),
            requests_by_purpose=dict(Counter(row["purpose"] for row in requests)),
            tx_contexts=len(txs), tx_verified=len(txs)-1, rejected_tx_was_not_transmitted=True,
            merged_events=len(merged), native_cutoff_event_order=cutoff, cutoff_time_ns=int(parent["time_ns"]),
            unconditional_global_order_equal=True, rounded_ns_times_equal=True,
            independently_compared_request_contexts_equal=True, recorded_phy_interval_component_ns_equal=True,
            noncontrolling_profile4_reported_nodes_differences=reported_differences,
            independently_recomputed_final_tx_differences=stop["fields"],
            stop_actual_wire_bytes=stop["actual"]["total_wire_bytes"], stop_native_wire_bytes=int(parent["total_wire_bytes"]),
            earlier_phy183_cleared=True, earlier_four_child82byte_tx_cleared=True,
            earlier_mac_population_guard_cleared=True,
            population_publications=[dict(time_s=row["time_s"], node=row["node"], count=row["details"]["ActiveNodes"])
                                     for row in events if row["kind"] == "mac_population_publish"],
            service_capture_complete_through_stop=True)
        inputs += [folder / name for name in ("random_requests.jsonl", "ordered_events.jsonl", "first_divergence.json", "random_summary.json")]
    assert case_requests[CASES[0]] == case_requests[CASES[1]][:len(case_requests[CASES[0]])]
    h_tx17 = next(row for row in events_by_case[CASES[1]] if row["kind"] == "physical_tx_context" and
                  int(row["details"]["native_semantic_tx_id"]) == 4294967303)
    assert not h_tx17["details"]["mismatches"]
    assert h_tx17["details"]["actual"]["child_count"] == 7 and h_tx17["details"]["actual"]["total_wire_bytes"] == 215
    assert [(row["case"],row["wire_bytes"]) for row in routing_table] == [
        ("G_population",65),("G_population",26),("H_admission_route",65)]
    for name, rows in (("global_random_comparison.csv", request_table), ("global_tx_comparison.csv", tx_table),
                       ("merged_random_tx_order.csv", merged_table), ("admission_routing_comparison.csv", routing_table)):
        csv_out(name, rows)
    report = dict(schema="csr-sixth-owner-gh-independent-audit-v1", cases=summaries, preflights=preflights,
        provenance=dict(issued_manifest_equal=True, bound_files_verified=len(manifest_files),
                        resolved_matlab_files_verified=len(provenance["resolved_matlab_files"]),
                        source_candidate_transforms_equal=True, runtime=provenance["runtime"],
                        accepted_natural_reused=True, fresh_natural_run=False, natural_trace_rows=natural_rows,
                        natural_trace_bytes_equal=True, configuration_equal_except_source_path=True),
        gh_first97_requests_byte_equivalent_values=True, H_clears_extra26byte_G_routing_control=True,
        G_extra_routing_section_hex="00000004000101000003", admission_routing=routing_table,
        new_simulations_executed_by_auditor=False, kit_or_model_edited=False,
        scope="Observed guarded prefix only, including rejected TX attempt. Matching random/TX order does not prove every internal callback/state equal or autonomous/6000-second performance parity.",
        input_hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs})
    (OUT / "gh_audit.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"cases":{key:{field:value for field,value in item.items() if field not in (
        "population_publications","noncontrolling_profile4_reported_nodes_differences")} for key,item in summaries.items()},
        "provenance":report["provenance"],"preflights":preflights},indent=2))


if __name__ == "__main__":
    main()
