#!/usr/bin/env python3
"""Independent raw service-trace checks used by the T9 return reviewer.

The ns-3 and MATLAB observations occur at different documented boundaries.
Identity joins below are within a simulator; they do not equate packet IDs or
internal callback counts across simulators.
"""
from __future__ import annotations

from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import analyze_tranche8_return as t8
import tranche8_metrics as metrics

require, integer, finite = sweep.require, sweep.integer, sweep.finite
PIN = t7.PIN
DIRECT_EVENTS = {"app_generate", "app_receive", "app_drop", "relay_accept", "network_policy_drop",
                 "hop_delivery_unconfirmed", "tx_start", "link_drop", "fault_drop", "link_enable",
                 "link_disable", "discovery_request"}
DETAIL_FIELDS = ("PreparationActive", "RemovedCount", "ReservationSlot", "ReservationCounter", "QueueDepth", "DataDepth", "AckDepth", "PendingData",
                 "PendingThreshold", "GlobalSpare", "NeighborOutstanding", "NeighborThreshold", "NeighborSpare",
                 "GlobalAllowed", "NeighborAllowed", "NsdpBefore", "NsdpAfter", "NsdpCount", "NsdpLimit", "NwkQueueSize",
                 "ResendCount", "AckWaitSeconds", "DurationSeconds", "HoldSeconds", "FirstReception", "LocalDelivery",
                 "IsDack", "CapacityReleased", "FlowIndex", "AttemptIndex", "Accepted")
BOOL_DETAILS = {"PreparationActive", "GlobalAllowed", "NeighborAllowed", "FirstReception", "LocalDelivery", "IsDack", "CapacityReleased", "Accepted"}
ADMISSION_BOOL_FIELDS = {"Accepted", "DiscoveryActive", "TopologyKnown", "GatewayCached",
                         "RouteCheckPerformed", "RouteAvailable"}
NATIVE_FIELDS = ("schema,event_index,time_s,event,node,peer,packet_type,src,dst,sequence,"
                 "success,reason,reservation_slot,reservation_counter,detail,packet_uid,"
                 "prior_packet_uid,decision_id,prior_decision_id,mac_state,preparation_active,"
                 "holdoff_over,sync_present,ack_queue,data_queue,tx_in_progress,rate_kbps,"
                 "size_bytes,rx_power_dbm,pathloss_db,snr_db,jsr_db,header_errors,payload_errors,"
                 "total_errors,statistic,value").split(",")


def in_window(value, plan):
    when = finite(value, "service time")
    return plan["service_window_s"][0] <= when < plan["service_window_s"][1]


def scalar(value):
    return type(value) in (int, float, bool) and math.isfinite(value)


def equal_number(left, right):
    return left == right or (left is not None and right is not None
                             and math.isclose(left, right, rel_tol=2e-12, abs_tol=1e-9))


def exact_integer(value, label):
    value = integer(value, label)
    require(value <= 2**64-1, f"{label} exceeds uint64 range")
    return value


def load_details(row):
    try:
        details = json.loads(row["DetailsJSON"])
    except (ValueError, TypeError) as failure:
        raise ValueError("Invalid service DetailsJSON") from failure
    require(isinstance(details, dict), "Service DetailsJSON must preserve an object")
    for field in DETAIL_FIELDS:
        supplied = details.get(field)
        expected = float(supplied) if scalar(supplied) else None
        actual = metrics.optional_number(row.get(field), field)
        require(equal_number(actual, expected), f"Service typed detail {field} differs from DetailsJSON")
        if field in BOOL_DETAILS and actual is not None:
            require(actual in (0, 1), f"Service boolean detail {field} is invalid")
    supplied = details.get("Segments")
    require(equal_number(metrics.optional_number(row.get("SegmentCount"), "SegmentCount"),
                         float(supplied) if scalar(supplied) else None), "Service segment count differs from DetailsJSON")
    for field in ("State", "Reason"):
        require(row.get(field) == details.get(field, ""), f"Service {field} differs from DetailsJSON")
    return details


def verify_matlab_rows(rows, protocol, admissions, feedback, summary, plan):
    """Match every service row to independently retained legacy observations."""
    require(summary.get("SchemaVersion") == "csr-matlab-ack-service-diagnostics-v1"
            and summary.get("Enabled") is True and summary.get("Complete") is True
            and summary.get("InheritedFeedbackComplete") is True and summary.get("Passive") is True
            and summary.get("MaxRecords") == plan["service_max_records"]
            and [summary.get("WindowStartSeconds"), summary.get("WindowEndSeconds")] == plan["service_window_s"]
            and summary.get("WindowBoundary") == "start_inclusive_end_exclusive",
            "MATLAB service observer schema/window/completion mismatch")
    for field in ("OmittedServiceRecords", "ScheduledEvents", "RandomDraws", "CancellationPairErrors"):
        require(integer(summary.get(field), field) == 0, f"Incomplete or perturbing service observer: {field}")
    require(len(rows) == integer(summary.get("ServiceEventCount"), "service events")
            == integer(summary.get("CapturedServiceRecords"), "captured service records")
            and len(rows) <= plan["service_max_records"], "MATLAB service row count mismatch")
    callbacks = [row for row in protocol if row["Event"] not in DIRECT_EVENTS]
    expected_callbacks = [row for row in callbacks if in_window(row["TimeSeconds"], plan)]
    expected_admissions = [row for row in admissions if in_window(row["TimeSeconds"], plan)]
    expected_outside = len(callbacks)-len(expected_callbacks)+len(admissions)-len(expected_admissions)
    require(integer(summary.get("OutOfWindowServiceEvents"), "outside service window") == expected_outside,
            "Service out-of-window count differs from independent callbacks/admissions")
    cancellations = [row for row in rows if row["Stage"] == "cancellation_callback"]
    require(len(rows) == len(expected_callbacks)+len(expected_admissions)+len(cancellations),
            "Service trace omitted or duplicated original callbacks/admission attempts")
    cancellation_result = verify_matlab_cancellations(cancellations, rows, summary)
    callback_index = admission_index = 0
    previous = plan["service_window_s"][0]
    observed_feedback, expected_feedback = Counter(), Counter()
    attempt_positions, first_callback_positions = {}, {}
    for index, row in enumerate(rows, 1):
        when = finite(row["TimeSeconds"], "service time")
        require(exact_integer(row["ObservationId"], "service identity") == index
                and in_window(when, plan) and when >= previous, "Invalid service identity/order/window")
        previous = when
        require(row["Stage"] in ("protocol_callback", "application_attempt", "cancellation_callback"), "Unknown MATLAB service stage")
        node = integer(row["NodeId"], "service node")
        packet = exact_integer(row["PacketId"], "service packet")
        available = sweep.boolean(row["PacketIdAvailable"], "packet available")
        require(available or packet == 0, "Unavailable service packet identity was fabricated")
        require(exact_integer(row["AggregateId"], "service aggregate") == 0
                and not sweep.boolean(row["AggregateIdAvailable"], "aggregate available"),
                "MAC callback cannot supply an OTA aggregate identity")
        details = load_details(row)
        for field in ("FrameDestinationsJSON", "HopSequencesJSON"):
            values = json.loads(row[field])
            require(isinstance(values, (int, list)), "Invalid copied grouped-frame identity")
            for value in values if isinstance(values, list) else [values]:
                integer(value, field)
        feedback_available = sweep.boolean(row["FeedbackIdentityAvailable"], "feedback identity available")
        for bitmap in ("AckBitmap", "DackBitmap"):
            value = exact_integer(row[bitmap], bitmap)
            require(feedback_available or value == 0, "Unavailable feedback bitmap was fabricated")
        if row["Stage"] == "cancellation_callback":
            continue
        if row["Stage"] == "application_attempt":
            require(admission_index < len(expected_admissions), "Unexpected extra application service observation")
            expected = expected_admissions[admission_index]
            admission_index += 1
            require(row["Event"] == "application_attempt" and row["Layer"] == "APP" and row["FrameKind"] == "APP"
                    and not feedback_available, "Application service stage/identity mismatch")
            require(set(details) == set(expected), "Service admission JSON omitted original admission fields")
            for field, value in expected.items():
                if field == "Reason":
                    require(details[field] == value, "Service admission reason differs from original attempt")
                elif field in ADMISSION_BOOL_FIELDS:
                    # jsonencode preserves MATLAB logical values as true/false;
                    # writetable represents the same admission fields as 1/0.
                    # Restrict this conversion to the declared logical fields.
                    observed = details[field]
                    require(type(observed) in (bool, int, float) and observed in (0, 1),
                            f"Service admission {field}: expected Boolean or numeric 0/1")
                    require(bool(observed) == sweep.boolean(value, field),
                            "Service admission logical value differs from original attempt")
                else:
                    require(equal_number(finite(details[field], field), finite(value, field)),
                            "Service admission identity/value differs from original attempt")
            require(node == integer(expected["SourceId"], "admission source")
                    and integer(row["PeerId"], "admission peer") == integer(expected["DestinationId"], "destination")
                    and packet == exact_integer(expected["PacketId"], "original admission packet")
                    and available == (sweep.boolean(expected["Accepted"], "accepted") and packet != 0)
                    and when == finite(expected["TimeSeconds"], "attempt time")
                    and integer(row["ApplicationSourceId"], "application source") == node
                    and integer(row["ApplicationDestinationId"], "application destination") == integer(expected["DestinationId"], "destination"),
                    "Service admission typed identity differs from original attempt")
            if available:
                attempt_positions[packet] = (index, when)
        else:
            require(callback_index < len(expected_callbacks), "Unexpected extra protocol service observation")
            expected = expected_callbacks[callback_index]
            callback_index += 1
            kind = row["FrameKind"] or "APP"
            layer = "MAC" if row["Event"].startswith("mac_") else "HOP" if row["Event"].startswith("hop_") else "NWK"
            require(row["Event"] == expected["Event"] and row["Layer"] == layer
                    and when == finite(expected["TimeSeconds"], "original callback time")
                    and node == integer(expected["NodeId"], "original callback node")
                    and kind == expected["FrameKind"] and row["Reason"] == expected["Reason"],
                    "Service callback identity/order differs from original protocol trace")
            peer = metrics.optional_number(row["PeerId"], "peer")
            # Legacy empty-frame callbacks use numeric zero. Grouped controls
            # can instead have vector destinations, which lack scalar peers.
            old_peer = metrics.optional_number(expected["PeerId"], "legacy peer")
            if peer is not None:
                require(peer == old_peer, "Service callback peer differs from original protocol trace")
            elif row["FrameDestinationsJSON"] == "[]":
                require(old_peer in (0, None), "Service callback omitted an available scalar peer")
            if kind == "AGGREGATE":
                require(not available and not row["ControlType"] and not feedback_available,
                        "Aggregate callback invented a member/OTA identity")
            else:
                require(not available or packet == exact_integer(expected["PacketId"], "original callback packet"),
                        "Service callback packet identity differs from original protocol trace")
                require(row["ControlType"] == expected["ControlType"], "Service callback control type mismatch")
            if available and kind in ("APP", "DATA"):
                first_callback_positions.setdefault(packet, (index, when))
            require(feedback_available == (kind in ("ACK", "DACK")), "Service feedback identity availability mismatch")
            if feedback_available:
                require(not available and row["HasAckWindow"] in ("0", "1"), "Feedback service identity is malformed")
                action = {"mac_enqueue": "enqueued", "mac_ack_replace": "replaced", "mac_queue_drop": "rejected"}.get(row["Event"])
                if action:
                    identity = (when, node, integer(row["PeerId"], "feedback peer"), kind,
                                exact_integer(row["Sequence"], "feedback sequence"),
                                sweep.boolean(row["HasAckWindow"], "ACK window"),
                                exact_integer(row["AckBitmap"], "ACK bitmap"), exact_integer(row["DackBitmap"], "DACK bitmap"), action)
                    observed_feedback[identity] += 1
    require(callback_index == len(expected_callbacks) and admission_index == len(expected_admissions),
            "Service stage coverage differs from original observations")
    for packet, (position, when) in attempt_positions.items():
        if packet in first_callback_positions:
            later, callback_time = first_callback_positions[packet]
            require(position < later and when <= callback_time, "Service callback precedes its completed admission decision")
    for row in feedback:
        if row["QueueDisposition"] not in ("enqueued", "replaced", "rejected") or not in_window(row["TimeSeconds"], plan):
            continue
        identity = (finite(row["TimeSeconds"], "decision time"), integer(row["NodeId"], "decision node"),
                    integer(row["PeerId"], "decision peer"), row["FrameKind"], integer(row["Sequence"], "decision sequence"),
                    sweep.boolean(row["HasAckWindow"], "ACK window"), exact_integer(row["AckBitmap"], "ACK bitmap"),
                    exact_integer(row["DackBitmap"], "DACK bitmap"), row["QueueDisposition"])
        expected_feedback[identity] += 1
    require(observed_feedback == expected_feedback, "Service feedback callback identity differs from inherited decisions")
    by_source = []
    for node in sorted({integer(row["SourceId"], "source") for row in expected_admissions}):
        attempts = [row for row in expected_admissions if integer(row["SourceId"], "source") == node]
        by_source.append({"source": node, "attempts": len(attempts),
                          "admitted": sum(sweep.boolean(row["Accepted"], "accepted") for row in attempts),
                          "admission_reasons": dict(Counter(row["Reason"] for row in attempts))})
    return {"rows": len(rows), "protocol_callbacks_joined": len(expected_callbacks),
            "application_attempts_joined": len(expected_admissions), "out_of_window_events_verified": expected_outside,
            "feedback_queue_callbacks_joined": sum(observed_feedback.values()),
            "event_counts": dict(sorted(Counter(row["Event"] for row in rows).items())),
            "window_s": plan["service_window_s"], "stop_endpoint": "exclusive", "flows": by_source,
            "cancellations": cancellation_result,
            "scope": "Every callback and admission attempt is joined to original observations; opaque callback details retain their documented observation boundary."}


def verify_matlab_service(directory, case, plan):
    raw = directory/"raw"
    summary = sweep.json_object(raw/"summary.json").get("ServiceDiagnostics", {})
    manifest = sweep.json_object(directory/"benchmark_manifest.json")
    require(manifest.get("service_observer_enabled") is True and manifest.get("service_diagnostics") == summary
            and manifest.get("service_reference_directory") == case["service_reference_directory"],
            "MATLAB service observer manifest/summary/reference binding mismatch")
    rows = list(t7.csv_records(raw/"service_trace.csv", ("ObservationId", "TimeSeconds", "Stage", "Event", "DetailsJSON")))
    protocol = list(t7.csv_records(raw/"protocol_trace.csv"))
    admissions = list(t7.csv_records(raw/"application_admission_trace.csv"))
    feedback = list(t7.csv_records(raw/"link_decisions.csv"))
    return verify_matlab_rows(rows, protocol, admissions, feedback, summary, plan)


def verify_matlab_cancellations(cancellations, rows, summary):
    require(len(cancellations) == integer(summary.get("CancellationSnapshotCount"), "cancellation snapshots")
            and integer(summary.get("AdditionalStateReads"), "additional state reads") == 6*len(cancellations)
            and summary.get("PendingCancellationPair") is False and summary.get("CancellationPairsComplete") is True,
            "Cancellation snapshot/read-count/completion mismatch")
    require(len(cancellations) % 2 == 0
            and integer(summary.get("CancellationBeforeCount"), "before cancellations") == len(cancellations)//2
            and integer(summary.get("CancellationAfterCount"), "after cancellations") == len(cancellations)//2,
            "Cancellation before/after coverage mismatch")
    selectors = Counter()
    removed_total = positive_pairs = 0
    for before, after in zip(cancellations[::2], cancellations[1::2]):
        require(before["Event"] in ("mac_cancel_before", "mac_control_cancel_before")
                and after["Event"] == before["Event"].replace("_before", "_after")
                and integer(after["ObservationId"], "after cancellation identity") == integer(before["ObservationId"], "before cancellation identity")+1,
                "Cancellation callbacks are not adjacent matching before/after pairs")
        for row in (before, after):
            details = load_details(row)
            require(row["Layer"] == "MAC" and row["FrameKind"] == ""
                    and not sweep.boolean(row["PacketIdAvailable"], "cancellation packet availability")
                    and not sweep.boolean(row["FeedbackIdentityAvailable"], "cancellation feedback availability"),
                    "Cancellation selector was mislabeled as a packet identity")
            require(set(details) == {"State", "PreparationActive", "ReservationSlot", "ReservationCounter", "DataDepth", "AckDepth",
                                     "PeerId", "Sequence", "ControlType", "RemovedCount"},
                    "Cancellation snapshot omitted or invented supplied scalar/selector fields")
            require(finite(row["PeerId"], "cancellation peer") == finite(details["PeerId"], "cancellation peer")
                    and equal_number(metrics.optional_number(row["Sequence"], "cancellation sequence"), details["Sequence"])
                    and row["ControlType"] == details["ControlType"], "Cancellation typed selectors differ from supplied snapshot")
        require(all(before[field] == after[field] for field in ("TimeSeconds", "NodeId", "PeerId", "Sequence", "ControlType")),
                "Cancellation before/after selector or time differs")
        require(metrics.optional_number(before["RemovedCount"], "before removed count") is None,
                "Before cancellation cannot report an eventual removal count")
        removed = integer(after["RemovedCount"], "removed queue entries")
        require(integer(before["DataDepth"], "before data depth")-integer(after["DataDepth"], "after data depth") == removed
                and before["AckDepth"] == after["AckDepth"], "Cancellation removed-count/queue-depth mismatch")
        require(all(before[field] == after[field] for field in ("State", "PreparationActive", "ReservationSlot", "ReservationCounter")),
                "Cancellation unexpectedly changed prepared reservation state")
        removed_total += removed
        positive_pairs += removed > 0
        if before["Event"] == "mac_cancel_before":
            require(not before["ControlType"], "Sequence cancellation fabricated a type selector")
            selectors[finite(before["TimeSeconds"], "cancellation time"), integer(before["NodeId"], "cancellation node"),
                      integer(before["PeerId"], "cancellation peer"), integer(before["Sequence"], "cancellation sequence")] += 1
        else:
            require(before["ControlType"] and metrics.optional_number(before["Sequence"], "control sequence") is None,
                    "Control-type cancellation fabricated a sequence selector")
    completions = Counter((finite(row["TimeSeconds"], "completion time"), integer(row["NodeId"], "completion node"),
                           integer(row["PeerId"], "completion peer"), integer(row["Sequence"], "completion sequence"))
                          for row in rows if row["Stage"] == "protocol_callback" and row["FrameKind"] == "DATA"
                          and row["Event"] in ("hop_ack", "hop_dack", "hop_failed"))
    require(all(selectors[key] >= count for key, count in completions.items()),
            "Service cancellation observations omitted completed DATA selectors")
    return {"paired_callbacks": len(cancellations)//2, "snapshot_rows": len(cancellations),
            "removed_queue_entries": removed_total, "callbacks_removing_entries": positive_pairs,
            "completed_data_selectors_joined": sum(completions.values()), "additional_scalar_reads": 6*len(cancellations),
            "scope": "Selectors identify cancellation requests; DATA completion coverage is cross-checked, while grouped/control requests retain distinct semantics."}


def verify_contracts(root, source_root, metadata, compare_rows):
    require(metadata.get("ContractDirectory") == "contracts" and metadata.get("ContractsExecuted") is True
            and metadata.get("ContractsPassed") is True, "Deterministic contract execution was not completed")
    reference = source_root/"evidence/tranche-9-contract-reference/checkpoints.csv"
    result = sweep.json_object(root/"contracts/summary.json")
    require(result.get("Schema") == "csr-tranche9-ack-service-contract-v1" and result.get("Passed") is True
            and integer(result.get("UnmatchedCount"), "unmatched contracts") == 0
            and integer(result.get("FailedCount"), "failed contracts") == 0
            and result.get("ReferenceSHA256") == sweep.digest(reference), "Contract summary/reference binding mismatch")
    count = compare_rows(root/"contracts/checkpoints.csv", reference)
    require(integer(result.get("CheckpointCount"), "contract checkpoints") == count,
            "Contract checkpoint count differs from complete rows")
    return {"passed": True, "checkpoint_count": count, "reference_sha256": sweep.digest(reference),
            "scope": "Matched prescribed MAC/HOP subsystem states; no RF or pseudorandom-stream equivalence claim."}


def parse_detail(text):
    result = {}
    for entry in text.split(";"):
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        require(key and key not in result, "Duplicate native service detail key")
        result[key] = value
    return result


def verify_native_rows(rows, original, feedback, flow_rows, summary, plan):
    require(summary.get("schema") == "csr-ns3-ack-service-summary-v1" and summary.get("status") == "passed"
            and summary.get("window_s") == plan["service_window_s"] and summary.get("stop_endpoint") == "exclusive"
            and summary.get("max_records") == plan["service_max_records"] and summary.get("omitted_records") == 0
            and summary.get("native_event_names_preserved") is True, "Native service summary scope/completion mismatch")
    require(rows and len(rows) == integer(summary.get("rows"), "native service rows")
            and len(rows) <= plan["service_max_records"], "Native service row coverage mismatch")
    contexts = {integer(row["decision_id"], "native feedback decision"): row for row in feedback
                if row["stage"] == "feedback_selection"}
    require(len(contexts) == sum(row["stage"] == "feedback_selection" for row in feedback), "Duplicate native feedback identity")
    pairs, observations, previous = {}, Counter(), plan["service_window_s"][0]
    selected_events = {"app_send", "nwk_delivery", "hop_feedback"}
    project = lambda row: tuple(row[name] for name in
                                ("time_s", "event", "node", "peer", "src", "dst", "sequence", "size_bytes", "reason", "statistic", "value", "detail"))
    expected_projection = [project(row) for row in original if row["event"] in selected_events and in_window(row["time_s"], plan)]
    actual_projection = []
    admitted, generated = Counter(), Counter()
    attempts = {}
    for index, row in enumerate(rows, 1):
        when = finite(row["time_s"], "native service time")
        require(set(row) == set(NATIVE_FIELDS) and row["schema"] == "csr-ns3-ack-service-v1"
                and exact_integer(row["event_index"], "native service identity") == index
                and in_window(when, plan) and when >= previous and row["event"] and row["node"],
                "Native service identity/order/window mismatch")
        previous = when
        event, node = row["event"], integer(row["node"], "native node")
        observations[event] += 1
        for field in ("preparation_active", "holdoff_over", "sync_present", "tx_in_progress", "success"):
            require(row[field] in ("", "0", "1"), "Invalid native service boolean")
        require(row["mac_state"] in ("", "idle", "search", "track", "tx"), "Invalid native MAC state")
        for field in ("packet_uid", "prior_packet_uid", "decision_id", "prior_decision_id", "ack_queue", "data_queue"):
            if row[field]:
                exact_integer(row[field], field)
        details = parse_detail(row["detail"])
        for prefix in ("", "prior_"):
            if not row[prefix+"decision_id"]:
                continue
            identity = integer(row[prefix+"decision_id"], "native decision")
            require(identity in contexts and row[prefix+"packet_uid"] == contexts[identity]["packet_uid"]
                    and when >= finite(contexts[identity]["time_s"], "native selection time"),
                    "Native service packet/decision identity differs from feedback selection")
            decision = contexts[identity]
            require(str(node) == decision["node_id"] and row["peer"] == decision["peer_id"],
                    "Native service feedback endpoints differ from decision")
            if not prefix:
                require(row["packet_type"].upper() == decision["frame_type"]
                        and all(details.get(name) == decision[name] for name in
                                ("hop_sequence", "has_ack_window", "ack_bitmap", "dack_bitmap")),
                        "Native service feedback window differs from retained selection")
        pair = {"ack_queue_replace_before": ("replace", True), "ack_queue_replace_after": ("replace", False),
                "mac_cancel_frame_before": ("cancel", True), "mac_cancel_frame_after": ("cancel", False),
                "mac_cancel_begin": ("cancel_operation", True), "mac_cancel_end": ("cancel_operation", False)}.get(event)
        if pair:
            key = node, pair[0]
            if pair[1]:
                require(key not in pairs, "Overlapping native queue before/after observations")
                pairs[key] = row
            else:
                require(key in pairs, "Native queue after observation has no preceding before observation")
                before = pairs.pop(key)
                require(row["time_s"] == before["time_s"] and row["peer"] == before["peer"],
                        "Native queue before/after time or endpoint changed")
                if pair[0] == "replace":
                    require(row["packet_uid"] == before["packet_uid"] and row["decision_id"] == before["decision_id"]
                            and row["ack_queue"] == before["ack_queue"], "Native ACK replacement changed queue size or retained identity")
                else:
                    require(all(row[field] == before[field] for field in
                                ("preparation_active", "holdoff_over", "reservation_slot", "reservation_counter", "mac_state")),
                            "Native cancellation changed prepared reservation state")
                    if pair[0] == "cancel":
                        require(integer(before["data_queue"], "before data queue")-integer(row["data_queue"], "after data queue") == 1,
                                "Native cancellation did not remove exactly one queued frame")
        if event in selected_events:
            actual_projection.append(project(row))
        if event == "app_send":
            generated[when, row["src"], row["dst"], row["sequence"]] += 1
        if event == "app_admission":
            flow, attempt = integer(details.get("flow_index"), "native flow index"), integer(details.get("attempt_index"), "native attempt index")
            require(0 <= flow < len(flow_rows) and (flow, attempt) not in attempts, "Native admission attempt identity is invalid/duplicated")
            item = flow_rows[flow]
            expected_time = finite(item["flow_start_s"], "flow start")+(attempt-1)*finite(item["flow_interval_s"], "flow interval")
            require(attempt >= 1 and abs(when-expected_time) <= 1e-8
                    and row["node"] == item["flow_src"] and row["src"] == item["flow_src"]
                    and row["dst"] == item["flow_dst"] and row["peer"] == item["flow_dst"],
                    "Native admission attempt differs from configured source/flow/schedule")
            attempts[flow, attempt] = row
            if sweep.boolean(row["success"], "native admitted"):
                require(row["sequence"] and row["reason"] == "admitted", "Native admitted attempt has no packet identity")
                admitted[when, row["src"], row["dst"], row["sequence"]] += 1
            else:
                require(not row["sequence"] and row["reason"] != "admitted", "Blocked native attempt fabricated a packet identity")
        if event == "nwk_nsdp_release":
            require(integer(details.get("count_before"), "NSDP before")-integer(details.get("count_after"), "NSDP after") == 1,
                    "Native NSDP release must free exactly one capacity slot")
    require(not pairs, "Native queue service observation omitted a matching after stage")
    require(actual_projection == expected_projection, "Native service app/feedback sequence differs from original trace")
    require(admitted == generated, "Native service admission identities differ from generated applications")
    expected_attempts = set()
    start, stop = (t7.time_tick(value, "service window") for value in plan["service_window_s"])
    for flow, row in enumerate(flow_rows):
        first, interval = t7.time_tick(row["flow_start_s"], "flow start"), t7.time_tick(row["flow_interval_s"], "flow interval")
        require(interval > 0, "Invalid native application interval")
        low = max(0, (start-first+interval-1)//interval)
        high = (stop-1-first)//interval
        expected_attempts.update((flow, offset+1) for offset in range(low, high+1))
    require(set(attempts) == expected_attempts, "Native service trace omitted scheduled application attempts")
    require(dict(sorted(observations.items())) == summary.get("event_counts")
            and summary.get("queue_replacement_events") == observations["ack_queue_replace_before"]
            and summary.get("cancelled_frames") == observations["mac_cancel_frame_before"]
            and summary.get("first_s") == finite(rows[0]["time_s"], "first service time")
            and summary.get("last_s") == finite(rows[-1]["time_s"], "last service time"),
            "Native service summary differs from complete raw rows")
    return {"rows": len(rows), "application_attempts_verified": len(attempts),
            "application_admissions_joined": sum(admitted.values()), "legacy_events_joined": len(actual_projection),
            "event_counts": dict(sorted(observations.items())), "window_s": plan["service_window_s"],
            "stop_endpoint": "exclusive", "scope": summary.get("scope", "")}


def verify_ns3_service(directory, case, plan):
    source_root = directory.parents[2]
    rows = list(metrics.csv_rows(directory/"ns3-service.csv.gz", NATIVE_FIELDS))
    original = list(metrics.csv_rows(directory/"ns3-trace.csv.gz"))
    feedback = list(metrics.csv_rows(directory/"ns3-link-decisions.csv.gz"))
    flows = [row for row in t7.csv_records(source_root/case["scenario_file"]) if row["record"] == "flow"]
    summary = sweep.json_object(directory/"service-summary.json")
    require(sweep.json_object(directory/"manifest.json").get("service_diagnostics") == summary,
            "Native service manifest/summary binding mismatch")
    return verify_native_rows(rows, original, feedback, flows, summary, plan)


def original_artifact(directory, manifest, name):
    entries = (sweep.entries(manifest.get("compressed_artifacts"), "native compressed observations")
               + sweep.entries(manifest.get("control_compressed_artifacts"), "native compressed controls"))
    matches = [row for row in entries if row.get("original_name") == name]
    if matches:
        require(len(matches) == 1, "Duplicate native compressed original identity")
        entry = matches[0]
        return integer(entry["original_bytes"], "original bytes"), sweep.valid_hash(entry["original_sha256"], "original hash")
    path = sweep.safe_path(directory, name)
    return path.stat().st_size, sweep.digest(path)


def verify_reference_suite(source_root, plan):
    root = source_root/"evidence/tranche-9-ns3-reference"
    suite = sweep.json_object(root/"manifest.json")
    require(suite.get("schema") == "csr-tranche9-ack-service-reference-suite-v1" and suite.get("status") == "completed"
            and suite.get("ns3_source_commit") == PIN and suite.get("plan_sha256") == sweep.digest(source_root/"scenarios/ack_service/plan.json")
            and all(suite.get(field) is True for field in
                    ("source_files_stable", "input_files_stable", "all_observer_on_off_checks_passed", "all_accepted_t8_anchors_passed", "closed_artifacts_reverified")),
            "Native T9 service reference did not complete with stable inputs and controls")
    require(suite.get("build_manifest_sha256") == sweep.digest(root/"build.json"), "Native T9 build manifest hash mismatch")
    build = sweep.json_object(root/"build.json")
    require(build.get("schema") == "csr-tranche9-ack-service-reference-build-v1" and build.get("ns3_source_commit") == PIN
            and build.get("source_headers_match_preserved_build") is True and build.get("standalone_runner_compiled") is True
            and build.get("full_ns3_rebuild_performed") is False and build.get("observer_compile", {}).get("exit_code") == 0
            and build.get("observer_helper_sha256") == sweep.digest(source_root/"scripts/ns3/tranche9-service-observer.h")
            and build.get("inherited_feedback_helper_sha256") == sweep.digest(source_root/"scripts/ns3/tranche8-link-observer.h"),
            "Native T9 compiled observer/source identity mismatch")
    inputs = build.get("input_sha256")
    require(isinstance(inputs, dict), "Native T9 build omitted generator inputs")
    for name in ("run_tranche9_ns3_service.py", "run_tranche8_ns3_diagnostics.py", "run_tranche7_ns3_reference.py", "run_tranche4_ns3_reference.py"):
        relative = "scripts/"+name
        matches = [digest for path, digest in inputs.items() if path.replace("\\", "/").endswith("/"+relative)]
        require(matches == [sweep.digest(source_root/relative)], "Native T9 overlay generator differs from compiled input")
    rows = sweep.entries(suite.get("cases"), "native T9 cases")
    require(len(rows) == 6 and [row.get("case_id") for row in rows] == [case["case_id"] for case in plan["cases"]],
            "Native T9 cases missing, duplicated or reordered")
    nested = set()
    compressed_count = control_pairs = anchor_pairs = 0
    for listed, case in zip(rows, plan["cases"]):
        key = case["storage_key"]
        require(listed.get("storage_key") == key and listed.get("status") == "completed"
                and listed.get("manifest") == f"{key}/manifest.json", "Native T9 case path/status mismatch")
        path = sweep.safe_path(root, listed["manifest"])
        require(listed.get("manifest_sha256") == sweep.digest(path), "Native T9 case manifest hash mismatch")
        record = sweep.json_object(path)
        require(record.get("schema") == "csr-tranche9-ack-service-reference-case-v1" and record.get("status") == "completed"
                and record.get("ns3_source_commit") == PIN and record.get("case") == case
                and record.get("case_id") == case["case_id"] and record.get("storage_key") == key
                and record.get("runner_sha256") == build.get("runner_sha256")
                and record.get("service_diagnostics") == listed.get("service_diagnostics")
                and record.get("application_admission_totals") == listed.get("application_admission_totals"),
                "Native T9 case provenance/summary binding mismatch")
        directory = path.parent
        t7.inventory(directory, record.get("files"), "native T9 case", excluded=("manifest.json",))
        compressed = (sweep.entries(record.get("compressed_artifacts"), "native T9 compressed observations")
                      + sweep.entries(record.get("control_compressed_artifacts"), "native T9 compressed controls"))
        require(len({item.get("original_name") for item in compressed}) == len(compressed), "Duplicate native compressed original")
        for item in compressed:
            t8.check_compressed(directory, item)
        compressed_count += len(compressed)
        controls = record.get("nonperturbation", {})
        pairs = sweep.entries(controls.get("compared_files"), "native T9 observer controls")
        require(controls.get("status") == "passed" and len(pairs) == 2
                and {item.get("name") for item in pairs} == {"ns3-trace.csv", "app-admission-diagnostics.csv"},
                "Native T9 observer control omitted original evidence")
        for item in pairs:
            name = item["name"]
            require(item.get("first_path") == name and item.get("second_path") == "off-"+name
                    and item.get("equal") is True
                    and original_artifact(directory, record, name)[1] == item.get("first_sha256")
                    and original_artifact(directory, record, "off-"+name)[1] == item.get("second_sha256")
                    and item["first_sha256"] == item["second_sha256"], "Native T9 observer on/off bytes differ")
        control_pairs += len(pairs)
        anchors = record.get("accepted_t8_anchor", {})
        pairs = sweep.entries(anchors.get("compared_files"), "native T8 anchors")
        require(anchors.get("status") == "passed" and anchors.get("reference_directory") == case["reference_directory"]
                and len(pairs) == 4 and {item.get("name") for item in pairs} ==
                {"ns3-trace.csv", "app-admission-diagnostics.csv", "ns3-aggregates.csv", "ns3-link-decisions.csv"},
                "Native T8 anchor omitted original evidence")
        for item in pairs:
            name = item["name"]
            reference_name = name+".gz" if name in ("ns3-trace.csv", "ns3-link-decisions.csv") else name
            require(item.get("reference_path") == case["reference_directory"]+"/"+reference_name, "Native T8 anchor path mismatch")
            reference = sweep.safe_path(source_root, item["reference_path"])
            data = gzip.decompress(reference.read_bytes()) if reference.suffix == ".gz" else reference.read_bytes()
            require(sweep.digest(reference) == item.get("reference_sha256") and item.get("equal") is True
                    and original_artifact(directory, record, name) == (len(data), hashlib.sha256(data).hexdigest())
                    and len(data) == item.get("bytes")
                    and hashlib.sha256(data).hexdigest() == item.get("original_sha256") == item.get("current_sha256"),
                    "Native T9 accepted T8 anchor changed or hashes are unbound")
        anchor_pairs += len(pairs)
        nested.update(f"{key}/{name}" for name in t7.listed_files(directory))
    t7.inventory(root, suite.get("files"), "native T9 suite", excluded={"manifest.json", *nested})
    contract = source_root/"evidence/tranche-9-contract-reference"
    record = sweep.json_object(contract/"manifest.json")
    require(record.get("schema") == "csr-tranche9-ack-contract-reference-v1" and record.get("status") == "passed"
            and record.get("source_commit") == PIN and record.get("source_headers_unchanged") is True
            and record.get("native_contract_executed") is True and record.get("matlab_executed") is False
            and record.get("engine_rebuilt") is False and record.get("checkpoint_count") == 101
            and record.get("case_count") == 6 and record.get("compile_returncode") == 0 and record.get("run_returncode") == 0,
            "Native controlled contract execution/source/count mismatch")
    for field, expected in (("contract_source", "scripts/ns3/tranche9_ack_contract.cc"),
                            ("runner_source", "scripts/run_tranche9_ack_contract.py")):
        entry = record.get(field, {})
        require(entry.get("path") == expected and entry.get("sha256") == sweep.digest(source_root/expected),
                "Native contract executable source binding mismatch")
    sweep.valid_hash(record.get("binary_sha256"), "native contract binary")
    t7.inventory(contract, record.get("artifacts"), "native T9 contract", excluded=("manifest.json",))
    checkpoints = list(t7.csv_records(contract/"checkpoints.csv"))
    require(len(checkpoints) == 101 and {row["case"] for row in checkpoints} ==
            {"mac_ack_wait", "mac_ack_sync", "mac_ack_track", "mac_cancel_then_ack", "mac_control_cancel_then_ack", "hop_release_order"},
            "Native contract checkpoint/case identity coverage mismatch")
    return {"passed": True, "case_count": 6, "compressed_roundtrips": compressed_count,
            "observer_control_file_pairs": control_pairs, "accepted_t8_file_pairs": anchor_pairs,
            "native_contract_checkpoints": len(checkpoints), "suite_manifest_sha256": sweep.digest(root/"manifest.json"),
            "contract_manifest_sha256": sweep.digest(contract/"manifest.json")}
