#!/usr/bin/env python3
"""Reconstruct final-hop timing from the accepted Tranche 4 evidence.

This is a bounded retrospective diagnostic, not a new simulator run or a
general trace-equivalence gate. Application matching reuses the strict T4
comparator. Final envelopes are joined within each runtime before comparison.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

import compare_matlab_ns3 as comparison

CASES = ("two_node_8", "two_node_128", "line_3_8", "high_rate_500", "high_rate_1000")
TOLERANCE = 1e-6  # ns-3 exports decimal times to nanosecond precision.


def one(rows, label):
    comparison.require(len(rows) == 1, f"{label}: expected one match, got {len(rows)}")
    return rows[0]


def near(left, right):
    return abs(float(left) - float(right)) <= TOLERANCE


def final_hop(application, matlab, ns3):
    """Associate a delivered app with its final OTA envelope, failing ambiguity.

    A MATLAB hop_sent carries the app ID; the corresponding tx_start carries
    the physical ID. ns-3 nwk_delivery carries the app tag; its preceding
    rx_accept carries the physical header identity, including aggregate heads.
    Therefore a relay ACK-headed aggregate is not mistaken for bare DATA.
    """
    packet = str(application["matlab_packet_id"])
    sequence = str(application["ns3_sequence"])
    destination = str(application["destination"])
    mr = one([r for r in matlab if r["Event"] == "app_receive"
              and r["PacketId"] == packet and r["NodeId"] == destination], "MATLAB delivery")
    mt = float(mr["TimeSeconds"])
    sends = [r for r in matlab if r["Event"] == "hop_sent" and r["PacketId"] == packet
             and r["PeerId"] == destination and float(r["TimeSeconds"]) <= mt]
    comparison.require(bool(sends), "Missing MATLAB final-hop send")
    last = max(float(r["TimeSeconds"]) for r in sends)
    sent = one([r for r in sends if near(r["TimeSeconds"], last)], "MATLAB final-hop send")
    mx = one([r for r in matlab if r["Event"] == "tx_start"
              and r["NodeId"] == sent["NodeId"] and near(r["TimeSeconds"], last)],
             "MATLAB physical envelope")
    delivery_index = [i for i, r in enumerate(ns3) if r["event"] == "nwk_delivery"
                      and r["sequence"] == sequence and r["node"] == destination]
    index = one(delivery_index, "ns-3 delivery")
    nr = ns3[index]
    nt = float(nr["time_s"])
    receive = one([r for r in ns3[:index] if r["event"] == "rx_accept"
                   and r["node"] == destination and r["peer"] == nr["peer"]
                   and near(r["time_s"], nt)], "ns-3 final physical reception")
    identity = ("packet_type", "src", "dst", "sequence", "rate_kbps", "size_bytes")
    starts = [r for r in ns3[:index] if r["event"] == "tx_start"
              and r["node"] == receive["peer"] and float(r["time_s"]) < nt
              and all(r[k] == receive[k] for k in identity)]
    comparison.require(bool(starts), "Missing ns-3 physical envelope")
    start_time = max(float(r["time_s"]) for r in starts)
    nx = one([r for r in starts if near(r["time_s"], start_time)], "ns-3 final envelope")
    mstart = float(mx["TimeSeconds"])
    nstart = float(nx["time_s"])
    delta = mt - nt
    slots = round(delta / 0.013)
    return {
        "source": application["source"], "destination": application["destination"],
        "ordinal": application["ordinal"], "matlab_application_id": packet,
        "ns3_application_sequence": sequence, "matlab_final_sender": int(mx["NodeId"]),
        "ns3_final_sender": int(nx["node"]), "ns3_final_envelope_head": nx["packet_type"],
        "matlab_delivery_s": mt, "ns3_delivery_s": nt,
        "matlab_final_tx_s": mstart, "ns3_final_tx_s": nstart,
        "matlab_final_transit_s": mt - mstart, "ns3_final_transit_s": nt - nstart,
        "delivery_delta_s": delta, "final_tx_delta_s": mstart - nstart,
        "final_transit_delta_s": (mt - mstart) - (nt - nstart),
        "slot_delta": slots, "slot_residual_s": delta - slots * 0.013,
    }


def archive_rows(archive, name):
    return list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"))))


def checked_archive(path, expected):
    comparison.require(comparison.digest(path) == expected, "Accepted archive hash mismatch")
    return zipfile.ZipFile(path)


def committed_digest(root, commit, path):
    data = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)
    return hashlib.sha256(data).hexdigest()


def published_code_identity(root, accepted):
    path = root / "evidence/tranche-4-publication.json"
    publication = json.loads(path.read_text())
    local = accepted["associated_code_commit"]
    comparison.require(publication["owner_validated_local_code_commit"] == local,
                       "Publication record does not map accepted code")
    published = publication["owner_validated_published_code_commit"]
    mapping = one([r for r in publication["commit_mapping"] if r["local_commit"] == local
                   and r["published_commit"] == published], "Published code mapping")
    tree = subprocess.check_output(["git", "rev-parse", f"{published}^{{tree}}"], cwd=root).decode().strip()
    comparison.require(tree == mapping["tree"], "Published tree disagrees with recorded validated tree")
    return {"local_commit": local, "published_commit": published, "tree": tree,
            "publication_record_sha256": comparison.digest(path),
            "published_tree_matches_recorded_validated_tree": True}


def audit(root, ns3_root):
    acceptance_path = root / "evidence/tranche-4-portable-acceptance.json"
    accepted = json.loads(acceptance_path.read_text())
    published_identity = published_code_identity(root, accepted)
    archive_path = root / "evidence" / accepted["uploaded_archive"]["path"]
    result = {"schema": "csr-matlab-tranche-5-residual-audit-v1",
              "execution": "Python retrospective audit of accepted R2025a and retained ns-3 traces",
              "matlab_execution_performed": False, "full_protocol_parity": False,
              "accepted_matlab_code_commit": accepted["associated_code_commit"],
              "accessed_matlab_source_identity": published_identity,
              "ns3_source_commit": comparison.PIN,
              "acceptance_sha256": comparison.digest(acceptance_path),
              "accepted_archive_sha256": accepted["uploaded_archive"]["sha256"],
              "time_tolerance_s": TOLERANCE, "cases": [], "research": []}
    with checked_archive(archive_path, result["accepted_archive_sha256"]) as archive, \
            tempfile.TemporaryDirectory(prefix="csr-t4-audit-") as temporary:
        for case in CASES:
            prefix = "shared/" + case + "/"
            target = Path(temporary) / case
            target.mkdir()
            for name in archive.namelist():
                if name.startswith(prefix):
                    relative = name[len(prefix):]
                    comparison.require(relative and Path(relative).name == relative,
                                       "Unexpected nested shared evidence path")
                    (target / relative).write_bytes(archive.read(name))
            reference = root / "evidence/tranche-4-ns3-reference" / case / "manifest.json"
            report, apps, _ = comparison.compare(target, reference)
            comparison.require(report["application_equal"], "Archived application mismatch")
            matlab = archive_rows(archive, prefix + "protocol_trace.csv")
            with (reference.parent / "trace.csv").open(newline="") as stream:
                ns3 = list(csv.DictReader(stream))
            rows = [final_hop(app, matlab, ns3) for app in apps]
            result["cases"].append({"case": case, "matlab_manifest_sha256":
                                    report["matlab_manifest_sha256"], "ns3_manifest_sha256":
                                    report["ns3_manifest_sha256"], "applications": rows})
        for case in ("hidden_node", "mesh_6", "route_recovery"):
            prefix = "research/" + case + "_seed_128/"
            rows = archive_rows(archive, prefix + "protocol_trace.csv")
            summary = json.loads(archive.read(prefix + "summary.json"))
            failures = [r for r in rows if r["Event"] == "hop_control_failed"]
            inactive = [float(r["TimeSeconds"]) for r in rows if r["Event"] == "neighbor_inactive"]
            first_application = min(float(r["TimeSeconds"]) for r in rows if r["Event"] == "app_generate")
            result["research"].append({"case": case,
                "protocol_sha256": hashlib.sha256(archive.read(prefix + "protocol_trace.csv")).hexdigest(),
                "first_application_s": first_application,
                "control_failures": [{k: r[k] for k in ("TimeSeconds", "NodeId", "PeerId", "ControlType", "Reason")}
                                     for r in failures],
                "control_failures_before_application": sum(float(r["TimeSeconds"]) < first_application for r in failures),
                "neighbor_inactive_times_s": inactive,
                "link_events": summary["Config"]["LinkEvents"],
                "discovery_events": summary["Config"]["DiscoveryEvents"],
                "neighbor_options": summary["Config"]["Nwk"]["Neighbor"]})
    rows = [r for case in result["cases"] for r in case["applications"]]
    result["findings"] = {
        "application_count": len(rows),
        "all_final_transit_durations_match": all(abs(r["final_transit_delta_s"]) <= TOLERANCE for r in rows),
        "all_delivery_deltas_are_integer_slots": all(abs(r["slot_residual_s"]) <= TOLERANCE for r in rows),
        "matlab_faster_applications": sum(r["delivery_delta_s"] < -TOLERANCE for r in rows),
        "matlab_slower_applications": sum(r["delivery_delta_s"] > TOLERANCE for r in rows),
        "causal_boundary": "Observed delivery gap is present at final TX; no measured final-envelope transit gap.",
        "rng_attribution": "Different RNG and reservation history are source-supported candidates; exact draw causality is not proven.",
        "recommended_protocol_change": "None from these single-seed residuals; retain PHY/ECC and expand seed evidence."}
    paths = ("+csr/+mac/Layer.m", "+csr/+sim/RandomStreams.m", "+csr/+nwk/Neighbors.m",
             "+csr/+nwk/Layer.m", "+csr/+scenario/researchNetwork.m")
    result["accepted_matlab_source_hashes"] = {
        p: committed_digest(root, published_identity["published_commit"], p) for p in paths}
    result["diagnostic_source_hashes"] = {p: comparison.digest(root / p) for p in
        ("scripts/audit_tranche4_residuals.py", "scripts/compare_matlab_ns3.py")}
    result["ns3_audited_source_hashes"] = {p: committed_digest(ns3_root, comparison.PIN, p) for p in
        ("model/csr-mac-core.h", "model/csr-net-device.h", "model/csr-nwk-layer.h")}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns3-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = audit(Path(__file__).resolve().parents[1], arguments.ns3_root)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["findings"], indent=2))


if __name__ == "__main__":
    main()
