#!/usr/bin/env python3
"""Verify a Tranche 7 MATLAB return and report pinned benchmark residuals.

Accepts an immutable ZIP or extracted directory. Source hashes must match the
complete --source-root candidate snapshot; use a preserved candidate checkout
when the working repository has advanced. This is an integrity/structural
review, never automatic MATLAB acceptance or numerical parity certification.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import zipfile

import analyze_research_sweep as sweep
import analyze_tranche6_return as tranche6
import compare_benchmark_aggregates as compare

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "csr-matlab-tranche-7-validation-v1"
PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
BASE = "b53653ed822d85db2fd4d351fb4a49bb1dd739ec"
T6_CODE = "21c0a3f024c9efffdbd11c8059f1540a67c19b1a"
COUNTS = ("Generated", "Received", "Dropped", "Pending")
TEST_COUNTS = ("TestCount", "PassedTests", "FailedTests", "IncompleteTests")
GATES = {"discovery_active": "BlockedDiscovery", "topology_unknown": "BlockedTopology",
         "gateway_route_unknown": "BlockedGatewayRoute", "destination_unavailable": "BlockedDestination",
         "nsdp_full": "BlockedNsdp"}
T3_CASES = {"autonomous", "no_route_custody", "control_loss", "route_recovery", "gateway",
            "leaf_no_transit", "high_rate_500", "high_rate_1000"}
T2_CASES = {"reliable", "ack_loss", "data_loss", "dack", "collision", "relay",
            "queue_pressure", "high_rate_500", "high_rate_1000"}
require, integer, finite = sweep.require, sweep.integer, sweep.finite


def csv_records(path, fields=()):
    """Stream records so million-row evidence does not require a second copy."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames),
                f"Missing/duplicate CSV columns: {path}")
        require(set(fields) <= set(reader.fieldnames), f"Missing CSV columns: {path}")
        for row in reader:
            require(None not in row and None not in row.values(), f"Malformed CSV row: {path}")
            yield row


def listed_files(root):
    found = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), f"Symlink is not evidence: {path}")
        if path.is_file():
            found.add(path.relative_to(root).as_posix())
    return found


def inventory(root, raw, label, *, excluded=(), local=()):
    entries = sweep.entries(raw, label, nonempty=False)
    found = {}
    for entry in entries:
        name = entry.get("path")
        path = sweep.safe_path(root, name)
        require(name not in found and not path.is_symlink(), f"Duplicate/symlink {label}: {name}")
        require(path.is_file(), f"Missing {label}: {name}")
        require(path.stat().st_size == integer(entry.get("bytes"), f"{name} bytes"),
                f"Byte count mismatch: {name}")
        require(sweep.digest(path) == sweep.valid_hash(entry.get("sha256"), name), f"Hash mismatch: {name}")
        if entry.get("row_count") not in (None, []):
            require(path.suffix == ".csv", f"Row count declared for non-CSV: {name}")
            require(sum(1 for _ in csv_records(path)) == integer(entry["row_count"], name),
                    f"Row count mismatch: {name}")
        found[name] = entry
    local_names = set()
    for entry in sweep.entries(local or [], "local artifacts", nonempty=False):
        name = entry.get("path")
        path = sweep.safe_path(root, name)
        require(path.suffix in (".mat", ".zip") and name not in local_names and name not in found,
                f"Invalid local-only artifact: {name}")
        local_names.add(name)
        if path.exists():
            require(path.is_file() and not path.is_symlink(), f"Invalid local artifact: {name}")
            require(path.stat().st_size == integer(entry.get("bytes"), name)
                    and sweep.digest(path) == sweep.valid_hash(entry.get("sha256"), name),
                    f"Local artifact hash mismatch: {name}")
    actual = listed_files(root) - set(excluded) - local_names
    require(actual == set(found), f"Incomplete {label} inventory: {sorted(actual ^ set(found))[:8]}")
    return found


@contextmanager
def evidence_directory(path):
    path = Path(path).resolve()
    if path.is_dir():
        listed_files(path)
        yield path
        return
    require(path.is_file() and zipfile.is_zipfile(path), "Expected evidence ZIP or directory")
    with tempfile.TemporaryDirectory(prefix="csr-t7-return-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(path) as bundle:
            seen, total = set(), 0
            require(len(bundle.infolist()) <= 20000, "Oversized ZIP member count")
            for member in bundle.infolist():
                name = member.filename.rstrip("/") if member.is_dir() else member.filename
                target = sweep.safe_path(root, name)
                require(name.casefold() not in seen, f"Duplicate/case-colliding ZIP path: {name}")
                seen.add(name.casefold())
                mode = member.external_attr >> 16
                require(not stat.S_ISLNK(mode) and not (member.flag_bits & 1),
                        "Symlink/encrypted ZIP member is not accepted")
                total += member.file_size
                require(total <= 20 * 1024**3, "Evidence ZIP expands beyond 20 GiB")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)  # ZipExtFile verifies CRC at EOF.
        require((root / "validation_metadata.json").is_file(), "ZIP must have validation metadata at its root")
        yield root


def candidate_snapshot(root):
    """Mirror csr.validation.Artifacts.sourceSnapshot membership, not a subset."""
    patterns = ["*.m", "+csr/**/*.m", "tests/**/*.m", "examples/**/*.m",
                "scripts/**/*.py", "scripts/**/*.cc", "scripts/**/*.h", "data/**/*", "scenarios/**/*",
                "evidence/tranche-*-candidate.json", "evidence/source-baseline.json"]
    paths = {path for pattern in patterns for path in root.glob(pattern) if path.is_file()}
    require(paths, "Candidate source snapshot is empty")
    require(not any(path.is_symlink() for path in paths), "Candidate source contains symlink")
    return {path.relative_to(root).as_posix(): sweep.digest(path) for path in sorted(paths)}


def source_binding(metadata, source, runtime, *, final=True):
    require(metadata.get("Status") == "completed" and metadata.get("MATLABExecuted") is True,
            "Completed MATLAB execution was not recorded")
    require(metadata.get("SourceCommit") == PIN and metadata.get("Runtime") == runtime,
            "Nested source/runtime identity mismatch")
    require(metadata.get("SourceFilesStableDuringRun") is True, "Unproven source stability")
    require(sweep.snapshot(metadata.get("SourceFiles"), "source") == source, "Source snapshot mismatch")
    if final:
        require(sweep.snapshot(metadata.get("SourceFilesFinal"), "final source") == source,
                "Final source snapshot mismatch")


def count_balance(stats, label):
    values = {name: integer(stats.get(name), f"{label} {name}") for name in COUNTS}
    require(values["Generated"] == sum(values[name] for name in COUNTS[1:]),
            f"Application accounting mismatch: {label}")
    return values


def time_tick(value, label):
    scaled = finite(value, label)*1_000_000_000
    tick = round(scaled)
    require(scaled >= 0 and scaled <= 2**53 and abs(scaled-tick) <= 1e-6,
            f"{label}: expected exact nanosecond time")
    return tick


def possible_attempts(duration, start, interval, packet_count):
    stop_tick, start_tick, interval_tick = (time_tick(x, label) for x, label in
                                            ((duration, "stop"), (start, "start"), (interval, "interval")))
    require(interval_tick > 0, "Application interval must be at least one nanosecond")
    count = 0 if start_tick >= stop_tick else (stop_tick-1-start_tick)//interval_tick+1
    return min(integer(packet_count, "packet count"), count)


def portable_test_names(source_root, *, native=False):
    names = set()
    directory = source_root / "tests/native" if native else source_root / "tests"
    for path in directory.glob("Test*.m"):
        code = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^    methods\s*\(([^)]*)\)(.*?)(?=^    methods\b|\Z)",
                                 code, re.M | re.S):
            if re.search(r"\bTest\b", match[1]):
                names.update(f"{path.stem}/{name}" for name in
                             re.findall(r"^        function\s+(\w+)\s*\(", match[2], re.M))
    require(names, "Candidate has no discoverable portable MATLAB test methods")
    return names


def verify_reference_suite(source_root, catalog):
    root = source_root / "evidence/tranche-7-ns3-reference"
    suite = sweep.json_object(root / "manifest.json")
    require(suite.get("schema") == "csr-tranche7-benchmark-reference-suite-v1"
            and suite.get("status") == "completed" and suite.get("source_files_stable") is True
            and suite.get("input_files_stable") is True and suite.get("ns3_source_commit") == PIN,
            "Reference suite provenance is incomplete")
    require(sweep.digest(root / "build.json") == suite.get("build_manifest_sha256"), "Reference build hash mismatch")
    build = sweep.json_object(root / "build.json")
    require(build.get("schema") == "csr-tranche7-benchmark-reference-build-v1"
            and build.get("ns3_source_commit") == PIN and build.get("exit_code") == 0
            and build.get("standalone_runner_compiled") is True
            and build.get("source_headers_match_preserved_build") is True, "Reference build did not pass")
    cases = sweep.entries(suite.get("cases"), "reference suite cases")
    require(len(cases) == len(catalog["cases"])
            and {x.get("case_id") for x in cases} == {x["case_id"] for x in catalog["cases"]},
            "Reference suite case set differs from runnable catalog")
    case_files = set()
    for item in cases:
        require(item.get("status") == "completed" and item.get("manifest") == f"{item['case_id']}/manifest.json",
                "Reference suite case did not complete")
        path = sweep.safe_path(root, item["manifest"])
        require(sweep.digest(path) == item.get("manifest_sha256"), "Reference case manifest hash mismatch")
        manifest = sweep.json_object(path)
        require(manifest.get("schema") == "csr-tranche7-benchmark-reference-case-v1"
                and manifest.get("status") == "completed" and manifest.get("ns3_source_commit") == PIN,
                "Reference case source/completion mismatch")
        expected = next(x for x in catalog["cases"] if x["case_id"] == item["case_id"])
        require(manifest.get("case") == expected, "Reference case descriptor differs from catalog")
        inventory(path.parent, manifest.get("files"), "reference case", excluded=("manifest.json",))
        case_files.update(f"{item['case_id']}/{name}" for name in listed_files(path.parent))
    inventory(root, suite.get("files"), "reference suite", excluded={"manifest.json", *case_files})
    inputs_root = source_root / "evidence/tranche-7-benchmark-inputs"
    inputs = sweep.json_object(inputs_root / "manifest.json")
    require(inputs.get("schema") == "csr-tranche7-benchmark-inputs-v1"
            and inputs.get("ns3_source_commit") == PIN
            and inputs.get("source_archive_sha256") == catalog.get("source_archive_sha256")
            and inputs.get("source_archive_contents_modified") is False, "Original input provenance mismatch")
    expected_paths = set()
    for item in sweep.entries(inputs.get("files"), "original inputs"):
        path = sweep.safe_path(source_root, item.get("path"))
        require(path.is_relative_to(inputs_root), "Original input path is outside its bundle")
        expected_paths.add(path.relative_to(inputs_root).as_posix())
        require(path.stat().st_size == integer(item.get("bytes"), "input bytes")
                and sweep.digest(path) == item.get("sha256"), "Original input packaged hash mismatch")
        hasher, size = hashlib.sha256(), 0
        with (gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")) as stream:
            for block in iter(lambda: stream.read(1024*1024), b""):
                hasher.update(block)
                size += len(block)
        require(size == integer(item.get("original_bytes"), "original bytes")
                and hasher.hexdigest() == item.get("original_sha256"), "Original input roundtrip mismatch")
    require(listed_files(inputs_root) == {"manifest.json", *expected_paths}, "Uninventoried original inputs")


def verify_config(case_root, config):
    rows = list(csv_records(case_root / "raw/scenario.csv", ("record",)))
    nodes = sorted((x for x in rows if x["record"] == "node"), key=lambda x: finite(x["node_id"], "node ID"))
    actual_nodes = sweep.entries(config.get("Nodes"), "config nodes")
    require(len(nodes) == len(actual_nodes), "Config node population mismatch")
    for expected, actual in zip(nodes, actual_nodes):
        capability = {"ordinary": 0, "routable": 1, "gateway": 2}[expected["node_type"]]
        require(actual.get("Id") == finite(expected["node_id"], "node ID")
                and actual.get("Capability") == capability
                and actual.get("TransitForwardingEnabled") is (capability > 0)
                and actual.get("PositionMeters") == [finite(expected[x], x) for x in ("x_m", "y_m", "height_m")],
                "Config geometry/capability differs from canonical nodes")
        radio = actual.get("RadioProfile", {})
        for field, column in (("TxPowerDbm", "max_power_dbm"), ("TxBaseFrequencyHz", "tx_frequency_hz"),
                              ("RxBaseFrequencyHz", "rx_frequency_hz"), ("TxHeightMeters", "height_m"),
                              ("RxHeightMeters", "height_m"), ("EccThreshold", "ecc_threshold")):
            require(radio.get(field) == finite(expected[column], column), f"Config radio {field} differs from canonical input")
        require(radio.get("StochasticSyncThreshold") is True, "Historical sync threshold is not enabled")
        expected_radio = {"NoiseFloorDbm": -106.975, "NoiseReferenceBwHz": 1e6, "ScaleNoiseWithBandwidth": True,
                          "TxBwHz": 1e6, "RxBwHz": 1e6, "TxAntennaGainDb": 0, "RxAntennaGainDb": 0,
                          "SyncSnrThresholdDb": -11, "SyncSnrThresholdVarianceDb2": 0.25,
                          "ClosureMode": "EARTH_LINE_OF_SIGHT", "EarthRadiusMeters": 6371000,
                          "PropagationModel": "OPNET_THREE_PATH", "RefLossDb": 60, "PathlossExp": 2,
                          "DistanceScale": 1, "ClosureDelegate": []}
        require(all(radio.get(k) == value for k, value in expected_radio.items()),
                "Benchmark actual PHY/closure/noise settings differ from importer defaults")
    info = config.get("Nwk", {}).get("Routing", {}).get("LocalInfo", {})
    for field, column, scale in (("MinSpeedKbps", "min_speed_kbps", 1), ("MaxSpeedKbps", "max_speed_kbps", 1),
                                 ("MinPowerDbmX10", "min_power_dbm", 10), ("MaxPowerDbmX10", "max_power_dbm", 10),
                                 ("LinkMarginDbX10", "link_margin_db", 10)):
        require(info.get(field) == scale*finite(nodes[0][column], column), "Config routing radio limit differs from input")
    expected_flows = [x for x in rows if x["record"] == "flow"]
    actual_flows = sweep.entries(config.get("Traffic"), "config traffic")
    require(len(expected_flows) == len(actual_flows), "Config traffic population mismatch")
    for expected, actual in zip(expected_flows, actual_flows):
        for field, column in (("SourceId", "flow_src"), ("DestinationId", "flow_dst"), ("StartSeconds", "flow_start_s"),
                              ("IntervalSeconds", "flow_interval_s"), ("Dscp", "flow_dscp")):
            require(actual.get(field) == finite(expected[column], column), "Config flow endpoints/timing/DSCP mismatch")
        require(actual.get("ApplicationPayloadBytes") == finite(expected["flow_packet_bytes"], "configured bytes")-15
                and actual.get("AckRequired") is True
                and actual.get("DestinationMode") == (expected.get("flow_destination_mode") or "fixed"),
                "Config flow envelope/mode mismatch")
        # Importer represents schedule endpoints as exact integer nanoseconds.
        count = possible_attempts(config["DurationSeconds"], expected["flow_start_s"],
                                  expected["flow_interval_s"], 2**53)
        require(integer(actual.get("PacketCount"), "PacketCount") == count, "Config flow attempt budget mismatch")
    require(config.get("Backend") == "portable" and config.get("Stack") == "network"
            and config.get("Trace", {}).get("Enabled") is True, "Benchmark must use portable full network/trace execution")
    require(config.get("Channel") == {"PropagationSpeedMps": 3e8, "FixedDropProbability": 0, "Model": "csr-phy"},
            "Benchmark actual channel differs from physical importer settings")
    expected_mac = {"DataQueueLimit": 512, "AckQueueLimit": 256, "AckTransmissions": 5, "MaxConcatSegments": 16,
                    "SlotSeconds": 0.013, "HoldoffSeconds": 0.3, "ActiveNodes": 1, "ReportedActiveNodes": 1,
                    "SlotReduction": 0, "ReservationSlotOverride": -1, "DutyCycleEnabled": True,
                    "WakeCycleSeconds": 0.988, "SearchSeconds": 0.0078, "BootSeconds": 0.0011,
                    "PostTxBaseSeconds": 15, "PostTxPerNodeSeconds": 1.5, "PostTxGuardSeconds": 0.5,
                    "ConcatenationEnabled": True}
    require(all(config.get("Mac", {}).get(k) == value for k, value in expected_mac.items()),
            "Benchmark actual MAC timing/queues/duty-cycle settings differ from importer")
    expected_hop = {"ResendSeconds": 2, "MaxResends": 2, "DackHoldSeconds": 20, "PendingThreshold": 16,
                    "ResendQueueLimit": 512, "FlowThresholdMax": 16, "NsdpLimit": 16, "TicSeconds": 1/36e6}
    require(config.get("Hop") == expected_hop, "Benchmark actual HOP timing/retry settings differ from importer")
    expected_nwk = {"StartupMode": "gateway", "StartupDelaySeconds": 10, "DiscoveryDurationSeconds": 30,
                    "QueueLimit": 512, "ControlQueueLimit": 64, "ControlRetrySeconds": 8, "MaxControlCycles": 3,
                    "RouteRequestSeconds": 8, "MaxRouteRequests": 2, "SnapshotWatchdogSeconds": 20,
                    "GatewayWatchdogSeconds": 60, "MaxHopCount": 32, "AdaptiveLinkControl": True, "SendOnlyToGateway": False}
    require(all(config.get("Nwk", {}).get(k) == value for k, value in expected_nwk.items()),
            "Benchmark actual NWK discovery/custody settings differ from importer")
    expected_neighbor = {"AdmissionEnabled": True, "AdmissionRetrySeconds": 5, "DiscoveryIntervalSeconds": 5,
                         "DiscoveryBroadcastCount": 3, "DiscoveryDurationSeconds": 30, "DiscoveryResponseEnabled": True,
                         "ResponseDelaySeconds": 0.020, "FreshnessEnabled": False, "FreshnessTimeoutSeconds": 20,
                         "FreshnessPeriodSeconds": 2}
    require(config.get("Nwk", {}).get("Neighbor") == expected_neighbor, "Benchmark actual NWK admission settings differ from importer")
    for field in ("Faults", "LinkEvents", "DiscoveryEvents"):
        require(config.get(field) in (None, []), "Canonical benchmark contains unexpected receive erasures or discovery overrides")


def reference_flow_progress(directory):
    diagnostics = list(csv_records(directory / "app-admission-diagnostics.csv",
                                    ("flow_index", "source", "configured_destination", "attempts", "admitted")))
    sent, delivered = {}, set()
    with gzip.open(directory / "ns3-trace.csv.gz", "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, strict=True):
            if row["event"] not in ("app_send", "nwk_delivery"):
                continue
            identity = (integer(row["src"], "ns3 source"), integer(row["dst"], "ns3 destination"), row["sequence"])
            if row["event"] == "app_send":
                require(identity not in sent, "Duplicate ns-3 generated application")
                sent[identity] = integer(row["size_bytes"], "ns3 network bytes")
            else:
                require(identity in sent and sent[identity] == integer(row["size_bytes"], "ns3 delivered bytes"),
                        "ns-3 delivery has no matching generated identity")
                delivered.add(identity)
    progress = []
    for expected, row in enumerate(diagnostics):
        require(integer(row["flow_index"], "ns3 flow index") == expected, "ns-3 flow index order mismatch")
        source = integer(row["source"], "ns3 source")
        admitted = sum(identity[0] == source for identity in sent)
        require(admitted == integer(row["admitted"], "ns3 admitted"), "ns-3 per-flow admission count mismatch")
        received = sum(identity[0] == source for identity in delivered)
        progress.append({"flow_index": expected+1, "source": source,
                         "configured_destination": integer(row["configured_destination"], "ns3 destination"),
                         "attempts": integer(row["attempts"], "ns3 attempts"), "admitted": admitted,
                         "delivered": received, "made_progress": admitted > 0 and received > 0})
    return progress


def verify_aggregate_values(directory, config, generated, received):
    width = finite(config["Benchmark"]["BucketWidthSeconds"], "bucket width")
    require(width > 0, "Nonpositive aggregate bucket width")
    count = round(config["DurationSeconds"]/width)
    require(count > 0 and abs(config["DurationSeconds"]/width-count) <= 1e-10, "Nonintegral aggregate window")
    sent_counts, sent_bits, recv_counts, recv_bits, delays = ([0.0]*count for _ in range(5))
    def bucket(when):
        quotient = when/width
        if abs(quotient-round(quotient)) <= 1e-12:
            quotient = round(quotient)
        return math.floor(quotient) if 0 <= quotient < count else None
    for record in generated.values():
        index = bucket(record[0])
        if index is not None:
            sent_counts[index] += 1
            sent_bits[index] += 8*(record[3]+7)
    for packet, record in received.items():
        index = bucket(record[0])
        if index is not None:
            require(bucket(generated[packet][0]) is not None, "In-window delivery has an excluded generation")
            recv_counts[index] += 1
            recv_bits[index] += 8*(record[3]+7)
            delays[index] += record[0]-generated[packet][0]
    names = list(compare.CORE_SERIES)
    seen = set()
    for row in csv_records(directory / "analysis/aggregates.csv", ("statistic", "time_s", "value", "value_status")):
        name = row["statistic"]
        require(name in names, "Unexpected MATLAB aggregate statistic")
        time = finite(row["time_s"], "bucket end")
        index = round(time/width)-1
        require(0 <= index < count and abs(time-(index+1)*width) <= 1e-8 and (name, index) not in seen,
                "Duplicate/off-grid MATLAB aggregate bucket")
        seen.add((name, index))
        values = [sent_counts[index]/width, sent_bits[index]/width,
                  sent_bits[index]/sent_counts[index] if sent_counts[index] else None,
                  recv_counts[index]/width, recv_counts[index], recv_bits[index]/width, recv_bits[index],
                  delays[index]/recv_counts[index] if recv_counts[index] else None]
        expected = values[names.index(name)]
        if expected is None:
            require(row["value"] == "" and row["value_status"] == "missing", "Empty sample mean must remain missing")
        else:
            # Round-trip tolerance covers text-exported trace time precision
            # and accumulation order; it is not a simulator parity tolerance.
            require(row["value_status"] == "observed"
                    and math.isclose(finite(row["value"], "aggregate value"), expected, rel_tol=2e-12, abs_tol=1e-8),
                    "MATLAB aggregate bucket disagrees with complete application trace")
    require(len(seen) == 8*count, "MATLAB aggregate grid is incomplete")


def verify_regression(root, metadata, source, runtime, source_root):
    options = metadata["Options"]
    requested = options["RunTests"] or options["IncludeNative"]
    if not requested:
        require(metadata.get("RegressionStatus") == "not_run" and not metadata.get("RegressionEvidenceDirectory")
                and not metadata.get("RegressionMetadataSHA256"), "Unrequested regression has execution claim")
        require(metadata.get("TestsExecuted") is False and metadata.get("TestsPassed") is False
                and metadata.get("NativeExecuted") is False
                and all(integer(metadata.get(k), k) == 0 for k in TEST_COUNTS),
                "Unrequested tests have results")
        return {"status": "not_run", "tests": 0, "sweeps": 0, "retained_cases": 0}
    require(metadata.get("RegressionStatus") == "completed", "Requested regression incomplete")
    t6_root = sweep.safe_path(root, metadata.get("RegressionEvidenceDirectory"))
    require(sweep.digest(t6_root / "validation_metadata.json") ==
            sweep.valid_hash(metadata.get("RegressionMetadataSHA256"), "regression"), "Regression metadata hash mismatch")
    _, t5_root, t6_meta, _ = tranche6.verify_wrapper(t6_root)
    source_binding(t6_meta, source, runtime)
    for name in (*TEST_COUNTS, "TestsExecuted", "TestsPassed", "NativeExecuted"):
        require(metadata.get(name) == t6_meta.get(name), f"Outer/regression {name} mismatch")
    t5_meta = sweep.json_object(t5_root / "validation_metadata.json")
    require(t5_meta.get("TestsRequested") is options["RunTests"]
            and t5_meta.get("NativeRequested") is options["IncludeNative"], "Regression request flags disagree")
    sweep_report, rows, _ = sweep.analyze(t5_root)
    source_binding(t5_meta, source, runtime)
    require(len(rows) == 18 and {r["Seed"] for r in rows} == {128, 129, 130},
            "Retained default 18-sweep regression is incomplete")
    expected_sweeps = {f"{kind}_{token}{value}_seed{seed}" for kind, token, values in
                       (("offered_load", "x", [1, 2, 4]), ("recovery_freshness", "s", [60, 180, 300]))
                       for value in values for seed in [128, 129, 130]}
    require({r["CaseId"] for r in rows} == expected_sweeps, "Default sweep membership mismatch")
    t4_root = sweep.safe_path(t5_root, t5_meta.get("RegressionEvidenceDirectory"))
    t4_meta = sweep.json_object(t4_root / "validation_metadata.json")
    require(t4_meta.get("Schema") == "csr-matlab-tranche-4-validation-v1", "Missing Tranche 4 regression")
    source_binding(t4_meta, source, runtime, final=False)
    inventory(t4_root, t4_meta.get("Artifacts"), "T4 artifacts",
              excluded=("validation_metadata.json", "tranche4_evidence.zip", "validation.log"),
              local=t4_meta.get("LocalArtifacts", []))
    if options["IncludeNative"]:
        native = t4_root / "native"
        status = sweep.json_object(native / "native_status.json")
        require(status.get("Status") == "passed" and status.get("MatlabVersion") == runtime["Version"]
                and status.get("MatlabRelease") == runtime["Release"], "Native status/runtime did not pass")
        native_rows = list(csv_records(native / "native_test_results.csv", ("Name", "Passed", "Failed", "Incomplete")))
        names = portable_test_names(source_root, native=True)
        require(len(native_rows) == len(names) and {x["Name"] for x in native_rows} == names,
                "Native test membership mismatch")
        require(all(sweep.boolean(x["Passed"], "native passed") and not sweep.boolean(x["Failed"], "native failed")
                    and not sweep.boolean(x["Incomplete"], "native incomplete") for x in native_rows), "Native tests did not pass")
    shared = sweep.json_object(source_root / "scenarios/shared/catalog.json")
    expected = {("shared", item["name"]) for item in shared["cases"]}
    expected |= {("research", f"{name}_seed_128") for name in
                 ("two_node", "line_4", "hidden_node", "mesh_6", "route_recovery", "leaf_no_transit")}
    cases = sweep.entries(t4_meta.get("Cases"), "retained Cases")
    require(len(cases) == len(expected) and {(x.get("Kind"), x.get("Name")) for x in cases} == expected,
            "Retained shared/research cases missing or duplicated")
    for item in cases:
        directory = sweep.safe_path(t4_root, item.get("Directory"))
        require(sweep.digest(directory / "case_manifest.json") == item.get("ManifestSHA256"),
                "Retained case manifest hash mismatch")
    if options["RunTests"]:
        test_file = sweep.safe_path(t5_root, t5_meta["TestResultsFile"])
        actual = {r["Name"] for r in csv_records(test_file, ("Name",))}
        require(actual == portable_test_names(source_root), "Test CSV does not contain every candidate portable test")
        for directory, names in ((t4_root / "regression", T3_CASES),
                                 (t4_root / "regression/regression", T2_CASES)):
            summaries = list(csv_records(directory / "scenario_summary.csv", ("Scenario", *COUNTS)))
            require(len(summaries) == len(names) and {r["Scenario"] for r in summaries} == names,
                    "Retained integrated scenario set incomplete")
            for row in summaries:
                counts = count_balance(row, row["Scenario"])
                summary = sweep.json_object(directory / row["Scenario"] / "summary.json")
                require(count_balance(summary["Statistics"], row["Scenario"]) == counts,
                        "Retained scenario counters disagree")
    for path in t4_root.rglob("case_manifest.json"):
        manifest = sweep.json_object(path)
        require(manifest.get("status") == "completed" and manifest.get("structural_checks_passed") is True
                and manifest.get("execution_completed") is True, "Retained case did not pass structural execution")
        require(sweep.snapshot(manifest.get("source_files"), "case source") == source,
                "Retained case source mismatch")
        inventory(path.parent, manifest.get("files"), "retained case",
                  excluded=("case_manifest.json",), local=manifest.get("local_files", []))
    return {"status": "passed", "tests": sweep_report["tests"]["TestCount"], "sweeps": len(rows),
            "retained_cases": len(cases) + (17 if options["RunTests"] else 0)}


def verify_admission(case_root, config, stats):
    flows = sweep.entries(config.get("Traffic"), "configured flows")
    rows = list(csv_records(case_root / "raw/application_admission_statistics.csv",
                           ("FlowIndex", "SourceId", "ConfiguredDestinationId", "Attempts", "Admitted", *GATES.values())))
    require(len(rows) == len(flows), "Admission counters must cover every flow")
    counts, total_attempts, total_admitted = {}, 0, 0
    duration, limit = finite(config.get("DurationSeconds"), "duration"), integer(config.get("ApplicationFlowLimit"), "flow limit")
    for index, (row, flow) in enumerate(zip(rows, flows), 1):
        require(integer(row["FlowIndex"], "FlowIndex") == index, "Duplicate/missing admission flow index")
        require(integer(row["SourceId"], "SourceId") == integer(flow["SourceId"], "source")
                and integer(row["ConfiguredDestinationId"], "destination") == integer(flow["DestinationId"], "destination"),
                "Admission flow endpoints differ from config")
        values = {name: integer(row[name], name) for name in ("Attempts", "Admitted", *GATES.values())}
        require(values["Attempts"] == sum(values[k] for k in ("Admitted", *GATES.values())),
                "Admission attempts do not partition into outcomes")
        interval = finite(flow["IntervalSeconds"], "interval")
        require(interval > 0, "Nonpositive application interval")
        possible = possible_attempts(duration, flow["StartSeconds"], interval, flow["PacketCount"])
        require(values["Attempts"] <= possible and (limit == 0 or values["Admitted"] <= limit)
                and ((limit > 0 and values["Admitted"] == limit) or values["Attempts"] == possible),
                "Admission attempt timing or flow cap mismatch")
        counts[index] = values
        total_attempts += values["Attempts"]
        total_admitted += values["Admitted"]
    require(total_admitted == integer(stats.get("Generated"), "Generated"), "Admitted/generated count mismatch")
    source_flows = {integer(flow["SourceId"], "flow source"): index for index, flow in enumerate(flows, 1)}
    require(len(source_flows) == len(flows), "Historical generators must have distinct source nodes")
    generated_attempts = set()
    generated, received, outcomes, previous = {}, {}, {}, -1.0
    for row in csv_records(case_root / "raw/protocol_trace.csv", ("TimeSeconds", "Event", "PacketId", "NodeId", "PeerId", "ApplicationBytes", "Dscp", "Reason")):
        when = finite(row["TimeSeconds"], "protocol time")
        require(previous <= when <= duration and when >= 0, "Protocol trace time order/range mismatch")
        previous = when
        if row["Event"] not in ("app_generate", "app_receive", "app_drop", "relay_accept"):
            continue
        packet = integer(row["PacketId"], "packet ID")
        record = (when, integer(row["NodeId"], "node"), integer(row["PeerId"], "peer"),
                  integer(row["ApplicationBytes"], "application bytes"), integer(row["Dscp"], "DSCP"))
        if row["Event"] == "app_generate":
            require(packet > 0 and packet not in generated, "Duplicate/invalid application trace ID")
            require(record[1] in source_flows, "Generated application has an unconfigured source")
            index = source_flows[record[1]]
            flow = flows[index-1]
            start_tick, interval_tick = time_tick(flow["StartSeconds"], "flow start"), time_tick(flow["IntervalSeconds"], "flow interval")
            attempt = round((when*1e9-start_tick)/interval_tick)+1
            require(1 <= attempt <= counts[index]["Attempts"] and (index, attempt) not in generated_attempts
                    and abs(when-(start_tick+(attempt-1)*interval_tick)/1e9) <= 1e-8,
                    "Generated application is not a unique scheduled flow attempt")
            require(record[3] == integer(flow["ApplicationPayloadBytes"], "flow payload")
                    and record[4] == integer(flow["Dscp"], "flow DSCP"), "Generated payload/DSCP differs from configured flow")
            if flow.get("DestinationMode", "fixed") == "fixed":
                require(record[2] == integer(flow["DestinationId"], "flow destination"), "Generated fixed-flow destination mismatch")
            generated_attempts.add((index, attempt))
            generated[packet] = record
            outcomes[packet] = ("pending", when, "")
            continue
        require(packet in generated and record[3] == generated[packet][3], "Outcome has unknown identity or payload")
        if row["Event"] == "app_receive":
            require(packet not in received and record[4] == generated[packet][4], "Duplicate delivery or DSCP mismatch")
            received[packet] = record
        if outcomes[packet][0] == "delivered":
            require(row["Event"] != "app_drop", "Delivered application dropped again")
            continue
        if row["Event"] == "app_receive":
            outcomes[packet] = ("delivered", when, "")
        elif row["Event"] == "app_drop":
            require(bool(row["Reason"]), "Dropped application has no reason")
            outcomes[packet] = ("dropped", when, row["Reason"])
        else:
            outcomes[packet] = ("pending", when, "")
    require(len(generated) == total_admitted and len(received) == integer(stats.get("Received"), "Received"),
            "Protocol application counts mismatch")
    for packet, row in received.items():
        require(packet in generated and row[0] >= generated[packet][0]
                and row[1] == generated[packet][2] and row[3] == generated[packet][3],
                "Delivery identity/endpoints/bytes mismatch")
    require(Counter(x[0] for x in outcomes.values()) == Counter({"delivered": integer(stats["Received"], "Received"),
            "dropped": integer(stats["Dropped"], "Dropped"), "pending": integer(stats["Pending"], "Pending")}),
            "Protocol final outcomes disagree with raw counters")
    found = set()
    for row in csv_records(case_root / "analysis/applications.csv", ("PacketId", "Outcome", "DropReason", "LatencySeconds")):
        packet = integer(row["PacketId"], "application packet")
        require(packet in generated and packet not in found, "Application diagnostics have missing/duplicate identities")
        found.add(packet)
        sent = generated[packet]
        require((finite(row["GeneratedSeconds"], "generation"), integer(row["SourceId"], "source"),
                 integer(row["DestinationId"], "destination"), integer(row["ApplicationBytes"], "bytes"),
                 integer(row["Dscp"], "DSCP")) == sent, "Application diagnostics generation identity mismatch")
        require(row["Outcome"] == outcomes[packet][0] and row["DropReason"] == outcomes[packet][2]
                and math.isclose(finite(row["LastEventSeconds"], "last event"), outcomes[packet][1], abs_tol=1e-8),
                "Application diagnostic terminal outcome mismatch")
        if row["Outcome"] == "delivered":
            require(math.isclose(finite(row["ReceivedSeconds"], "received"), received[packet][0], abs_tol=1e-8)
                    and math.isclose(finite(row["LatencySeconds"], "latency"), received[packet][0]-sent[0], abs_tol=1e-8),
                    "Application diagnostic latency mismatch")
        else:
            require(row["ReceivedSeconds"].lower() in ("", "nan") and row["LatencySeconds"].lower() in ("", "nan"),
                    "Undelivered application has delivery timing")
    require(found == set(generated), "Application diagnostics omit generated packets")
    require(sum(row[3] for row in received.values()) == integer(stats.get("ApplicationBytesReceived"), "received bytes"),
            "Delivered application byte total mismatch")
    verify_aggregate_values(case_root, config, generated, received)
    observed = Counter()
    prefix = Counter()
    admitted_ids, previous, trace_count = set(), -1.0, 0
    for row in csv_records(case_root / "raw/application_admission_trace.csv",
                           ("TimeSeconds", "FlowIndex", "AttemptIndex", "SourceId", "DestinationId", "PacketId", "Accepted", "Reason")):
        index = integer(row["FlowIndex"], "flow")
        require(index in counts, "Unknown admission flow")
        prefix[index] += 1
        require(integer(row["AttemptIndex"], "attempt") == prefix[index] <= counts[index]["Attempts"],
                "Admission trace is not an ordered per-flow prefix")
        when = finite(row["TimeSeconds"], "admission time")
        require(previous <= when < duration and when >= 0, "Admission trace time order/range mismatch")
        scheduled = (time_tick(flows[index-1]["StartSeconds"], "flow start") +
                     (prefix[index]-1)*time_tick(flows[index-1]["IntervalSeconds"], "flow interval"))/1e9
        require(abs(when-scheduled) <= 1e-8, "Admission trace attempt is off its canonical schedule")
        previous = when
        source = integer(row["SourceId"], "source")
        require(source == integer(flows[index-1]["SourceId"], "flow source"), "Admission trace source mismatch")
        packet = integer(row["PacketId"], "packet ID")
        if sweep.boolean(row["Accepted"], "Accepted"):
            require(row["Reason"] == "admitted" and packet in generated and packet not in admitted_ids,
                    "Invalid/duplicate admitted application")
            require(generated[packet][:3] == (when, source, integer(row["DestinationId"], "destination")),
                    "Admitted application disagrees with generated identity")
            admitted_ids.add(packet)
            observed[index, "Admitted"] += 1
        else:
            require(packet == 0 and row["Reason"] in GATES, "Blocked attempt owns a packet or unknown reason")
            observed[index, GATES[row["Reason"]]] += 1
        trace_count += 1
    omitted = integer(stats.get("OmittedApplicationAdmissionRecords"), "admission omissions")
    require(trace_count + omitted == total_attempts, "Admission trace coverage mismatch")
    for index, values in counts.items():
        for name in ("Admitted", *GATES.values()):
            require(observed[index, name] <= values[name], "Recorded admission reason exceeds complete counters")
            if omitted == 0:
                require(observed[index, name] == values[name], "Complete admission trace disagrees with counters")
    flow_rows = []
    for index, flow in enumerate(flows, 1):
        # The supported benchmark importer permits one historical generator
        # per source, so every complete app identity belongs to exactly one flow.
        population = [packet for packet, record in generated.items() if record[1] == flow["SourceId"]]
        require(len(population) == counts[index]["Admitted"], "Per-flow admitted/protocol generation mismatch")
        delivered = sum(packet in received for packet in population)
        flow_rows.append({"flow_index": index, "source": flow["SourceId"],
                          "configured_destination": flow["DestinationId"], "attempts": counts[index]["Attempts"],
                          "admitted": len(population), "delivered": delivered,
                          "made_progress": bool(population) and delivered > 0})
    return {"attempts": total_attempts, "admitted": total_admitted, "blocked": total_attempts-total_admitted,
            "trace_records": trace_count, "omitted_trace_records": omitted, "flows": flow_rows,
            "all_flows_made_progress": all(row["made_progress"] for row in flow_rows)}


def verify_case(root, item, catalog, source, runtime, source_snapshot_hash, *, expected_directory=None):
    case_id = catalog["case_id"]
    expected_directory = expected_directory or f"benchmarks/{case_id}"
    require(item.get("Directory") == expected_directory, "Noncanonical benchmark directory")
    directory = sweep.safe_path(root, item["Directory"])
    path = directory / "benchmark_manifest.json"
    require(sweep.digest(path) == sweep.valid_hash(item.get("ManifestSHA256"), case_id), "Benchmark manifest hash mismatch")
    manifest = sweep.json_object(path)
    require(manifest.get("schema") == "csr-matlab-benchmark-case-v1" and manifest.get("status") == "completed"
            and manifest.get("structural_checks_passed") is True and manifest.get("admission_counts_complete") is True,
            "Benchmark structural execution incomplete")
    for name in ("case_id", "scenario", "scenario_sha256", "profile_id", "source_kind", "reference_directory", "opnet_available"):
        require(manifest.get(name) == catalog[name], f"Benchmark/catalog {name} mismatch")
    for name in ("duration_s", "seed", "bucket_width_s"):
        require(finite(manifest.get(name), name) == finite(catalog[name], name), f"Benchmark/catalog {name} mismatch")
    require(manifest.get("ns3_source_commit") == PIN and manifest.get("runtime") == runtime
            and manifest.get("matlab_version") == runtime["Version"] and manifest.get("matlab_release") == runtime["Release"],
            "Benchmark source/runtime identity mismatch")
    require(sweep.snapshot(manifest.get("source_files"), "benchmark source") == source
            and manifest.get("source_snapshot_sha256") == source_snapshot_hash, "Benchmark source binding mismatch")
    inventory(directory, manifest.get("files"), "benchmark files", excluded=("benchmark_manifest.json",),
              local=manifest.get("local_files", []))
    raw = sweep.json_object(directory / "raw/case_manifest.json")
    require(raw.get("schema") == "csr-matlab-research-case-v1" and raw.get("status") == "completed"
            and raw.get("execution_completed") is True and raw.get("structural_checks_passed") is True
            and raw.get("source_files_stable") is True and raw.get("ns3_source_commit") == PIN,
            "Raw case structural execution incomplete")
    require(sweep.snapshot(raw.get("source_files"), "raw source") == source, "Raw case source mismatch")
    inventory(directory / "raw", raw.get("files"), "raw files", excluded=("case_manifest.json",),
              local=raw.get("local_files", []))
    require(sweep.digest(directory / "raw/scenario.csv") == catalog["scenario_sha256"]
            and raw.get("scenario_sha256") == catalog["scenario_sha256"], "Canonical scenario hash mismatch")
    summary = sweep.json_object(directory / "raw/summary.json")
    config, stats, md = summary["Config"], summary["Statistics"], summary["Metadata"]
    verify_config(directory, config)
    require(config.get("Benchmark", {}).get("BucketWidthSeconds") == catalog["bucket_width_s"], "Actual benchmark bucket width mismatch")
    require(config.get("Name") == catalog["scenario"] and config.get("DurationSeconds") == catalog["duration_s"]
            and config.get("Seed") == catalog["seed"] and md.get("SourceCommit") == PIN, "Archived config identity mismatch")
    require(config.get("ApplicationFlowLimit") == catalog["flow_limit"], "Archived flow limit mismatch")
    shared = config.get("SharedScenario", {})
    require(shared.get("SourceSHA256") == catalog["scenario_sha256"]
            and shared.get("HopSecurityProfile") == catalog["profile_id"], "Archived canonical profile mismatch")
    provenance = sweep.json_object(directory / "analysis/aggregate_provenance.json")
    require(provenance.get("source_snapshot_sha256") == source_snapshot_hash, "Aggregate source binding mismatch")
    counts = count_balance(stats, case_id)
    require(integer(stats.get("PhysicalAttempts"), "PhysicalAttempts") == sum(integer(stats.get(name), name)
            for name in ("PhysicalReceived", "PhysicalDropped", "PhysicalPending")), "Physical receiver accounting mismatch")
    for name in ("OmittedTraceRecords", "OmittedPhyTraceRecords"):
        require(integer(stats.get(name), name) == 0, "Truncated protocol/PHY trace evidence")
    performance = list(csv_records(directory / "analysis/performance_summary.csv"))
    require(len(performance) == 1, "Expected one performance row")
    metrics = sweep.metrics(performance[0])
    require(all(metrics[name] == counts[name] for name in COUNTS), "Performance/raw application counts mismatch")
    for file, mappings, bound in (("nodes.csv", {x: x for x in ("Generated", "Received", "Dropped")}, None),
                                  ("hop_nodes.csv", {"PendingData": "HopPendingData", "ResendQueueDepth": "ResendQueueDepth",
                                   "DackHoldCount": "DackHoldCount", "ControlPending": "ControlPending",
                                   "ControlPendingTargets": "ControlPendingTargets"}, None),
                                  ("nwk_nodes.csv", {"PendingCustody": "NwkPendingCustody",
                                   "PendingControlMessages": "NwkPendingControlMessages"}, ("PendingCustody", config["Nwk"]["QueueLimit"]))):
        node_rows = list(csv_records(directory / "raw" / file, mappings))
        for field, metric in mappings.items():
            require(sum(integer(row[field], field) for row in node_rows) == metrics[metric], "Per-node ownership/count mismatch")
        if bound:
            require(all(integer(row[bound[0]], bound[0]) <= bound[1] for row in node_rows), "NWK queue bound exceeded")
    admission = verify_admission(directory, config, stats)
    require(integer(manifest.get("admission_trace_omitted_records"), "omissions") == admission["omitted_trace_records"],
            "Manifest admission omission count mismatch")
    return {"case_id": case_id, "counts": counts, "admission": admission,
            "data_drained": bool(metrics["DataDrained"]), "controls_drained": bool(metrics["ControlsDrained"])}


def verify_return(root, source_root):
    root, source_root = Path(root).resolve(), Path(source_root).resolve()
    metadata = sweep.json_object(root / "validation_metadata.json")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 7, "Unsupported Tranche 7 schema")
    require(metadata.get("MatlabBaseCommit") == BASE and metadata.get("ValidatedTranche6CodeCommit") == T6_CODE,
            "Tranche 7 baseline identity mismatch")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB"
            and isinstance(runtime.get("Version"), str) and runtime["Version"]
            and isinstance(runtime.get("Release"), str) and runtime["Release"], "Missing MATLAB runtime/release")
    source = candidate_snapshot(source_root)
    source_binding(metadata, source, runtime)
    inventory(root, metadata.get("Artifacts"), "outer artifacts",
              excluded=("validation_metadata.json", "tranche7_evidence.zip"), local=metadata.get("LocalArtifacts", []))
    source_hash = sweep.digest(root / "source_snapshot.json")
    require(source_hash == metadata.get("SourceSnapshotSHA256")
            and sweep.snapshot(json.loads((root / "source_snapshot.json").read_text()), "source snapshot file") == source,
            "Hash-bound source snapshot file mismatch")
    catalog_path = source_root / "scenarios/benchmarks/catalog.json"
    catalog = sweep.json_object(catalog_path)
    require(catalog.get("schema") == "csr-benchmark-catalog-v1" and catalog.get("ns3_source_commit") == PIN,
            "Unsupported candidate benchmark catalog")
    verify_reference_suite(source_root, catalog)
    catalog_hash = sweep.digest(catalog_path)
    require(metadata.get("CatalogSHA256") == catalog_hash and sweep.digest(root / "benchmark_catalog.json") == catalog_hash,
            "Returned catalog is not the candidate catalog")
    entries = sweep.entries(catalog.get("cases"), "catalog cases")
    available = {x["case_id"]: x for x in entries}
    require(len(entries) == len(available), "Duplicate catalog cases")
    options = metadata.get("Options")
    require(isinstance(options, dict) and set(options) == {"RunTests", "IncludeNative", "Cases"}
            and type(options["RunTests"]) is bool and type(options["IncludeNative"]) is bool,
            "Invalid Tranche 7 options")
    require(metadata.get("TestsRequested") is options["RunTests"]
            and metadata.get("NativeRequested") is options["IncludeNative"], "Request flags disagree with options")
    selected = options["Cases"]
    if isinstance(selected, str):
        selected = [selected]
    require(isinstance(selected, list) and all(isinstance(x, str) for x in selected)
            and len(set(selected)) == len(selected), "Invalid selected cases")
    defaults = [x["case_id"] for x in entries if x.get("default") is True]
    selected = selected or defaults
    require(set(selected) <= set(available), "Unknown/deferred selected case")
    cases = sweep.entries(metadata.get("Cases"), "completed cases")
    require(len(cases) == len(selected) and {x.get("CaseId") for x in cases} == set(selected)
            and integer(metadata.get("CompletedCaseCount"), "completed cases") == len(cases)
            and integer(metadata.get("PlannedCaseCount"), "planned cases") == len(cases), "Missing/duplicated benchmark cases")
    plan = sweep.json_object(root / "benchmark_plan.json")
    planned = sweep.entries(plan.get("Cases"), "plan cases")
    require(plan.get("Schema") == "csr-matlab-benchmark-plan-v1" and plan.get("SourceCommit") == PIN
            and plan.get("CatalogSHA256") == catalog_hash and metadata.get("BenchmarkPlan") == "benchmark_plan.json"
            and integer(plan.get("CaseCount"), "plan cases") == len(selected)
            and len(planned) == len(selected) and {x.get("CaseId") for x in planned} == set(selected),
            "Benchmark plan identity mismatch")
    for item in planned:
        entry = available[item["CaseId"]]
        for field, catalog_field in (("Scenario", "scenario"), ("ScenarioFile", "scenario_file"),
                                     ("ScenarioSHA256", "scenario_sha256"), ("ProfileId", "profile_id"),
                                     ("DurationSeconds", "duration_s"), ("Seed", "seed"),
                                     ("BucketWidthSeconds", "bucket_width_s"), ("ReferenceDirectory", "reference_directory")):
            require(item.get(field) == entry[catalog_field], "Benchmark plan differs from canonical catalog")
    require(metadata.get("ReferenceFilesStableDuringRun") is True, "Reference stability unproven")
    initial = sweep.entries(metadata.get("ReferenceFiles"), "references")
    final = sweep.entries(metadata.get("ReferenceFilesFinal"), "final references")
    require(initial == final, "Reference snapshots changed during execution")
    expected_reference_paths = {f"{tree}/{relative}"
                                for tree in ("evidence/tranche-7-ns3-reference", "evidence/tranche-7-benchmark-inputs")
                                for relative in listed_files(source_root / tree)}
    require({x.get("path") for x in initial} == expected_reference_paths, "Reference snapshot membership mismatch")
    seen = set()
    for entry in initial:
        path = sweep.safe_path(source_root, entry.get("path"))
        require(entry["path"] not in seen, "Duplicate reference snapshot path")
        seen.add(entry["path"])
        require(path.stat().st_size == integer(entry.get("bytes"), "reference bytes")
                and sweep.digest(path) == sweep.valid_hash(entry.get("sha256"), "reference"), "Reference snapshot hash mismatch")
    regression = verify_regression(root, metadata, source, runtime, source_root)
    observations = [verify_case(root, item, available[item["CaseId"]], source, runtime, source_hash) for item in cases]
    for observed in observations:
        reference = sweep.safe_path(source_root, available[observed["case_id"]]["reference_directory"])
        observed["ns3_flows"] = reference_flow_progress(reference)
        observed["ns3_all_flows_made_progress"] = all(x["made_progress"] for x in observed["ns3_flows"])
    rows = list(csv_records(root / "benchmark_summary.csv", ("CaseId", *COUNTS, "Attempts", "AdmissionBlocked")))
    require(len(rows) == len(cases) and {x["CaseId"] for x in rows} == set(selected), "Benchmark summary membership mismatch")
    for row in rows:
        observed = next(x for x in observations if x["case_id"] == row["CaseId"])
        require(count_balance(row, row["CaseId"]) == observed["counts"]
                and integer(row["Attempts"], "attempts") == observed["admission"]["attempts"]
                and integer(row["AdmissionBlocked"], "blocked") == observed["admission"]["blocked"],
                "Benchmark summary counters mismatch")
    full = (set(selected) == set(defaults) and options["RunTests"]
            and regression["status"] == "passed" and regression["retained_cases"] == 28)
    report = {"schema": "csr-matlab-tranche-7-return-review-v1", "status": "structural_review_completed",
              "evidence_integrity_verified": True, "default_structural_gate_completed": full,
              "diagnostic_only": not full, "matlab_runtime": runtime,
              "metadata_sha256": sweep.digest(root / "validation_metadata.json"),
              "source_snapshot_sha256": source_hash, "source_files_verified": len(source),
              "reference_files_verified": len(initial), "regression": regression, "cases": observations,
              "all_flows_made_progress": all(x["admission"]["all_flows_made_progress"] for x in observations),
              "acceptance_established": False, "numerical_parity_established": False,
              "limitations": ["Hashes bind candidate inputs and returned records, not independent proof of MATLAB execution.",
                              "Numerical and no-sample differences require engineering review; delivery alone is not acceptance.",
                              "Admission counters remain complete when their separately bounded trace omits records.",
                              "Finite-stop pending applications and controls are reported rather than silently drained."]}
    return report, [(sweep.safe_path(root, x["Directory"]),
                     sweep.safe_path(source_root, available[x["CaseId"]]["reference_directory"])) for x in cases]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=REPO)
    parser.add_argument("--output", type=Path, required=True, help="New review directory outside evidence and candidate")
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        require(not output.exists(), "Review output already exists")
        require(not output.is_relative_to(args.evidence.resolve())
                and not output.is_relative_to(args.source_root.resolve()), "Output must be outside evidence and source")
        with evidence_directory(args.evidence) as root:
            report, cases = verify_return(root, args.source_root)
            output.mkdir(parents=True, exist_ok=False)
            results = []
            for case, reference in cases:
                result = compare.compare_case(case, reference, output / case.name)
                results.append({"case_id": case.name, "report": f"{case.name}/comparison.json",
                                "structural_gate_passed": result["structural_gate_passed"]})
            report["comparisons"] = results
            progress_rows = []
            for case in report["cases"]:
                for source, flows in (("matlab", case["admission"]["flows"]), ("ns3", case["ns3_flows"])):
                    progress_rows.extend(dict(case_id=case["case_id"], simulator=source, **row) for row in flows)
            if progress_rows:
                sweep.write_csv(output / "flow_progress.csv", list(progress_rows[0]), progress_rows)
            if args.evidence.is_file():
                report["uploaded_zip_sha256"] = sweep.digest(args.evidence)
            (output / "review.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        print(f"Reviewed {len(cases)} benchmarks; default structural gate={report['default_structural_gate_completed']}. Acceptance requires review.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error, zipfile.BadZipFile) as failure:
        print(f"Tranche 7 review failed: {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
