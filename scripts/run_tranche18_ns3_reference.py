#!/usr/bin/env python3
"""Build passive native relay diagnostics and preserve complete on/off evidence.

The exact CSR/engine checkouts and fresh shared-library receipt are required.
Only copied headers in the standalone runner receive observational hooks.
No model events, RNG draws, queue policy or production source are changed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import difflib
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


T9 = module("t18_native_t9", ROOT / "scripts/run_tranche9_ns3_service.py")
T8, T7, BASE = T9.T8, T9.T7, T9.BASE
METRICS = module("t18_native_metrics", ROOT / "scripts/tranche8_metrics.py")
PLAN = "scenarios/t18/plan.json"
HELPER = ROOT / "scripts/ns3/tranche18-relay-observer.h"
ENGINE_PIN = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
SERVICE_SCHEMA = "csr-ns3-relay-service-v1"
SERVICE_FIELDS = T9.FIELDS + ["next_hop", "route_cost"]
TRACE_FIELDS = ("schema,event_index,time_s,event,node,peer,packet_type,src,dst,sequence,rate_kbps,"
                "size_bytes,success,reason,pathloss_db,rx_power_dbm,noise_dbm,snr_db,jsr_db,"
                "header_errors,payload_errors,total_errors,route_cost,next_hop,security_count,"
                "reservation_slot,reservation_counter,detail,statistic,value").split(",")
SERVICE_LIMIT = 2000000
CASE_SCHEMA = "csr-tranche18-relay-reference-case-v1"
SUITE_SCHEMA = "csr-tranche18-relay-reference-suite-v1"
CASE_ORDER = [f"{condition}{seed}" for seed in (128, 129, 130) for condition in "rlm"] + ["p128"]
EXTRA_EVENTS = {"mac_receive_state_before", "mac_receive_state_after", "mac_sync_change_before",
                "mac_slot_tick", "ack_queue_replace_before", "ack_queue_replace_after",
                "ack_queue_exact_duplicate", "ack_queue_reject", "ack_queue_enqueue_after",
                "mac_schedule_request", "mac_idle_rts_defer", "mac_idle_rts_schedule",
                "mac_holdoff_schedule_before", "mac_holdoff_expired", "mac_prepare_after",
                "mac_cancel_begin", "mac_cancel_frame_before", "mac_cancel_frame_after",
                "mac_cancel_end", "hop_retry"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def csv_rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames),
                "Missing or duplicate CSV fields")
        for row in reader:
            require(None not in row and None not in row.values(), "Nonrectangular native CSV")
            yield row


def verify_plan(repository, plan):
    require(plan["schema"] == "csr-tranche18-relay-service-plan-v1" and
            plan["ns3_source_commit"] == BASE.PIN and plan["engine_commit"] == ENGINE_PIN and
            plan["case_order"] == CASE_ORDER and
            [case["storage_key"] for case in plan["cases"]] == CASE_ORDER,
            "Unexpected T18 native plan identity or order")
    for case in plan["cases"]:
        for stem in ("scenario", "recipe"):
            path = repository / case[stem + "_file"]
            path.resolve().relative_to(repository.resolve())
            require(BASE.digest(path) == case[stem + "_sha256"], "T18 scenario or recipe changed")
        require(case["flow_limit"] == 0 and case["bucket_width_s"] == 60 and
                case["duration_s"] == (900 if case["storage_key"] == "p128" else 600),
                "Unexpected native horizon or traffic limit")


def prepare_overlay(source, directory):
    runner, _ = T9.prepare_overlay(source, directory)
    headers = directory / "include/ns3"
    for path in [runner, *headers.glob("*.h")]:
        text = path.read_text().replace("Tranche9", "Tranche18")
        text = text.replace("tranche9-service-observer.h", HELPER.name)
        path.write_text(text)
    (headers / "tranche9-service-observer.h").unlink()
    shutil.copy2(HELPER, headers / HELPER.name)
    hop = headers / "csr-hop-layer.h"
    retry = '''      if (Tranche18ServiceActive () && e.flowControlTracked && e.networkFlowMetadataValid)
        {
          CsrDifferentialTraceEvent observation;
          observation.event = "hop_retry";
          observation.node = CsrTraceInteger (m_nodeId);
          observation.peer = CsrTraceInteger (e.dest);
          observation.nextHop = CsrTraceInteger (e.dest);
          observation.packetType = "data";
          observation.source = CsrTraceInteger (e.networkSource);
          observation.destination = CsrTraceInteger (e.networkDestination);
          CsrDifferentialAppTag app;
          if (e.frame->PeekPacketTag (app))
            observation.sequence = CsrTraceInteger (app.GetSequence ());
          observation.reason = "submitted_to_mac";
          observation.detail =
            "hop_sequence=" + CsrTraceInteger (e.seq) +
            ";resend_before=" + CsrTraceInteger (e.resendCount) +
            ";resend_after=" + CsrTraceInteger (e.resendCount + 1) +
            ";last_tx_time_s=" + CsrTraceDouble (e.lastTxTime.GetSeconds ()) +
            ";resend_time_s=" + CsrTraceDouble (m_resendTime.GetSeconds ()) +
            ";max_resend=" + CsrTraceInteger (m_maxNumResend) +
            ";initial_tx_confirmed=" + CsrTraceInteger (e.initialTxConfirmed ? 1 : 0);
          Tranche18WriteService (observation);
        }
'''
    hop.write_text(T8.replace_once(hop.read_text(), "      e.resendCount++;\n", retry + "      e.resendCount++;\n"))
    modifications, patch = [], []
    for original in sorted((source / "model").iterdir()) + [source / "csr-opnet-scenario-runner.cc"]:
        if not original.is_file():
            continue
        overlay = runner if original.name == runner.name else headers / original.name
        if original.read_bytes() != overlay.read_bytes():
            modifications.append({"source_path": str(original), "source_sha256": BASE.digest(original),
                                  "overlay_path": str(overlay), "overlay_sha256": BASE.digest(overlay)})
            patch.extend(difflib.unified_diff(original.read_text().splitlines(True), overlay.read_text().splitlines(True),
                         fromfile="a/" + original.name, tofile="b/" + original.name))
    (directory / "observational-overlay.patch").write_text("".join(patch))
    return runner, modifications


def service_summary(path, case):
    counts, forwards, completions, retries, blockers = Counter(), Counter(), Counter(), Counter(), Counter()
    count, previous = 0, 0.0
    required = {"app_admission", "nwk_enqueue", "nwk_forward", "hop_admission", "mac_slot_tick"}
    for index, row in enumerate(csv_rows(path), 1):
        now = float(row["time_s"])
        require(list(row) == SERVICE_FIELDS and row["schema"] == SERVICE_SCHEMA and
                int(row["event_index"]) == index and math.isfinite(now) and
                previous <= now < case["duration_s"], "Invalid native service schema, time or index")
        previous, count = now, index
        counts[row["event"]] += 1
        for field in ("preparation_active", "holdoff_over", "sync_present", "tx_in_progress"):
            require(row[field] in ("", "0", "1"), "Invalid native snapshot boolean")
        if row["event"] == "nwk_forward":
            require(row["next_hop"] and row["reason"] in ("local", "relay"), "Native egress lineage missing")
            forwards[tuple(row[x] for x in ("src", "dst", "node", "peer", "next_hop", "reason"))] += 1
        elif row["event"] == "hop_completion":
            completions[tuple(row[x] for x in ("src", "dst", "node", "peer", "reason"))] += 1
        elif row["event"] == "hop_retry":
            require(row["reason"] == "submitted_to_mac" and row["sequence"], "Native retry identity missing")
            retries[tuple(row[x] for x in ("src", "dst", "node", "peer"))] += 1
        elif row["event"] == "nwk_admission" and row["success"] == "0":
            blockers[tuple(row[x] for x in ("src", "dst", "node", "peer", "reason"))] += 1
    require(0 < count <= SERVICE_LIMIT and required <= counts.keys(), "Native observer incomplete or over limit")
    def records(values, names):
        return [dict(zip(names, key), count=value) for key, value in sorted(values.items())]
    return {"schema": "csr-tranche18-native-service-summary-v1", "status": "passed", "rows": count,
            "max_records": SERVICE_LIMIT, "omitted_records": 0,
            "window_s": [0, case["duration_s"]], "stop_endpoint": "exclusive",
            "event_counts": dict(sorted(counts.items())),
            "forwarding": records(forwards, ["src", "dst", "node", "ingress_peer", "next_hop", "kind"]),
            "completions": records(completions, ["src", "dst", "node", "peer", "reason"]),
            "retry_submissions": records(retries, ["src", "dst", "node", "peer"]),
            "blocked_admission_observations": records(blockers, ["src", "dst", "node", "peer", "reason"]),
            "scope": "Callback observations. Retry means MAC submission, not OTA. DACK is not application loss; no_ack is a custody completion, not proven end-to-end loss. NSDP release has no packet sequence. Finite-horizon unmatched lifetimes are censored."}


def compare_files(directory, first, second, names):
    records = []
    for name in names:
        a, b = directory / (first + name), directory / (second + name)
        require(a.read_bytes() == b.read_bytes(), "Passive observer changed native bytes: " + name)
        records.append({"name": name, "first_path": a.name, "second_path": b.name,
                        "first_sha256": BASE.digest(a), "second_sha256": BASE.digest(b), "equal": True})
    return {"status": "passed", "compared_files": records}


def compress(path):
    """Close and verify deterministic compressed bytes before removing raw data."""
    data = path.read_bytes()
    target = path.with_name(path.name + ".gz")
    encoded = gzip.compress(data, mtime=0)
    require(target.write_bytes(encoded) == len(encoded), "Incomplete native compressed write")
    target.chmod(0o444)
    require(gzip.decompress(target.read_bytes()) == data, "Native compression roundtrip differs")
    record = {"original_name": path.name, "original_bytes": len(data),
              "original_sha256": hashlib.sha256(data).hexdigest(), **T7.file_record(target, target.parent)}
    path.unlink()
    return record


def verify_service_projection(home, case):
    raw = iter(csv_rows(home / "ns3-trace.csv.gz"))
    seen, previous = 0, 0.0
    for observed in csv_rows(home / "ns3-service.csv.gz"):
        require(list(observed) == SERVICE_FIELDS, "Incomplete native service schema")
        if observed["event"] in EXTRA_EVENTS:
            continue
        event = next(raw, None)
        require(event is not None, "Service has excess canonical events")
        now = float(event["time_s"])
        require(list(event) == TRACE_FIELDS and event["schema"] == "csr-differential-trace-v1" and int(event["event_index"]) == seen and
                math.isfinite(now) and previous <= now < case["duration_s"], "Canonical native trace is incomplete or unordered")
        fields = (set(event) & set(observed)) - {"schema", "event_index"}
        require(all(event[field] == observed[field] for field in fields), "Service projection differs from canonical trace")
        seen, previous = seen + 1, now
    require(next(raw, None) is None and seen > 0, "Service omitted canonical events")
    return {"status": "passed", "canonical_rows": seen,
            "shared_fields_equal": True, "next_hop_and_route_cost_preserved": True}


def feedback_summary(path):
    if path.suffix != ".gz":
        return T8.observer_summary(path)
    with tempfile.TemporaryDirectory(prefix="t18-feedback-") as temporary:
        expanded = Path(temporary) / "feedback.csv"
        expanded.write_bytes(gzip.decompress(path.read_bytes()))
        return T8.observer_summary(expanded)


def verify_comparisons(home, record, originals, key):
    expected = {"nonperturbation": ("", "off-", ["ns3-trace.csv", "app-admission-diagnostics.csv"]),
                "aggregate_nonperturbation": ("", "off-", ["ns3-aggregates.csv"])}
    if key == "m128":
        expected["pristine_nonperturbation"] = ("off-", "pristine-", ["ns3-trace.csv", "app-admission-diagnostics.csv"])
    else:
        require("pristine_nonperturbation" not in record, "Unexpected pristine comparison")
    for label, (first, second, names) in expected.items():
        comparison = record[label]
        require(comparison["status"] == "passed" and [x["name"] for x in comparison["compared_files"]] == names,
                "Native comparison membership differs")
        for check, name in zip(comparison["compared_files"], names):
            require(check["first_path"] == first + name and check["second_path"] == second + name and
                    check["equal"] is True and check["first_sha256"] == check["second_sha256"], "Native comparison pair differs")
            for prefix in ("first", "second"):
                filename = check[prefix + "_path"]
                actual = originals[filename] if filename in originals else BASE.digest(home / filename)
                require(actual == check[prefix + "_sha256"], "Native control byte binding differs")


def execute_case(case, source, output, runner, pristine, timeout):
    directory = output / case["storage_key"]
    directory.mkdir()
    record = {"schema": CASE_SCHEMA, "status": "running", "case": case, "case_id": case["case_id"],
              "storage_key": case["storage_key"], "scenario_sha256": case["scenario_sha256"],
              "started_utc": BASE.utc_now(), "ns3_source_commit": BASE.PIN, "engine_commit": ENGINE_PIN,
              "runner_sha256": BASE.digest(runner), "matlab_executed": False, "opnet_executed": False,
              "stages": {}, "compressed_artifacts": [], "control_compressed_artifacts": []}
    try:
        scenario = ROOT / case["scenario_file"]
        runs = [("", runner, True), ("off-", runner, False)]
        if case["storage_key"] == "m128":
            runs.append(("pristine-", pristine, False))
        for prefix, executable, observed in runs:
            command = T8.runner_command(executable, scenario, case, directory, prefix, observed)
            command[command.index("--aggregateTraceOnly=1")] = "--aggregateTraceOnly=0"
            command += ["--admissionTrace=1"]
            if observed:
                command += [f"--serviceDiagnostics={directory / 'ns3-service.csv'}", "--serviceStart=0",
                            f"--serviceStop={case['duration_s']}", f"--serviceLimit={SERVICE_LIMIT}"]
            stage = T7.run_stage(command, directory / (prefix + "ns3-run.log"), timeout)
            record["stages"][prefix + "run_ns3"] = stage
            require(stage["exit_code"] == 0, "Native execution failed")
            for name in (prefix + "ns3-trace.csv", prefix + "app-admission-diagnostics.csv", prefix + "ns3-run.log"):
                (directory / name).chmod(0o444)
            if observed:
                for name in ("ns3-service.csv", "ns3-link-decisions.csv"):
                    (directory / name).chmod(0o444)
        record["nonperturbation"] = compare_files(directory, "", "off-", ["ns3-trace.csv", "app-admission-diagnostics.csv"])
        if case["storage_key"] == "m128":
            record["pristine_nonperturbation"] = compare_files(directory, "off-", "pristine-", ["ns3-trace.csv", "app-admission-diagnostics.csv"])
        # Both aggregate invocations use the canonical basename in distinct directories;
        # source_file is a provenance field, so no post-hoc CSV normalization is used.
        offdir = directory / "off-aggregate"
        offdir.mkdir()
        shutil.copy2(directory / "off-ns3-trace.csv", offdir / "ns3-trace.csv")
        for prefix, target in (("", directory), ("off-", offdir)):
            command = [sys.executable, "-B", "-I", str(source / "utils/aggregate-ns3-trace.py"),
                       str(target / "ns3-trace.csv"), str(target / "ns3-aggregates.csv"),
                       "--scenario", case["scenario"], "--bucket-width", str(case["bucket_width_s"]),
                       "--stop-time", str(case["duration_s"]), "--legacy-trace-size-exclusion-bits", "0",
                       "--require-zero-size-mismatches", "--provenance", str(target / "ns3-aggregates.provenance.json")]
            record["stages"][prefix + "aggregate_ns3"] = T7.run_stage(command, directory / (prefix + "ns3-aggregate.log"), timeout)
            require(record["stages"][prefix + "aggregate_ns3"]["exit_code"] == 0, "Native aggregation failed")
        shutil.copy2(offdir / "ns3-aggregates.csv", directory / "off-ns3-aggregates.csv")
        shutil.copy2(offdir / "ns3-aggregates.provenance.json", directory / "off-ns3-aggregates.provenance.json")
        shutil.rmtree(offdir)
        record["aggregate_nonperturbation"] = compare_files(directory, "", "off-", ["ns3-aggregates.csv"])
        workflow = module("t18_upstream_workflow", source / "utils/run-opnet-aggregate-differential.py")
        parsed = workflow.load_scenario_run(scenario)
        record["application_admission_totals"] = workflow.validate_app_admission_diagnostics(
            directory / "app-admission-diagnostics.csv", case["scenario"], parsed["application_profile"], parsed["flows"])
        record["exact_sequence_validation"] = workflow._load_and_validate_ns3_provenance(
            directory / "ns3-aggregates.provenance.json", directory / "ns3-trace.csv", directory / "ns3-aggregates.csv", case["scenario"])
        T7.normalized_sidecar(case, directory, "ns3")
        record["feedback_diagnostics"] = T8.observer_summary(directory / "ns3-link-decisions.csv")
        record["service_diagnostics"] = service_summary(directory / "ns3-service.csv", case)
        BASE.write_json(directory / "service-summary.json", record["service_diagnostics"])
        BASE.write_json(directory / "feedback-summary.json", record["feedback_diagnostics"])
        record["status"] = "completed"
    except Exception as error:
        record.update(status="failed", error=str(error))
        raise
    finally:
        for path in sorted(directory.glob("*.csv")):
            if path.name not in ("ns3-aggregates.csv", "app-admission-diagnostics.csv", "off-ns3-aggregates.csv", "off-app-admission-diagnostics.csv", "pristine-app-admission-diagnostics.csv"):
                key = "control_compressed_artifacts" if path.name.startswith(("off-", "pristine-")) else "compressed_artifacts"
                record[key].append(compress(path))
        if record["status"] == "completed":
            record["service_projection"] = verify_service_projection(directory, case)
            record["application_metrics"] = METRICS.ns3_applications(directory, {**case, "base_case_id": case["condition"]})
            require(record["application_metrics"]["attempts"] == case["expected_admission_attempts"], "Native attempts differ from declared schedule")
        record["completed_utc"] = BASE.utc_now()
        record["files"] = [T7.file_record(path, directory) for path in sorted(directory.iterdir()) if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(directory / "manifest.json", record)
        for path in directory.iterdir():
            if path.is_file():
                path.chmod(0o444)
    return record


def verify_inventory(directory, files, extra):
    names = [record["path"] for record in files]
    require(len(names) == len(set(names)), "Duplicate native inventory member")
    require(set(names) | set(extra) == {path.name for path in directory.iterdir()}, "Native evidence inventory not closed")
    for record in files:
        require(Path(record["path"]).name == record["path"], "Native inventory path is not a basename")
        path = directory / record["path"]
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == record["bytes"] and
                BASE.digest(path) == record["sha256"], "Native evidence integrity failure")


def verify_reference_suite(repository, plan, reference_directory=None):
    repository = Path(repository).resolve()
    verify_plan(repository, plan)
    directory = Path(reference_directory) if reference_directory is not None else repository / "evidence/tranche-18-ns3-reference"
    suite = load_json(directory / "manifest.json")
    require(suite["schema"] == SUITE_SCHEMA and suite["status"] == "completed" and
            suite["ns3_source_commit"] == BASE.PIN and suite["engine_commit"] == ENGINE_PIN and
            suite["plan_sha256"] == BASE.digest(repository / PLAN) and
            suite["all_observer_on_off_checks_passed"] is True and suite["source_files_stable"] is True and
            suite["input_files_stable"] is True and suite["binary_and_overlay_files_stable"] is True and
            suite["matlab_executed"] is False and suite["opnet_executed"] is False,
            "Native suite did not complete against the exact plan")
    require([x["storage_key"] for x in suite["cases"]] == CASE_ORDER, "Native case membership differs")
    verify_inventory(directory, suite["files"], ["manifest.json", *CASE_ORDER])
    require(BASE.digest(directory / "build.json") == suite["build_manifest_sha256"], "Native build identity differs")
    build = load_json(directory / "build.json")
    require(build["schema"] == "csr-tranche18-native-build-v1" and build["ns3_source_commit"] == BASE.PIN and
            build["engine_commit"] == ENGINE_PIN and build["full_ns3_rebuild_performed"] is True and
            build["source_headers_match_build"] is True and build["standalone_runner_compiled"] is True and
            set(build["compiles"]) == {"observer", "pristine"} and
            all(x["exit_code"] == 0 for x in build["compiles"].values()) and
            BASE.digest(directory / "environment-build.json") == build["environment_receipt_sha256"] and
            BASE.digest(repository / "scripts/ns3/tranche18-relay-observer.h") == build["helper_sha256"],
            "Native build semantics differ")
    environment = load_json(directory / "environment-build.json")
    require(environment["status"] == "completed" and environment["source_commit"] == BASE.PIN and
            environment["engine_commit"] == ENGINE_PIN and environment["source_tracked_clean"] is True and
            environment["engine_tracked_clean"] is True and environment["build_exit_code"] == 0 and
            environment["full_engine_and_csr_rebuild_performed"] is True and
            set(environment["libraries"]) == {f"libns3-dev-{name}-debug.so" for name in BASE.MODULES},
            "Fresh native environment receipt differs")
    reviewed = []
    for case, item in zip(plan["cases"], suite["cases"]):
        home = directory / case["storage_key"]
        require(BASE.digest(home / "manifest.json") == item["manifest_sha256"], "Native case manifest differs")
        record = load_json(home / "manifest.json")
        require(record["schema"] == CASE_SCHEMA and record["status"] == "completed" and record["case"] == case and
                record["ns3_source_commit"] == BASE.PIN and record["engine_commit"] == ENGINE_PIN and
                record["runner_sha256"] == build["runner_sha256"] and record["matlab_executed"] is False and
                record["opnet_executed"] is False,
                "Native case identity or completion differs")
        verify_inventory(home, record["files"], ["manifest.json"])
        originals = {}
        for compressed in record["compressed_artifacts"] + record["control_compressed_artifacts"]:
            data = gzip.decompress((home / compressed["path"]).read_bytes())
            require(len(data) == compressed["original_bytes"] and hashlib.sha256(data).hexdigest() == compressed["original_sha256"], "Native compression binding differs")
            require(compressed["original_name"] not in originals, "Duplicate native compression identity")
            originals[compressed["original_name"]] = compressed["original_sha256"]
        verify_comparisons(home, record, originals, case["storage_key"])
        stages = {"run_ns3", "off-run_ns3", "aggregate_ns3", "off-aggregate_ns3"}
        if case["storage_key"] == "m128":
            stages.add("pristine-run_ns3")
        require(set(record["stages"]) == stages and all(stage["exit_code"] == 0 for stage in record["stages"].values()), "Native stage missing or failed")
        require(verify_service_projection(home, case) == record["service_projection"], "Native service projection changed")
        feedback = feedback_summary(home / "ns3-link-decisions.csv.gz")
        require(feedback == record["feedback_diagnostics"] == load_json(home / "feedback-summary.json"), "Native feedback reconstruction differs")
        service = service_summary(home / "ns3-service.csv.gz", case)
        require(service == record["service_diagnostics"] == load_json(home / "service-summary.json"), "Native service reconstruction differs")
        metrics = METRICS.ns3_applications(home, {**case, "base_case_id": case["condition"]})
        require(metrics == record["application_metrics"] and metrics["attempts"] == case["expected_admission_attempts"], "Native application reconstruction differs")
        reviewed.append({"storage_key": case["storage_key"], "status": "passed", "application_metrics": metrics, "service_diagnostics": service})
    return {"schema": "csr-tranche18-native-review-v1", "status": "passed", "cases": reviewed,
            "scope": "Exact native inputs, complete inventory, passive on/off equality and descriptive application/cohort evidence. No MATLAB runtime or full numerical parity claim."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--environment-receipt", type=Path, required=True)
    parser.add_argument("--build-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    source, engine, output = args.source.resolve(), args.engine.resolve(), args.output.resolve()
    build, directory = engine / "build", args.build_directory.resolve()
    require(not output.exists() and not directory.exists(), "Native output and runner build directories must be fresh")
    output.mkdir(parents=True)
    directory.mkdir(parents=True)
    summary = {"schema": SUITE_SCHEMA, "status": "running", "ns3_source_commit": BASE.PIN,
               "engine_commit": ENGINE_PIN, "started_utc": BASE.utc_now(), "plan_sha256": BASE.digest(ROOT / PLAN),
               "matlab_executed": False, "opnet_executed": False, "full_ns3_rebuild_performed": True, "cases": []}
    try:
        BASE.check_source(source, build)
        require(BASE.checked(["git", "rev-parse", "HEAD"], engine) == ENGINE_PIN and
                not BASE.checked(["git", "status", "--porcelain", "--untracked-files=no"], engine), "Native engine pin/cleanliness differs")
        plan = load_json(ROOT / PLAN)
        verify_plan(ROOT, plan)
        receipt = load_json(args.environment_receipt)
        require(receipt["status"] == "completed" and receipt["source_commit"] == BASE.PIN and
                receipt["engine_commit"] == ENGINE_PIN, "Fresh environment build receipt differs")
        for name, value in receipt["libraries"].items():
            require(BASE.digest(build / "lib" / name) == value, "Rebuilt native library digest differs")
        paths = [Path(__file__), HELPER, ROOT / PLAN, T9.HELPER, T8.HELPER, args.environment_receipt]
        paths += [ROOT / "scripts" / name for name in ("run_tranche9_ns3_service.py", "run_tranche8_ns3_diagnostics.py", "run_tranche7_ns3_reference.py", "run_tranche4_ns3_reference.py", "tranche8_metrics.py")]
        paths += list((source / "utils").glob("*.py"))
        paths += [ROOT / case[stem + "_file"] for case in plan["cases"] for stem in ("scenario", "recipe")]
        inputs = {**BASE.input_snapshot(source, build), **{str(path): BASE.digest(path) for path in paths}}
        overlay, modifications = prepare_overlay(source, directory / "overlay")
        runner, pristine = directory / "t18-observed", directory / "t18-pristine"
        observed_cmd = BASE.compile_runner(source, build, runner, args.compiler)
        observed_cmd[observed_cmd.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(overlay)
        observed_cmd.insert(observed_cmd.index("-I" + str(build / "include")), "-I" + str(directory / "overlay/include"))
        compiles = {}
        for name, command in (("observer", observed_cmd), ("pristine", BASE.compile_runner(source, build, pristine, args.compiler))):
            compiles[name] = T7.run_stage(command, output / (name + "-compile.log"), 300)
            require(compiles[name]["exit_code"] == 0, "Native standalone compile failed: " + name)
        shutil.copy2(directory / "overlay/observational-overlay.patch", output / "observational-overlay.patch")
        shutil.copy2(args.environment_receipt, output / "environment-build.json")
        build_record = {"schema": "csr-tranche18-native-build-v1", "input_sha256": inputs, "ns3_source_commit": BASE.PIN,
                        "engine_commit": ENGINE_PIN, "full_ns3_rebuild_performed": True, "source_headers_match_build": True,
                        "standalone_runner_compiled": True, "compiler_version": BASE.checked([args.compiler, "--version"]),
                        "compiles": compiles, "overlay_modifications": modifications, "helper_sha256": BASE.digest(HELPER),
                        "runner_sha256": BASE.digest(runner), "pristine_runner_sha256": BASE.digest(pristine),
                        "environment_receipt_sha256": BASE.digest(output / "environment-build.json")}
        BASE.write_json(output / "build.json", build_record)
        binary_inputs = {str(path): BASE.digest(path) for path in [runner, pristine, *directory.glob("overlay/**/*")] if path.is_file()}
        for case in plan["cases"]:
            record = execute_case(case, source, output, runner, pristine, args.timeout_seconds)
            summary["cases"].append({"storage_key": case["storage_key"], "status": record["status"],
                                     "manifest_sha256": BASE.digest(output / case["storage_key"] / "manifest.json")})
            print(case["storage_key"] + ": " + json.dumps(record["application_admission_totals"]), flush=True)
        BASE.check_source(source, build)
        require(all(BASE.digest(Path(path)) == value for path, value in inputs.items()), "Native inputs changed during execution")
        require(all(BASE.digest(Path(path)) == value for path, value in binary_inputs.items()), "Native executable or overlay changed during execution")
        summary.update(status="completed", all_observer_on_off_checks_passed=True, source_files_stable=True,
                       input_files_stable=True, binary_and_overlay_files_stable=True, build_manifest_sha256=BASE.digest(output / "build.json"))
    except Exception as error:
        summary.update(status="failed", error=str(error))
        print("T18 native reference failed: " + str(error), file=sys.stderr)
        return 1
    finally:
        summary["completed_utc"] = BASE.utc_now()
        summary["files"] = [T7.file_record(path, output) for path in sorted(output.iterdir()) if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(output / "manifest.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
