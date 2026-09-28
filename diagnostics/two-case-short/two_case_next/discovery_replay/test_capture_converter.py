#!/usr/bin/env python3
"""Verify receiver input ownership on the bundled immutable native capture.

This checks binding and rejects trace mutations. It does not execute MATLAB
or claim that receiver parity has passed.
"""
import csv
import json
import shutil
import tempfile
from pathlib import Path

from convert_capture_draws import run, file_hash

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native/seed131"


def main():
    with tempfile.TemporaryDirectory(prefix="discovery-converter-") as scratch:
        root = Path(scratch)
        for name in ("capture.jsonl", "ns3-trace.csv"):
            shutil.copyfile(NATIVE / name, root / name)
        shutil.copyfile(NATIVE / "mac_csv/inputs.csv", root / "mac_inputs.csv")
        shutil.copyfile(NATIVE / "mac_csv/tx.csv", root / "mac_tx.csv")
        capture, requests, mac_tx = (root / "capture.jsonl", root / "mac_inputs.csv", root / "mac_tx.csv")
        output = root / "phy_draws.csv"
        report = run(capture, HERE / "fixture", output, requests, mac_tx)
        assert report["capture_tx_count"] == 162
        assert report["draw_count"] == 223
        assert report["external_receiver_input_count"] == 122
        assert report["receiver_actual_state_count"] == 412
        assert report["observer_wake_sleep_crosscheck_count"] == 122
        assert file_hash(output) == file_hash(NATIVE / "phy_draws.csv")
        with (root / "receiver_inputs.csv").open(newline="") as stream:
            external = list(csv.DictReader(stream))
        with (root / "receiver_state_audit.csv").open(newline="") as stream:
            audit = list(csv.DictReader(stream))
        assert all(r["node"] == "2" for r in external)
        assert all(r["origin"] in ("external_wake", "external_sleep") for r in external)
        target_end = "72308832444"
        assert not any(r["time_ns"] == target_end and r["node"] == "5" for r in external)
        assert any(r["time_ns"] == target_end and r["node"] == "5" and
                   r["origin"] == "phy_receive_completion" for r in audit)
        # The native request hook can add redundant refresh calls. Such calls
        # remain audit evidence and cannot create new PHY state inputs.
        external_hash = file_hash(root / "receiver_inputs.csv")
        with requests.open(newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            calls = list(reader)
        duplicate = next(dict(r) for r in calls if r["kind"] == "receiver_state" and
                         r["node"] == "5" and r["value"] == "search" and
                         25_000_000_000 <= int(r["time_ns"]) < 85_000_000_000)
        calls.append(duplicate)
        with requests.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fields)
            writer.writeheader()
            writer.writerows(calls)
        updated = run(capture, HERE / "fixture", output, requests, mac_tx)
        assert updated["receiver_request_audit_count"] == report["receiver_request_audit_count"] + 1
        assert file_hash(root / "receiver_inputs.csv") == external_hash
        # A changed native actual transition must never be accepted against
        # the immutable trace fixture, even if request values look harmless.
        trace = root / "ns3-trace.csv"
        original = trace.read_text()
        with trace.open(newline="") as stream:
            reader = csv.DictReader(stream)
            trace_fields = reader.fieldnames
            trace_rows = list(reader)
        target = next(r for r in trace_rows if r["event"] == "mac_state" and
                      r["node"] == "5" and round(float(r["time_s"]) * 1e9) == int(target_end))
        target["detail"] = "idle"
        with trace.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, trace_fields)
            writer.writeheader()
            writer.writerows(trace_rows)
        try:
            run(capture, HERE / "fixture", output, requests, mac_tx)
        except AssertionError as error:
            assert "state history differs" in str(error)
        else:
            raise AssertionError("changed native actual state history was accepted")
        trace.write_text(original)
        events = [json.loads(line) for line in capture.read_text().splitlines()]
        next(r for r in events if r["event"] == "tx_start")["detail"]["payload_bytes"] = "9999"
        capture.write_text("".join(json.dumps(r) + "\n" for r in events))
        try:
            run(capture, HERE / "fixture", output, requests, mac_tx)
        except AssertionError:
            pass
        else:
            raise AssertionError("changed native TX size was accepted")
    print("capture ownership/binding regression passed; corrected MATLAB replay remains pending")


if __name__ == "__main__":
    main()
