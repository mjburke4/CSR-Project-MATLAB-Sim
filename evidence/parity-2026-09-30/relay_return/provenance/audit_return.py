#!/usr/bin/env python3
"""Audit the returned relay-custody preflights against the issued sealed kit.

Run from the workspace root. Optional arguments: --return-zip, --kit-zip,
--data and --output. This validates returned evidence; it does not run MATLAB.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def array(value):
    return value if isinstance(value, list) else [value]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--return-zip", type=Path, default=Path("upload/out_node8_20260930_094958.zip"))
    parser.add_argument("--kit-zip", type=Path, default=Path("relay_return/issued_v1_tests.zip"))
    parser.add_argument("--data", type=Path, default=Path("relay_return/data"))
    parser.add_argument("--output", type=Path, default=Path("relay_return/provenance/audit.json"))
    args = parser.parse_args()
    report = load(args.data / "report.json")
    provenance = load(args.data / "provenance.json")
    with zipfile.ZipFile(args.return_zip) as returned:
        assert returned.testzip() is None
        members = [item for item in returned.infolist() if not item.is_dir()]
        assert len({item.filename for item in members}) == len(members)
        # The owner archive uses paths relative to the output folder.
        for item in members:
            assert returned.read(item) == (args.data / item.filename).read_bytes(), item.filename
    with zipfile.ZipFile(args.kit_zip) as kit:
        assert kit.testzip() is None
        manifest_bytes = kit.read("node8case/FILES.json")
        manifest = json.loads(manifest_bytes)
        assert digest(manifest_bytes) == provenance["manifest_sha256"]
        assert manifest == provenance["manifest"]
        sealed = {item["path"]: item for item in manifest["files"]}
        assert len(sealed) == len(manifest["files"]) == 496
        for path, item in sealed.items():
            content = kit.read("node8case/" + path)
            assert digest(content) == item["sha256"] and len(content) == item["bytes"], path
        resolved = provenance["resolved_matlab_files"]
        assert len({item["name"] for item in resolved}) == len(resolved) == 162
        for item in resolved:
            relative = item["path"].replace("\\", "/").split("/node8case/", 1)[1]
            assert relative in sealed
            assert item["sha256"] == sealed[relative]["sha256"], relative

    runtime = {"version": "25.1.0.2943329 (R2025a)", "release": "2025a", "computer": "PCWIN64"}
    assert report["runtime"] == provenance["runtime"] == runtime
    prior = [item for item in report["preflights"] if item["name"] != "relay_custody"]
    assert len(prior) == 17 and all(item["passed"] for item in prior)
    custody = load(args.data / "relay_custody_preflight/relay_custody_preflight.json")
    assert custody["completed"] and custody["attempted_checks"] == 22
    assert custody["passed_checks"] == 20 and custody["failed_checks"] == 2
    failed = [item["name"] for item in custody["checks"] if not item["passed"]]
    assert failed == [prefix + "_queue_full_rejection_then_same_sequence_retry" for prefix in ("production", "candidate")]
    behavioral = {}
    for prefix in ("production", "candidate"):
        capture = load(args.data / f"relay_custody_preflight/{prefix}_captured_nsdp_25_26_27/public_custody_trace.json")
        assert all(item["passed"] for item in capture["checks"])
        checks = capture["checks"]
        counts = [checks[0]["actual"]["accepted_copies"], checks[1]["actual"]["accepted_copies"], checks[2]["actual"]["state"]["accepted_copies"]]
        assert counts == [25, 26, 27]
        first, second = checks[2]["actual"]["first"], checks[2]["actual"]["second"]
        assert (first["SourceId"], first["Id"]) == (second["SourceId"], second["Id"]) == (7, 2873)
        assert first["NwkCustodyNodeId"] == second["NwkCustodyNodeId"] == 4
        assert [first["NwkCustodyId"], second["NwkCustodyId"]] == [26, 27]
        fifo = load(args.data / f"relay_custody_preflight/{prefix}_fifo_distinct_sequences_and_ack_ownership/public_custody_trace.json")
        assert all(item["passed"] for item in fifo["checks"])
        assert fifo["checks"][3]["actual"] == [7, 7, 8]
        final = fifo["checks"][-1]["actual"]
        assert final["network"]["PendingCustody"] == 0 and final["releases"] == final["terminals"] == 3
        behavioral[prefix] = {"accepted_copy_counts": counts, "incoming_application": {"source": 7, "id": 2873}, "local_custody_ids": [26, 27], "fifo_sources": [7, 7, 8], "independent_ack_releases": 3, "final_pending_custody": 0}
    accounting = load(args.data / "integrated_accounting/integrated_accounting_preflight.json")
    assert accounting["completed"] and accounting["passed"] and accounting["passed_groups"] == 4 and accounting["failed_groups"] == 0
    assert [item["name"] for item in accounting["checks"]] == ["cutoff", "final", "relay", "siblings"]
    siblings = accounting["checks"][-1]["details"]
    assert siblings["execution_complete"] and siblings["final_checks_complete"] and all(item["passed"] for item in siblings["checks"])
    sibling_checks = {item["label"]: item for item in siblings["checks"]}
    checkpoint_summary = {}
    for label in ("two_retained", "one_failed", "stale_failure", "lower_hop_survives", "last_failed", "same_hop_recovered", "delivered_once"):
        actual = sibling_checks["sibling accounting " + label]["actual"]
        stats = actual["statistics"]
        checkpoint_summary[label] = {"custody_counts": actual["custody_counts"], **{key: stats[key] for key in ("Generated", "Received", "Dropped", "RelayAccepted", "ApplicationBytesReceived", "LatencySumSeconds")}}
    assert checkpoint_summary["one_failed"]["Dropped"] == checkpoint_summary["lower_hop_survives"]["Dropped"] == 0
    assert checkpoint_summary["last_failed"]["Dropped"] == 1
    assert checkpoint_summary["same_hop_recovered"]["Dropped"] == 0
    assert checkpoint_summary["delivered_once"]["Received"] == 1
    assert checkpoint_summary["delivered_once"]["ApplicationBytesReceived"] == 185
    assert checkpoint_summary["delivered_once"]["LatencySumSeconds"] == 4.5
    case = load(args.data / "S132_1200/case_summary.json")
    assert report["cases"] == case
    assert not case["completed"] and case["diagnostic_status"] == "prerequisite_failed" and case["reached_time_s"] is None and case["wall_seconds"] == 0
    assert case["import_preflight"]["passed"]
    case_files = sorted(str(path.relative_to(args.data / "S132_1200")) for path in (args.data / "S132_1200").rglob("*") if path.is_file())
    assert case_files == ["case_summary.json", "import_preflight/preflight.json", "import_preflight/random_requests.jsonl"]
    assert not report["numerical_parity_established"]
    identities = ["+ac/DiscoveryMembershipNwk.m", "model/+csr/+nwk/Layer.m", "+ac/TerminalSimulation.m", "model/+csr/+sim/NetworkSimulation.m", "+ac/relayCustodyPreflight.m", "+ac/RelayCustodyProbe.m"]
    result = {
        "schema": "csr-relay-custody-return-audit-v1", "audit_passed": True,
        "return_archive": {"name": args.return_zip.name, "sha256": digest(args.return_zip.read_bytes()), "bytes": args.return_zip.stat().st_size, "members": len(members), "crc_passed": True, "extracted_bytes_exact": True},
        "issued_archive": {"name": args.kit_zip.name, "sha256": digest(args.kit_zip.read_bytes()), "manifest_sha256": digest(manifest_bytes), "sealed_files_verified": len(sealed), "resolved_matlab_hashes_verified": len(resolved)},
        "runtime": runtime, "source_identity": {path: sealed[path]["sha256"] for path in identities},
        "production_model_changed": provenance["production_model_changed"], "simulation_class": provenance["simulation_class"],
        "prior_preflights_passed": [item["name"] for item in prior],
        "custody": {"attempted": 22, "passed": 20, "failed": failed, "successful_behavioral_groups": [item["name"] for item in custody["checks"] if item["passed"]], "independently_checked_public_trace_values": behavioral},
        "integrated_accounting": {"passed_groups": 4, "groups": [item["name"] for item in accounting["checks"]], "sibling_checkpoints": checkpoint_summary},
        "replay": {"seed": case["seed"], "requested_stop_seconds": case["requested_stop_seconds"], "import_passed": True, "started": False, "status": case["diagnostic_status"], "reached_time_s": None, "files": case_files},
        "scope": "Owner-executed component evidence verified against issued source. No new network replay or parity result exists; raw drop accounting remains provisional, not a full MAC-copy liveness ledger."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"audit_passed": True, "runtime": runtime, "sealed_files": len(sealed), "resolved_sources": len(resolved), "prior_groups_passed": 17, "custody_checks_passed": "20/22", "accounting_groups_passed": "4/4", "network_started": False, "receipt": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
