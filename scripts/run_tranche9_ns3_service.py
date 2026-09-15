#!/usr/bin/env python3
"""Run unchanged T8 inputs with a bounded passive ns-3 ACK service observer.

Only the standalone runner is compiled against verified preserved libraries.
The original source checkout is read-only. All six on/off executions and the
accepted T8 application/admission/aggregate/feedback bytes must match.
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
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


T8 = module("tranche9_reference_t8", ROOT / "scripts/run_tranche8_ns3_diagnostics.py")
T7, BASE = T8.T7, T8.BASE
PLAN = ROOT / "scenarios/ack_service/plan.json"
HELPER = ROOT / "scripts/ns3/tranche9-service-observer.h"
SCHEMA = "csr-ns3-ack-service-v1"
FIELDS = ("schema,event_index,time_s,event,node,peer,packet_type,src,dst,sequence,"
          "success,reason,reservation_slot,reservation_counter,detail,packet_uid,"
          "prior_packet_uid,decision_id,prior_decision_id,mac_state,preparation_active,"
          "holdoff_over,sync_present,ack_queue,data_queue,tx_in_progress,rate_kbps,"
          "size_bytes,rx_power_dbm,pathloss_db,snr_db,jsr_db,header_errors,payload_errors,"
          "total_errors,statistic,value").split(",")


def snapshot(stage: str, peer="0", frame="nullptr", prior="nullptr", detail='""') -> str:
    return (f'  Tranche9MacSnapshot ("{stage}", m_nodeId, {peer}, StateName (m_state),\n'
            '    m_txPreparationActive, m_txHoldoffOver, m_syncPresent,\n'
            '    m_ackQueue.size (), m_queue.size (), m_txInProgress,\n'
            f'    m_scheduledTxSlot, m_txCountdownCounter, {frame}, {prior}, {detail});\n')


def prepare_overlay(source: Path, directory: Path) -> tuple[Path, list[dict]]:
    runner, _ = T8.prepare_overlay(source, directory)
    headers = directory / "include/ns3"
    shutil.copy2(HELPER, headers / HELPER.name)
    once = T8.replace_once
    common = headers / "csr-common.h"
    common.write_text(common.read_text() + '\n#include "tranche9-service-observer.h"\n')

    trace = headers / "csr-differential-trace.h"
    code = trace.read_text()
    code = once(code, "inline bool g_csrDifferentialAdmissionTraceEnabled = false;\n",
                "inline bool g_csrDifferentialAdmissionTraceEnabled = false;\n"
                "inline bool Tranche9ServiceActive ();\n"
                "inline void Tranche9ObserveDifferential (const CsrDifferentialTraceEvent &event);\n")
    code = once(code, "WriteDifferentialTrace (const CsrDifferentialTraceEvent &event)\n{\n",
                "WriteDifferentialTrace (const CsrDifferentialTraceEvent &event)\n{\n"
                "  Tranche9ObserveDifferential (event);\n")
    code = once(code, "WriteDifferentialAdmissionTrace (const CsrDifferentialTraceEvent &event)\n{\n",
                "WriteDifferentialAdmissionTrace (const CsrDifferentialTraceEvent &event)\n{\n"
                "  if (!g_csrDifferentialAdmissionTraceEnabled)\n"
                "    {\n      Tranche9ObserveDifferential (event);\n    }\n")
    trace.write_text(code)

    # Enable only existing observation branches during the bounded window.
    # Their queries are const/read-only. Preserve the original aggregate
    # writer's flag and the two existing enqueue-detail branches, so old CSV
    # bytes remain unchanged rather than being normalized after execution.
    gate = "(IsDifferentialAdmissionTraceEnabled () || Tranche9ServiceActive ())"
    for name in ("csr-hop-layer.h", "csr-nwk-layer.h"):
        path = headers / name
        code = path.read_text().replace("IsDifferentialAdmissionTraceEnabled ()", gate)
        if name == "csr-nwk-layer.h":
            pattern = re.escape("if (" + gate + ")") + r"(\n\s*\{\n\s*enqueueEvent\.detail)"
            code, count = re.subn(pattern, r"if (IsDifferentialAdmissionTraceEnabled ())\1", code)
            if count != 2:
                raise ValueError("Pinned NWK aggregate-detail observation anchors changed")
        path.write_text(code)

    mac = headers / "csr-mac-core.h"
    code = mac.read_text()
    code = once(code, "        State previous = m_state;\n",
                snapshot("mac_receive_state_before", detail='std::string ("to=") + StateName (state)') +
                "        State previous = m_state;\n")
    code = once(code, "        event.detail = StateName (state);\n        WriteDifferentialTrace (event);\n",
                "        event.detail = StateName (state);\n        WriteDifferentialTrace (event);\n" +
                snapshot("mac_receive_state_after"))
    code = once(code, "    m_syncPresent = present;\n",
                "    if (m_syncPresent != present)\n    {\n" +
                snapshot("mac_sync_change_before", detail='std::string ("new_sync=") + (present ? "1" : "0")') +
                "    }\n    m_syncPresent = present;\n")
    anchor = "  // OPNET tslot_tasks() advances reservation counters only in Search_st and\n"
    code = once(code, anchor, snapshot("mac_slot_tick") + "\n" + anchor)
    mac.write_text(code)

    device = headers / "csr-net-device.h"
    code = device.read_text()
    code = once(code, "              entry.frame = frame;\n              entry.seq = seq;\n",
                snapshot("ack_queue_replace_before", "dest", "frame", "entry.frame",
                         'std::string ("prior_tx_count=") + CsrTraceInteger (entry.txCount)') +
                "              entry.frame = frame;\n              entry.seq = seq;\n")
    code = once(code, "              entry.txCount = 0;\n", "              entry.txCount = 0;\n" +
                snapshot("ack_queue_replace_after", "dest", "frame"))
    code = once(code, '              std::cout << "[MAC " << m_nodeId\n                        << "] Ignore duplicate exact ACK"\n',
                snapshot("ack_queue_exact_duplicate", "dest", "frame", "entry.frame") +
                '              std::cout << "[MAC " << m_nodeId\n                        << "] Ignore duplicate exact ACK"\n')
    code = once(code, "  if (m_ackQueue.size () >= ACK_QUEUE_SIZE)\n    {\n",
                "  if (m_ackQueue.size () >= ACK_QUEUE_SIZE)\n    {\n" +
                snapshot("ack_queue_reject", "dest", "frame"))
    code = once(code, "  m_ackQueue.push_back (entry);\n", "  m_ackQueue.push_back (entry);\n" +
                snapshot("ack_queue_enqueue_after", "dest", "frame"))
    code = once(code, "CsrMacCore::MaybeScheduleNextTx ()\n{\n",
                "CsrMacCore::MaybeScheduleNextTx ()\n{\n" + snapshot("mac_schedule_request"))
    code = once(code, "  if (deferToWake)\n    {\n",
                "  if (deferToWake)\n    {\n" + snapshot("mac_idle_rts_defer"))
    code = once(code, "  m_idleRtsEvent = Simulator::Schedule (\n",
                snapshot("mac_idle_rts_schedule", detail='std::string ("due_s=") + CsrTraceDouble (nextSlot.GetSeconds ())') +
                "  m_idleRtsEvent = Simulator::Schedule (\n")
    code = once(code, "CsrMacCore::StartTxHoldoff ()\n{\n",
                "CsrMacCore::StartTxHoldoff ()\n{\n" + snapshot("mac_holdoff_schedule_before",
                detail='std::string ("delay_s=") + CsrTraceDouble (TS_HOLDOFF_SECONDS)'))
    code = once(code, "  WriteDifferentialTrace (event);\n\n  std::cout << \"[MAC \" << m_nodeId\n            << \"] OPNET 300-ms transmit holdoff complete\"\n",
                "  WriteDifferentialTrace (event);\n" + snapshot("mac_holdoff_expired") +
                '\n  std::cout << "[MAC " << m_nodeId\n            << "] OPNET 300-ms transmit holdoff complete"\n')
    code = once(code, "    : (selectedNewSlot ? \"new\" : \"reuse\");\n  WriteDifferentialTrace (event);\n",
                '    : (selectedNewSlot ? "new" : "reuse");\n  WriteDifferentialTrace (event);\n' +
                snapshot("mac_prepare_after", detail="event.reason"))
    start = code.index("CsrMacCore::CancelAcknowledgedFrames (")
    end = code.index("CsrMacCore::CancelQueuedFramesByType (", start)
    block = code[start:end]
    block = once(block, "  uint64_t completedBitmap = ackBitmap | dackBitmap;\n",
                 snapshot("mac_cancel_begin", "neighbor", detail='std::string ("base_sequence=") + CsrTraceInteger (baseSeq)') +
                 "  uint64_t completedBitmap = ackBitmap | dackBitmap;\n")
    block = once(block, "          it = m_queue.erase (it);\n", snapshot("mac_cancel_frame_before", "neighbor", "it->frame") +
                 "          it = m_queue.erase (it);\n" + snapshot("mac_cancel_frame_after", "neighbor"))
    block = once(block, "  return removed;\n", snapshot("mac_cancel_end", "neighbor", detail='std::string ("removed=") + CsrTraceInteger (removed)') +
                 "  return removed;\n")
    code = code[:start] + block + code[end:]
    device.write_text(code)

    code = runner.read_text()
    code = once(code, "  std::string feedbackDiagnosticsPath;\n",
                "  std::string feedbackDiagnosticsPath;\n  std::string serviceDiagnosticsPath;\n"
                "  double serviceStart = 300.0, serviceStop = 320.0;\n  uint64_t serviceLimit = 100000;\n")
    code = once(code, "  command.Parse (argc, argv);\n",
                '  command.AddValue ("serviceDiagnostics", "Passive ACK service CSV", serviceDiagnosticsPath);\n'
                '  command.AddValue ("serviceStart", "Inclusive service window start", serviceStart);\n'
                '  command.AddValue ("serviceStop", "Exclusive service window stop", serviceStop);\n'
                '  command.AddValue ("serviceLimit", "Service observer record ceiling", serviceLimit);\n'
                "  command.Parse (argc, argv);\n")
    code = once(code, "  Tranche8OpenFeedbackCsv (feedbackDiagnosticsPath);\n",
                "  Tranche8OpenFeedbackCsv (feedbackDiagnosticsPath);\n"
                "  Tranche9OpenServiceCsv (serviceDiagnosticsPath, serviceStart, serviceStop, serviceLimit);\n")
    code = once(code, "  Tranche8CloseFeedbackCsv ();\n",
                "  Tranche8CloseFeedbackCsv ();\n  Tranche9CloseServiceCsv ();\n")
    code = once(code, "  const bool traceAdmission = IsDifferentialAdmissionTraceEnabled ();\n",
                "  const bool traceAdmission = IsDifferentialAdmissionTraceEnabled () || Tranche9ServiceActive ();\n")
    runner.write_text(code)

    records, patch = [], []
    for original in sorted((source / "model").iterdir()) + [source / "csr-opnet-scenario-runner.cc"]:
        if not original.is_file():
            continue
        overlay = runner if original.name == runner.name else headers / original.name
        if original.read_bytes() == overlay.read_bytes():
            continue
        records.append({"source_path": str(original), "source_sha256": BASE.digest(original),
                        "overlay_path": str(overlay), "overlay_sha256": BASE.digest(overlay)})
        patch.extend(difflib.unified_diff(original.read_text().splitlines(True), overlay.read_text().splitlines(True),
                     fromfile="a/" + original.name, tofile="b/" + original.name))
    (directory / "observational-overlay.patch").write_text("".join(patch))
    return runner, records


def verify_plan(plan: dict) -> None:
    parent = T7.load_json(ROOT / plan["parent_plan"])
    if (plan["schema"] != "csr-ack-service-plan-v1" or plan["ns3_source_commit"] != BASE.PIN or
            plan["case_count"] != 6 or len(plan["cases"]) != 6 or plan["service_window_s"] != [300, 320] or
            plan["service_max_records"] != 100000 or
            BASE.digest(ROOT / plan["parent_plan"]) != plan["parent_plan_sha256"]):
        raise ValueError("Unexpected ACK service plan contract")
    by_id = {case["case_id"]: case for case in parent["cases"]}
    expected = ["c129", "c128", "c130", "c131", "c132", "a129"]
    if plan["case_order"] != expected or [case["storage_key"] for case in plan["cases"]] != expected:
        raise ValueError("Unexpected ACK service fixture order")
    for case in plan["cases"]:
        old = by_id[case["case_id"]]
        if any(case.get(key) != value for key, value in old.items()):
            raise ValueError("ACK service fixture changed an accepted T8 input")
        key = ("a" if case["base_case_id"].startswith("two") else "c") + str(case["seed"])
        if case["storage_key"] != key or case["service_reference_directory"] != "evidence/tranche-9-ns3-reference/" + key:
            raise ValueError("ACK service storage paths are not compact canonical paths")
        for stem in ("scenario", "recipe"):
            if BASE.digest(ROOT / case[stem + "_file"]) != case[stem + "_sha256"]:
                raise ValueError("Accepted T8 scenario/recipe digest changed")


def service_summary(path: Path, window: list[float], limit: int) -> dict:
    rows = BASE.csv_rows(path)
    if not rows or list(rows[0]) != FIELDS:
        raise ValueError("Missing or unexpected service CSV schema")
    previous = window[0]
    for index, row in enumerate(rows, 1):
        now = float(row["time_s"])
        if (row["schema"] != SCHEMA or int(row["event_index"]) != index or
                not math.isfinite(now) or not window[0] <= now < window[1] or now < previous or
                not row["event"] or not row["node"]):
            raise ValueError("Invalid service ordering, identity or window")
        previous = now
        for field in ("preparation_active", "holdoff_over", "sync_present", "tx_in_progress"):
            if row[field] not in ("", "0", "1"):
                raise ValueError("Invalid service boolean")
        if row["mac_state"] not in ("", "idle", "search", "track", "tx"):
            raise ValueError("Invalid native MAC state")
    if len(rows) > limit:
        raise ValueError("Service trace limit exceeded")
    counts = Counter(row["event"] for row in rows)
    required = {"app_admission", "hop_admission", "hop_completion", "nwk_nsdp_release", "mac_slot_tick",
                "ack_queue_enqueue_after", "ack_queue_replace_before", "mac_prepare_after", "mac_state"}
    if not required.issubset(counts):
        raise ValueError("Service trace omitted a required observation stage")
    return {"schema": "csr-ns3-ack-service-summary-v1", "status": "passed", "rows": len(rows),
            "window_s": window, "stop_endpoint": "exclusive", "max_records": limit,
            "omitted_records": 0, "event_counts": dict(sorted(counts.items())),
            "first_s": float(rows[0]["time_s"]), "last_s": float(rows[-1]["time_s"]),
            "queue_replacement_events": counts["ack_queue_replace_before"],
            "cancelled_frames": counts["mac_cancel_frame_before"],
            "native_event_names_preserved": True,
            "sequence_semantics": "Native sequence is event-specific: application identity for app/NWK/admission/completion records; HOP sequence for PHY/OTA records. MAC queue snapshots carry app-tag identity when present and explicit hop_sequence in detail. These are not interchangeable.",
            "scope": "Native trace events plus read-only MAC decision snapshots; blank fields are unavailable, not zero. Native HOP completion is observed before resend-entry erase with declared post-operation counts."}


def read_artifact(path: Path) -> bytes:
    return gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()


def accepted_anchor(case: dict, directory: Path) -> dict:
    reference = ROOT / case["reference_directory"]
    records = []
    for name in ("ns3-trace.csv", "app-admission-diagnostics.csv", "ns3-aggregates.csv", "ns3-link-decisions.csv"):
        old = reference / (name + ".gz" if name in ("ns3-trace.csv", "ns3-link-decisions.csv") else name)
        new = directory / name
        left, right = read_artifact(old), new.read_bytes()
        if left != right:
            raise ValueError("Passive service observer changed accepted T8 bytes: " + name)
        records.append({"name": name, "reference_path": old.relative_to(ROOT).as_posix(),
                        "reference_sha256": BASE.digest(old), "original_sha256": hashlib.sha256(left).hexdigest(),
                        "current_sha256": BASE.digest(new), "bytes": len(left), "equal": True})
    return {"status": "passed", "reference_directory": case["reference_directory"], "compared_files": records}


def execute_case(case: dict, plan: dict, source: Path, output: Path, runner: Path, timeout: int) -> dict:
    directory = output / case["storage_key"]
    directory.mkdir()
    record = {"schema": "csr-tranche9-ack-service-reference-case-v1", "case_id": case["case_id"],
              "storage_key": case["storage_key"], "case": case, "status": "running", "started_utc": BASE.utc_now(),
              "runner_sha256": BASE.digest(runner), "ns3_source_commit": BASE.PIN,
              "full_ns3_rebuild_performed": False, "matlab_executed": False, "opnet_executed": False,
              "stages": {}, "compressed_artifacts": [], "control_compressed_artifacts": []}
    scenario = ROOT / case["scenario_file"]
    workflow = module("tranche9_upstream_execution", source / "utils/run-opnet-aggregate-differential.py")
    parsed = workflow.load_scenario_run(scenario)
    try:
        for prefix, observed in (("", True), ("off-", False)):
            command = T8.runner_command(runner, scenario, case, directory, prefix, observed)
            if observed:
                command += [f"--serviceDiagnostics={directory / 'ns3-service.csv'}",
                            f"--serviceStart={plan['service_window_s'][0]}",
                            f"--serviceStop={plan['service_window_s'][1]}",
                            f"--serviceLimit={plan['service_max_records']}"]
            stage = T7.run_stage(command, directory / (prefix + "ns3-run.log"), timeout)
            record["stages"][prefix + "run_ns3"] = stage
            if stage["exit_code"]:
                raise ValueError("ns-3 service execution failed")
            for name in (prefix + "ns3-trace.csv", prefix + "app-admission-diagnostics.csv", prefix + "ns3-run.log"):
                (directory / name).chmod(0o444)
            if observed:
                for name in ("ns3-link-decisions.csv", "ns3-service.csv"):
                    (directory / name).chmod(0o444)
        record["nonperturbation"] = T8.compare_bytes(directory, "", "off-")
        command = [sys.executable, "-B", "-I", str(source / "utils/aggregate-ns3-trace.py"),
                   str(directory / "ns3-trace.csv"), str(directory / "ns3-aggregates.csv"),
                   "--scenario", case["scenario"], "--bucket-width", str(case["bucket_width_s"]),
                   "--stop-time", str(case["duration_s"]), "--legacy-trace-size-exclusion-bits", "0",
                   "--require-zero-size-mismatches", "--provenance", str(directory / "ns3-aggregates.provenance.json")]
        record["stages"]["aggregate_ns3"] = T7.run_stage(command, directory / "ns3-aggregate.log", timeout)
        if record["stages"]["aggregate_ns3"]["exit_code"]:
            raise ValueError("ns-3 service aggregation failed")
        record["application_admission_totals"] = workflow.validate_app_admission_diagnostics(
            directory / "app-admission-diagnostics.csv", case["scenario"], parsed["application_profile"], parsed["flows"])
        record["exact_sequence_validation"] = workflow._load_and_validate_ns3_provenance(
            directory / "ns3-aggregates.provenance.json", directory / "ns3-trace.csv",
            directory / "ns3-aggregates.csv", case["scenario"])
        record["normalized_sidecars"] = [T7.normalized_sidecar(case, directory, "ns3")]
        record["accepted_t8_anchor"] = accepted_anchor(case, directory)
        record["feedback_diagnostics"] = T8.observer_summary(directory / "ns3-link-decisions.csv")
        record["service_diagnostics"] = service_summary(directory / "ns3-service.csv", plan["service_window_s"], plan["service_max_records"])
        BASE.write_json(directory / "feedback-summary.json", record["feedback_diagnostics"])
        BASE.write_json(directory / "service-summary.json", record["service_diagnostics"])
        record["status"] = "completed"
    except Exception as error:
        record.update(status="failed", error=str(error))
        raise
    finally:
        for pattern in ("*trace.csv", "*link-decisions.csv", "*service.csv"):
            for path in sorted(directory.glob(pattern)):
                field = "control_compressed_artifacts" if path.name.startswith("off-") else "compressed_artifacts"
                record[field].append(T7.compress(path))
        record["completed_utc"] = BASE.utc_now()
        record["files"] = [T7.file_record(path, directory) for path in sorted(directory.iterdir())
                           if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(directory / "manifest.json", record)
        for path in directory.iterdir():
            if path.is_file():
                path.chmod(0o444)
    return record


def verify_closed_case(directory: Path, record: dict) -> None:
    for item in record["files"]:
        path = directory / item["path"]
        if BASE.digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError("Closed ns-3 service artifact changed")
    originals = {}
    for item in record["compressed_artifacts"] + record["control_compressed_artifacts"]:
        data = read_artifact(directory / item["path"])
        if len(data) != item["original_bytes"] or hashlib.sha256(data).hexdigest() != item["original_sha256"]:
            raise ValueError("Compressed ns-3 service evidence failed roundtrip")
        originals[item["original_name"]] = item["original_sha256"]
    for item in record["nonperturbation"]["compared_files"]:
        for prefix in ("first", "second"):
            name = item[prefix + "_path"]
            digest = originals.get(name) or BASE.digest(directory / name)
            if digest != item[prefix + "_sha256"]:
                raise ValueError("Closed on/off comparison artifact changed")
    for item in record["accepted_t8_anchor"]["compared_files"]:
        name = item["name"]
        digest = originals.get(name) or BASE.digest(directory / name)
        if digest != item["current_sha256"] or digest != item["original_sha256"]:
            raise ValueError("Closed accepted T8 anchor changed")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ns3-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-directory", type=Path)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    source, build, output = args.source.resolve(), args.ns3_build.resolve(), args.output.resolve()
    if output.exists():
        parser.error("--output must not exist; reference evidence is never overwritten")
    output.mkdir(parents=True)
    summary = {"schema": "csr-tranche9-ack-service-reference-suite-v1", "status": "running",
               "ns3_source_commit": BASE.PIN, "started_utc": BASE.utc_now(), "plan_sha256": BASE.digest(PLAN),
               "matlab_executed": False, "opnet_executed": False, "full_ns3_rebuild_performed": False, "cases": []}
    try:
        BASE.check_source(source, build)
        plan = T7.load_json(PLAN)
        verify_plan(plan)
        paths = [Path(__file__), HELPER, PLAN, T8.HELPER, ROOT / "scripts/run_tranche8_ns3_diagnostics.py",
                 ROOT / "scripts/run_tranche7_ns3_reference.py", ROOT / "scripts/run_tranche4_ns3_reference.py",
                 ROOT / plan["parent_plan"]]
        paths += sorted((source / "utils").glob("*.py"))
        for case in plan["cases"]:
            paths += [ROOT / case[stem + "_file"] for stem in ("scenario", "recipe")]
            paths += sorted((ROOT / case["reference_directory"]).glob("*"))
        inputs = {**BASE.input_snapshot(source, build), **{str(path): BASE.digest(path) for path in paths}}
        directory = (args.build_directory or Path(tempfile.mkdtemp(prefix="t9b-"))).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        overlay_runner, modifications = prepare_overlay(source, directory / "o")
        runner = directory / "t9"
        command = BASE.compile_runner(source, build, runner, args.compiler)
        command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(overlay_runner)
        command.insert(command.index("-I" + str(build / "include")), "-I" + str(directory / "o/include"))
        compilation = T7.run_stage(command, output / "compile.log", 300)
        shutil.copy2(directory / "o/observational-overlay.patch", output / "observational-overlay.patch")
        build_record = {"schema": "csr-tranche9-ack-service-reference-build-v1", "input_sha256": inputs,
                        "observer_compile": compilation, "ns3_source_commit": BASE.PIN,
                        "source_headers_match_preserved_build": True, "standalone_runner_compiled": True,
                        "full_ns3_rebuild_performed": False, "compiler_version": BASE.checked([args.compiler, "--version"]),
                        "overlay_modifications": modifications, "observer_helper_sha256": BASE.digest(HELPER),
                        "inherited_feedback_helper_sha256": BASE.digest(T8.HELPER),
                        "library_provenance_limit": "Verified preserved shared libraries; only the observer standalone runner translation unit was freshly compiled."}
        if runner.exists():
            build_record["runner_sha256"] = BASE.digest(runner)
        BASE.write_json(output / "build.json", build_record)
        if compilation["exit_code"]:
            raise ValueError("Standalone ns-3 service runner compilation failed")
        for case in plan["cases"]:
            record = execute_case(case, plan, source, output, runner, args.timeout_seconds)
            summary["cases"].append({"case_id": case["case_id"], "storage_key": case["storage_key"],
                "status": record["status"], "manifest": case["storage_key"] + "/manifest.json",
                "manifest_sha256": BASE.digest(output / case["storage_key"] / "manifest.json"),
                "application_admission_totals": record["application_admission_totals"],
                "service_diagnostics": record["service_diagnostics"]})
            print(case["storage_key"] + ": completed " + json.dumps(record["application_admission_totals"]), flush=True)
        BASE.check_source(source, build)
        if any(BASE.digest(Path(path)) != value for path, value in inputs.items()):
            raise ValueError("Source/build/observer/plan/reference inputs changed during ns-3 execution")
        for case in summary["cases"]:
            manifest = output / case["manifest"]
            if BASE.digest(manifest) != case["manifest_sha256"]:
                raise ValueError("Completed ns-3 service manifest changed")
            verify_closed_case(manifest.parent, T7.load_json(manifest))
        summary.update(status="completed", source_files_stable=True, input_files_stable=True,
                       all_observer_on_off_checks_passed=True, all_accepted_t8_anchors_passed=True,
                       closed_artifacts_reverified=True, build_manifest_sha256=BASE.digest(output / "build.json"))
    except Exception as error:
        summary.update(status="failed", error=str(error))
        print(f"Tranche9 ns-3 service reference failed: {error}", file=sys.stderr)
        return 1
    finally:
        summary["completed_utc"] = BASE.utc_now()
        summary["files"] = [T7.file_record(path, output) for path in sorted(output.iterdir())
                            if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(output / "manifest.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
