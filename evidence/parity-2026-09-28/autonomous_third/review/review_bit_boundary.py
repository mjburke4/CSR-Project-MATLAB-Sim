#!/usr/bin/env python3
"""Review captured PHY bit arithmetic; does not run or change either simulator."""
from pathlib import Path
import csv
import hashlib
import json
import math
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / "autonomous_third/data/B_common"
OBS = ROOT / "autonomous/native_capture/run/observations.tsv"
RATE = 4 / .000510


def sample_source_binomial(n, probability, uniform):
    """Independent Python transcription of the existing inverse-CDF formula."""
    if n == 0 or probability <= 0:
        return 0
    if probability >= 1:
        return n
    p = min(probability, 1 - probability)
    target = min(uniform, 1 - 2 ** -53)
    cumulative = 0.0
    errors = n
    factorial = math.lgamma(n + 1)
    for candidate in range(n + 1):
        log_mass = (factorial - math.lgamma(candidate + 1)
                    - math.lgamma(n - candidate + 1)
                    + candidate * math.log(p)
                    + (n - candidate) * math.log(1 - p))
        cumulative += math.exp(log_mass)
        if cumulative >= target:
            errors = candidate
            break
    return n - errors if probability > .5 else errors


def main():
    requests = [json.loads(line) for line in (DATA / "random_requests.jsonl").read_text().splitlines()]
    events = [json.loads(line) for line in (DATA / "ordered_events.jsonl").read_text().splitlines()]
    native = list(csv.DictReader(OBS.open(), delimiter="\t"))
    samples = [r for r in native if r["event"] == "rx_binomial_draw"]
    fixture = list(csv.DictReader((ROOT / "autonomous/native_capture/fixture/random_draws.csv").open()))
    tx_rows = list(csv.DictReader((ROOT / "autonomous/native_capture/fixture/tx_signatures.csv").open()))
    rate_by_tx = {row["tx_id"]: int(row["rate_kbps"]) for row in tx_rows}
    assert all(rate_by_tx[row["tx_id"]] == 8 for row in samples)
    fixture_by_key = {(int(r["node"]), r["purpose"], int(r["ordinal"])): r for r in fixture}
    request_keys = set()
    for actual in requests:
        key = (actual["node"], actual["purpose"], actual["ordinal"])
        request_keys.add(key)
        wanted = fixture_by_key[key]
        assert actual["expected"]["event_order"] == int(wanted["event_order"])
        assert actual["expected"]["value"] == float(wanted["value"])
    assert [r["context_matched"] for r in requests] == [True] * 6 + [False]
    tx = [r for r in events if r["kind"] == "physical_tx_context"]
    assert len(tx) == 1 and not tx[0]["details"]["mismatches"]
    divergence = json.loads((DATA / "first_divergence.json").read_text())
    assert divergence["fields"] == ["bits"]
    assert divergence["actual"]["bits"] == 184 and divergence["expected"]["bits"] == 183
    native_cutoff = int(divergence["expected"]["time_ns"])
    native_before_stop = [row for row in fixture if int(row["time_ns"]) <= native_cutoff]
    indexed_requests = {(row["node"], row["purpose"], row["ordinal"]): (index, row)
                        for index, row in enumerate(requests, 1)}
    global_schedule = []
    for index, row in enumerate(native_before_stop, 1):
        match = indexed_requests.get((int(row["node"]), row["purpose"], int(row["ordinal"])))
        global_schedule.append({"native_request_index": index, "native_event_order": int(row["event_order"]),
                                "native_time_ns": int(row["time_ns"]), "node": int(row["node"]),
                                "purpose": row["purpose"], "ordinal": int(row["ordinal"]),
                                "matlab_request_index": match[0] if match else None,
                                "matlab_time_s": match[1]["time_s"] if match else None,
                                "context_matched": match[1]["context_matched"] if match else None,
                                "status": ("matched_request" if match[1]["context_matched"] else "guard_rejected")
                                if match else "not_requested_by_matlab_before_stop"})
    with (OUT / "global_draw_schedule_comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(global_schedule[0]))
        writer.writeheader()
        writer.writerows(global_schedule)
    prior_native_unrequested = [r for r in fixture
                               if int(r["event_order"]) < divergence["expected"]["event_order"]
                               and (int(r["node"]), r["purpose"], int(r["ordinal"])) not in request_keys]
    assert [(r["node"], r["purpose"], r["ordinal"]) for r in prior_native_unrequested] == [
        ("3", "mac_slot", "1"), ("5", "mac_slot", "1")]
    early_mac = []
    for node in (3, 5):
        matlab_pending = next(r for r in events if r["kind"] == "mac_boundary" and r["node"] == node
                              and r["time_s"] > 11.5 and r["details"]["Cause"] == "schedulePending_after")
        native_pending = next(r for r in native if r["node"] == str(node)
                              and 11500300000 < int(r["time_ns"]) < 11500323000
                              and r["event"] == "receiver_boundary"
                              and (d := json.loads(r["detail_json"]))["cause"] == "CsrNetDevice::ReturnToSearchAfterReceive"
                              and d["phase"] == "exit")
        native_state = json.loads(native_pending["detail_json"])
        assert native_state["preparation_active"] == "1"
        assert not matlab_pending["details"]["PreparationActive"]
        assert matlab_pending["details"]["DataQueueCount"] == 1
        early_mac.append({"node": node, "native_after_receive": native_pending,
                          "matlab_after_control_admission": matlab_pending})
    for key, actual in divergence["actual"].items():
        if key.endswith("_ns"):
            assert actual == divergence["expected"][key]
    node4_end = next(r for r in events if r["kind"] == "phy_boundary" and r["node"] == 4
                     and r["details"]["Cause"] == "endSignal_before")
    native_prior = next(r for r in native if r["event"] == "rx_prior_stage" and r["node"] == "4"
                        and r["tx_id"] == "4294967297")
    native_prior_detail = json.loads(native_prior["detail_json"])
    assert node4_end["details"]["State"] == "Idle"
    assert node4_end["details"]["TrackedId"] == 0
    assert native_prior["state_before"] == "idle"
    assert native_prior_detail["rejected"] == native_prior_detail["missed_by_state"] == "1"
    first = divergence["expected"]
    p, u = first["probability"], first["value"]
    first_errors = {str(n): sample_source_binomial(n, p, u) for n in (183, 184)}
    header = requests[-2]
    header_errors = sample_source_binomial(header["actual"]["bits"], p, header["value"])
    assert first_errors == {"183": 2, "184": 2} and header_errors == 2
    counts = Counter()
    changed = []
    inventory = []
    for row in samples:
        detail = json.loads(row["detail_json"])
        begin, end = float(detail["component_start_sec"]), float(detail["component_end_sec"])
        product = max(0.0, end - begin) * RATE
        bits = int(detail["bits"])
        assert math.floor(product) == bits
        nearest = round(product)
        near_boundary = abs(product - nearest) <= RATE * 1e-9
        lower_side = near_boundary and bits != nearest
        n_errors = alternative_errors = None
        if lower_side:
            counts[detail["component"]] += 1
            probability, uniform = float(detail["probability"]), float(detail["draw"])
            n_errors = sample_source_binomial(bits, probability, uniform)
            alternative_errors = sample_source_binomial(nearest, probability, uniform)
            if n_errors != alternative_errors:
                changed.append(dict(time_ns=int(row["time_ns"]), node=int(row["node"]),
                                    tx_id=int(row["tx_id"]), component=detail["component"],
                                    native_bits=bits, sensitivity_bits=nearest,
                                    native_sample=n_errors, sensitivity_sample=alternative_errors,
                                    probability=probability, uniform=uniform))
        inventory.append(dict(time_ns=int(row["time_ns"]), event_order=int(row["event_order"]),
                              node=int(row["node"]), tx_id=int(row["tx_id"]),
                              component=detail["component"], native_bits=bits,
                              raw_duration_product=product,
                              distance_to_integer_bits=abs(product - nearest),
                              within_one_ns_of_integer=near_boundary,
                              lower_side_candidate=lower_side,
                              native_sample=n_errors, sensitivity_sample=alternative_errors))
    with (OUT / "phy_bit_boundary_inventory.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(inventory[0]))
        writer.writeheader()
        writer.writerows(inventory)
    result = {
        "schema": "csr-phy-bit-boundary-independent-review-v1",
        "matched_physical_transmissions": 1,
        "matched_random_samples": 6,
        "matched_sample_purposes": dict(Counter(r["purpose"] for r in requests if r["context_matched"])),
        "matched_samples_are_global_native_prefix": False,
        "global_native_requests_through_stop": len(native_before_stop),
        "global_matlab_requests_through_stop": len(requests),
        "global_draw_schedule_comparison": global_schedule,
        "earlier_native_requests_not_yet_requested_in_matlab": prior_native_unrequested,
        "earlier_post_receive_mac_preparation_difference": early_mac,
        "first_rejected_request_number": 7,
        "first_rejected_request_component": "payload",
        "first_mismatch_rounded_ns_fields_equal": True,
        "first_mismatch_bits": {"matlab": 184, "native": 183},
        "first_packet_same_uniform_payload_errors": first_errors,
        "first_packet_header_errors": header_errors,
        "first_packet_total_errors_under_either_count": 4,
        "first_packet_native_prior_stage": native_prior,
        "first_packet_matlab_receiver_state": node4_end,
        "first_packet_delivery_effect_demonstrated": False,
        "first_packet_prior_gate_already_rejected": True,
        "native_fixture_draw_rows": len(samples),
        "native_component_product_floors_reproduced": len(inventory),
        "native_components_within_one_ns_of_integer_bits": sum(r["within_one_ns_of_integer"] for r in inventory),
        "native_lower_side_candidates": sum(counts.values()),
        "native_lower_side_candidates_by_component": dict(counts),
        "same_uniform_adjacent_count_sensitivity_changes": changed,
        "sensitivity_interpretation": "Counterfactual arithmetic only: compare native n with nearest integer n+1 for products within one callback tick of that integer. This neither predicts actual MATLAB counts nor recommends rounding or relaxed matching.",
        "new_simulations_executed": False,
        "model_files_edited": False,
        "source_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [DATA / "random_requests.jsonl", DATA / "first_divergence.json", OBS]},
    }
    (OUT / "bit_boundary_review.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in (
        "first_packet_native_prior_stage", "first_packet_matlab_receiver_state", "source_hashes")}, indent=2))


if __name__ == "__main__":
    main()
