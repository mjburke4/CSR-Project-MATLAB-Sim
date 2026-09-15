#!/usr/bin/env python3
"""Read-only independent T9 owner-return gate; stdlib, no project imports.

Run: python3 independent_qa.py --archive /path/tranche9_evidence.zip
      --candidate /path/to/frozen/99fff038 --output /path/receipt.json
No simulation is executed. All artifact data stays in the uploaded ZIP.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

PIN = "99fff0381fe9621ccd76fbdce41eac9aba5a9469"
ARCHIVE_SHA = "ddcede0a83b5ff906a7736f63406fc4cecb11e841795e39e93237364e0e11edf"
NS3_PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
BOOL_ADMISSION = {"Accepted", "DiscoveryActive", "TopologyKnown", "GatewayCached", "RouteCheckPerformed", "RouteAvailable"}
DIRECT = {"app_generate", "app_receive", "app_drop", "relay_accept", "network_policy_drop", "hop_delivery_unconfirmed", "tx_start", "link_drop", "fault_drop", "link_enable", "link_disable", "discovery_request"}
LEGACY_CSV = {"trace.csv", "protocol_trace.csv", "phy_trace.csv", "nodes.csv", "mac_nodes.csv", "hop_nodes.csv", "nwk_nodes.csv", "routes.csv", "neighbors.csv", "application_admission_statistics.csv", "application_admission_trace.csv", "scenario.csv"}


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def entries(value):
    return [value] if isinstance(value, dict) else value


def num(value):
    check(type(value) is not bool, "Boolean supplied for numerical field")
    x = float(value)
    check(math.isfinite(x), "Nonfinite numerical field")
    return x


def boolean(value):
    if type(value) is bool:
        return value
    check(value in (0, 1, "0", "1"), "Invalid explicit boolean")
    return str(value) == "1"


def close(a, b):
    return math.isclose(num(a), num(b), rel_tol=2e-12, abs_tol=1e-9)


def csv_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))


def verify(args):
    root = Path(args.candidate).resolve()
    archive = Path(args.archive).resolve()
    actual_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    check(actual_commit == PIN, "Wrong frozen candidate commit")
    tree = {}
    for record in subprocess.check_output(["git", "ls-tree", "-r", "-z", "HEAD"], cwd=root).split(b"\0"):
        if record:
            meta, name = record.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            check(kind == "blob", "Non-blob Git item")
            tree[name.decode()] = (mode, blob)

    def committed_bytes(name):
        check(name in tree, "Source path not in committed candidate: " + name)
        p = root / name
        check(not p.is_symlink(), "Symlink in candidate")
        data = p.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        check(blob == tree[name][1], "Working file differs from committed Git blob: " + name)
        return data

    receipt = {"schema": "csr-tranche9-independent-owner-return-qa-v1", "candidate_commit": PIN,
               "archive_sha256": sha(archive.read_bytes()), "archive_bytes": archive.stat().st_size,
               "simulation_executed_by_reviewer": False}
    check(receipt["archive_sha256"] == ARCHIVE_SHA, "Owner archive changed")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        check(len(names) == len(set(names)) == len({name.casefold() for name in names}), "Duplicate ZIP member")
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            check(not p.is_absolute() and ".." not in p.parts and "\\" not in info.filename and ":" not in info.filename,
                  "Unsafe ZIP path")
            check(not info.is_dir() and not stat.S_ISLNK(info.external_attr >> 16), "Non-file ZIP member")
        actual_files = {}
        for name in names:
            data = z.read(name)  # ZIP CRC is verified by stdlib at EOF.
            actual_files[name] = {"sha256": sha(data), "bytes": len(data)}
        receipt["archive_members"] = len(names)
        receipt["expanded_bytes"] = sum(v["bytes"] for v in actual_files.values())
        receipt["crc_and_safe_membership_passed"] = True

        def get_json(name):
            return json.loads(z.read(name))

        metadata = get_json("validation_metadata.json")
        check(metadata["Schema"] == "csr-matlab-tranche-9-validation-v1" and metadata["Status"] == "completed", "Incomplete T9 metadata")
        check(metadata["MATLABExecuted"] is True and metadata["SourceCommit"] == NS3_PIN, "Missing owner execution or source pin")
        runtime = metadata["Runtime"]
        check(runtime["Runtime"] == "MATLAB" and runtime["Version"] == "25.1.0.2943329 (R2025a)" and runtime["Release"] == "2025a" and runtime["DefaultBackend"] == "portable", "Unexpected runtime")
        check(metadata["NativeRequested"] is False and metadata["NativeExecuted"] is False, "Native scope mismatch")
        receipt["owner_runtime"] = runtime
        receipt["started_utc"], receipt["completed_utc"] = metadata["StartedUTC"], metadata["CompletedUTC"]
        start, stop = (datetime.datetime.fromisoformat(metadata[k].replace("Z", "+00:00")) for k in ("StartedUTC", "CompletedUTC"))
        receipt["elapsed_seconds"] = (stop - start).total_seconds()

        source_rows = metadata["SourceFiles"]
        source = {row["path"]: row["sha256"] for row in source_rows}
        check(len(source) == len(source_rows) and metadata["SourceFilesFinal"] == source_rows and metadata["SourceFilesStableDuringRun"] is True, "Source identity/stability mismatch")
        patterns = ("*.m", "+csr/**/*.m", "tests/**/*.m", "examples/**/*.m", "scripts/**/*.py", "scripts/**/*.cc", "scripts/**/*.h", "data/**/*", "scenarios/**/*", "evidence/tranche-*-candidate.json", "evidence/source-baseline.json")
        expected = {p.relative_to(root).as_posix() for pattern in patterns for p in root.glob(pattern) if p.is_file()}
        check(set(source) == expected, "Incomplete source snapshot membership")
        for name, digest in source.items():
            check(sha(committed_bytes(name)) == digest, "Returned source hash mismatch: " + name)
        check(get_json("source_snapshot.json") == source_rows and actual_files["source_snapshot.json"]["sha256"] == metadata["SourceSnapshotSHA256"], "Source snapshot file mismatch")
        receipt["committed_source_files_verified"] = len(source)
        receipt["committed_matlab_files_verified"] = sum(name.endswith(".m") for name in source)
        reference = metadata["ReferenceFiles"]
        check(reference == metadata["ReferenceFilesFinal"] and metadata["ReferenceFilesStableDuringRun"] is True, "Reference stability mismatch")
        ref_roots = ("evidence/tranche-9-ns3-reference", "evidence/tranche-9-contract-reference", "evidence/tranche-8-ns3-reference", "evidence/tranche-7-ns3-reference", "evidence/tranche-7-benchmark-inputs")
        expected_refs = {p.relative_to(root).as_posix() for path in ref_roots for p in (root/path).rglob("*") if p.is_file()}
        expected_refs.add("evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip")
        check({row["path"] for row in reference} == expected_refs and len(reference) == len(expected_refs), "Reference membership mismatch")
        for row in reference:
            data = committed_bytes(row["path"])
            check(sha(data) == row["sha256"] and len(data) == row["bytes"], "Returned reference hash mismatch: " + row["path"])
        receipt["committed_reference_files_verified"] = len(reference)

        checks = []
        def inventory(prefix, listed, excluded):
            listed = entries(listed)
            expected_names = {prefix + row["path"] for row in listed}
            actual_names = {name for name in names if name.startswith(prefix)} - set(excluded)
            check(len(listed) == len(expected_names) and expected_names == actual_names, "Inventory membership mismatch: " + prefix)
            for row in listed:
                name = prefix + row["path"]
                check(actual_files[name]["sha256"] == row["sha256"] and actual_files[name]["bytes"] == row["bytes"], "Inventory hash/size mismatch: " + name)
                checks.append(name)
        inventory("", metadata["Artifacts"], {"validation_metadata.json"})
        receipt["outer_artifact_checks"] = len(checks)
        plan = get_json("diagnostic_plan.json")
        plan_bytes = committed_bytes("scenarios/ack_service/plan.json")
        check(z.read("diagnostic_plan.json") == plan_bytes and sha(plan_bytes) == metadata["DiagnosticPlanSHA256"], "Returned plan differs from committed input")
        keys = [c["storage_key"] for c in plan["cases"]]
        check(keys == ["c129", "c128", "c130", "c131", "c132", "a129"] and plan["control_keys"] == ["c129", "a129"], "Case or control plan membership mismatch")
        check(metadata["CompletedCaseCount"] == metadata["PlannedCaseCount"] == 6 and [r["Directory"] for r in metadata["Cases"]] == ["b/" + k for k in keys], "Returned cases incomplete")
        for row in metadata["Cases"]:
            check(actual_files[row["Directory"] + "/benchmark_manifest.json"]["sha256"] == row["ManifestSHA256"], "Case manifest binding mismatch")

        for name in names:
            if name.endswith("benchmark_manifest.json") or name.endswith("case_manifest.json"):
                m = get_json(name)
                prefix = str(PurePosixPath(name).parent) + "/"
                inventory(prefix, m["files"], {name})
                check(m["source_files"] == source_rows and m["ns3_source_commit"] == NS3_PIN and m["status"] == "completed", "Case provenance mismatch")
                check(m["matlab_version"] == runtime["Version"] and m["matlab_release"] == runtime["Release"], "Case runtime mismatch")
                check(m["structural_checks_passed"] is True, "Case structural flag failed")
        receipt["nested_artifact_checks"] = len(checks) - receipt["outer_artifact_checks"]
        receipt["total_declared_artifact_hash_and_size_checks"] = len(checks)
        receipt["local_mat_artifacts_not_in_upload"] = len(entries(metadata["LocalArtifacts"]))
        check(not any(name.endswith(".mat") for name in names), "Unexpected MAT in portable evidence")

        returned_tests = csv_rows(z.read("tests/test_results.csv"))
        expected_tests = set()
        for p in (root/"tests").glob("Test*.m"):
            in_test = False
            for line in committed_bytes(p.relative_to(root).as_posix()).decode().splitlines():
                if re.match(r"^    methods\b", line):
                    in_test = re.search(r"\bTest\b", line) is not None
                match = re.match(r"^        function\s+(\w+)\s*\(", line)
                if in_test and match:
                    expected_tests.add(p.stem + "/" + match.group(1))
        check(len(returned_tests) == len(expected_tests) == 514 and {row["Name"] for row in returned_tests} == expected_tests, "Full portable test membership mismatch")
        check(all(row["Passed"] == "1" and row["Failed"] == row["Incomplete"] == "0" and num(row["DurationSeconds"]) >= 0 for row in returned_tests), "Test failure/incompletion")
        prepared = json.loads(committed_bytes("evidence/tranche-9-local-checks/prepared-test-membership.json"))
        check(set(prepared["tests"]) == expected_tests, "Prepared independent test inventory mismatch")
        check(metadata["TestCount"] == metadata["PassedTests"] == 514 and metadata["FailedTests"] == metadata["IncompleteTests"] == 0, "Test metadata mismatch")
        log = z.read("validation.log").decode()
        for test_class in {name.split("/")[0] for name in expected_tests}:
            check("Running " + test_class in log and "Done " + test_class in log, "Missing test class in owner diary")
        check(not re.search(r"(^|\n)(Error using|Error in|Failed Tests|Uncaught exception)", log), "Error marker in owner diary")
        receipt["test_count"] = len(returned_tests)
        receipt["passed_tests"] = len(returned_tests)
        receipt["failed_tests"] = receipt["incomplete_tests"] = 0
        receipt["summed_test_duration_seconds"] = sum(num(row["DurationSeconds"]) for row in returned_tests)

        contract = csv_rows(z.read("contracts/checkpoints.csv"))
        reference_bytes = committed_bytes("evidence/tranche-9-contract-reference/checkpoints.csv")
        native_contract = csv_rows(reference_bytes)
        csum = get_json("contracts/summary.json")
        check(csum["ReferenceSHA256"] == sha(reference_bytes) and csum["CheckpointCount"] == len(contract) == len(native_contract) == 101, "Contract reference/count mismatch")
        check(csum["FailedCount"] == csum["UnmatchedCount"] == 0 and csum["Passed"] is True, "Contract summary failed")
        identities = []
        max_contract_delta = 0
        for a, b in zip(contract, native_contract):
            identity = tuple(a[k] for k in ("case", "checkpoint", "field"))
            identities.append(identity)
            check(identity == tuple(b[k] for k in ("case", "checkpoint", "field")), "Contract identity/order mismatch")
            check(a["pass"] == b["pass"] == "1", "Contract row failed")
            for k in ("time_seconds", "actual", "expected"):
                delta = abs(num(a[k])-num(b[k]))
                max_contract_delta = max(max_contract_delta, delta)
                check(delta <= 1e-9, "Contract numerical mismatch")
            check(abs(num(a["actual"])-num(a["expected"])) <= 1e-9, "Owner actual does not satisfy contract")
        check(len(set(identities)) == 101, "Duplicated contract checkpoint")
        receipt["contract_checkpoints_passed"] = len(contract)
        receipt["contract_cases"] = dict(collections.Counter(row["case"] for row in contract))
        receipt["contract_max_abs_difference_from_native"] = max_contract_delta

        nonperturb = get_json("nonperturbation.json")
        control_pairs = 0
        for row in nonperturb["cases"]:
            on, off = row["observer_on_directory"] + "/", row["observer_off_directory"] + "/"
            left, right = get_json(on+"summary.json"), get_json(off+"summary.json")
            check(left["Statistics"] == right["Statistics"] and left["Config"] == right["Config"], "Observer perturbed statistics/configuration")
            check("ServiceDiagnostics" not in right and "LinkDiagnostics" not in right, "Off control contains observer summary")
            check(set(x["path"] for x in row["compared_files"]) == LEGACY_CSV, "Control comparison membership mismatch")
            for comp in row["compared_files"]:
                key = comp["path"]
                check(z.read(on+key) == z.read(off+key), "Observer perturbed legacy CSV: " + key)
                check(actual_files[on+key]["sha256"] == comp["observer_on_sha256"] == comp["observer_off_sha256"], "Unbound nonperturbation hashes")
                control_pairs += 1
        check(len(nonperturb["cases"]) == 2 and control_pairs == 24, "Missing control execution")
        receipt["controls_passed"] = 2
        receipt["byte_exact_control_csv_pairs"] = control_pairs

        service_cases = []
        total_logical_fields = collections.Counter()
        for key in keys:
            prefix = "b/" + key + "/raw/"
            summary = get_json(prefix+"summary.json")
            stats = summary["Statistics"]
            check(stats["Generated"] == stats["Received"] + stats["Dropped"] + stats["Pending"], "Application conservation mismatch")
            check(all(stats[k] == 0 for k in ("OmittedTraceRecords", "OmittedPhyTraceRecords", "OmittedApplicationAdmissionRecords")), "Omitted legacy trace records")
            service = csv_rows(z.read(prefix+"service_trace.csv"))
            protocol = csv_rows(z.read(prefix+"protocol_trace.csv"))
            admissions = csv_rows(z.read(prefix+"application_admission_trace.csv"))
            svc = summary["ServiceDiagnostics"]
            in_window = lambda row: 300 <= num(row["TimeSeconds"]) < 320
            callbacks = [row for row in protocol if row["Event"] not in DIRECT]
            wanted_callbacks = [row for row in callbacks if in_window(row)]
            wanted_attempts = [row for row in admissions if in_window(row)]
            attempts = [row for row in service if row["Stage"] == "application_attempt"]
            observed_callbacks = [row for row in service if row["Stage"] == "protocol_callback"]
            cancellations = [row for row in service if row["Stage"] == "cancellation_callback"]
            check(len(service) == svc["ServiceEventCount"] == svc["CapturedServiceRecords"] and len(service) <= 100000, "Service count/cap mismatch")
            check(len(service) == len(attempts) + len(observed_callbacks) + len(cancellations), "Unknown service stage")
            check(svc["OmittedServiceRecords"] == svc["ScheduledEvents"] == svc["RandomDraws"] == svc["CancellationPairErrors"] == 0, "Service completeness/passivity failure")
            check(svc["OutOfWindowServiceEvents"] == len(callbacks)-len(wanted_callbacks)+len(admissions)-len(wanted_attempts), "Service outside-window accounting mismatch")
            check([int(r["ObservationId"]) for r in service] == list(range(1, len(service)+1)), "Service order identity mismatch")
            times = [num(r["TimeSeconds"]) for r in service]
            check(times == sorted(times) and all(300 <= t < 320 for t in times), "Service window/time order mismatch")
            check(len(attempts) == len(wanted_attempts) and len(observed_callbacks) == len(wanted_callbacks), "Service omitted/duplicated legacy observation")
            for a, b in zip(attempts, wanted_attempts):
                details = json.loads(a["DetailsJSON"])
                check(set(details) == set(b), "Admission detail membership mismatch")
                for field, value in b.items():
                    if field == "Reason":
                        check(details[field] == value, "Admission reason mismatch")
                    elif field in BOOL_ADMISSION:
                        check(boolean(details[field]) == boolean(value), "Admission boolean mismatch")
                        if type(details[field]) is bool:
                            total_logical_fields[field] += 1
                    else:
                        check(close(details[field], value), "Admission numerical field mismatch")
                check(a["TimeSeconds"] == b["TimeSeconds"] and a["PacketId"] == b["PacketId"] and a["NodeId"] == b["SourceId"], "Admission observation identity mismatch")
            for a, b in zip(observed_callbacks, wanted_callbacks):
                check(all(a[field] == b[field] for field in ("TimeSeconds", "Event", "NodeId", "Reason")), "Protocol service projection mismatch")
                if boolean(a["PacketIdAvailable"]):
                    check(a["PacketId"] == b["PacketId"], "Protocol service available packet mismatch")
                check(a["AggregateId"] == "0" and a["AggregateIdAvailable"] == "0", "Invented aggregate identity")
            check(len(cancellations) % 2 == 0 and len(cancellations) == svc["CancellationSnapshotCount"], "Cancellation pair count mismatch")
            check(svc["AdditionalStateReads"] == len(cancellations)*6, "Cancellation scalar read count mismatch")
            positive = removed = 0
            for a, b in zip(cancellations[::2], cancellations[1::2]):
                check(b["Event"] == a["Event"].replace("_before", "_after") and int(b["ObservationId"]) == int(a["ObservationId"]) + 1, "Cancellation pairing mismatch")
                check(all(a[k] == b[k] for k in ("TimeSeconds", "NodeId", "PeerId", "Sequence", "ControlType", "State", "PreparationActive", "ReservationSlot", "ReservationCounter", "AckDepth")), "Cancellation changed reservation/selector")
                n = int(b["RemovedCount"])
                check(int(a["DataDepth"]) - int(b["DataDepth"]) == n, "Cancellation queue removal count mismatch")
                positive += n > 0
                removed += n
            check(svc["CancellationBeforeCount"] == svc["CancellationAfterCount"] == len(cancellations)//2 and svc["PendingCancellationPair"] is False and svc["CancellationPairsComplete"] is True, "Cancellation summary mismatch")
            service_cases.append({"key": key, "rows": len(service), "joined_protocol_callbacks": len(wanted_callbacks), "joined_admission_attempts": len(wanted_attempts), "cancellation_pairs": len(cancellations)//2, "positive_cancellations": positive, "removed_entries": removed, "counts": {k: stats[k] for k in ("Generated", "Received", "Dropped", "Pending")}})
        receipt["service_cases"] = service_cases
        receipt["service_rows_independently_reconciled"] = sum(x["rows"] for x in service_cases)
        receipt["admission_logical_json_fields_checked"] = dict(total_logical_fields)
        receipt["parser_issue"] = {"file": "scripts/tranche9_metrics.py", "function": "verify_matlab_rows", "problem": "Frozen reviewer sends logical admission DetailsJSON fields to finite(), which intentionally rejects Python bool; CSV renders those logical values as 0/1.", "independent_result": "All six explicit logical fields agree with original admission CSV across every in-window attempt. This is a reporting-only representation defect; retain raw MATLAB evidence and repair the reviewer with narrow logical-field handling."}

        receipt["limitations"] = ["Owner archive records portable MATLAB R2025a execution; this reviewer did not execute MATLAB, ns-3, or OPNET.", "MAT objects remain on owner laptop and are unavailable for independent rereading.", "Source and reference stability during execution are recorded by the owner runner; current returned snapshots bind exactly to committed candidate bytes.", "No native MATLAB R2026a validation or campus benchmark rerun is present.", "Matched deterministic MAC/HOP checkpoints establish only their specified conditions; full radio, timing, random-stream, and statistical parity are not established.", "Final portable acceptance should incorporate a successful repaired full Python reviewer and quantitative comparison; parser failure alone does not require rerunning unchanged MATLAB sources."]
        receipt["status"] = "independent_portable_structural_checks_passed"
        receipt["recommendation"] = "Accept portable owner execution once the narrow reporting-only parser repair passes its regressions and full return review; no MATLAB structural blocker found. Do not claim parity or performance improvement from structural success."
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = verify(args)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
