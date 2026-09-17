"""Small callback-ledger fixtures: meaningful joins, namespaces and censoring."""
from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tranche18_metrics as metrics


SERVICE_FIELDS = ("ObservationId", "TimeSeconds", "Stage", "Event", "NodeId", "PeerId", "FrameKind",
                  "PacketId", "PacketIdAvailable", "ApplicationSourceId", "FrameSourceId", "Sequence",
                  "ResendCount", "Reason", "ControlType")
PROTOCOL_FIELDS = ("TimeSeconds", "Event", "NodeId", "PeerId", "PacketId", "FrameKind", "Sequence")
APP_FIELDS = ("PacketId", "SourceId", "DestinationId", "GeneratedSeconds", "ReceivedSeconds", "LatencySeconds", "Outcome")
ADMISSION_FIELDS = ("TimeSeconds", "SourceId", "PacketId", "Accepted", "Reason")
DECISION_FIELDS = ("DecisionId", "TimeSeconds", "NodeId", "PeerId", "FrameKind", "InputContextAvailable",
                   "InputFrameKind", "InputPacketId", "QueueDisposition")
ACTUAL_FIELDS = ("ObservationId", "DecisionId", "TimeSeconds", "NodeId", "PeerId", "FrameKind", "AggregateId")


def callback(when, event, node, packet=101, peer=5, source=4, sequence=10, resend="NaN", kind=None):
    kind = kind or ("APP" if event.startswith("network_") else "DATA")
    return {"TimeSeconds": when, "Stage": "protocol_callback", "Event": event, "NodeId": node,
            "PeerId": peer, "FrameKind": kind, "PacketId": packet, "PacketIdAvailable": int(packet != 0),
            "ApplicationSourceId": source, "FrameSourceId": node, "Sequence": sequence,
            "ResendCount": resend, "Reason": "", "ControlType": ""}


def fixture():
    service = [callback(300, "network_enqueue", 4),
               callback(300, "network_enqueue", 5, 201, 1, 5),
               callback(300.1, "mac_enqueue", 4), callback(300.1, "hop_admit", 4),
               callback(300.1, "network_submit", 4), callback(301, "hop_sent", 4, resend=0),
               callback(303, "hop_retry", 4, resend=1), callback(303, "mac_enqueue", 4),
               callback(304, "mac_prepare", 4, 0, 0, "NaN", "NaN", kind="APP"),
               callback(305, "hop_sent", 4, 101, 5, "NaN", 10, 0, kind="CONTROL"),
               callback(306, "hop_sent", 4, resend=1),
               callback(306.25, "network_enqueue", 5, 101, 1, 4),
               callback(306.25, "hop_receive", 5, 101, 4, 4, 10),
               callback(306.5, "network_custody_release", 4),
               callback(306.5, "hop_ack", 4),
               callback(307, "mac_enqueue", 5, 101, 1, 4, 20),
               callback(307, "hop_admit", 5, 101, 1, 4, 20),
               callback(307, "network_submit", 5, 101, 1, 4, 20),
               callback(308, "hop_sent", 5, 101, 1, 4, 20, 0),
               callback(308.5, "network_custody_release", 5, 101, 1, 4, 20),
               callback(308.5, "hop_dack", 5, 101, 1, 4, 20),
               callback(309.5, "hop_dack_expired", 5, 101, 1, 4, 20)]
    service[9]["ControlType"] = "KEY_REQUEST"
    service[12]["FrameSourceId"] = 4
    apps = [{"PacketId": 101, "SourceId": 4, "DestinationId": 1, "GeneratedSeconds": 300,
             "ReceivedSeconds": 308.2, "LatencySeconds": 8.2, "Outcome": "delivered"},
            {"PacketId": 201, "SourceId": 5, "DestinationId": 1, "GeneratedSeconds": 300,
             "ReceivedSeconds": "NaN", "LatencySeconds": "NaN", "Outcome": "pending"}]
    admissions = [{"TimeSeconds": 300, "SourceId": 4, "PacketId": 101, "Accepted": 1, "Reason": "admitted"},
                  {"TimeSeconds": 300, "SourceId": 5, "PacketId": 201, "Accepted": 1, "Reason": "admitted"},
                  {"TimeSeconds": 301, "SourceId": 5, "PacketId": 0, "Accepted": 0, "Reason": "nsdp_limit"}]
    decisions = [{"DecisionId": 1, "TimeSeconds": 306.25, "NodeId": 5, "PeerId": 4, "FrameKind": "ACK",
                  "InputContextAvailable": 1, "InputFrameKind": "DATA", "InputPacketId": 101, "QueueDisposition": "enqueued"},
                 {"DecisionId": 2, "TimeSeconds": 306.27, "NodeId": 5, "PeerId": 4, "FrameKind": "ACK",
                  "InputContextAvailable": 1, "InputFrameKind": "CONTROL", "InputPacketId": 101, "QueueDisposition": "enqueued"}]
    actual = [{"ObservationId": 1, "DecisionId": 1, "TimeSeconds": 306.3, "NodeId": 5, "PeerId": 4,
               "FrameKind": "ACK", "AggregateId": 900},
              {"ObservationId": 2, "DecisionId": 1, "TimeSeconds": 306.4, "NodeId": 5, "PeerId": 4,
               "FrameKind": "ACK", "AggregateId": 901},
              {"ObservationId": 3, "DecisionId": 2, "TimeSeconds": 306.6, "NodeId": 5, "PeerId": 4,
               "FrameKind": "ACK", "AggregateId": 902}]
    return {"service": service, "apps": apps, "admissions": admissions, "decisions": decisions, "actual": actual}


def write_csv(path, records, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def materialize(directory, data, window=(300, 600)):
    directory = Path(directory)
    data = copy.deepcopy(data)
    service = data["service"]
    for ordinal, row in enumerate(service, 1):
        row.setdefault("ObservationId", ordinal)
    protocol = [{k: r[k] for k in PROTOCOL_FIELDS} for r in service]
    for ordinal, row in enumerate(service, 1):
        if row["Event"] == "hop_sent":
            protocol.append({"TimeSeconds": row["TimeSeconds"], "Event": "tx_start", "NodeId": row["NodeId"],
                             "PeerId": row["PeerId"], "PacketId": 1000+ordinal, "FrameKind": "AGGREGATE", "Sequence": 0})
    protocol.sort(key=lambda r: float(r["TimeSeconds"]))
    data["protocol"] = data.get("protocol", protocol)
    for key, name, fields in (("service", "raw/service_trace.csv", SERVICE_FIELDS),
                               ("protocol", "raw/protocol_trace.csv", PROTOCOL_FIELDS),
                               ("apps", "analysis/applications.csv", APP_FIELDS),
                               ("admissions", "raw/application_admission_trace.csv", ADMISSION_FIELDS),
                               ("decisions", "raw/link_decisions.csv", DECISION_FIELDS),
                               ("actual", "raw/actual_feedback.csv", ACTUAL_FIELDS)):
        write_csv(directory/name, data[key], fields)
    (directory/"raw/summary.json").write_text(json.dumps({"ServiceDiagnostics": {
        "WindowStartSeconds": window[0], "WindowEndSeconds": window[1]}}), encoding="utf-8")


class TestTranche18Metrics(unittest.TestCase):
    def analyze(self, data=None, window=(300, 600)):
        with tempfile.TemporaryDirectory() as temporary:
            materialize(temporary, fixture() if data is None else data, window)
            return metrics.analyze_case(temporary, {"case_id": "mixed_p128", "duration_s": 600,
                                                     "service_window_s": list(window)})

    def test_relay_uses_application_source_not_transmitting_node(self):
        result = self.analyze()
        ledger = {r["packet_id"]: r for r in result["node5_application_ledger"]}
        self.assertEqual(ledger[101]["cohort"], "relay")
        self.assertEqual(ledger[101]["application_source_id"], 4)
        self.assertEqual(ledger[201]["cohort"], "local")
        self.assertEqual(result["hop_4_to_5"]["actual_data_attempt_count"], 2)
        self.assertEqual(result["hop_4_to_5"]["retry_request_count"], 1)
        self.assertEqual(result["hop_4_to_5"]["actual_retry_attempt_count"], 1)
        json.dumps(result, allow_nan=False)

    def test_callback_waits_and_same_time_release_order(self):
        result = self.analyze()
        hop = result["hop_4_to_5"]["episodes"][0]
        self.assertAlmostEqual(hop["initial_service_wait"]["seconds"], .9)
        wait = hop["retry_service_waits"][0]
        self.assertEqual(wait["seconds"], 3)
        self.assertEqual(wait["completion"], "actual_hop_transmission")
        self.assertEqual(wait["node_policy_callback_counts"], {"mac_prepare": 1})
        self.assertEqual(hop["feedback_waits"][0]["seconds"], .5)
        relay = next(r for r in result["node5_application_ledger"] if r["packet_id"] == 101)
        release = relay["network_episodes"][0]["custody_release"]
        terminal = relay["outgoing_hops"][0]["terminal"]
        self.assertEqual(release["time_s"], terminal["time_s"])
        self.assertLess(release["service_observation_id"], terminal["service_observation_id"])
        self.assertEqual(relay["outgoing_hops"][0]["dack_hold"]["seconds"], 1)
        self.assertEqual(relay["network_episodes"][0]["submit_to_first_actual_hop_tx"]["seconds"], 1)

    def test_end_pending_is_finitely_censored(self):
        result = self.analyze()
        cohort = next(r for r in result["source_cohorts"] if r["application_source_id"] == 5)
        self.assertEqual(cohort["end_pending_ages"][0]["age_seconds"], 300)
        pending = next(r for r in result["node5_application_ledger"] if r["packet_id"] == 201)
        wait = pending["network_episodes"][0]["enqueue_to_submit"]
        self.assertTrue(wait["right_censored"])
        self.assertEqual(wait["seconds"], 300)

    def test_control_same_packet_id_is_a_separate_namespace(self):
        result = self.analyze()
        self.assertEqual(result["feedback_5_to_4"]["decision_ids"], [1])
        self.assertEqual(len(result["feedback_5_to_4"]["actual_feedback_members"]), 2)
        hop = result["hop_4_to_5"]["episodes"][0]
        self.assertEqual([r["time_s"] for r in hop["attempts"]], [301, 306])

    def test_feedback_repeats_preserved_without_claiming_all_bitmap_members(self):
        feedback = self.analyze()["feedback_5_to_4"]
        self.assertEqual(feedback["decision_to_ota_seconds"]["count"], 2)
        self.assertEqual([r["actual_feedback_observation_id"] for r in feedback["actual_feedback_members"]], [1, 2])
        self.assertIn("not every packet", feedback["scope"])

    def test_pending_queued_retry_is_valid_and_policy_delay_not_failure(self):
        data = fixture()
        data["service"] = [r for r in data["service"] if not
                           (r["NodeId"] == 4 and r["TimeSeconds"] >= 306)]
        hop = self.analyze(data)["hop_4_to_5"]["episodes"][0]
        wait = hop["retry_service_waits"][0]
        self.assertTrue(wait["right_censored"])
        self.assertEqual(wait["seconds"], 297)
        self.assertEqual(wait["completion"], "observation_ended")

    def test_terminal_can_cancel_an_observed_queued_retry(self):
        data = fixture()
        data["service"] = [r for r in data["service"] if not
                           (r["NodeId"] == 4 and r["Event"] == "hop_sent" and r["FrameKind"] == "DATA" and r["ResendCount"] == 1)]
        hop = self.analyze(data)["hop_4_to_5"]["episodes"][0]
        wait = hop["retry_service_waits"][0]
        self.assertFalse(wait["right_censored"])
        self.assertEqual(wait["completion"], "terminal_before_next_transmission")

    def test_partial_service_window_censors_at_window_end_not_simulation_end(self):
        data = fixture()
        data["service"] = [r for r in data["service"] if r["TimeSeconds"] < 304]
        result = self.analyze(data, (300, 304))
        wait = result["hop_4_to_5"]["episodes"][0]["retry_service_waits"][0]
        self.assertEqual(wait["seconds"], 1)
        self.assertEqual(wait["censor_time_s"], 304)
        cohort = next(r for r in result["source_cohorts"] if r["application_source_id"] == 5)
        self.assertEqual(cohort["end_pending_ages"][0]["censor_time_s"], 600)

    def test_actual_t18_observer_window_censors_at_horizon(self):
        data = fixture()
        data["service"] = [r for r in data["service"] if not
                           (r["NodeId"] == 4 and r["TimeSeconds"] >= 306)]
        result = self.analyze(data, (0, 601))
        self.assertEqual(result["service_window_s"], [0, 601])
        self.assertEqual(result["observation_censor_time_s"], 600)
        retry = result["hop_4_to_5"]["episodes"][0]["retry_service_waits"][0]
        self.assertEqual(retry["censor_time_s"], 600)
        self.assertEqual(retry["seconds"], 297)
        local = next(r for r in result["node5_application_ledger"] if r["packet_id"] == 201)
        for name in ("enqueue_to_submit", "enqueue_to_release", "queue_observation_interval"):
            self.assertEqual(local["network_episodes"][0][name]["censor_time_s"], 600)
            self.assertEqual(local["network_episodes"][0][name]["seconds"], 300)

    def test_actual_t18_observer_window_accepts_callbacks_at_horizon(self):
        data = fixture()
        for row in data["service"]:
            if row["NodeId"] == 4 and row["Event"] in ("network_custody_release", "hop_ack"):
                row["TimeSeconds"] = 600
        data["service"].sort(key=lambda r: r["TimeSeconds"])
        result = self.analyze(data, (0, 601))
        hop = result["hop_4_to_5"]["episodes"][0]
        self.assertEqual(hop["terminal"]["time_s"], 600)
        self.assertEqual(hop["feedback_waits"][0]["seconds"], 294)
        self.assertFalse(hop["feedback_waits"][0]["right_censored"])

    def test_actual_t18_observer_window_rejects_callbacks_after_horizon(self):
        data = fixture()
        data["service"].append(callback(600.5, "mac_prepare", 4, 0, 0, "NaN", "NaN", kind="APP"))
        with self.assertRaisesRegex(ValueError, "outside service window"):
            self.analyze(data, (0, 601))

    def test_missing_application_source_rejected(self):
        data = fixture(); data["service"][18]["ApplicationSourceId"] = "NaN"
        with self.assertRaisesRegex(ValueError, "ApplicationSourceId"):
            self.analyze(data)

    def test_frame_source_substitution_rejected(self):
        data = fixture(); data["service"][18]["ApplicationSourceId"] = 5
        with self.assertRaisesRegex(ValueError, "ApplicationSourceId"):
            self.analyze(data)

    def test_missing_data_packet_identity_rejected(self):
        data = fixture(); data["service"][18]["PacketIdAvailable"] = 0
        with self.assertRaisesRegex(ValueError, "Missing application identity"):
            self.analyze(data)

    def test_unknown_data_packet_rejected(self):
        data = fixture(); data["service"][18]["PacketId"] = 999
        with self.assertRaisesRegex(ValueError, "Unknown DATA"):
            self.analyze(data)

    def test_duplicate_application_id_rejected(self):
        data = fixture(); data["apps"].append(dict(data["apps"][0], SourceId=5))
        with self.assertRaisesRegex(ValueError, "duplicate application"):
            self.analyze(data)

    def test_control_mislabeled_as_data_rejected(self):
        data = fixture(); data["service"][9].update(FrameKind="DATA", ApplicationSourceId=4)
        with self.assertRaisesRegex(ValueError, "CONTROL identity"):
            self.analyze(data)

    def test_negative_service_interval_rejected(self):
        data = fixture(); data["service"][10]["TimeSeconds"] = 302
        with self.assertRaisesRegex(ValueError, "Negative service time"):
            self.analyze(data)

    def test_negative_feedback_queue_wait_rejected(self):
        data = fixture(); data["actual"][0]["TimeSeconds"] = 306
        with self.assertRaisesRegex(ValueError, "Negative feedback queue"):
            self.analyze(data)

    def test_negative_application_delay_rejected(self):
        data = fixture(); data["apps"][0].update(ReceivedSeconds=299, LatencySeconds=-1)
        with self.assertRaisesRegex(ValueError, "Negative/inconsistent application"):
            self.analyze(data)

    def test_nonfinite_horizon_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            materialize(temporary, fixture())
            with self.assertRaisesRegex(ValueError, "Nonfinite case duration"):
                metrics.analyze_case(temporary, {"duration_s": float("inf")})

    def test_duplicate_feedback_decision_rejected(self):
        data = fixture(); data["decisions"].append(dict(data["decisions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate feedback DecisionId"):
            self.analyze(data)

    def test_actual_feedback_unknown_decision_rejected(self):
        data = fixture(); data["actual"][0]["DecisionId"] = 500
        with self.assertRaisesRegex(ValueError, "missing decision identity"):
            self.analyze(data)

    def test_duplicate_actual_feedback_id_rejected(self):
        data = fixture(); data["actual"][1]["ObservationId"] = 1
        with self.assertRaisesRegex(ValueError, "duplicate actual-feedback"):
            self.analyze(data)

    def test_feedback_unknown_triggering_data_rejected(self):
        data = fixture(); data["decisions"][0]["InputPacketId"] = 500
        with self.assertRaisesRegex(ValueError, "feedback-triggering application"):
            self.analyze(data)

    def test_duplicate_service_id_rejected(self):
        data = fixture(); data["service"][5]["ObservationId"] = 5
        with self.assertRaisesRegex(ValueError, "service observation identity"):
            self.analyze(data)

    def test_missing_retry_callback_rejected(self):
        data = fixture(); data["service"] = [r for r in data["service"] if r["Event"] != "hop_retry"]
        with self.assertRaisesRegex(ValueError, "lacks unambiguous retry"):
            self.analyze(data)

    def test_retry_count_mismatch_rejected(self):
        data = fixture(); data["service"][10]["ResendCount"] = 2
        with self.assertRaisesRegex(ValueError, "inconsistent retry identity"):
            self.analyze(data)

    def test_missing_actual_tx_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            materialize(temporary, fixture())
            path = Path(temporary)/"raw/protocol_trace.csv"
            records = metrics.rows(path, PROTOCOL_FIELDS)
            records = [r for r in records if not (r["Event"] == "tx_start" and r["TimeSeconds"] == "306")]
            write_csv(path, records, PROTOCOL_FIELDS)
            with self.assertRaisesRegex(ValueError, "Missing or ambiguous actual TX"):
                metrics.analyze_case(temporary, {"duration_s": 600})

    def test_ambiguous_actual_tx_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            materialize(temporary, fixture())
            path = Path(temporary)/"raw/protocol_trace.csv"
            records = metrics.rows(path, PROTOCOL_FIELDS)
            records.append(next(dict(r) for r in records if r["Event"] == "tx_start" and r["TimeSeconds"] == "306"))
            write_csv(path, records, PROTOCOL_FIELDS)
            with self.assertRaisesRegex(ValueError, "Missing or ambiguous actual TX"):
                metrics.analyze_case(temporary, {"duration_s": 600})

    def test_service_peer_must_match_original_protocol(self):
        with tempfile.TemporaryDirectory() as temporary:
            materialize(temporary, fixture())
            path = Path(temporary)/"raw/protocol_trace.csv"
            records = metrics.rows(path, PROTOCOL_FIELDS)
            next(r for r in records if r["Event"] == "hop_sent")["PeerId"] = 8
            write_csv(path, records, PROTOCOL_FIELDS)
            with self.assertRaisesRegex(ValueError, "identities differ from protocol"):
                metrics.analyze_case(temporary, {"duration_s": 600})

    def test_service_sequence_must_match_original_protocol(self):
        with tempfile.TemporaryDirectory() as temporary:
            materialize(temporary, fixture())
            path = Path(temporary)/"raw/protocol_trace.csv"
            records = metrics.rows(path, PROTOCOL_FIELDS)
            next(r for r in records if r["Event"] == "hop_sent")["Sequence"] = 55
            write_csv(path, records, PROTOCOL_FIELDS)
            with self.assertRaisesRegex(ValueError, "identities differ from protocol"):
                metrics.analyze_case(temporary, {"duration_s": 600})

    def test_capacity_snapshot_preserves_false_without_inventing_missing_state(self):
        observed = metrics.evidence({"_id": 8, "_time": 305.5, "Event": "hop_dack",
                                     "CapacityReleased": "0", "PendingData": "NaN", "HoldSeconds": "5"})
        self.assertEqual(observed["exported_callback_snapshots"], {"CapacityReleased": 0.0, "HoldSeconds": 5.0})

    def test_uint64_packet_identity_preserved(self):
        data = fixture()
        large = 2**63+13
        for key in ("service", "apps", "admissions"):
            for row in data[key]:
                if row.get("PacketId") == 101:
                    row["PacketId"] = large
        for row in data["decisions"]:
            if row["InputPacketId"] == 101:
                row["InputPacketId"] = large
        self.assertEqual(self.analyze(data)["hop_4_to_5"]["episodes"][0]["packet_id"], large)


class TestFiniteStopApplicationSummary(unittest.TestCase):
    CASE = {"case_id": "mixed_p128", "base_case_id": "mixed", "seed": 128,
            "duration_s": 600, "bucket_width_s": 60}

    def prepare(self, directory, data):
        materialize(directory, data)
        records = [dict(r, ApplicationBytes=100, DropReason="") for r in data["apps"]]
        write_csv(Path(directory)/"analysis/applications.csv", records, APP_FIELDS+("ApplicationBytes", "DropReason"))
        write_csv(Path(directory)/"raw/application_admission_statistics.csv", [{"Attempts": 3}], ("Attempts",))

    def summarize(self, data):
        with tempfile.TemporaryDirectory() as temporary:
            self.prepare(temporary, data)
            return metrics.summarize_matlab_applications(temporary, self.CASE)

    def test_no_endpoint_matches_existing_summary_keys_and_values(self):
        import tranche8_metrics
        with tempfile.TemporaryDirectory() as temporary:
            self.prepare(temporary, fixture())
            legacy = tranche8_metrics.matlab_applications(temporary, self.CASE)
            current = metrics.summarize_matlab_applications(temporary, self.CASE)
            self.assertEqual({k: current[k] for k in legacy}, legacy)
            self.assertEqual(current["aggregation_boundary"]["excluded_delivery_count"], 0)

    def test_exact_stop_delivery_retained_and_not_pending(self):
        data = fixture()
        data["apps"][0].update(ReceivedSeconds=600, LatencySeconds=300)
        data["apps"][1].update(Outcome="delivered", ReceivedSeconds=320, LatencySeconds=20)
        result = self.summarize(data)
        self.assertEqual(result["delivered"], 2)
        self.assertEqual(result["pending"], 0)
        self.assertEqual(result["unmatched_sends"], 0)
        self.assertEqual(result["mean_packet_latency_s"], 160)
        self.assertEqual(result["mean_populated_bucket_latency_s"], 20)
        self.assertEqual(result["populated_delay_buckets"], 1)
        self.assertEqual(result["aggregation_boundary"]["excluded_deliveries"], [
            {"packet_id": 101, "time_s": 600.0, "network_bytes": 107, "latency_s": 300.0, "reason": "exact_stop"}])
        self.assertEqual([r["delivered"] for r in result["flows"]], [1, 1])
        self.assertEqual(result["network_bytes_received"], 214)
        json.dumps(result, allow_nan=False)

    def test_only_endpoint_arrival_has_no_populated_bucket(self):
        data = fixture(); data["apps"][0].update(ReceivedSeconds=600, LatencySeconds=300)
        result = self.summarize(data)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(result["mean_packet_latency_s"], 300)
        self.assertIsNone(result["mean_populated_bucket_latency_s"])
        self.assertEqual(result["populated_delay_buckets"], 0)

    def test_just_before_stop_follows_existing_bucket_snap_without_losing_delivery(self):
        data = fixture()
        arrival = math.nextafter(600, 0)
        data["apps"][0].update(ReceivedSeconds=arrival, LatencySeconds=arrival-300)
        result = self.summarize(data)
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(result["aggregation_boundary"]["excluded_delivery_count"], 1)
        self.assertEqual(result["aggregation_boundary"]["excluded_deliveries"][0]["reason"], "quotient_snapped_to_stop")

    def test_arrival_after_stop_rejected(self):
        data = fixture(); data["apps"][0]["ReceivedSeconds"] = 600.001
        with self.assertRaisesRegex(ValueError, "outside finite stop"):
            self.summarize(data)

    def test_generation_at_stop_rejected(self):
        data = fixture(); data["apps"][1]["GeneratedSeconds"] = 600
        with self.assertRaisesRegex(ValueError, "generation must precede"):
            self.summarize(data)


if __name__ == "__main__":
    unittest.main()
