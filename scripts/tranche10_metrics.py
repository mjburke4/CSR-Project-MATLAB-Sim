#!/usr/bin/env python3
"""Strict contract, retained-run and accepted-archive helpers for Tranche 10.

All inputs are read only. Baseline differences are measured outcomes, never a
numerical tolerance or an automatic acceptance decision.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import copy
import csv
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import analyze_tranche8_return as t8
import analyze_tranche9_return as t9

require, integer, finite = sweep.require, sweep.integer, sweep.finite
T7_ARCHIVE = "evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip"
T7_SHA = "ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655"
T9_ARCHIVE = "evidence/tranche-9-r2025a-accepted/tranche9_evidence.zip"
T9_SHA = "ddcede0a83b5ff906a7736f63406fc4cecb11e841795e39e93237364e0e11edf"


def decimal_number(value, label):
    require(isinstance(value, (str, int)) and type(value) is not bool,
            f"{label}: expected exact decimal text")
    try:
        number = Decimal(value)
    except InvalidOperation as failure:
        raise ValueError(f"{label}: invalid decimal") from failure
    require(number.is_finite(), f"{label}: expected finite decimal")
    return number


def exact_contract_rows(actual_path, reference_path):
    """Match every checkpoint; preserve integers and reject nanosecond shifts.

The 1 ps allowance covers decimal printing of fractional double values only.
Integral state/count values compare exactly, including integers above 2**53.
"""
    fields = ("case", "checkpoint", "time_seconds", "field", "actual", "expected", "pass")
    actual, reference = (list(t7.csv_records(path, fields)) for path in (actual_path, reference_path))
    require(reference and len(actual) == len(reference), "Contract checkpoint coverage mismatch")
    identity = lambda row: (row["case"], row["checkpoint"], row["field"])
    require(all(len({identity(row) for row in rows}) == len(rows) for rows in (actual, reference)),
            "Duplicate contract checkpoint identity")
    require([identity(row) for row in actual] == [identity(row) for row in reference],
            "Contract checkpoint identity/order differs from pinned native execution")
    def equivalent(left, right, field):
        a, b = decimal_number(left, field), decimal_number(right, field)
        tolerance = Decimal("1e-12") if field == "time_seconds" or a % 1 or b % 1 else Decimal(0)
        require(abs(a-b) <= tolerance, "Contract checkpoint differs from pinned native execution")
    for row, expected in zip(actual, reference):
        require(sweep.boolean(row["pass"], "contract pass")
                and sweep.boolean(expected["pass"], "native contract pass"),
                "Controlled contract checkpoint failed")
        for field in ("time_seconds", "actual", "expected"):
            equivalent(row[field], expected[field], field)
        equivalent(row["actual"], row["expected"], "value")
        equivalent(expected["actual"], expected["expected"], "value")
    return len(actual)


def same_configuration(before, after, source_root, case=None):
    """Only permit relocation of a canonical, hash-bound SharedScenario input."""
    if "SharedScenario" not in before and "SharedScenario" not in after:
        require(before == after, "Retained experiment configuration changed")
        return {"configuration_equal": True, "configuration_exact_equal": True,
                "configuration_path_relocation": None}
    require(isinstance(before.get("SharedScenario"), dict)
            and isinstance(after.get("SharedScenario"), dict), "Canonical input provenance disappeared")
    if case is None:
        shared = before["SharedScenario"]
        path = str(shared.get("SourcePath", "")).replace("\\", "/")
        parts = PurePosixPath(path).parts
        require(parts.count("scenarios") == 1, "Ambiguous accepted scenario input path")
        relative = PurePosixPath(*parts[parts.index("scenarios"):]).as_posix()
        case = {"scenario_file": relative, "scenario_sha256": shared.get("SourceSHA256")}
    path = sweep.safe_path(source_root, case["scenario_file"])
    require(sweep.digest(path) == sweep.valid_hash(case["scenario_sha256"], "scenario SHA-256"),
            "Relocated input is not hash-bound to the candidate")
    relocation = t9.verify_anchor_configuration(before, after, case)
    return {"configuration_equal": True, "configuration_exact_equal": before == after,
            "configuration_path_relocation": relocation}


def archive_roots(bundle):
    """Follow the accepted T7 metadata chain; never choose a suffix match."""
    root = PurePosixPath(".")
    metadata = json.loads(bundle.read("validation_metadata.json"))
    require(metadata.get("Schema") == t7.SCHEMA and metadata.get("Status") == "completed",
            "Accepted T7 outer metadata mismatch")
    result = {7: root}
    for tranche in (6, 5, 4):
        relative = metadata.get("RegressionEvidenceDirectory")
        # Reuse the strict path validator without extracting or writing files.
        sweep.safe_path(Path("/archive"), relative)
        root /= relative
        metadata = json.loads(bundle.read(str(root/"validation_metadata.json")))
        require(metadata.get("Schema") == f"csr-matlab-tranche-{tranche}-validation-v1"
                and metadata.get("Status") == "completed", "Accepted T7 regression chain mismatch")
        result[tranche] = root
    return result


def baseline_path(item, roots):
    kind, name = item["kind"], item["name"]
    if kind == "foundation":
        require(name == "default", "Unknown foundation fixture")
        return roots[4]/"regression/regression/tests"
    if kind == "mac_hop":
        require(name in t7.T2_CASES, "Unknown MAC/HOP fixture")
        return roots[4]/"regression/regression"/name
    if kind == "routed":
        require(name in t7.T3_CASES, "Unknown routed fixture")
        return roots[4]/"regression"/name
    if kind in ("shared", "research"):
        return roots[4]/kind/name
    if kind == "sweep":
        return roots[5]/"sweep"/name
    raise ValueError("Unknown retained baseline namespace")


def compare_baseline(bundle, prefix, current, source_root, *, case=None, files=()):
    old = json.loads(bundle.read(str(prefix/"summary.json")))
    new = sweep.json_object(current/"summary.json")
    configuration = same_configuration(old["Config"], new["Config"], source_root, case)
    before = t7.count_balance(old["Statistics"], "accepted baseline")
    after = t7.count_balance(new["Statistics"], "T10 return")
    differences = []
    for name in files:
        with bundle.open(str(prefix/name)) as old_file, (current/name).open(encoding="utf-8-sig", newline="") as new_file:
            difference = t9.csv_difference(io.TextIOWrapper(old_file, encoding="utf-8-sig", newline=""), new_file)
        differences.append({"path": name, **difference})
    return {**configuration, "baseline_directory": str(prefix), "before_counts": before,
            "after_counts": after, "count_changes": {name: after[name]-before[name] for name in t7.COUNTS},
            "statistics_equal": old["Statistics"] == new["Statistics"], "files": differences,
            "equality_required": False}


def verify_raw_accounting(directory, summary):
    """Reconstruct unique application outcomes and per-node count balances."""
    stats, config = summary["Statistics"], summary["Config"]
    stack = config.get("Stack")
    require(stack in ("phy-only", "mac-hop", "network"), "Unsupported retained protocol stack")
    required = {"trace.csv", "nodes.csv", "phy_trace.csv", "summary.json"}
    if stack in ("mac-hop", "network"):
        required.update(("protocol_trace.csv", "mac_nodes.csv", "hop_nodes.csv"))
    if stack == "network":
        required.update(("nwk_nodes.csv", "neighbors.csv", "routes.csv", "application_admission_statistics.csv", "application_admission_trace.csv"))
    require(all((directory/name).is_file() for name in required), "Retained case omitted required protocol outputs")
    counts = t7.count_balance(stats, str(directory))
    require(integer(stats.get("PhysicalAttempts"), "physical attempts") == sum(integer(stats.get(k), k)
            for k in ("PhysicalReceived", "PhysicalDropped", "PhysicalPending")), "Physical accounting mismatch")
    require(config.get("Trace", {}).get("Enabled") is True
            and all(integer(stats.get(k), k) == 0 for k in ("OmittedTraceRecords", "OmittedPhyTraceRecords")),
            "Retained traces are disabled or truncated")
    nodes = list(t7.csv_records(directory/"nodes.csv", ("Id", "Generated", "Received", "Dropped")))
    expected_nodes = {integer(row["Id"], "configured node") for row in sweep.entries(config["Nodes"], "nodes")}
    require(len(nodes) == len(expected_nodes) and {integer(row["Id"], "node") for row in nodes} == expected_nodes,
            "Retained node membership mismatch")
    require(all(sum(integer(row[k], k) for row in nodes) == counts[k] for k in ("Generated", "Received", "Dropped")),
            "Per-node application counts disagree")
    path = directory/("protocol_trace.csv" if (directory/"protocol_trace.csv").exists() else "trace.csv")
    gateway = None
    if config.get("Nwk", {}).get("SendOnlyToGateway") is True:
        gateways = [row["Id"] for row in sweep.entries(config["Nodes"], "nodes") if row.get("Capability") == 2]
        require(len(gateways) == 1, "Retained gateway rewrite requires its unique configured gateway")
        gateway = integer(gateways[0], "gateway node")
    generated, received, states, previous = {}, {}, {}, -1.0
    for row in t7.csv_records(path, ("TimeSeconds", "Event", "NodeId", "PeerId", "PacketId", "ApplicationBytes", "Reason")):
        when = finite(row["TimeSeconds"], "trace time")
        require(previous <= when <= finite(config["DurationSeconds"], "duration") and when >= 0,
                "Retained trace time order/range mismatch")
        previous = when
        if row["Event"] not in ("app_generate", "app_receive", "app_drop", "relay_accept"):
            continue
        packet = integer(row["PacketId"], "application identity")
        observation = (when, integer(row["NodeId"], "node"), integer(row["PeerId"], "peer"),
                       integer(row["ApplicationBytes"], "payload"))
        if row["Event"] == "app_generate":
            require(packet > 0 and packet not in generated, "Duplicate/invalid generated application")
            require(observation[1] in expected_nodes and observation[2] in expected_nodes,
                    "Generated application references an unconfigured node")
            generated[packet], states[packet] = observation, "pending"
            continue
        require(packet in generated and observation[3] == generated[packet][3], "Unknown application outcome/payload")
        if row["Event"] == "app_receive":
            # Layer.pump rewrites source applications after app_generate when
            # SendOnlyToGateway is enabled. The retained gateway fixture has
            # exactly one configured gateway; the generation peer remains the
            # originally requested destination in the legacy trace schema.
            destination = gateway if gateway is not None else generated[packet][2]
            require(packet not in received and observation[0] >= generated[packet][0]
                    and observation[1] == destination, "Duplicate delivery or delivery endpoint mismatch")
            received[packet], states[packet] = observation, "delivered"
        elif states[packet] == "delivered":
            require(row["Event"] != "app_drop", "Delivered application dropped again")
        else:
            states[packet] = "dropped" if row["Event"] == "app_drop" else "pending"
            require(states[packet] != "dropped" or row["Reason"], "Dropped application lacks reason")
    expected = Counter({"delivered": counts["Received"], "dropped": counts["Dropped"], "pending": counts["Pending"]})
    require(len(generated) == counts["Generated"] and Counter(states.values()) == expected,
            "Retained application trace outcomes disagree with counters")
    require(sum(row[3] for row in received.values()) == integer(stats["ApplicationBytesReceived"], "received bytes"),
            "Retained delivered payload total mismatch")
    for name in ("mac_nodes.csv", "hop_nodes.csv", "nwk_nodes.csv"):
        if not (directory/name).exists():
            continue
        rows = list(t7.csv_records(directory/name, ("NodeId",)))
        require(len(rows) == len(expected_nodes) and {integer(row["NodeId"], "node") for row in rows} == expected_nodes,
                "Retained protocol node membership mismatch")
        if name == "nwk_nodes.csv":
            require(all(integer(row["PendingCustody"], "custody") <= config["Nwk"]["QueueLimit"] for row in rows),
                    "Retained network queue bound exceeded")
        if name == "mac_nodes.csv":
            require(all(integer(row["MaxDataQueueDepth"], "MAC data queue") <= config["Mac"]["DataQueueLimit"] for row in rows),
                    "Retained MAC data queue bound exceeded")
    admission = None
    if stack == "network":
        admission = verify_retained_admission(directory, config, stats, generated)
    return {"counts": counts, "application_identities_verified": len(generated),
            "unique_deliveries_verified": len(received), "physical_accounting_verified": True,
            "admission": admission}


def verify_retained_admission(directory, config, stats, generated):
    """Reconstruct complete retained attempt counters and local packet joins."""
    require(integer(stats.get("OmittedApplicationAdmissionRecords"), "retained admission omissions") == 0,
            "Retained admission trace is truncated")
    flows = sweep.entries(config["Traffic"], "retained flows")
    counters = list(t7.csv_records(directory/"application_admission_statistics.csv", ("FlowIndex", "SourceId", "Attempts", "Admitted", *t7.GATES.values())))
    require(len(counters) == len(flows), "Retained admission counters omit a flow")
    expected, observed, prefix, admitted = {}, Counter(), Counter(), set()
    for index, (row, flow) in enumerate(zip(counters, flows), 1):
        values = {name: integer(row[name], name) for name in ("Attempts", "Admitted", *t7.GATES.values())}
        require(integer(row["FlowIndex"], "flow index") == index and integer(row["SourceId"], "flow source") == flow["SourceId"]
                and integer(row["ConfiguredDestinationId"], "flow destination") == flow["DestinationId"]
                and values["Attempts"] == sum(values[name] for name in ("Admitted", *t7.GATES.values())),
                "Retained admission counter identity/balance mismatch")
        expected[index] = values
    if config.get("ApplicationGenerator") == "configured-count":
        # NetworkSimulation.generate updates generator counters for these
        # retained fixtures, but records successful attempt rows only for
        # historical-opnet-gated workloads. Empty rows are deliberate here.
        require(all(row["Attempts"] == row["Admitted"] for row in expected.values())
                and sum(row["Admitted"] for row in expected.values()) == len(generated),
                "Retained configured-count admission counters disagree with generation")
        rows = list(t7.csv_records(directory/"application_admission_trace.csv"))
        require(not rows, "Configured-count retained fixture has unexpected admission trace rows")
        return {"attempts": len(generated), "admitted": len(generated), "blocked": 0,
                "omitted_trace_records": 0, "successful_attempt_rows_exported": False,
                "scope": "Configured-count generator counters and application trace; successful attempt rows are intentionally absent."}
    require(config.get("ApplicationGenerator") == "historical-opnet-gated", "Unknown retained generator profile")
    previous = -1.0
    for row in t7.csv_records(directory/"application_admission_trace.csv", ("TimeSeconds", "FlowIndex", "AttemptIndex", "SourceId", "DestinationId", "PacketId", "Accepted", "Reason")):
        index = integer(row["FlowIndex"], "flow index")
        require(index in expected, "Unknown retained admission flow")
        prefix[index] += 1
        when = finite(row["TimeSeconds"], "admission time")
        require(previous <= when <= config["DurationSeconds"] and when >= 0
                and integer(row["AttemptIndex"], "attempt ordinal") == prefix[index], "Retained admission time/ordinal mismatch")
        previous = when
        packet = integer(row["PacketId"], "admission packet")
        source, destination = integer(row["SourceId"], "admission source"), integer(row["DestinationId"], "admission destination")
        require(source == flows[index-1]["SourceId"], "Retained admission source differs from configured flow")
        if sweep.boolean(row["Accepted"], "admission accepted"):
            require(row["Reason"] == "admitted" and packet in generated and packet not in admitted
                    and generated[packet][:3] == (when, source, destination), "Retained admitted packet does not join its application")
            admitted.add(packet)
            observed[index, "Admitted"] += 1
        else:
            require(packet == 0 and row["Reason"] in t7.GATES, "Invalid blocked retained application")
            observed[index, t7.GATES[row["Reason"]]] += 1
    require(admitted == set(generated), "Retained admission trace omits generated applications")
    for index, row in expected.items():
        require(prefix[index] == row["Attempts"]
                and all(observed[index, name] == row[name] for name in ("Admitted", *t7.GATES.values())),
                "Retained admission trace disagrees with complete counters")
    return {"attempts": sum(prefix.values()), "admitted": len(admitted),
            "blocked": sum(prefix.values())-len(admitted), "omitted_trace_records": 0}


def verify_case_manifest(directory, item, source, runtime, *, custom=False):
    manifest_path = directory/"case_manifest.json"
    require(sweep.digest(manifest_path) == item.get("ManifestSHA256"), "Retained manifest hash mismatch")
    manifest = sweep.json_object(manifest_path)
    schema = "csr-matlab-retained-case-v1" if custom else "csr-matlab-research-case-v1"
    require(manifest.get("schema") == schema and manifest.get("status") == "completed"
            and all(manifest.get(k) is True for k in ("execution_completed", "source_files_stable", "structural_checks_passed"))
            and manifest.get("ns3_source_commit") == t7.PIN, "Retained case structural execution incomplete")
    require(sweep.snapshot(manifest.get("source_files"), "retained source") == source,
            "Retained case source mismatch")
    require(manifest.get("matlab_version") == runtime["Version"] and manifest.get("matlab_release") == runtime["Release"],
            "Retained runtime mismatch")
    t7.inventory(directory, manifest.get("files"), "retained raw artifacts", excluded=("case_manifest.json",),
                 local=manifest.get("local_files", []))
    summary = sweep.json_object(directory/"summary.json")
    config, metadata = summary["Config"], summary["Metadata"]
    require(manifest.get("scenario") == config.get("Name") and manifest.get("seed") == config.get("Seed")
            and manifest.get("duration_s") == config.get("DurationSeconds")
            and config.get("Backend") == "portable" and metadata.get("SourceCommit") == t7.PIN
            and metadata.get("Runtime") == "MATLAB" and metadata.get("Version") == runtime["Version"]
            and metadata.get("Release") == runtime["Release"], "Retained archived configuration/runtime mismatch")
    accounting = verify_raw_accounting(directory, summary)
    return summary, accounting
