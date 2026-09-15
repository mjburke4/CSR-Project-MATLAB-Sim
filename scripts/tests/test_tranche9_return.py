#!/usr/bin/env python3
"""Corruption tests for returned T9 identities, complete service traces and contracts."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche9_return as review
import tranche9_metrics as service

REPO = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class PlanAndContracts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def source(self):
        source = self.root/"source"
        shutil.copytree(REPO/"scenarios", source/"scenarios")
        return source

    def test_declared_six_cases_preserve_accepted_inputs(self):
        plan, parent = review.verify_plan(REPO)
        self.assertEqual([row["storage_key"] for row in plan["cases"]], ["c129", "c128", "c130", "c131", "c132", "a129"])
        self.assertEqual(len(parent["cases"]), 10)
        self.assertTrue(plan["policy_changes"])
        self.assertFalse(plan["baseline_anchor"]["expected_existing_traces_equal"])

    def test_case_order_or_duplicate_cannot_be_rehashed_away(self):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        plan["cases"][0], plan["cases"][1] = plan["cases"][1], plan["cases"][0]
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, "missing, duplicated or reordered"):
            review.verify_plan(source)

    def test_same_case_label_cannot_hide_changed_seed(self):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        plan["cases"][0]["seed"] = 130
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, "accepted T8 input"):
            review.verify_plan(source)

    def test_service_stop_must_be_exclusive(self):
        source = self.source()
        plan = json.loads((source/review.PLAN).read_text())
        plan["service_window_end_exclusive"] = False
        write_json(source/review.PLAN, plan)
        with self.assertRaisesRegex(ValueError, "window or limits"):
            review.verify_plan(source)

    def test_true_native_contract_rows_pass_and_control_cancellation_is_present(self):
        reference = REPO/review.CONTRACT_ROOT/"checkpoints.csv"
        rows = list(review.t7.csv_records(reference))
        write_csv(self.root/"actual.csv", rows)
        self.assertEqual(review.verify_contract_rows(self.root/"actual.csv", reference), 101)
        self.assertIn("mac_control_cancel_then_ack", {row["case"] for row in rows})

    def corrupt_contract(self, mutation, message):
        reference = REPO/review.CONTRACT_ROOT/"checkpoints.csv"
        rows = list(review.t7.csv_records(reference))
        mutation(rows)
        write_csv(self.root/"actual.csv", rows)
        with self.assertRaisesRegex(ValueError, message):
            review.verify_contract_rows(self.root/"actual.csv", reference)

    def test_relabelled_contract_checkpoint_fails(self):
        self.corrupt_contract(lambda rows: rows[0].update(checkpoint="another_state"), "identity/order")

    def test_reordered_contract_checkpoint_fails(self):
        def change(rows):
            rows[0], rows[1] = rows[1], rows[0]
        self.corrupt_contract(change, "identity/order")

    def test_duplicate_contract_row_fails_even_with_same_count(self):
        self.corrupt_contract(lambda rows: rows.__setitem__(1, dict(rows[0])), "Duplicate contract")

    def test_claimed_passing_changed_contract_value_fails(self):
        self.corrupt_contract(lambda rows: rows[0].update(actual=str(float(rows[0]["actual"])+1), **{"pass": "1"}),
                              "differs from pinned native")

    def test_nonfinite_contract_value_fails(self):
        self.corrupt_contract(lambda rows: rows[0].update(actual="NaN"), "finite")

    def test_failure_cli_preserves_a_failure_report(self):
        evidence, output = self.root/"return", self.root/"review"
        write_json(evidence/"validation_metadata.json", {"Schema": review.SCHEMA, "Tranche": 9, "Status": "failed"})
        self.assertEqual(review.main(["--evidence", str(evidence), "--source-root", str(REPO), "--output", str(output)]), 1)
        result = json.loads((output/"review-failure.json").read_text())
        self.assertEqual(result["status"], "structural_review_failed")
        self.assertFalse(result["acceptance_established"])
        self.assertFalse(result["default_structural_gate_completed"])


def observation(index, time, event, *, node=2, peer=1, packet=1, kind="DATA", details=None, admission=False):
    details = details or {}
    row = {field: "NaN" for field in service.DETAIL_FIELDS}
    row.update(ObservationId=str(index), TimeSeconds=str(time), Stage="application_attempt" if admission else "protocol_callback",
               Layer="APP" if admission else "MAC" if event.startswith("mac_") else "HOP" if event.startswith("hop_") else "NWK",
               Event=event, NodeId=str(node), PeerId=str(peer), FrameKind=kind, PacketId=str(packet),
               PacketIdAvailable="1" if packet else "0", AggregateId="0", AggregateIdAvailable="0",
               FrameSourceId=str(node), FrameDestinationId=str(peer), ApplicationSourceId=str(node),
               ApplicationDestinationId=str(peer), Sequence="1", FrameDestinationsJSON="[]", HopSequencesJSON="[]",
               ControlType="TEST" if kind == "CONTROL" else "", FeedbackIdentityAvailable="0", HasAckWindow="NaN",
               AckBitmap="0", DackBitmap="0", State=details.get("State", ""), Reason=details.get("Reason", ""),
               SegmentCount="NaN", DetailsJSON=json.dumps(details))
    for field in service.DETAIL_FIELDS:
        if field in details and service.scalar(details[field]):
            row[field] = str(int(details[field])) if type(details[field]) is bool else str(details[field])
    return row


def legacy(row):
    return {name: row[name] for name in ("TimeSeconds", "Event", "NodeId", "PeerId", "PacketId", "FrameKind", "Reason", "ControlType")}


class AnchorConfiguration(unittest.TestCase):
    def setUp(self):
        self.case = dict(scenario_file="scenarios/link_diagnostics/inputs/case.csv", scenario_sha256="a"*64)
        self.before = dict(Seed=129, SharedScenario=dict(SourcePath="C:\\csr8\\scenarios\\link_diagnostics\\inputs\\case.csv",
                                                       SourceSHA256="a"*64), Other=dict(SourcePath="unchanged"))
        self.after = copy.deepcopy(self.before)
        self.after["SharedScenario"]["SourcePath"] = "/new/csr9/scenarios/link_diagnostics/inputs/case.csv"

    def test_only_hash_bound_input_installation_prefix_may_change(self):
        original = copy.deepcopy(self.before)
        result = review.verify_anchor_configuration(self.before, self.after, self.case)
        self.assertEqual(result["scenario_sha256"], "a"*64)
        self.assertEqual(self.before, original)
        self.assertIn("SourcePath", self.after["SharedScenario"])

    def test_changed_input_hash_is_rejected(self):
        self.after["SharedScenario"]["SourceSHA256"] = "b"*64
        with self.assertRaisesRegex(ValueError, "input hash differs"):
            review.verify_anchor_configuration(self.before, self.after, self.case)

    def test_changed_seed_is_rejected(self):
        self.after["Seed"] = 130
        with self.assertRaisesRegex(ValueError, "changed accepted T8 experiment configuration"):
            review.verify_anchor_configuration(self.before, self.after, self.case)

    def test_same_hash_cannot_hide_a_different_input_filename(self):
        self.after["SharedScenario"]["SourcePath"] = "/new/csr9/scenarios/link_diagnostics/inputs/other.csv"
        with self.assertRaisesRegex(ValueError, "does not identify the planned input"):
            review.verify_anchor_configuration(self.before, self.after, self.case)

    def test_other_path_fields_are_not_ignored(self):
        self.after["Other"]["SourcePath"] = "changed"
        with self.assertRaisesRegex(ValueError, "changed accepted T8 experiment configuration"):
            review.verify_anchor_configuration(self.before, self.after, self.case)


class MatlabServiceIntegrity(unittest.TestCase):
    def setUp(self):
        self.plan = {"service_window_s": [300, 320], "service_max_records": 100000}
        original = {"TimeSeconds": "300", "FlowIndex": "1", "AttemptIndex": "1", "SourceId": "2",
                    "ConfiguredDestinationId": "1", "DestinationId": "1", "PacketId": "1", "Accepted": "1",
                    "Reason": "admitted", "DiscoveryActive": "0", "TopologyKnown": "1", "GatewayCached": "1",
                    "GatewayNodeId": "1", "RouteCheckPerformed": "1", "RouteAvailable": "1", "NsdpCount": "0",
                    "NsdpLimit": "16", "NwkQueueSize": "0"}
        details = {name: value if name == "Reason" else value == "1" if name in service.ADMISSION_BOOL_FIELDS
                   else float(value) for name, value in original.items()}
        self.rows = [observation(1, 300, "application_attempt", kind="APP", details=details, admission=True),
                     observation(2, 300, "network_enqueue", kind="APP", details={"QueueDepth": 1}),
                     observation(3, 300, "hop_admit", details={"PendingData": 1, "GlobalAllowed": True}),
                     observation(4, 301, "hop_ack", details={"PendingData": 0, "GlobalAllowed": True})]
        self.admissions = [original]
        self.protocol = [legacy(row) for row in self.rows[1:]]
        self.feedback = []
        self.summary = dict(SchemaVersion="csr-matlab-ack-service-diagnostics-v1", Enabled=True, Complete=True,
                            InheritedFeedbackComplete=True, Passive=True, MaxRecords=100000, WindowStartSeconds=300,
                            WindowEndSeconds=320, WindowBoundary="start_inclusive_end_exclusive", ServiceEventCount=4,
                            CapturedServiceRecords=4, OmittedServiceRecords=0, OutOfWindowServiceEvents=0,
                            ScheduledEvents=0, RandomDraws=0, AdditionalStateReads=12,
                            CancellationSnapshotCount=2, CancellationBeforeCount=1, CancellationAfterCount=1,
                            CancellationPairErrors=0, PendingCancellationPair=False, CancellationPairsComplete=True)
        for index, event, removed, depth in ((5, "mac_cancel_before", None, 1), (6, "mac_cancel_after", 1, 0)):
            details = dict(State="Idle", PreparationActive=True, ReservationSlot=7, ReservationCounter=0,
                           DataDepth=depth, AckDepth=0, PeerId=1, Sequence=1, ControlType="", RemovedCount=removed)
            row = observation(index, 301, event, packet=0, kind="", details=details)
            row.update(Stage="cancellation_callback", FrameSourceId="NaN", FrameDestinationId="NaN",
                       ApplicationSourceId="NaN", ApplicationDestinationId="NaN")
            self.rows.append(row)
        self.summary.update(ServiceEventCount=6, CapturedServiceRecords=6)

    def verify(self):
        return service.verify_matlab_rows(self.rows, self.protocol, self.admissions, self.feedback, self.summary, self.plan)

    def test_every_callback_and_admission_is_joined(self):
        result = self.verify()
        self.assertEqual((result["protocol_callbacks_joined"], result["application_attempts_joined"]), (3, 1))

    def test_matlab_logical_json_matches_csv_zero_one(self):
        details = json.loads(self.rows[0]["DetailsJSON"])
        self.assertTrue(all(type(details[name]) is bool for name in service.ADMISSION_BOOL_FIELDS))
        self.assertTrue(details["Accepted"])
        self.assertFalse(details["DiscoveryActive"])
        self.assertEqual(self.verify()["application_attempts_joined"], 1)

    def test_numeric_zero_one_logical_details_remain_supported(self):
        details = json.loads(self.rows[0]["DetailsJSON"])
        for name in service.ADMISSION_BOOL_FIELDS:
            details[name] = int(details[name])
        self.rows[0]["DetailsJSON"] = json.dumps(details)
        self.assertEqual(self.verify()["application_attempts_joined"], 1)

    def test_logical_json_value_must_match_original_admission(self):
        details = json.loads(self.rows[0]["DetailsJSON"])
        details["TopologyKnown"] = False
        self.rows[0]["DetailsJSON"] = json.dumps(details)
        with self.assertRaisesRegex(ValueError, "admission logical value differs"):
            self.verify()

    def test_logical_admission_field_rejects_non_boolean_number(self):
        details = json.loads(self.rows[0]["DetailsJSON"])
        details["TopologyKnown"] = 2
        self.rows[0]["DetailsJSON"] = json.dumps(details)
        with self.assertRaisesRegex(ValueError, "expected Boolean or numeric 0/1"):
            self.verify()

    def test_numeric_admission_identity_still_rejects_boolean(self):
        details = json.loads(self.rows[0]["DetailsJSON"])
        details["AttemptIndex"] = True
        self.rows[0]["DetailsJSON"] = json.dumps(details)
        with self.assertRaisesRegex(ValueError, "AttemptIndex: Boolean is not numeric"):
            self.verify()

    def test_control_packet_id_collision_does_not_enter_application_ordering(self):
        control = observation(1, 300, "hop_control_ack", kind="CONTROL")
        self.rows.insert(0, control)
        self.protocol.insert(0, legacy(control))
        for index, row in enumerate(self.rows, 1):
            row["ObservationId"] = str(index)
        self.summary.update(ServiceEventCount=7, CapturedServiceRecords=7)
        self.assertEqual(self.verify()["protocol_callbacks_joined"], 4)

    def test_reindexed_service_omission_is_detected_against_raw_protocol(self):
        self.rows.pop(2)
        for index, row in enumerate(self.rows, 1):
            row["ObservationId"] = str(index)
        self.summary.update(ServiceEventCount=5, CapturedServiceRecords=5)
        with self.assertRaisesRegex(ValueError, "omitted or duplicated"):
            self.verify()

    def test_swapped_same_time_callbacks_reject_even_with_repaired_ids(self):
        self.rows[1], self.rows[2] = self.rows[2], self.rows[1]
        self.rows[1]["ObservationId"], self.rows[2]["ObservationId"] = "2", "3"
        with self.assertRaisesRegex(ValueError, "callback identity/order"):
            self.verify()

    def test_same_time_callback_before_admission_is_rejected(self):
        self.rows[0], self.rows[1] = self.rows[1], self.rows[0]
        self.rows[0]["ObservationId"], self.rows[1]["ObservationId"] = "1", "2"
        with self.assertRaisesRegex(ValueError, "precedes its completed admission"):
            self.verify()

    def test_mismatched_packet_identity_is_rejected(self):
        self.rows[2]["PacketId"] = "2"
        with self.assertRaisesRegex(ValueError, "packet identity differs"):
            self.verify()

    def test_fabricated_ota_aggregate_identity_is_rejected(self):
        self.rows[2].update(AggregateId="99", AggregateIdAvailable="1")
        with self.assertRaisesRegex(ValueError, "OTA aggregate"):
            self.verify()

    def test_fabricated_capacity_detail_is_rejected(self):
        self.rows[2]["PendingData"] = "99"
        with self.assertRaisesRegex(ValueError, "PendingData differs"):
            self.verify()

    def test_rehashed_admission_json_cannot_change_attempt_identity(self):
        details = json.loads(self.rows[0]["DetailsJSON"])
        details["AttemptIndex"] = 9
        self.rows[0].update(AttemptIndex="9", DetailsJSON=json.dumps(details))
        with self.assertRaisesRegex(ValueError, "admission identity/value"):
            self.verify()

    def test_omission_counter_blocks_completion(self):
        self.summary["OmittedServiceRecords"] = 1
        with self.assertRaisesRegex(ValueError, "Incomplete or perturbing"):
            self.verify()

    def test_endpoint_320_is_excluded(self):
        self.rows[0]["TimeSeconds"] = "320"
        with self.assertRaisesRegex(ValueError, "identity/order/window"):
            self.verify()

    def test_false_outside_window_counter_is_rejected(self):
        self.summary["OutOfWindowServiceEvents"] = 1
        with self.assertRaisesRegex(ValueError, "out-of-window count"):
            self.verify()

    def test_matlab_cancellation_removal_preserves_preparation(self):
        result = self.verify()["cancellations"]
        self.assertEqual(result["removed_queue_entries"], 1)
        self.assertEqual(result["additional_scalar_reads"], 12)

    def test_entire_omitted_cancellation_pair_fails_independent_data_completion_join(self):
        self.rows = self.rows[:4]
        self.summary.update(ServiceEventCount=4, CapturedServiceRecords=4, CancellationSnapshotCount=0,
                            CancellationBeforeCount=0, CancellationAfterCount=0, AdditionalStateReads=0)
        with self.assertRaisesRegex(ValueError, "omitted completed DATA selectors"):
            self.verify()

    def test_changed_cancellation_selector_is_rejected(self):
        self.rows[-1]["PeerId"] = "3"
        with self.assertRaisesRegex(ValueError, "selectors differ"):
            self.verify()

    def test_cancellation_false_removal_count_is_rejected(self):
        row = self.rows[-1]
        details = json.loads(row["DetailsJSON"])
        details["RemovedCount"] = 0
        row.update(RemovedCount="0", DetailsJSON=json.dumps(details))
        with self.assertRaisesRegex(ValueError, "removed-count/queue-depth"):
            self.verify()

    def test_reintroduced_queue_empty_preparation_reset_is_rejected(self):
        row = self.rows[-1]
        details = json.loads(row["DetailsJSON"])
        details["PreparationActive"] = False
        row.update(PreparationActive="0", DetailsJSON=json.dumps(details))
        with self.assertRaisesRegex(ValueError, "changed prepared reservation"):
            self.verify()


class NativeRawEvidence(unittest.TestCase):
    """Mutate in-memory copies of genuine native traces; never edit references."""
    @classmethod
    def setUpClass(cls):
        cls.plan, _ = review.verify_plan(REPO)
        cls.case = cls.plan["cases"][0]
        root = REPO/cls.case["service_reference_directory"]
        cls.rows = list(service.metrics.csv_rows(root/"ns3-service.csv.gz"))
        cls.original = list(service.metrics.csv_rows(root/"ns3-trace.csv.gz"))
        cls.feedback = list(service.metrics.csv_rows(root/"ns3-link-decisions.csv.gz"))
        cls.flows = [row for row in review.t7.csv_records(REPO/cls.case["scenario_file"]) if row["record"] == "flow"]
        cls.summary = json.loads((root/"service-summary.json").read_text())

    def verify(self, rows=None, summary=None):
        return service.verify_native_rows(rows or self.rows, self.original, self.feedback, self.flows, summary or self.summary, self.plan)

    def test_native_seed129_raw_service_reconstructs_twenty_thousand_attempts(self):
        result = self.verify()
        self.assertEqual(result["application_attempts_verified"], 20000)
        self.assertGreater(result["event_counts"]["ack_queue_replace_before"], 0)

    def test_native_reference_inventory_controls_and_compiled_inputs(self):
        result = service.verify_reference_suite(REPO, self.plan)
        self.assertTrue(result["passed"])
        self.assertEqual((result["compressed_roundtrips"], result["observer_control_file_pairs"], result["accepted_t8_file_pairs"]),
                         (24, 12, 24))

    def test_repeated_original_lookup_preserves_manifest_inventory(self):
        root = REPO/self.case["service_reference_directory"]
        manifest = json.loads((root/"manifest.json").read_text())
        unchanged = copy.deepcopy(manifest)
        first = service.original_artifact(root, manifest, "off-ns3-trace.csv")
        self.assertEqual(first, service.original_artifact(root, manifest, "off-ns3-trace.csv"))
        self.assertEqual(manifest, unchanged)

    def mutate(self, event, field, value, message):
        rows = list(self.rows)
        index = next(index for index, row in enumerate(rows) if row["event"] == event)
        rows[index] = dict(rows[index], **{field: value})
        with self.assertRaisesRegex(ValueError, message):
            self.verify(rows=rows)

    def test_native_service_relabelled_event_index_is_rejected(self):
        self.mutate("app_admission", "event_index", "999999", "identity/order/window")

    def test_native_service_feedback_packet_uid_mutation_is_rejected(self):
        self.mutate("ack_queue_replace_before", "packet_uid", "18446744073709551615", "packet/decision identity")

    def test_native_cancelled_preparation_mutation_is_rejected(self):
        row = next(row for row in self.rows if row["event"] == "mac_cancel_end")
        self.mutate("mac_cancel_end", "preparation_active", "0" if row["preparation_active"] == "1" else "1",
                    "changed prepared reservation")

    def test_native_blocked_attempt_cannot_invent_packet_identity(self):
        rows = list(self.rows)
        index = next(index for index, row in enumerate(rows) if row["event"] == "app_admission" and row["success"] == "0")
        rows[index] = dict(rows[index], sequence="999999")
        with self.assertRaisesRegex(ValueError, "fabricated a packet identity"):
            self.verify(rows=rows)


if __name__ == "__main__":
    unittest.main()
