"""Failure gates for matched stimuli and honest source outcome attribution."""

import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tranche6_reference", ROOT / "scripts/run_tranche6_ns3_reference.py")
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)


def row(event, time, **values):
    values = {({"source": "src", "destination": "dst"}.get(key, key)): value
              for key, value in values.items()}
    return {"schema": "csr-differential-trace-v1", "event_index": "0",
            "event": event, "time_s": str(time), "node": "3", "peer": "",
            "src": "", "dst": "", "sequence": "", "size_bytes": "",
            "reason": "", **{key: str(value) for key, value in values.items()}}


def trace(*extra):
    rows = [row("app_send", time, source=3, destination=1, sequence=index + 1,
                size_bytes=71) for index, time in enumerate((450, 486, 522, 558, 594))]
    rows += [row("manual_discovery", time, node=node)
             for time, node in ((10, 1), (45, 2), (80, 3), (315, 1), (320, 2),
                                (325, 3), (576, 1), (581, 2), (586, 3))]
    rows += [row("link_disable", 405, node=2), row("link_enable", 540, node=2), *extra]
    rows.sort(key=lambda value: float(value["time_s"]))
    for index, item in enumerate(rows):
        item["event_index"] = str(index)
    return rows


def snapshots():
    return [{"time_s": "900", "node": str(node), "nwk_queue": "0",
             "hop_pending_data": "0", "hop_resend_queue": "0", "mac_queue": "0"}
            for node in (1, 2, 3)]


class TestMatchedOutageReference(unittest.TestCase):
    def test_all_nine_cases_keep_identical_stimuli_except_parameter_and_seed(self):
        catalog = REFERENCE.case_catalog()
        self.assertEqual(len(catalog), 9)
        self.assertEqual(len({case["name"] for case in catalog}), 9)
        contracts = [REFERENCE.scenario_contract(case) for case in catalog]
        for contract in contracts:
            self.assertEqual(contract["application"]["times_seconds"], [450, 486, 522, 558, 594])
            self.assertEqual(contract["blackout"]["start_seconds"], 405)
            self.assertEqual(contract["blackout"]["end_seconds"], 540)
            self.assertFalse(contract["radio"]["custom_phy_error_model"])
            self.assertFalse(contract["numerical_parity_certified"])
        normalized = [{k: v for k, v in c.items() if k not in
                       ("name", "seed", "freshness_seconds")} for c in contracts]
        self.assertTrue(all(c == normalized[0] for c in normalized))
        with self.assertRaisesRegex(ValueError, "bounded"):
            REFERENCE.scenario_contract({"name": "unscheduled", "seed": 1, "freshness_seconds": 60})

    def test_later_delivery_overrides_earlier_local_hop_exhaustion(self):
        rows = trace(row("hop_completion", 500, source=3, destination=1, sequence=1,
                         node=3, reason="no_ack"),
                     row("nwk_delivery", 602, source=3, destination=1, sequence=1, node=1))
        observed, apps = REFERENCE.analyze_trace(rows, snapshots())
        self.assertEqual(observed["app_delivered_unique"], 1)
        self.assertEqual(observed["undelivered_with_retry_exhaustion"], 0)
        self.assertEqual(observed["hop_no_ack_completions"], 1)
        self.assertEqual(apps[0]["outcome"], "delivered")
        self.assertEqual(apps[0]["latency_s"], 152)

    def test_missing_terminal_evidence_stays_unresolved_despite_empty_queues(self):
        observed, apps = REFERENCE.analyze_trace(trace(), snapshots())
        self.assertEqual(observed["undelivered_without_terminal_trace"], 5)
        self.assertEqual(observed["undelivered_with_retry_exhaustion"], 0)
        compact = REFERENCE.compact_case_summary(REFERENCE.case_catalog()[0], observed)
        self.assertEqual(compact["dropped"], "unknown")
        self.assertEqual(compact["pending"], "unknown")
        self.assertIsNone(compact["first_delivery_s"])

    def test_duplicate_delivery_is_visible_without_double_counting(self):
        observed, _ = REFERENCE.analyze_trace(trace(
            row("nwk_delivery", 560, source=3, destination=1, sequence=1, node=1),
            row("nwk_delivery", 565, source=3, destination=1, sequence=1, node=1)), snapshots())
        self.assertEqual(observed["app_delivered_unique"], 1)
        self.assertEqual(observed["app_delivery_events"], 2)
        self.assertEqual(observed["duplicate_app_deliveries"], 1)

    def test_blackout_gate_allows_disabled_source_or_receiver_but_not_end_boundary(self):
        for node, source in ((2, 3), (1, 2)):
            REFERENCE.analyze_trace(trace(row("post_phy_eligibility_drop", 405,
                                             node=node, source=source)), snapshots())
        for time, node, source in ((404.999, 2, 3), (540, 1, 2), (500, 1, 3)):
            with self.subTest(time=time, node=node, source=source):
                with self.assertRaisesRegex(ValueError, "two-endpoint blackout"):
                    REFERENCE.analyze_trace(trace(row("post_phy_eligibility_drop", time,
                                                     node=node, source=source)), snapshots())

    def test_wrong_schedule_size_and_incomplete_stop_snapshot_rejected(self):
        for field, bad_value in (("time_s", "451"), ("size_bytes", "79"), ("src", "2")):
            rows = trace()
            next(r for r in rows if r["event"] == "app_send")[field] = bad_value
            with self.subTest(field=field), self.assertRaises(ValueError):
                REFERENCE.analyze_trace(rows, snapshots())
        with self.assertRaisesRegex(ValueError, "stop-time"):
            REFERENCE.analyze_trace(trace(), snapshots()[:2])

    def test_compression_preserves_bytes_and_is_reproducible(self):
        content = b"time_s,event\n405,link_disable\n540,link_enable\n"
        with tempfile.TemporaryDirectory() as directory:
            files = []
            for name in ("first.csv", "second.csv"):
                path = Path(directory) / name
                path.write_bytes(content)
                compressed = REFERENCE.compress_file(path)
                self.assertFalse(path.exists())
                self.assertEqual(gzip.decompress(compressed.read_bytes()), content)
                files.append(compressed.read_bytes())
            self.assertEqual(files[0], files[1])


if __name__ == "__main__":
    unittest.main()
