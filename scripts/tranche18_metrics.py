#!/usr/bin/env python3
"""Passive, descriptive T18 cohort and retry-service observations.

Application identities and CONTROL identities have separate namespaces.  The
service observer supplies the application source; a relayed DATA frame's radio
source is deliberately not used to classify its cohort.  Timing is between
exported callbacks, never a reconstruction of hidden queue state.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path


NETWORK_EVENTS = {"network_enqueue", "network_submit", "network_custody_release",
                  "network_queue_reject"}
HOP_EVENTS = {"hop_admit", "hop_sent", "hop_retry", "hop_ack", "hop_dack",
              "hop_failed", "hop_dack_expired"}
INCOMING_EVENTS = {"hop_receive", "hop_no_route", "hop_custody_refused"}
TERMINALS = {"hop_ack", "hop_dack", "hop_failed"}
POLICY_EVENTS = {"mac_prepare", "mac_holdoff", "mac_state", "mac_transmit"}
DATA_EVENTS = NETWORK_EVENTS | HOP_EVENTS | INCOMING_EVENTS | {"mac_enqueue", "mac_queue_drop"}
SNAPSHOT_FIELDS = ("QueueDepth", "DataDepth", "AckDepth", "PendingData", "PendingThreshold",
                   "GlobalSpare", "NeighborOutstanding", "NeighborThreshold", "NeighborSpare",
                   "GlobalAllowed", "NeighborAllowed", "NsdpBefore", "NsdpAfter", "NsdpCount",
                   "NsdpLimit", "NwkQueueSize", "CapacityReleased", "HoldSeconds", "AckWaitSeconds")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, label, minimum=0):
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid {label}") from exc
    require(number.is_finite() and number == number.to_integral_value()
            and minimum <= number <= 2**64-1, f"Invalid {label}")
    return int(number)


def finite(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    require(math.isfinite(number), f"Nonfinite {label}")
    return number


def optional(value, label):
    if value is None or str(value).strip().lower() in ("", "nan"):
        return None
    return finite(value, label)


def logical(value, label):
    require(str(value).lower() in ("0", "1", "true", "false"), f"Invalid {label}")
    return str(value).lower() in ("1", "true")


def rows(path, fields):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and set(fields) <= set(reader.fieldnames),
                f"Missing columns in {path.name}: {sorted(set(fields)-set(reader.fieldnames or []))}")
        require(len(reader.fieldnames) == len(set(reader.fieldnames)), f"Duplicate columns in {path.name}")
        result = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in result),
            f"Malformed rows in {path.name}")
    return result


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    n = len(values)
    return {"count": n, "min": values[0], "median": (values[(n-1)//2]+values[n//2])/2,
            "mean": math.fsum(values)/n, "max": values[-1]}


def interval_summary(observations):
    """Keep censored lower bounds separate from completed waiting times."""
    observations = [r for r in observations if r is not None]
    return {"completed_seconds": distribution([r["seconds"] for r in observations if not r["right_censored"]]),
            "right_censored_count": sum(r["right_censored"] for r in observations),
            "censored_lower_bound_seconds": distribution([r["seconds"] for r in observations if r["right_censored"]])}


def evidence(row):
    result = {"service_observation_id": row["_id"], "time_s": row["_time"], "event": row["Event"]}
    snapshots = {field: optional(row.get(field), field) for field in SNAPSHOT_FIELDS}
    snapshots = {field: value for field, value in snapshots.items() if value is not None}
    if snapshots:
        result["exported_callback_snapshots"] = snapshots
    return result


def interval(start, end, label, stop=None):
    finish = end["_time"] if end is not None else stop
    require(finish is not None and math.isfinite(finish) and finish >= start["_time"],
            f"Negative or nonfinite {label} interval")
    return {"start": evidence(start), "end": evidence(end) if end is not None else None,
            "seconds": finish-start["_time"], "right_censored": end is None,
            "censor_time_s": finish if end is None else None}


def _applications(app_rows, admissions, duration):
    applications = {}
    for row in app_rows:
        packet = integer(row["PacketId"], "application packet", 1)
        require(packet not in applications, "Ambiguous duplicate application PacketId")
        row = dict(row, _packet=packet, _source=integer(row["SourceId"], "application source"),
                   _destination=integer(row["DestinationId"], "application destination"),
                   _generated=finite(row["GeneratedSeconds"], "application generation"))
        require(0 <= row["_generated"] <= duration, "Application generation outside horizon")
        require(row["Outcome"] in ("delivered", "dropped", "pending"), "Unknown application outcome")
        if row["Outcome"] == "delivered":
            arrival = finite(row["ReceivedSeconds"], "application arrival")
            latency = finite(row["LatencySeconds"], "application latency")
            require(row["_generated"] <= arrival <= duration and latency >= 0
                    and math.isclose(latency, arrival-row["_generated"], rel_tol=2e-12, abs_tol=1e-9),
                    "Negative/inconsistent application delivery interval")
            row["_latency"] = latency
        applications[packet] = row
    admitted = set()
    for ordinal, row in enumerate(admissions, 1):
        when = finite(row["TimeSeconds"], "admission time")
        source = integer(row["SourceId"], "admission source")
        require(0 <= when <= duration, "Admission outside horizon")
        if logical(row["Accepted"], "admission accepted"):
            packet = integer(row["PacketId"], "admitted packet", 1)
            require(packet in applications and packet not in admitted, "Missing/ambiguous admitted application identity")
            app = applications[packet]
            require(source == app["_source"] and when == app["_generated"],
                    "Admission application source/time mismatch")
            admitted.add(packet)
    require(admitted == set(applications), "Application admission identity coverage mismatch")
    return applications


def _services(service_rows, protocol, applications, window, duration):
    selected, policy = [], defaultdict(lambda: defaultdict(list))
    previous, previous_id = window[0], 0
    for row in service_rows:
        row = dict(row, _id=integer(row["ObservationId"], "service observation", 1),
                   _time=finite(row["TimeSeconds"], "service time"),
                   _node=integer(row["NodeId"], "service node"))
        require(row["_id"] > previous_id,
                "Duplicate/unordered service observation identity")
        previous_id = row["_id"]
        require(window[0] <= row["_time"] < window[1] and row["_time"] <= duration
                and row["_time"] >= previous,
                "Negative service time interval or row outside service window")
        previous = row["_time"]
        if row["Event"] in POLICY_EVENTS:
            policy[row["_node"]][row["Event"]].append(row["_time"])
        kind = row["FrameKind"]
        if kind not in ("APP", "DATA") or row["Stage"] != "protocol_callback":
            continue
        # An empty-frame callback may be represented as APP with no identity.
        # Lifecycle callbacks, however, must carry their actual application.
        available = logical(row["PacketIdAvailable"], "packet availability")
        if not available:
            require(row["Event"] not in NETWORK_EVENTS | HOP_EVENTS | INCOMING_EVENTS,
                    "Missing application identity on DATA lifecycle callback")
            continue
        packet = integer(row["PacketId"], "service application packet", 1)
        require(packet in applications, "Unknown DATA/APP application PacketId")
        source = optional(row["ApplicationSourceId"], "application source")
        require(source is not None and source == applications[packet]["_source"],
                "Missing or inconsistent ApplicationSourceId; FrameSourceId cannot classify cohorts")
        require(not row.get("ControlType"), "CONTROL identity mislabeled as application DATA")
        require(row["_time"] >= applications[packet]["_generated"], "Application callback precedes generation")
        row.update(_packet=packet, _source=int(source))
        peer = optional(row["PeerId"], "service peer")
        row["_peer"] = integer(peer, "service peer") if peer is not None else None
        if row["Event"] in HOP_EVENTS | INCOMING_EVENTS:
            require(kind == "DATA" and row["_peer"] is not None, "Missing DATA hop/peer identity")
            row["_sequence"] = integer(row["Sequence"], "DATA hop sequence")
        if row["Event"] in DATA_EVENTS:
            selected.append(row)
    # Bind local application callbacks to original protocol observations.
    def key(row, service=False):
        peer = row["_peer"] if service else optional(row["PeerId"], "protocol peer")
        sequence = integer(row["Sequence"], "protocol DATA sequence") if row["Event"] in HOP_EVENTS | INCOMING_EVENTS else None
        return (row["_time"] if service else finite(row["TimeSeconds"], "protocol time"),
                row["Event"], row["_node"] if service else integer(row["NodeId"], "protocol node"),
                row["_packet"] if service else integer(row["PacketId"], "protocol packet", 1),
                row["FrameKind"], peer, sequence)
    expected = Counter(key(r) for r in protocol if r["Event"] in DATA_EVENTS
                       and r["FrameKind"] in ("APP", "DATA")
                       and window[0] <= finite(r["TimeSeconds"], "protocol time") < window[1])
    require(Counter(key(r, True) for r in selected) == expected,
            "Application service callback identities differ from protocol trace")
    tx = defaultdict(list)
    for ordinal, row in enumerate(protocol, 1):
        if row["Event"] == "tx_start":
            when = finite(row["TimeSeconds"], "actual transmission time")
            require(0 <= when <= duration, "Actual transmission outside horizon")
            tx[(integer(row["NodeId"], "TX node"), when)].append(
                {"protocol_row": ordinal, "packet_or_aggregate_id": integer(row["PacketId"], "TX identity", 1),
                 "frame_kind": row["FrameKind"], "time_s": when})
    for row in selected:
        if row["Event"] == "hop_sent":
            matches = tx[(row["_node"], row["_time"])]
            require(len(matches) == 1, "Missing or ambiguous actual TX for hop_sent callback")
            row["_tx"] = matches[0]
    return selected, policy


def _policy_context(policy, node, wait):
    start = wait["start"]["time_s"]
    stop = wait["end"]["time_s"] if wait["end"] else wait["censor_time_s"]
    return {event: bisect_right(times, stop)-bisect_left(times, start)
            for event, times in sorted(policy[node].items())
            if bisect_right(times, stop) > bisect_left(times, start)}


def _hop_ledger(group, stop, policy):
    first = group[0]
    result = {"packet_id": first["_packet"], "application_source_id": first["_source"],
              "node_id": first["_node"], "peer_id": first["_peer"], "sequence": first["_sequence"],
              "events": [evidence(r) for r in group], "attempts": [], "retry_requests": [],
              "retry_service_waits": [], "initial_service_wait": None, "feedback_waits": [],
              "dack_hold": None, "terminal": None}
    last_sent = pending_retry = admitted = dack = None
    last_retry = None
    for row in group:
        event = row["Event"]
        if event == "hop_admit":
            require(admitted is None and not result["attempts"], "Ambiguous repeated DATA hop admission")
            admitted = row
        elif event == "hop_retry":
            require(result["terminal"] is None, "Retry follows terminal DATA callback")
            require(pending_retry is None, "Ambiguous overlapping retry requests")
            require(admitted is None or last_sent is not None,
                    "Retry for observed admission lacks an actual DATA transmission")
            retry_count = integer(row["ResendCount"], "DATA resend count", 1)
            require(last_retry is None or retry_count == last_retry+1, "Nonconsecutive DATA retry identity")
            last_retry, pending_retry = retry_count, row
            result["retry_requests"].append(dict(evidence(row), resend_count=retry_count))
        elif event == "hop_sent":
            require(result["terminal"] is None, "DATA transmission follows terminal callback")
            resend = integer(row["ResendCount"], "DATA TX resend count")
            if pending_retry is not None:
                require(resend == integer(pending_retry["ResendCount"], "retry count"),
                        "DATA TX has inconsistent retry identity")
                wait = interval(pending_retry, row, "retry service wait")
                wait["completion"] = "actual_hop_transmission"
                wait["node_policy_callback_counts"] = _policy_context(policy, row["_node"], wait)
                result["retry_service_waits"].append(wait)
                pending_retry = None
            elif result["attempts"]:
                raise ValueError("Repeated DATA transmission lacks unambiguous retry callback")
            elif admitted is not None:
                require(resend == 0, "First admitted DATA TX has missing retry identity")
                result["initial_service_wait"] = interval(admitted, row, "initial HOP service wait")
            result["attempts"].append(dict(evidence(row), resend_count=resend, actual_tx=row["_tx"]))
            last_sent = row
        elif event in TERMINALS:
            require(result["terminal"] is None, "Ambiguous duplicate DATA terminal callback")
            require(event == "hop_failed" or admitted is None or last_sent is not None,
                    "DATA ACK/DACK for observed admission lacks an actual transmission")
            result["terminal"] = dict(evidence(row), reason=row.get("Reason", ""))
            if last_sent is not None:
                result["feedback_waits"].append(dict(interval(last_sent, row, "DATA feedback wait"),
                    outcome=event, reference="most_recent_actual_hop_sent_callback"))
            if pending_retry is not None:
                wait = interval(pending_retry, row, "retry cancelled before service")
                wait["completion"] = "terminal_before_next_transmission"
                wait["node_policy_callback_counts"] = _policy_context(policy, row["_node"], wait)
                result["retry_service_waits"].append(wait)
                pending_retry = None
            if event == "hop_dack":
                dack = row
        elif event == "hop_dack_expired":
            require(result["dack_hold"] is None, "Ambiguous repeated DACK expiration")
            if dack is not None:
                result["dack_hold"] = interval(dack, row, "observed DACK hold")
    if pending_retry is not None:
        wait = interval(pending_retry, None, "pending retry service wait", stop)
        wait["completion"] = "observation_ended"
        wait["node_policy_callback_counts"] = _policy_context(policy, first["_node"], wait)
        result["retry_service_waits"].append(wait)
    if admitted is not None and not result["attempts"] and result["terminal"] is None:
        result["initial_service_wait"] = interval(admitted, None, "pending initial HOP service", stop)
    if last_sent is not None and result["terminal"] is None:
        result["feedback_waits"].append(dict(interval(last_sent, None, "pending DATA feedback", stop),
            outcome="observation_ended", reference="most_recent_actual_hop_sent_callback"))
    if dack is not None and result["dack_hold"] is None:
        result["dack_hold"] = interval(dack, None, "pending DACK hold", stop)
    result["left_censored"] = admitted is None
    return result


def _network_ledger(group, stop):
    episodes, current = [], None
    for row in group:
        event = row["Event"]
        if event == "network_enqueue":
            require(current is None, "Ambiguous overlapping NWK custody episodes")
            current = {"enqueue": row, "submit": None, "release": None}
        elif event == "network_submit":
            if current is None:
                current = {"enqueue": None, "submit": None, "release": None}
            require(current["submit"] is None, "Ambiguous repeated NWK submit")
            current["submit"] = row
        elif event == "network_custody_release":
            if current is None:
                current = {"enqueue": None, "submit": None, "release": None}
            current["release"] = row
            episodes.append(current)
            current = None
    if current is not None:
        episodes.append(current)
    result = []
    for episode in episodes:
        enq, submit, release = (episode[k] for k in ("enqueue", "submit", "release"))
        sent = next((r for r in group if submit is not None and r["Event"] == "hop_sent"
                     and r["_time"] >= submit["_time"]
                     and (release is None or r["_time"] <= release["_time"])), None)
        result.append({"enqueue": evidence(enq) if enq else None,
                       "submit": evidence(submit) if submit else None,
                       "custody_release": dict(evidence(release), reason=release.get("Reason", "")) if release else None,
                       "enqueue_to_submit": interval(enq, submit, "NWK enqueue to handoff", stop)
                           if enq and (submit or not release) else None,
                       "queue_observation_interval": interval(enq, submit or release, "NWK observed queue retention", stop) if enq else None,
                       "enqueue_to_release": interval(enq, release, "NWK custody retention", stop) if enq else None,
                       "submit_to_release": interval(submit, release, "NWK submitted custody retention", stop) if submit else None,
                       "submit_to_first_actual_hop_tx": interval(submit, sent, "NWK submit to actual HOP TX", stop)
                           if submit and (sent or not release) else None,
                       "queue_exit": "submitted" if submit else "released_without_submit" if release else "observation_ended",
                       "left_censored": enq is None})
    return result


def _feedback(decisions, actual, applications, window, duration):
    by_id, chosen, observations, seen = {}, [], [], set()
    for row in decisions:
        key = integer(row["DecisionId"], "feedback decision", 1)
        require(key not in by_id, "Ambiguous duplicate feedback DecisionId")
        row = dict(row, _id=key, _time=finite(row["TimeSeconds"], "feedback decision time"))
        require(0 <= row["_time"] <= duration, "Feedback decision outside horizon")
        require(row["FrameKind"] in ("ACK", "DACK"), "Invalid feedback frame kind")
        by_id[key] = row
        if logical(row["InputContextAvailable"], "feedback input context"):
            require(row["InputFrameKind"] in ("DATA", "CONTROL"), "Unknown feedback input namespace")
            if row["InputFrameKind"] == "DATA":
                packet = integer(row["InputPacketId"], "feedback triggering DATA packet", 1)
                require(packet in applications, "Missing feedback-triggering application identity")
                row["_packet"] = packet
                if (integer(row["NodeId"], "feedback node"), integer(row["PeerId"], "feedback peer")) == (5, 4):
                    chosen.append(row)
    chosen_ids = {r["_id"] for r in chosen}
    for row in actual:
        identity = integer(row["ObservationId"], "actual feedback identity", 1)
        require(identity not in seen, "Ambiguous duplicate actual-feedback ObservationId")
        seen.add(identity)
        decision_id = integer(row["DecisionId"], "actual feedback decision", 1)
        require(decision_id in by_id, "Actual feedback has missing decision identity")
        decision = by_id[decision_id]
        when = finite(row["TimeSeconds"], "actual feedback time")
        require(decision["_time"] <= when <= duration, "Negative feedback queue interval")
        require(all(row[k] == decision[k] for k in ("NodeId", "PeerId", "FrameKind")),
                "Actual feedback endpoints/kind differ from decision")
        if decision_id in chosen_ids and window[0] <= when < window[1]:
            observations.append({"actual_feedback_observation_id": identity, "decision_id": decision_id,
                "trigger_application_packet_id": decision["_packet"],
                "trigger_application_source_id": applications[decision["_packet"]]["_source"],
                "frame_kind": row["FrameKind"], "decision_time_s": decision["_time"],
                "actual_tx_time_s": when, "decision_to_ota_seconds": when-decision["_time"],
                "aggregate_id": integer(row["AggregateId"], "feedback aggregate", 1)})
    inside = [r for r in chosen if window[0] <= r["_time"] < window[1]]
    return {"receiver_node_id": 5, "peer_id": 4, "data_trigger_decision_count": len(inside),
            "decision_ids": [r["_id"] for r in inside],
            "decision_dispositions": dict(sorted(Counter(r["QueueDisposition"] for r in inside).items())),
            "actual_feedback_members": observations,
            "decision_to_ota_seconds": distribution([r["decision_to_ota_seconds"] for r in observations]),
            "scope": "InputPacketId identifies the DATA that triggered feedback generation, not every packet covered by a cumulative ACK/DACK bitmap. Repeated OTA members remain separate; an untransmitted decision is not asserted pending because it may have been replaced."}


def summarize_matlab_applications(directory, case):
    """Legacy summary keys with finite-stop outcomes and explicit bucket scope.

    Deliveries at H remain delivered, with full-stop packet-weighted latency.
    Mean populated-bucket latency reproduces benchmarkAggregates' [0,H)
    window and its existing 1e-12 quotient snap, including boundary exclusions.
    """
    directory = Path(directory)
    duration = finite(case["duration_s"], "summary duration")
    width = finite(case["bucket_width_s"], "summary bucket width")
    require(duration > 0 and width > 0 and abs(duration/width-round(duration/width)) <= 1e-10,
            "Invalid application observation window")
    bucket_count = round(duration/width)

    def bucket(when):
        quotient = when/width
        if abs(quotient-round(quotient)) <= 1e-12:
            quotient = round(quotient)
        require(0 <= quotient <= bucket_count, "Application bucket outside finite-stop window")
        return math.floor(quotient) if quotient < bucket_count else None

    app_rows = rows(directory/"analysis/applications.csv", ("PacketId", "SourceId", "DestinationId",
        "ApplicationBytes", "GeneratedSeconds", "ReceivedSeconds", "Outcome", "DropReason"))
    sent, flows, buckets, drops = {}, {}, defaultdict(list), Counter()
    delays, received_bytes, pending = [], 0, 0
    excluded_deliveries, excluded_sends = [], []
    for row in app_rows:
        packet = integer(row["PacketId"], "application packet", 1)
        require(packet not in sent, "Duplicate MATLAB application identity")
        when = finite(row["GeneratedSeconds"], "generation")
        require(0 <= when < duration, "Application generation must precede finite stop")
        source, destination = integer(row["SourceId"], "source"), integer(row["DestinationId"], "destination")
        size = integer(row["ApplicationBytes"], "payload")+7
        sent[packet] = (when, source, destination, size)
        if bucket(when) is None:
            excluded_sends.append({"packet_id": packet, "time_s": when, "network_bytes": size,
                                   "reason": "quotient_snapped_to_stop"})
        flow = flows.setdefault((source, destination), {"source": source, "destination": destination,
            "admitted": 0, "delivered": 0, "delivered_unique": 0, "delay_sum_s": 0.0, "delay_samples": 0})
        flow["admitted"] += 1
        if row["Outcome"] == "delivered":
            arrival = finite(row["ReceivedSeconds"], "delivery")
            require(when <= arrival <= duration, "Delivery outside finite stop or before generation")
            delay = arrival-when
            delays.append(delay)
            received_bytes += size
            flow["delivered"] += 1
            flow["delivered_unique"] += 1
            flow["delay_samples"] += 1
            flow["delay_sum_s"] += delay
            index = bucket(arrival)
            if index is None:
                excluded_deliveries.append({"packet_id": packet, "time_s": arrival, "network_bytes": size,
                    "latency_s": delay, "reason": "exact_stop" if arrival == duration else "quotient_snapped_to_stop"})
            else:
                buckets[index].append(delay)
        elif row["Outcome"] == "dropped":
            require(row["DropReason"], "Dropped application has no reason")
            drops[row["DropReason"]] += 1
        else:
            require(row["Outcome"] == "pending", "Unknown MATLAB application outcome")
            pending += 1
    for flow in flows.values():
        flow["mean_packet_latency_s"] = flow["delay_sum_s"]/flow["delay_samples"] if flow["delay_samples"] else None
        flow["unmatched_sends"] = flow["admitted"]-flow["delivered_unique"]
    attempts = sum(integer(row["Attempts"], "attempts") for row in
                   rows(directory/"raw/application_admission_statistics.csv", ("Attempts",)))
    require(attempts >= len(sent), "Admitted count exceeds attempts")
    require(len(delays)+sum(drops.values())+pending == len(sent), "MATLAB terminal application accounting mismatch")
    means = [math.fsum(values)/len(values) for values in buckets.values()]
    excluded_bytes = sum(r["network_bytes"] for r in excluded_deliveries)
    excluded_delay = math.fsum(r["latency_s"] for r in excluded_deliveries)
    result = {"simulator": "matlab", "case_id": case["case_id"], "base_case_id": case["base_case_id"],
        "seed": integer(case["seed"], "seed"), "duration_s": duration, "attempts": attempts,
        "admitted": len(sent), "admission_blocked": attempts-len(sent), "delivered": len(delays),
        "delivered_unique": len(delays), "duplicate_delivery_events": 0,
        "unmatched_sends": len(sent)-len(delays), "explicit_drops": sum(drops.values()), "pending": pending,
        "drop_reasons": dict(drops), "network_bytes_sent": sum(row[3] for row in sent.values()),
        "network_bytes_received": received_bytes, "delay_samples": len(delays), "delay_sum_s": math.fsum(delays),
        "mean_packet_latency_s": math.fsum(delays)/len(delays) if delays else None,
        "max_packet_latency_s": max(delays) if delays else None, "populated_delay_buckets": len(means),
        "bucket_latency_mean_sum_s": math.fsum(means),
        "mean_populated_bucket_latency_s": math.fsum(means)/len(means) if means else None,
        "received_packet_rate_over_full_window": len(delays)/duration,
        "flows": [flows[key] for key in sorted(flows)],
        "aggregation_boundary": {"finite_stop_outcome_window": "[0,H]", "generation_window": "[0,H)",
            "bucket_window": "[0,H)", "bucket_quotient_snap_tolerance": 1e-12,
            "excluded_delivery_count": len(excluded_deliveries), "excluded_delivery_network_bytes": excluded_bytes,
            "excluded_delivery_delay_sum_s": excluded_delay, "excluded_deliveries": excluded_deliveries,
            "excluded_send_count": len(excluded_sends), "excluded_sends": excluded_sends,
            "included_delivery_count": len(delays)-len(excluded_deliveries),
            "included_delivery_network_bytes": received_bytes-excluded_bytes,
            "included_delivery_delay_sum_s": math.fsum(delays)-excluded_delay,
            "scope": "Terminal delivery totals and packet-weighted latency include H. Populated-bucket latency follows the exported strict-stop aggregation and its quotient snap. Excluded endpoint deliveries are never reclassified as pending."}}
    json.dumps(result, allow_nan=False)
    return result


def analyze_case(directory, case):
    """Return JSON-compatible descriptive metrics; reject ambiguous local joins.

    The caller validates candidate inventories, whole-trace accounting, observer
    completion and configuration.  This function reads but never changes them.
    Required case field: duration_s.  service_window_s may override only with an
    identical window to the exported ServiceDiagnostics summary.
    """
    directory = Path(directory)
    raw = directory/"raw"
    duration = finite(case["duration_s"], "case duration")
    require(duration > 0, "Invalid case duration")
    summary = json.loads((raw/"summary.json").read_text(encoding="utf-8-sig"))
    observer = summary["ServiceDiagnostics"]
    window = [finite(observer["WindowStartSeconds"], "window start"),
              finite(observer["WindowEndSeconds"], "window end")]
    # Full T18 observers deliberately extend to H+1 so the end-exclusive
    # observer retains callbacks executed at the simulator's inclusive stop H.
    # The extra observer allowance never extends the actual simulation time.
    require(0 <= window[0] <= duration and window[0] <= window[1] <= duration+1,
            "Invalid service observation window")
    require("service_window_s" not in case or list(case["service_window_s"]) == window,
            "Case/service observation windows differ")
    apps = rows(directory/"analysis/applications.csv", ("PacketId", "SourceId", "DestinationId",
                "GeneratedSeconds", "ReceivedSeconds", "LatencySeconds", "Outcome"))
    admissions = rows(raw/"application_admission_trace.csv", ("TimeSeconds", "SourceId", "PacketId", "Accepted", "Reason"))
    applications = _applications(apps, admissions, duration)
    protocol = rows(raw/"protocol_trace.csv", ("TimeSeconds", "Event", "NodeId", "PeerId", "PacketId", "FrameKind", "Sequence"))
    service = rows(raw/"service_trace.csv", ("ObservationId", "TimeSeconds", "Stage", "Event", "NodeId", "PeerId",
        "FrameKind", "PacketId", "PacketIdAvailable", "ApplicationSourceId", "FrameSourceId", "Sequence", "ResendCount"))
    selected, policy = _services(service, protocol, applications, window, duration)
    decisions = rows(raw/"link_decisions.csv", ("DecisionId", "TimeSeconds", "NodeId", "PeerId", "FrameKind",
        "InputContextAvailable", "InputFrameKind", "InputPacketId", "QueueDisposition"))
    actual = rows(raw/"actual_feedback.csv", ("ObservationId", "DecisionId", "TimeSeconds", "NodeId", "PeerId", "FrameKind", "AggregateId"))
    grouped_hop, grouped_node5 = defaultdict(list), defaultdict(list)
    for row in selected:
        if row["Event"] in HOP_EVENTS:
            grouped_hop[(row["_node"], row["_peer"], row["_packet"], row["_sequence"])].append(row)
        if row["_node"] == 5:
            grouped_node5[row["_packet"]].append(row)
    observation_stop = min(window[1], duration)
    hops = [_hop_ledger(group, observation_stop, policy) for _, group in sorted(grouped_hop.items())]
    node5_ledger = []
    for packet, group in sorted(grouped_node5.items()):
        app = applications[packet]
        node5_ledger.append({"packet_id": packet, "application_source_id": app["_source"],
            "cohort": "local" if app["_source"] == 5 else "relay", "application_outcome": app["Outcome"],
            "events": [evidence(r) for r in group], "network_episodes": _network_ledger(group, observation_stop),
            "outgoing_hops": [h for h in hops if h["node_id"] == 5 and h["packet_id"] == packet]})
    by_source = []
    for source in sorted({a["_source"] for a in applications.values()} | {integer(r["SourceId"], "attempt source") for r in admissions}):
        source_apps = [a for a in applications.values() if a["_source"] == source]
        source_attempts = [(i, r) for i, r in enumerate(admissions, 1) if integer(r["SourceId"], "attempt source") == source]
        node5 = [r for r in node5_ledger if r["application_source_id"] == source]
        events = [r for r in selected if r["_source"] == source and r["_node"] == 5]
        source_hops = [h for h in hops if h["application_source_id"] == source and h["node_id"] == 5]
        nwk_episodes = [e for r in node5 for e in r["network_episodes"]]
        by_source.append({"application_source_id": source, "node5_cohort": "local" if source == 5 else "relay",
            "admission_attempt_count": len(source_attempts), "admission_csv_rows": [i for i, _ in source_attempts],
            "admission_reasons": dict(sorted(Counter(r["Reason"] for _, r in source_attempts).items())),
            "generated_application_count": len(source_apps), "outcomes": dict(sorted(Counter(a["Outcome"] for a in source_apps).items())),
            "delivery_latency_seconds": distribution([a["_latency"] for a in source_apps if a["Outcome"] == "delivered"]),
            "end_pending_ages": [{"packet_id": a["_packet"], "age_seconds": duration-a["_generated"],
                                  "right_censored": True, "censor_time_s": duration}
                                 for a in source_apps if a["Outcome"] == "pending"],
            "node5_observed_application_count": len(node5), "node5_packet_ids": [r["packet_id"] for r in node5],
            "node5_event_counts": dict(sorted(Counter(r["Event"] for r in events).items())),
            "node5_service_observation_ids": [r["_id"] for r in events],
            "node5_observed_service": {
                "nwk_enqueue_to_submit": interval_summary([e["enqueue_to_submit"] for e in nwk_episodes]),
                "nwk_submit_to_first_actual_hop_tx": interval_summary([e["submit_to_first_actual_hop_tx"] for e in nwk_episodes]),
                "nwk_custody_retention": interval_summary([e["enqueue_to_release"] for e in nwk_episodes]),
                "initial_hop_service_wait": interval_summary([h["initial_service_wait"] for h in source_hops]),
                "retry_to_next_actual_hop_tx": interval_summary([w for h in source_hops for w in h["retry_service_waits"]
                    if w["completion"] in ("actual_hop_transmission", "observation_ended")]),
                "retry_requests_terminated_before_tx": sum(w["completion"] == "terminal_before_next_transmission"
                    for h in source_hops for w in h["retry_service_waits"]),
                "actual_hop_tx_to_terminal_callback": interval_summary([w for h in source_hops for w in h["feedback_waits"]]),
                "actual_hop_attempts": sum(len(h["attempts"]) for h in source_hops),
                "hop_terminal_callbacks": dict(sorted(Counter(h["terminal"]["event"] for h in source_hops if h["terminal"]).items()))}})
    link_hops = [h for h in hops if (h["node_id"], h["peer_id"]) == (4, 5)]
    result = {"schema": "csr-tranche18-cohort-service-v1", "case_id": case.get("case_id"),
        "duration_s": duration, "service_window_s": window, "service_window_boundary": "start_inclusive_end_exclusive",
        "observation_censor_time_s": observation_stop,
        "source_cohorts": by_source, "node5_application_ledger": node5_ledger,
        "hop_4_to_5": {"data_hop_episode_count": len(link_hops),
            "actual_data_attempt_count": sum(len(h["attempts"]) for h in link_hops),
            "retry_request_count": sum(len(h["retry_requests"]) for h in link_hops),
            "actual_retry_attempt_count": sum(a["resend_count"] > 0 for h in link_hops for a in h["attempts"]),
            "terminal_callbacks": dict(sorted(Counter(h["terminal"]["event"] for h in link_hops if h["terminal"]).items())),
            "episodes": link_hops},
        "feedback_5_to_4": _feedback(decisions, actual, applications, window, duration),
        "limitations": [
            "All metrics are descriptive; no numerical parity threshold or causal bottleneck classification is applied.",
            "ApplicationSourceId defines cohorts; DATA and CONTROL packet IDs occupy separate namespaces.",
            "hop_sent joins the unique same-node actual tx_start at that timestamp; callback identities do not independently expose aggregate member lists.",
            "NWK custody release may precede the corresponding HOP terminal callback at the same simulation timestamp. Event order is retained; ACK/DACK-to-release latency is not fabricated.",
            "Retry-to-transmission intervals include observed MAC service delays and the accepted retry-policy pause while queued. Concurrent MAC policy callbacks are context, not proof of the delay's cause.",
            "No instantaneous hidden queue state or unexported capacity-release instant is reconstructed. A right-censored interval ends at the earlier of service-window end and the simulation horizon. An observer window extending to H+1 captures callbacks at H and does not add simulated waiting time.",
            "Exported callback snapshots retain each event's documented boundary. NSDP, admission and capacity snapshots are not treated as continuously known state, and DACK custody release is distinct from later admission-capacity release.",
            "Delivery and admission summaries cover the whole run; service callback counts and ledgers cover the declared observation window."
        ]}
    # This also rejects accidental nonfinite values before the caller serializes.
    json.dumps(result, allow_nan=False)
    return result
