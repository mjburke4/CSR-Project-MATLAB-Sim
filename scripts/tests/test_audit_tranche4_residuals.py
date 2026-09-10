"""Final-envelope association checks; synthetic fixtures are not MATLAB runs."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_tranche4_residuals as audit


class ResidualAuditTests(unittest.TestCase):
    def setUp(self):
        self.application = dict(matlab_packet_id=7, ns3_sequence=900,
                                source=3, destination=1, ordinal=1)
        # The final physical frame is ACK-headed, but carries relayed DATA.
        self.matlab = [
            dict(Event="tx_start", TimeSeconds="10", NodeId="2", PacketId="48"),
            dict(Event="hop_sent", TimeSeconds="10", NodeId="2", PeerId="1", PacketId="7"),
            dict(Event="app_receive", TimeSeconds="10.2", NodeId="1", PacketId="7")]
        header = dict(packet_type="ack", src="2", dst="3", sequence="4",
                      rate_kbps="8", size_bytes="147")
        self.ns3 = [dict(header, event="tx_start", time_s="10.026", node="2"),
                    dict(header, event="rx_accept", time_s="10.226", node="1", peer="2"),
                    dict(event="nwk_delivery", time_s="10.226", node="1", peer="2", sequence="900")]

    def test_aggregate_head_uses_physical_identity(self):
        result = audit.final_hop(self.application, self.matlab, self.ns3)
        self.assertEqual(result["ns3_final_envelope_head"], "ack")
        self.assertEqual(result["slot_delta"], -2)
        self.assertAlmostEqual(result["final_transit_delta_s"], 0)

    def test_retransmission_selects_latest_physical_attempt(self):
        rows = [dict(self.ns3[0], time_s="8")] + self.ns3
        result = audit.final_hop(self.application, self.matlab, rows)
        self.assertEqual(result["ns3_final_tx_s"], 10.026)

    def test_duplicate_matlab_envelope_is_rejected(self):
        rows = self.matlab + [copy.deepcopy(self.matlab[0])]
        with self.assertRaisesRegex(audit.comparison.EvidenceError, "physical envelope"):
            audit.final_hop(self.application, rows, self.ns3)

    def test_wrong_ns3_header_sequence_is_rejected(self):
        rows = copy.deepcopy(self.ns3)
        rows[0]["sequence"] = "5"
        with self.assertRaisesRegex(audit.comparison.EvidenceError, "physical envelope"):
            audit.final_hop(self.application, self.matlab, rows)

    def test_modified_accepted_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("record.csv", "a,b\n1,2\n")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            with audit.checked_archive(path, expected):
                pass
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaisesRegex(audit.comparison.EvidenceError, "hash mismatch"):
                audit.checked_archive(path, expected)


if __name__ == "__main__":
    unittest.main()
