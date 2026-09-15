"""Failure-sensitive gates for the ns-3 ACK service reference tool."""
import copy
import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("t9_ns3_test", ROOT / "scripts/run_tranche9_ns3_service.py")
T9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T9)


class TestTranche9Ns3Service(unittest.TestCase):
    def rows(self):
        kinds = ("app_admission", "hop_admission", "hop_completion", "nwk_nsdp_release", "mac_slot_tick",
                 "ack_queue_enqueue_after", "ack_queue_replace_before", "mac_prepare_after", "mac_state")
        result = []
        for index, event in enumerate(kinds, 1):
            row = dict.fromkeys(T9.FIELDS, "")
            row.update(schema=T9.SCHEMA, event_index=str(index), time_s=str(300 + index/1000),
                       event=event, node="1", mac_state="search")
            result.append(row)
        return result

    def write(self, path, rows):
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=T9.FIELDS)
            w.writeheader()
            w.writerows(rows)

    def test_native_lowercase_states_and_half_open_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"service.csv"
            rows = self.rows()
            self.write(path, rows)
            self.assertEqual(T9.service_summary(path, [300,320],100000)["rows"],len(rows))
            rows[-1]["time_s"] = "320"
            self.write(path, rows)
            with self.assertRaisesRegex(ValueError,"window"):
                T9.service_summary(path,[300,320],100000)

    def test_missing_event_identity_and_order_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"service.csv"
            for field, value in (("event_index","20"),("node",""),("time_s","nan"),("mac_state","garbage")):
                rows=self.rows();rows[-1][field]=value;self.write(path,rows)
                with self.subTest(field=field),self.assertRaises(ValueError):
                    T9.service_summary(path,[300,320],100000)

    def test_required_admission_surface_cannot_be_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"service.csv";rows=self.rows();rows[0]["event"]="other"
            self.write(path,rows)
            with self.assertRaisesRegex(ValueError,"required observation"):
                T9.service_summary(path,[300,320],100000)

    def test_real_plan_preserves_every_parent_input(self):
        plan=T9.T7.load_json(T9.PLAN);T9.verify_plan(plan)
        mutated=copy.deepcopy(plan);mutated["cases"][0]["duration_s"]-=1
        with self.assertRaisesRegex(ValueError,"accepted T8 input"):
            T9.verify_plan(mutated)

    def test_noncompact_or_reordered_case_is_rejected(self):
        plan=T9.T7.load_json(T9.PLAN)
        plan["cases"][0]["storage_key"]="long-name"
        with self.assertRaises(ValueError):T9.verify_plan(plan)

    def test_closed_compression_roundtrip_checks_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/"ns3-service.csv";path.write_bytes(b"original\n")
            item=T9.T7.compress(path)
            record={"files":[{k:item[k] for k in ("path","bytes","sha256")}],
                    "compressed_artifacts":[item],"control_compressed_artifacts":[],
                    "nonperturbation":{"compared_files":[]},"accepted_t8_anchor":{"compared_files":[]}}
            T9.verify_closed_case(root,record)
            record["compressed_artifacts"][0]["original_sha256"]="0"*64
            with self.assertRaisesRegex(ValueError,"roundtrip"):
                T9.verify_closed_case(root,record)


if __name__ == "__main__":unittest.main()
