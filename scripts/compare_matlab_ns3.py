#!/usr/bin/env python3
"""Compare complete, provenance-matched CSR application observations.

Only the Python standard library is needed. This is an application comparison,
not a PHY/MAC/NWK trace-equivalence or OPNET certification tool.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
TIME_TOLERANCE_SECONDS = 1e-6
IDENTITY_FIELDS = (
    "scenario_sha256", "ns3_source_commit", "flow_limit", "application_profile",
    "mac_profile", "hop_security_profile",
)
RUN_OPTIONS = {
    "opnetAppGating": False,
    "stochasticSyncThreshold": False,
    "dutyCycling": True,
    "opnetAlignedDutyCycle": True,
    "gatewayDiscovery": True,
}
MATLAB_FIELDS = (
    "TimeSeconds,Event,NodeId,PeerId,PacketId,ApplicationBytes,Reason,FrameKind,"
    "Sequence,Dscp,QueueDepth,ControlType,HopCount"
).split(",")
NS3_FIELDS = (
    "schema,event_index,time_s,event,node,peer,packet_type,src,dst,sequence,"
    "rate_kbps,size_bytes,success,reason,pathloss_db,rx_power_dbm,noise_dbm,"
    "snr_db,jsr_db,header_errors,payload_errors,total_errors,route_cost,next_hop,"
    "security_count,reservation_slot,reservation_counter,detail,statistic,value"
).split(",")
APP_FIELDS = (
    "source,destination,ordinal,matlab_packet_id,ns3_sequence,matlab_payload_bytes,"
    "ns3_payload_bytes,matlab_dscp,ns3_dscp,matlab_generated_s,ns3_generated_s,matlab_status,"
    "ns3_status,matlab_latency_s,ns3_latency_s,latency_delta_s,delivery_equal"
).split(",")
FLOW_FIELDS = (
    "source,destination,matlab_generated,ns3_generated,matlab_delivered,"
    "ns3_delivered,matlab_delivery_ratio,ns3_delivery_ratio,"
    "matlab_delivered_payload_bytes,ns3_delivered_payload_bytes,"
    "matlab_mean_latency_s,ns3_mean_latency_s,application_equal"
).split(",")


class EvidenceError(ValueError):
    """An input cannot support a trustworthy comparison."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def integer(value, label: str, minimum: int = 0) -> int:
    require(not isinstance(value, bool), f"{label}: Boolean is not an integer")
    require(bool(re.fullmatch(r"[0-9]+", str(value))), f"{label}: invalid integer {value!r}")
    result = int(value)
    require(result >= minimum, f"{label}: integer below {minimum}")
    return result


def finite(value, label: str) -> float:
    require(not isinstance(value, bool), f"{label}: Boolean is not a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceError(f"{label}: invalid number {value!r}") from exc
    require(math.isfinite(result), f"{label}: nonfinite number")
    return result


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_object(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"{path.name}: duplicate JSON key {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise EvidenceError(f"{path.name}: nonfinite JSON constant {value}")

    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"),
                            object_pairs_hook=pairs, parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Cannot read {path}: {exc}") from exc
    require(isinstance(result, dict), f"{path.name}: expected JSON object")
    return result


def csv_rows(path: Path, required_fields, *, exact: bool = False):
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            names = reader.fieldnames
            require(names is not None, f"{path.name}: missing CSV header")
            require(len(names) == len(set(names)), f"{path.name}: duplicate CSV columns")
            require(all(name in names for name in required_fields), f"{path.name}: missing CSV columns")
            if exact:
                require(names == required_fields, f"{path.name}: unexpected CSV schema/header order")
            rows = []
            for line, row in enumerate(reader, 2):
                require(None not in row and all(value is not None for value in row.values()),
                        f"{path.name}:{line}: malformed or truncated CSV row")
                rows.append(row)
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise EvidenceError(f"Cannot read {path}: {exc}") from exc


def manifest(path: Path, schema: str):
    data = json_object(path)
    require(data.get("schema") == schema, f"{path.name}: wrong manifest schema")
    require(data.get("status") == "completed", f"{path.name}: run is not completed")
    for field in ("execution_completed", "source_files_stable"):
        require(data.get(field) is True, f"{path.name}: {field} must be true")
    if "exit_code" in data:
        require(type(data["exit_code"]) is int and data["exit_code"] == 0,
                f"{path.name}: execution failed")
    if "structural_checks_passed" in data:
        require(data["structural_checks_passed"] is True, f"{path.name}: structural checks failed")
    require(data.get("ns3_source_commit") == PIN, f"{path.name}: foreign ns-3 source pin")
    for field in IDENTITY_FIELDS:
        require(field in data, f"{path.name}: missing {field}")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", str(data["scenario_sha256"]))),
            f"{path.name}: invalid scenario SHA-256")
    integer(data["flow_limit"], "flow_limit")
    for field in ("application_profile", "mac_profile", "hop_security_profile"):
        require(isinstance(data[field], str) and bool(data[field]), f"Invalid {field}")
    options = data.get("run_options")
    require(isinstance(options, dict), f"{path.name}: missing run_options")
    for key, expected in RUN_OPTIONS.items():
        require(options.get(key) is expected, f"{path.name}: unsupported run option {key}")
    require(set(options) == set(RUN_OPTIONS), f"{path.name}: unknown run options")
    entries = data.get("files")
    require(isinstance(entries, list) and bool(entries), f"{path.name}: missing file inventory")
    files = {}
    for entry in entries:
        require(isinstance(entry, dict), f"{path.name}: invalid file entry")
        relative = entry.get("path")
        require(isinstance(relative, str) and bool(relative), "Missing inventory path")
        part = Path(relative)
        require(not part.is_absolute() and ".." not in part.parts and "\\" not in relative,
                f"Unsafe inventory path: {relative}")
        full = (path.parent / part).resolve()
        require(full.is_relative_to(path.parent.resolve()), f"Inventory path escapes case: {relative}")
        require(relative not in files and full.is_file(), f"Missing or duplicate file: {relative}")
        expected = entry.get("sha256")
        require(isinstance(expected, str) and bool(re.fullmatch(r"[0-9a-f]{64}", expected)),
                f"Invalid file hash: {relative}")
        require(digest(full) == expected, f"SHA-256 mismatch: {relative}")
        files[relative] = (full, entry)
    for required in ("scenario.csv",):
        require(required in files, f"{path.name}: missing {required} evidence")
    require(files["scenario.csv"][1]["sha256"] == data["scenario_sha256"],
            f"{path.name}: scenario identity does not match scenario.csv")
    return data, files


def inventory_rows(files, name, fields, *, exact=False, count_required=False):
    require(name in files, f"Missing evidence inventory entry: {name}")
    path, entry = files[name]
    rows = csv_rows(path, fields, exact=exact)
    if count_required or "row_count" in entry:
        require("row_count" in entry, f"{name}: missing recorded row_count")
        require(integer(entry["row_count"], f"{name} row_count") == len(rows),
                f"{name}: row_count mismatch (truncated or stale evidence)")
    return rows


def scenario_contract(files, identity):
    rows = inventory_rows(files, "scenario.csv", ["record", "schema", "scenario", "duration_s",
        "application_profile", "mac_profile", "hop_security_profile", "flow_src", "flow_dst",
        "flow_destination_mode", "flow_start_s", "flow_interval_s", "flow_packet_bytes", "flow_dscp"])
    require(rows and all(row["schema"] == "csr-opnet-scenario-v1" for row in rows),
            "scenario.csv: wrong or empty scenario schema")
    runs = [row for row in rows if row["record"] == "run"]
    require(len(runs) == 1, "scenario.csv: expected one run record")
    run = runs[0]
    require(bool(run["scenario"]), "scenario.csv: missing scenario name")
    for field in ("application_profile", "mac_profile", "hop_security_profile"):
        require(run[field] == identity[field], f"scenario.csv: inconsistent {field}")
    duration = finite(run["duration_s"], "scenario duration")
    require(duration > 0, "scenario duration must be positive")
    flows = []
    for row in rows:
        if row["record"] != "flow":
            continue
        require(row["flow_destination_mode"] == "fixed", "Only fixed-destination comparison is supported")
        source = integer(row["flow_src"], "flow source", 1)
        destination = integer(row["flow_dst"], "flow destination", 1)
        require(source != destination, "Self-addressed flow is outside comparison scope")
        payload = integer(row["flow_packet_bytes"], "configured flow bytes", 15) - 15
        start = finite(row["flow_start_s"], "flow start")
        interval = finite(row["flow_interval_s"], "flow interval")
        dscp = integer(row["flow_dscp"], "flow DSCP")
        require(start >= 0 and interval > 0 and dscp <= 7, "Invalid flow schedule or DSCP")
        flows.append({"source": source, "destination": destination, "payload": payload,
                      "start": start, "interval": interval, "dscp": dscp})
    require(bool(flows), "scenario.csv: no comparable application flows")
    return run["scenario"], duration, flows


@dataclass
class Application:
    uid: str
    source: int
    destination: int
    generated: float
    payload: int
    dscp: int
    status: str = "pending"
    received: float | None = None

    @property
    def latency(self):
        return None if self.received is None else self.received - self.generated


def trace_clock(rows, key, duration):
    previous = -1.0
    for row in rows:
        current = finite(row[key], "trace time")
        require(0 <= current <= duration + TIME_TOLERANCE_SECONDS, "Trace time outside scenario duration")
        require(current >= previous, "Trace time moves backwards")
        previous = current


def matlab_applications(files, identity, duration):
    rows = inventory_rows(files, "protocol_trace.csv", MATLAB_FIELDS, exact=True, count_required=True)
    require(bool(rows), "Empty MATLAB protocol trace")
    trace_clock(rows, "TimeSeconds", duration)
    apps = {}
    for row in rows:
        event = row["Event"]
        if event not in ("app_generate", "app_receive", "app_drop", "relay_accept"):
            continue
        uid = str(integer(row["PacketId"], "MATLAB PacketId"))
        now = finite(row["TimeSeconds"], "MATLAB application time")
        payload = integer(row["ApplicationBytes"], "MATLAB application bytes")
        node = integer(row["NodeId"], "MATLAB node", 1)
        peer = integer(row["PeerId"], "MATLAB peer", 1)
        dscp = integer(row["Dscp"], "MATLAB DSCP")
        if event == "app_generate":
            require(uid not in apps, f"Duplicate MATLAB generation identity {uid}")
            apps[uid] = Application(uid, node, peer, now, payload, dscp)
            continue
        require(uid in apps, f"Unknown MATLAB application identity {uid} in {event}")
        app = apps[uid]
        require(payload == app.payload and dscp == app.dscp, "Inconsistent MATLAB application payload/DSCP")
        require(now >= app.generated, "MATLAB application observation before generation")
        if event == "app_receive":
            require(node == app.destination, "MATLAB application delivered at wrong endpoint")
            require(app.received is None, f"Duplicate MATLAB delivery identity {uid}")
            app.status, app.received = "delivered", now
        elif event == "app_drop":
            require(peer == app.destination, "MATLAB drop has wrong destination")
            require(app.status == "pending", f"Duplicate/inconsistent MATLAB drop identity {uid}")
            app.status = "dropped"
        elif app.status == "dropped":
            # A late retained relay custody transfer reverses an earlier drop.
            app.status = "pending"
    require(bool(apps), "MATLAB trace contains no application generations")
    require("summary.json" in files, "Missing MATLAB summary.json")
    summary = json_object(files["summary.json"][0])
    stats = summary.get("Statistics", {})
    require(isinstance(stats, dict), "Invalid MATLAB summary statistics")
    expected = {
        "Generated": len(apps),
        "Received": sum(app.status == "delivered" for app in apps.values()),
        "Dropped": sum(app.status == "dropped" for app in apps.values()),
        "Pending": sum(app.status == "pending" for app in apps.values()),
        "ApplicationBytesReceived": sum(app.payload for app in apps.values() if app.received is not None),
        "OmittedTraceRecords": 0,
        "OmittedPhyTraceRecords": 0,
    }
    for key, value in expected.items():
        require(key in stats and integer(stats[key], key) == value,
                f"MATLAB summary {key} disagrees with trace or indicates omitted records")
    config = summary.get("Config", {})
    require(isinstance(config, dict), "Invalid MATLAB Config")
    shared = config.get("SharedScenario", {})
    require(isinstance(shared, dict), "Invalid MATLAB SharedScenario")
    mapping = {"SourceSHA256": "scenario_sha256", "SourceCommit": "ns3_source_commit",
               "FlowLimit": "flow_limit", "ApplicationProfile": "application_profile",
               "MacProfile": "mac_profile", "HopSecurityProfile": "hop_security_profile"}
    for key, manifest_key in mapping.items():
        require(shared.get(key) == identity[manifest_key], f"MATLAB summary provenance mismatch: {key}")
    require(shared.get("RunOptions") == identity["run_options"], "MATLAB summary run options mismatch")
    require(finite(config.get("DurationSeconds"), "MATLAB duration") == duration,
            "MATLAB summary duration mismatch")
    metadata = summary.get("Metadata", {})
    require(isinstance(metadata, dict) and metadata.get("SourceCommit") == PIN,
            "MATLAB runtime metadata source pin mismatch")
    return list(apps.values())


def ns3_applications(files, identity, scenario_name, duration, flows):
    rows = inventory_rows(files, "trace.csv", NS3_FIELDS, exact=True, count_required=True)
    require(bool(rows), "Empty ns-3 trace")
    trace_clock(rows, "time_s", duration)
    apps = {}
    for index, row in enumerate(rows):
        require(row["schema"] == "csr-differential-trace-v1", "Wrong ns-3 trace schema")
        require(integer(row["event_index"], "ns-3 event_index") == index,
                "Noncontiguous ns-3 event_index (missing, duplicated or reordered records)")
        event = row["event"]
        if event not in ("app_send", "nwk_delivery"):
            continue
        uid = str(integer(row["sequence"], "ns-3 application sequence"))
        source = integer(row["src"], "ns-3 application source", 1)
        destination = integer(row["dst"], "ns-3 application destination", 1)
        node = integer(row["node"], "ns-3 application node", 1)
        now = finite(row["time_s"], "ns-3 application time")
        payload = integer(row["size_bytes"], "ns-3 application bytes", 7) - 7
        require(row["packet_type"] == "data", "ns-3 application observation has wrong packet type")
        if event == "app_send":
            require(uid not in apps, f"Duplicate ns-3 generation identity {uid}")
            require(node == source, "ns-3 send has wrong source node")
            match = re.fullmatch(r"dscp=([0-9]+)", row["detail"])
            require(match is not None, "ns-3 application send missing canonical DSCP detail")
            apps[uid] = Application(uid, source, destination, now, payload, int(match.group(1)),
                                    status="not_observed_delivered")
            continue
        require(uid in apps, f"Unknown ns-3 delivery sequence {uid}")
        app = apps[uid]
        require((source, destination, payload) == (app.source, app.destination, app.payload),
                "Inconsistent ns-3 application delivery identity/payload")
        require(node == destination and row["success"] == "1", "Invalid ns-3 final delivery")
        require(now >= app.generated and app.received is None, f"Duplicate or early ns-3 delivery {uid}")
        app.received, app.status = now, "delivered"
    require(bool(apps), "ns-3 trace contains no application sends")
    if "observations" in identity:
        require(isinstance(identity["observations"], dict), "Invalid ns-3 observation totals")
        for event, expected in identity["observations"].items():
            require(integer(expected, f"ns-3 {event} observations") == sum(row["event"] == event for row in rows),
                    f"ns-3 {event} observations disagree with trace")
    diagnostics = inventory_rows(files, "app_diagnostics.csv", ["schema", "scenario", "application_profile",
        "flow_index", "source", "configured_destination", "destination_mode", "attempts", "admitted",
        "blocked_discovery", "blocked_topology", "blocked_gateway_route", "blocked_destination", "blocked_nsdp",
        "first_admitted_s", "last_admitted_s"])
    require(len(diagnostics) == len(flows), "ns-3 application diagnostics missing/extra flows")
    seen = set()
    totals = defaultdict(int)
    for row in diagnostics:
        require(row["schema"] == "csr-app-admission-diagnostics-v1", "Wrong ns-3 diagnostics schema")
        require(row["scenario"] == scenario_name and row["application_profile"] == identity["application_profile"],
                "ns-3 application diagnostics scenario/profile mismatch")
        index = integer(row["flow_index"], "diagnostic flow index")
        require(index < len(flows) and index not in seen, "Duplicate/unknown diagnostic flow index")
        seen.add(index)
        flow = flows[index]
        endpoints = (integer(row["source"], "diagnostic source", 1),
                     integer(row["configured_destination"], "diagnostic destination", 1))
        require(endpoints == (flow["source"], flow["destination"]) and row["destination_mode"] == "fixed",
                "Diagnostic flow identity mismatch")
        admitted = integer(row["admitted"], "diagnostic admitted")
        attempts = integer(row["attempts"], "diagnostic attempts")
        blocked = sum(integer(row[key], key) for key in ("blocked_discovery", "blocked_topology",
            "blocked_gateway_route", "blocked_destination", "blocked_nsdp"))
        require(attempts == admitted + blocked and blocked == 0,
                "Diagnostic admission counts contradict disabled application gating")
        if admitted:
            first = finite(row["first_admitted_s"], "first admitted time")
            last = finite(row["last_admitted_s"], "last admitted time")
            require(0 <= first <= last <= duration, "Invalid diagnostic admission times")
            same_endpoint_flows = [f for f in flows if (f["source"], f["destination"]) == endpoints]
            if len(same_endpoint_flows) == 1:
                generated = [app.generated for app in apps.values() if (app.source, app.destination) == endpoints]
                require(generated and abs(first - min(generated)) <= TIME_TOLERANCE_SECONDS
                        and abs(last - max(generated)) <= TIME_TOLERANCE_SECONDS,
                        "Diagnostic admission times disagree with trace")
        totals[endpoints] += admitted
    observed = defaultdict(int)
    for app in apps.values():
        observed[(app.source, app.destination)] += 1
    require(dict(totals) == dict(observed), "ns-3 diagnostic admitted counts disagree with trace")
    return list(apps.values())


def validate_generation(apps, flows, flow_limit, duration, label):
    """Check each observed generation against the shared controlled schedule.

    Missing scheduled generations remain a comparison diagnostic. Hash, row
    count, summary and admission-ledger checks establish evidence completeness.
    """
    occupied = set()
    for app in apps:
        choices = []
        for index, flow in enumerate(flows):
            if (app.source, app.destination, app.payload, app.dscp) != (
                    flow["source"], flow["destination"], flow["payload"], flow["dscp"]):
                continue
            ordinal = round((app.generated - flow["start"]) / flow["interval"])
            expected = flow["start"] + ordinal * flow["interval"]
            if ordinal >= 0 and (flow_limit == 0 or ordinal < flow_limit) and expected <= duration and abs(
                    app.generated - expected) <= TIME_TOLERANCE_SECONDS:
                choices.append((index, ordinal))
        available = [choice for choice in choices if choice not in occupied]
        require(bool(available), f"{label}: generation payload, DSCP, time or multiplicity contradicts scenario")
        occupied.add(available[0])


def aligned(apps):
    flows = defaultdict(list)
    for app in apps:
        flows[(app.source, app.destination)].append(app)
    result = {}
    for endpoints, members in flows.items():
        # Stable ordering preserves each runtime's generation order at ties.
        for ordinal, app in enumerate(sorted(members, key=lambda item: item.generated), 1):
            result[(*endpoints, ordinal)] = app
    return result


def compare(matlab_dir: Path, reference_manifest: Path):
    mat, mf = manifest(matlab_dir / "case_manifest.json", "csr-matlab-research-case-v1")
    ns, nf = manifest(reference_manifest, "csr-matlab-ns3-reference-case-v1")
    for field in IDENTITY_FIELDS + ("run_options",):
        require(mat[field] == ns[field], f"Cross-simulator case/profile mismatch: {field}")
    name, duration, flows = scenario_contract(nf, ns)
    scenario_contract(mf, mat)
    ma = matlab_applications(mf, mat, duration)
    na = ns3_applications(nf, ns, name, duration, flows)
    for label, apps in (("MATLAB", ma), ("ns-3", na)):
        validate_generation(apps, flows, int(mat["flow_limit"]), duration, label)
    left, right = aligned(ma), aligned(na)
    rows, differences = [], []
    for key in sorted(set(left) | set(right)):
        m, n = left.get(key), right.get(key)
        equal = m is not None and n is not None
        if equal:
            equal = (m.payload == n.payload and m.dscp == n.dscp
                     and abs(m.generated - n.generated) <= TIME_TOLERANCE_SECONDS
                     and (m.received is not None) == (n.received is not None))
        if not equal:
            differences.append({"source": key[0], "destination": key[1], "ordinal": key[2],
                                "reason": "generation_or_delivery_mismatch"})
        rows.append(dict(zip(APP_FIELDS, [*key, m.uid if m else None, n.uid if n else None,
            m.payload if m else None, n.payload if n else None, m.dscp if m else None, n.dscp if n else None,
            m.generated if m else None,
            n.generated if n else None, m.status if m else "missing_generation",
            n.status if n else "missing_generation", m.latency if m else None, n.latency if n else None,
            m.latency - n.latency if m and n and m.latency is not None and n.latency is not None else None,
            equal])))
    flow_rows = []
    for source, destination in sorted({(row["source"], row["destination"]) for row in rows}):
        mflow = [app for app in ma if (app.source, app.destination) == (source, destination)]
        nflow = [app for app in na if (app.source, app.destination) == (source, destination)]
        md = [app for app in mflow if app.received is not None]
        nd = [app for app in nflow if app.received is not None]
        equal = all(row["delivery_equal"] for row in rows if (row["source"], row["destination"]) == (source, destination))
        flow_rows.append(dict(zip(FLOW_FIELDS, [source, destination, len(mflow), len(nflow), len(md), len(nd),
            len(md) / len(mflow) if mflow else None, len(nd) / len(nflow) if nflow else None,
            sum(app.payload for app in md), sum(app.payload for app in nd),
            sum(app.latency for app in md) / len(md) if md else None,
            sum(app.latency for app in nd) / len(nd) if nd else None, equal])))
    report = {
        "schema": "csr-matlab-ns3-application-comparison-v1",
        "status": "application_match" if not differences else "application_differences",
        "evidence_valid": True,
        "application_equal": not differences,
        "full_protocol_parity": False,
        "scenario": name,
        "identity": {field: mat[field] for field in IDENTITY_FIELDS},
        "generation_time_tolerance_seconds": TIME_TOLERANCE_SECONDS,
        "matlab_manifest_sha256": digest(matlab_dir / "case_manifest.json"),
        "ns3_manifest_sha256": digest(reference_manifest),
        "application_count_matlab": len(ma),
        "application_count_ns3": len(na),
        "differences": differences,
        "flows": flow_rows,
        "limitations": [
            "Application identities are aligned by source/destination generation ordinal; runtime IDs are not equated.",
            "Payload conversion: ns-3 size_bytes minus 7; scenario flow_packet_bytes minus 15.",
            "Latency differences are diagnostic and do not fail application equality.",
            "Missing ns-3 delivery is not evidence of terminal application drop.",
            "PHY/MAC/NWK timing, rates, control counts, RNG streams and security equivalence are not certified.",
            "A matching application outcome does not establish OPNET or full network-level parity.",
        ],
    }
    return report, rows, flow_rows


def write_results(output: Path, report, applications, flows):
    output.mkdir(parents=True, exist_ok=True)
    for filename, fields, rows in (("applications.csv", APP_FIELDS, applications),
                                   ("flows.csv", FLOW_FIELDS, flows)):
        with (output / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (output / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matlab", type=Path, required=True, help="MATLAB case output directory")
    parser.add_argument("--ns3", type=Path, required=True, help="ns-3 reference case manifest JSON")
    parser.add_argument("--output", type=Path, required=True, help="dedicated comparison output directory")
    parser.add_argument("--require-application-equality", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(args.output.resolve() not in (args.matlab.resolve(), args.ns3.parent.resolve()),
                "Comparison output must differ from evidence directories")
        report, apps, flows = compare(args.matlab, args.ns3)
        write_results(args.output, report, apps, flows)
        print(f"{report['status']}: MATLAB {report['application_count_matlab']} applications; "
              f"ns-3 {report['application_count_ns3']} applications; full protocol parity is not asserted")
        return 1 if args.require_application_equality and not report["application_equal"] else 0
    except (EvidenceError, OSError) as exc:
        report = {"schema": "csr-matlab-ns3-application-comparison-v1", "status": "invalid_evidence",
                  "evidence_valid": False, "application_equal": False, "full_protocol_parity": False,
                  "errors": [str(exc)]}
        if args.output.resolve() not in (args.matlab.resolve(), args.ns3.parent.resolve()):
            try:
                write_results(args.output, report, [], [])
            except OSError as output_error:
                print(f"Cannot write comparison output: {output_error}", file=sys.stderr)
        print(f"invalid_evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
