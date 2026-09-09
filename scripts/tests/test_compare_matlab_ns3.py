"""Evidence integrity and application-identity regression tests (no MATLAB)."""

import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_matlab_ns3 as comparator


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.matlab = self.root / "matlab"
        self.ns3 = self.root / "ns3"
        self.output = self.root / "comparison"
        self.matlab.mkdir()
        self.ns3.mkdir()
        self.matlab_rows = [self.mrow("app_generate", 120, 1), self.mrow("app_receive", 122, 1),
                            self.mrow("app_generate", 135, 2), self.mrow("app_receive", 137, 2)]
        self.ns3_rows = [self.nrow("app_send", 120, 177), self.nrow("nwk_delivery", 121, 177),
                         self.nrow("app_send", 135, 187), self.nrow("nwk_delivery", 136, 187)]
        self.scenario_fields = ["record", "schema", "scenario", "duration_s", "application_profile",
            "mac_profile", "hop_security_profile", "flow_src", "flow_dst", "flow_destination_mode",
            "flow_start_s", "flow_interval_s", "flow_packet_bytes", "flow_dscp"]
        self.scenario_rows = [dict(record="run", schema="csr-opnet-scenario-v1", scenario="case_8", duration_s=200,
            application_profile="current-send-only", mac_profile="current-fine-free-slot",
            hop_security_profile="production-pairwise16"),
            dict(record="flow", schema="csr-opnet-scenario-v1", flow_src=2, flow_dst=1,
                 flow_destination_mode="fixed", flow_start_s=120, flow_interval_s=15, flow_packet_bytes=79, flow_dscp=0)]
        self.diagnostic_rows = [dict(schema="csr-app-admission-diagnostics-v1", scenario="case_8",
            application_profile="current-send-only", flow_index=0, source=2, configured_destination=1,
            destination_mode="fixed", attempts=2, admitted=2, blocked_discovery=0, blocked_topology=0,
            blocked_gateway_route=0, blocked_destination=0, blocked_nsdp=0, first_admitted_s=120, last_admitted_s=135)]
        self.identity = dict(ns3_source_commit=comparator.PIN, flow_limit=2,
            application_profile="current-send-only", mac_profile="current-fine-free-slot",
            hop_security_profile="production-pairwise16", run_options=copy.deepcopy(comparator.RUN_OPTIONS))
        for directory in (self.matlab, self.ns3):
            self.write_csv(directory / "scenario.csv", self.scenario_fields, self.scenario_rows)
        self.identity["scenario_sha256"] = comparator.digest(self.ns3 / "scenario.csv")
        self.summary = dict(Metadata=dict(SourceCommit=comparator.PIN),
            Statistics=dict(Generated=2, Received=2, Dropped=0, Pending=0, ApplicationBytesReceived=128,
                            OmittedTraceRecords=0, OmittedPhyTraceRecords=0),
            Config=dict(DurationSeconds=200, SharedScenario=dict(SourceSHA256=self.identity["scenario_sha256"],
                SourceCommit=comparator.PIN, FlowLimit=2, ApplicationProfile="current-send-only",
                MacProfile="current-fine-free-slot", HopSecurityProfile="production-pairwise16",
                RunOptions=copy.deepcopy(comparator.RUN_OPTIONS))))
        self.refresh()

    @staticmethod
    def mrow(event, time, uid):
        row = dict.fromkeys(comparator.MATLAB_FIELDS, "")
        row.update(TimeSeconds=time, Event=event, NodeId=1 if event == "app_receive" else 2,
                   PeerId=2 if event == "app_receive" else 1, PacketId=uid, ApplicationBytes=64,
                   Dscp=0, HopCount=0, QueueDepth=0)
        return row

    @staticmethod
    def nrow(event, time, uid):
        row = dict.fromkeys(comparator.NS3_FIELDS, "")
        row.update(schema="csr-differential-trace-v1", time_s=time, event=event,
                   node=1 if event == "nwk_delivery" else 2, peer=2 if event == "nwk_delivery" else 1,
                   packet_type="data", src=2, dst=1, sequence=uid, size_bytes=71,
                   success="1" if event == "nwk_delivery" else "", detail="dscp=0" if event == "app_send" else "")
        return row

    @staticmethod
    def write_csv(path, fields, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def write_json(path, data):
        path.write_text(json.dumps(data) + "\n", encoding="utf-8")

    def refresh(self):
        """Regenerate honest file inventories after an intentional fixture edit."""
        self.write_csv(self.matlab / "protocol_trace.csv", comparator.MATLAB_FIELDS, self.matlab_rows)
        for index, row in enumerate(self.ns3_rows):
            row["event_index"] = index
        self.write_csv(self.ns3 / "trace.csv", comparator.NS3_FIELDS, self.ns3_rows)
        self.write_csv(self.ns3 / "app_diagnostics.csv", list(self.diagnostic_rows[0]), self.diagnostic_rows)
        self.write_json(self.matlab / "summary.json", self.summary)
        for directory, schema, filename in ((self.matlab, "csr-matlab-research-case-v1", "case_manifest.json"),
                (self.ns3, "csr-matlab-ns3-reference-case-v1", "reference_manifest.json")):
            data = dict(self.identity, schema=schema, status="completed", execution_completed=True,
                        source_files_stable=True, files=[])
            for path in sorted(directory.iterdir()):
                if path.name == filename:
                    continue
                entry = dict(path=path.name, sha256=comparator.digest(path))
                if path.suffix == ".csv":
                    with path.open(newline="", encoding="utf-8") as stream:
                        entry["row_count"] = len(list(csv.reader(stream))) - 1
                data["files"].append(entry)
            self.write_json(directory / filename, data)

    def compare(self):
        return comparator.compare(self.matlab, self.ns3 / "reference_manifest.json")

    def assert_invalid(self, pattern):
        with self.assertRaisesRegex(comparator.EvidenceError, pattern):
            self.compare()

    def change_manifest(self, directory, key, value):
        name = "case_manifest.json" if directory == self.matlab else "reference_manifest.json"
        path = directory / name
        data = json.loads(path.read_text())
        data[key] = value
        self.write_json(path, data)

    def rehash_file(self, directory, filename):
        name = "case_manifest.json" if directory == self.matlab else "reference_manifest.json"
        path = directory / name
        data = json.loads(path.read_text())
        for entry in data["files"]:
            if entry["path"] == filename:
                entry["sha256"] = comparator.digest(directory / filename)
        self.write_json(path, data)

    def test_runtime_ids_are_not_cross_simulator_identifiers(self):
        report, apps, flows = self.compare()
        self.assertTrue(report["application_equal"])
        self.assertFalse(report["full_protocol_parity"])
        self.assertEqual(apps[0]["matlab_packet_id"], "1")
        self.assertEqual(apps[0]["ns3_sequence"], "177")
        self.assertEqual(apps[0]["ns3_payload_bytes"], 64)
        self.assertEqual(apps[0]["latency_delta_s"], 1)
        self.assertEqual(flows[0]["matlab_delivered_payload_bytes"], 128)

    def test_latency_differences_do_not_gate_application_equality(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = comparator.main(["--matlab", str(self.matlab), "--ns3", str(self.ns3 / "reference_manifest.json"),
                                    "--output", str(self.output), "--require-application-equality"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.output / "comparison.json").read_text())["status"], "application_match")

    def test_different_delivery_sets_report_and_gate(self):
        self.ns3_rows.pop()
        self.refresh()
        report, apps, flows = self.compare()
        self.assertFalse(report["application_equal"])
        self.assertEqual(apps[1]["ns3_status"], "not_observed_delivered")
        self.assertEqual(flows[0]["ns3_delivered"], 1)
        args = ["--matlab", str(self.matlab), "--ns3", str(self.ns3 / "reference_manifest.json"),
                "--output", str(self.output)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(comparator.main(args), 0)
            self.assertEqual(comparator.main(args + ["--require-application-equality"]), 1)

    def test_consistent_different_generated_counts_are_explicit_diagnostics(self):
        self.ns3_rows = self.ns3_rows[:2]
        self.diagnostic_rows[0].update(attempts=1, admitted=1, last_admitted_s=120)
        self.refresh()
        report, apps, _ = self.compare()
        self.assertFalse(report["application_equal"])
        self.assertEqual(apps[1]["ns3_status"], "missing_generation")

    def test_reordered_deliveries_keep_generation_identity(self):
        self.matlab_rows = [self.mrow("app_generate", 120, 1), self.mrow("app_generate", 135, 2),
                            self.mrow("app_receive", 136, 2), self.mrow("app_receive", 138, 1)]
        self.refresh()
        report, apps, _ = self.compare()
        self.assertTrue(report["application_equal"])
        self.assertEqual([row["matlab_latency_s"] for row in apps], [18, 1])

    def test_uint64_identifiers_do_not_pass_through_float(self):
        for row in self.matlab_rows:
            if row["PacketId"] == 1:
                row["PacketId"] = 18446744073709551614
        self.refresh()
        report, apps, _ = self.compare()
        self.assertTrue(report["application_equal"])
        self.assertEqual(apps[0]["matlab_packet_id"], "18446744073709551614")

    def test_late_delivery_reverses_prior_drop(self):
        self.matlab_rows.insert(1, self.mrow("app_drop", 121, 1))
        self.refresh()
        self.assertTrue(self.compare()[0]["application_equal"])

    def test_late_relay_custody_reverses_drop_to_pending(self):
        self.matlab_rows = [self.mrow("app_generate", 120, 1), self.mrow("app_drop", 121, 1),
                            self.mrow("relay_accept", 122, 1), self.mrow("app_generate", 135, 2),
                            self.mrow("app_receive", 137, 2)]
        self.summary["Statistics"].update(Received=1, Pending=1, ApplicationBytesReceived=64)
        self.refresh()
        self.assertEqual(self.compare()[1][0]["matlab_status"], "pending")

    def test_unknown_delivery_uid_is_rejected(self):
        self.ns3_rows[1]["sequence"] = 999
        self.refresh()
        self.assert_invalid("Unknown ns-3 delivery")

    def test_duplicate_generation_is_rejected_even_with_inventory_rehashed(self):
        self.matlab_rows[2]["PacketId"] = 1
        self.refresh()
        self.assert_invalid("Duplicate MATLAB generation")

    def test_duplicate_delivery_is_rejected(self):
        self.ns3_rows.insert(2, self.nrow("nwk_delivery", 122, 177))
        self.refresh()
        self.assert_invalid("Duplicate or early ns-3 delivery")

    def test_same_sequence_for_two_flows_is_rejected(self):
        self.ns3_rows[2].update(sequence=177, src=3, node=3)
        self.refresh()
        self.assert_invalid("Duplicate ns-3 generation")

    def test_payload_change_in_delivery_is_rejected(self):
        self.ns3_rows[1]["size_bytes"] = 79
        self.refresh()
        self.assert_invalid("delivery identity/payload")

    def test_wrong_payload_conversion_is_rejected(self):
        for row in self.ns3_rows:
            row["size_bytes"] = 79
        self.refresh()
        self.assert_invalid("generation payload, DSCP, time")

    def test_generation_time_not_in_shared_schedule_is_rejected(self):
        self.ns3_rows[0]["time_s"] = 120.1
        self.diagnostic_rows[0]["first_admitted_s"] = 120.1
        self.refresh()
        self.assert_invalid("generation payload, DSCP, time")

    def test_nonfinite_time_is_rejected(self):
        self.matlab_rows[0]["TimeSeconds"] = "NaN"
        self.refresh()
        self.assert_invalid("nonfinite")

    def test_backwards_trace_time_is_rejected(self):
        self.matlab_rows[1]["TimeSeconds"] = 119
        self.refresh()
        self.assert_invalid("moves backwards")

    def test_source_pin_profile_and_incomplete_status_are_rejected(self):
        for key, value, message in (("ns3_source_commit", "0" * 40, "foreign ns-3"),
                                   ("application_profile", "legacy-no-dscp", "case/profile mismatch"),
                                   ("status", "failed", "not completed"),
                                   ("source_files_stable", False, "source_files_stable"),
                                   ("execution_completed", False, "execution_completed")):
            with self.subTest(key=key):
                self.refresh()
                self.change_manifest(self.matlab, key, value)
                self.assert_invalid(message)

    def test_runtime_options_cannot_silently_enable_other_models(self):
        options = dict(comparator.RUN_OPTIONS, opnetAppGating=True)
        self.change_manifest(self.ns3, "run_options", options)
        self.assert_invalid("unsupported run option")

    def test_hash_mismatch_is_rejected(self):
        with (self.matlab / "protocol_trace.csv").open("a") as stream:
            stream.write("\n")
        self.assert_invalid("SHA-256 mismatch")

    def test_row_count_mismatch_is_rejected_even_when_hash_matches(self):
        path = self.matlab / "case_manifest.json"
        data = json.loads(path.read_text())
        for item in data["files"]:
            if item["path"] == "protocol_trace.csv":
                item["row_count"] += 1
        self.write_json(path, data)
        self.assert_invalid("row_count mismatch")

    def test_missing_trace_rows_cannot_be_hidden_by_rehash(self):
        self.matlab_rows.pop()
        self.refresh()
        self.assert_invalid("summary Received disagrees")

    def test_missing_ns3_send_cannot_be_hidden_by_rehash(self):
        self.ns3_rows = self.ns3_rows[:2]
        self.diagnostic_rows[0]["last_admitted_s"] = 120
        self.refresh()
        self.assert_invalid("admitted counts disagree")

    def test_noncontiguous_ns3_event_indices_are_rejected(self):
        self.ns3_rows[1]["event_index"] = 20
        self.write_csv(self.ns3 / "trace.csv", comparator.NS3_FIELDS, self.ns3_rows)
        self.rehash_file(self.ns3, "trace.csv")
        self.assert_invalid("Noncontiguous ns-3 event_index")

    def test_missing_csv_header_is_rejected(self):
        rows = [{key: value for key, value in row.items() if key != "HopCount"} for row in self.matlab_rows]
        self.write_csv(self.matlab / "protocol_trace.csv", comparator.MATLAB_FIELDS[:-1], rows)
        self.rehash_file(self.matlab, "protocol_trace.csv")
        self.assert_invalid("missing CSV columns")

    def test_partial_csv_row_is_rejected(self):
        path = self.matlab / "protocol_trace.csv"
        with path.open("a") as stream:
            stream.write("140,app_receive,1\n")
        self.rehash_file(self.matlab, "protocol_trace.csv")
        self.assert_invalid("malformed or truncated CSV row")

    def test_recorded_ns3_observation_totals_are_checked(self):
        self.change_manifest(self.ns3, "observations", {"app_send": 2, "nwk_delivery": 3})
        self.assert_invalid("nwk_delivery observations disagree")

    def test_failed_execution_cannot_claim_completed_status(self):
        self.change_manifest(self.ns3, "exit_code", 1)
        self.assert_invalid("execution failed")

    def test_omitted_trace_counters_are_rejected(self):
        for key in ("OmittedTraceRecords", "OmittedPhyTraceRecords"):
            with self.subTest(key=key):
                self.summary["Statistics"][key] = 1
                self.refresh()
                self.assert_invalid("omitted records")
                self.summary["Statistics"][key] = 0

    def test_summary_provenance_mismatch_is_rejected(self):
        self.summary["Config"]["SharedScenario"]["SourceSHA256"] = "0" * 64
        self.refresh()
        self.assert_invalid("summary provenance mismatch")

    def test_schema_and_empty_evidence_are_rejected(self):
        self.ns3_rows[0]["schema"] = "invented-v2"
        self.refresh()
        self.assert_invalid("Wrong ns-3 trace schema")
        self.ns3_rows = []
        self.refresh()
        self.assert_invalid("Empty ns-3 trace")

    def test_duplicate_json_keys_are_rejected(self):
        path = self.matlab / "case_manifest.json"
        contents = path.read_text()
        path.write_text('{"status":"completed",' + contents[1:])
        self.assert_invalid("duplicate JSON key")

    def test_unsafe_inventory_path_is_rejected(self):
        path = self.matlab / "case_manifest.json"
        data = json.loads(path.read_text())
        data["files"][0]["path"] = "../outside.csv"
        self.write_json(path, data)
        self.assert_invalid("Unsafe inventory path")

    def test_invalid_evidence_replaces_previous_success_report(self):
        args = ["--matlab", str(self.matlab), "--ns3", str(self.ns3 / "reference_manifest.json"),
                "--output", str(self.output)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(comparator.main(args), 0)
            self.change_manifest(self.matlab, "status", "failed")
            self.assertEqual(comparator.main(args), 2)
        report = json.loads((self.output / "comparison.json").read_text())
        self.assertEqual(report["status"], "invalid_evidence")
        with (self.output / "applications.csv").open(newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])


if __name__ == "__main__":
    unittest.main()
