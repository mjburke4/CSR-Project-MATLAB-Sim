#!/usr/bin/env python3
"""Run frozen small ns-3 diagnostics with a passive feedback observer overlay.

Only standalone runner translation units are compiled; engine/CSR libraries are
preserved verified products. Original source and accepted T7 inputs stay intact.
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


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


T7 = module("tranche8_reference_shared", ROOT / "scripts/run_tranche7_ns3_reference.py")
BASE = T7.BASE
PLAN = ROOT / "scenarios/link_diagnostics/plan.json"
HELPER = ROOT / "scripts/ns3/tranche8-link-observer.h"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Pinned observational overlay anchor is not unique")
    return text.replace(old, new, 1)


def prepare_overlay(source: Path, directory: Path) -> tuple[Path, list[dict]]:
    """Copy all headers first, then add only read-only side-channel hooks."""
    headers = directory / "include/ns3"
    headers.mkdir(parents=True)
    for path in (source / "model").iterdir():
        if path.is_file():
            shutil.copy2(path, headers / path.name)
    shutil.copy2(HELPER, headers / HELPER.name)
    records, patch = [], []

    def change(original: Path, output: Path, changed: str) -> None:
        before = original.read_text()
        output.write_text(changed)
        patch.extend(difflib.unified_diff(before.splitlines(True), changed.splitlines(True),
                                         fromfile="a/" + original.name, tofile="b/" + original.name))
        records.append({"source_path": str(original), "source_sha256": BASE.digest(original),
                        "overlay_path": str(output), "overlay_sha256": BASE.digest(output)})

    common = source / "model/csr-common.h"
    change(common, headers / common.name, common.read_text() + '\n#include "tranche8-link-observer.h"\n')
    hop = source / "model/csr-hop-layer.h"
    observe = """
      // Passive Tranche 8 observer: read the already-selected header and peer inputs.
      if (g_tranche8FeedbackStream.is_open ())
        {
          const auto observedPeer = m_neighbors.find (header.GetDst ());
          const bool observedKnown = observedPeer != m_neighbors.end ();
          const double unavailable = std::numeric_limits<double>::quiet_NaN ();
          Tranche8ObserveFeedbackSelection (
            FRAME, header, observedKnown,
            observedKnown ? observedPeer->second.s0PowerDbm : unavailable,
            observedKnown ? observedPeer->second.lastPathlossDb : unavailable,
            observedKnown ? observedPeer->second.numFailures : unavailable,
            m_minSpeed, m_maxSpeed, m_minPower, m_maxPower, m_linkMargin);
        }
"""
    hop_text = replace_once(hop.read_text(), "      return bareFrame;\n",
                            observe.replace("FRAME", "bareFrame") + "      return bareFrame;\n")
    anchor = "      LEGACY_ACK_HOP_SECURITY_OVERHEAD);\n  return protectedFrame;\n"
    hop_text = replace_once(hop_text, anchor, "      LEGACY_ACK_HOP_SECURITY_OVERHEAD);\n" +
                            observe.replace("FRAME", "protectedFrame") + "  return protectedFrame;\n")
    hop_text = replace_once(hop_text, "      ackPkt = ProtectAckFrame (ackHdr);\n",
                            "      ackPkt = ProtectAckFrame (ackHdr);\n"
                            "      Tranche8ObserveFeedbackContext (ackPkt, hdr);\n")
    change(hop, headers / hop.name, hop_text)
    device = source / "model/csr-net-device.h"
    anchor = "                    | (++m_nextTxSignalId & 0xffffffffULL);\n"
    change(device, headers / device.name, replace_once(device.read_text(), anchor, anchor +
        "  Tranche8ObserveFeedbackTransmission (frameCopies, rateKbps, txPowerDbm, signalId);\n"))
    runner = source / "csr-opnet-scenario-runner.cc"
    code = replace_once(runner.read_text(), "  std::string appDiagnosticsPath;\n",
                        "  std::string appDiagnosticsPath;\n  std::string feedbackDiagnosticsPath;\n")
    code = replace_once(code, "  command.Parse (argc, argv);\n",
                        '  command.AddValue ("feedbackDiagnostics", "Passive ACK/DACK observer CSV", feedbackDiagnosticsPath);\n'
                        "  command.Parse (argc, argv);\n")
    code = replace_once(code, "  OpenDifferentialTraceCsv (tracePath);\n",
                        "  OpenDifferentialTraceCsv (tracePath);\n"
                        "  Tranche8OpenFeedbackCsv (feedbackDiagnosticsPath);\n")
    code = replace_once(code, "  CloseDifferentialTraceCsv ();\n",
                        "  CloseDifferentialTraceCsv ();\n  Tranche8CloseFeedbackCsv ();\n")
    output_runner = directory / runner.name
    change(runner, output_runner, code)
    (directory / "observational-overlay.patch").write_text("".join(patch))
    return output_runner, records


def runner_command(runner: Path, scenario: Path, case: dict, directory: Path,
                   prefix: str = "", observed: bool = False) -> list[str]:
    command = [str(runner), f"--scenario={scenario}",
               f"--trace={directory / (prefix + 'ns3-trace.csv')}",
               f"--appDiagnostics={directory / (prefix + 'app-admission-diagnostics.csv')}",
               f"--stop={case['duration_s']}", "--flowLimit=0", "--dutyCycling=1",
               "--opnetAlignedDutyCycle=1", "--gatewayDiscovery=1", "--opnetAppGating=1",
               "--aggregateTraceOnly=1", "--quietModelLogs=1"]
    if observed:
        command.append(f"--feedbackDiagnostics={directory / 'ns3-link-decisions.csv'}")
    return command


def compare_bytes(directory: Path, first_prefix: str, second_prefix: str) -> dict:
    records = []
    for name in ("ns3-trace.csv", "app-admission-diagnostics.csv"):
        first, second = directory / (first_prefix + name), directory / (second_prefix + name)
        record = {"name": name, "first_path": first.name, "second_path": second.name,
                  "first_sha256": BASE.digest(first), "second_sha256": BASE.digest(second)}
        record["equal"] = record["first_sha256"] == record["second_sha256"]
        if not record["equal"]:
            raise ValueError(f"Observer altered simulation output: {name}")
        records.append(record)
    return {"status": "passed", "compared_files": records}


def compress_outputs(directory: Path, record: dict) -> None:
    for path in sorted(directory.glob("*trace.csv")) + sorted(directory.glob("*link-decisions.csv")):
        field = "control_compressed_artifacts" if path.name.startswith(("observer-off-", "pristine-")) else "compressed_artifacts"
        record[field].append(T7.compress(path))


def validate_final_control_bindings(directory: Path, record: dict) -> None:
    """Bind the closed compressed bytes back to the earlier on/off comparisons."""
    by_name = {item["original_name"]: item for item in
               record["compressed_artifacts"] + record["control_compressed_artifacts"]}
    checks = [record["nonperturbation"]]
    if "source_runner_vs_observer_off" in checks[0]:
        checks.append(checks[0]["source_runner_vs_observer_off"])
    for check in checks:
        for item in check["compared_files"]:
            for prefix in ("first", "second"):
                name = item[prefix + "_path"]
                if name in by_name:
                    compressed = by_name[name]
                    data = gzip.decompress((directory / compressed["path"]).read_bytes())
                    actual = hashlib.sha256(data).hexdigest()
                    if len(data) != compressed["original_bytes"] or actual != compressed["original_sha256"]:
                        raise ValueError("Compressed control evidence does not reproduce original bytes")
                else:
                    actual = BASE.digest(directory / name)
                if actual != item[prefix + "_sha256"]:
                    raise ValueError("Closed control artifact changed after observer comparison")
    record["nonperturbation"]["closed_artifacts_reverified"] = True


def csv_from_bytes(data: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def baseline_anchor(case: dict, directory: Path) -> dict | None:
    if case["seed"] != 128:
        return None
    reference = ROOT / "evidence/tranche-7-ns3-reference" / case["base_case_id"]
    old = T7.load_json(reference / "manifest.json")
    old_trace = gzip.decompress((reference / "ns3-trace.csv.gz").read_bytes())
    new_trace = (directory / "ns3-trace.csv").read_bytes()
    if old_trace != new_trace:
        raise ValueError("Seed128 ns-3 event trace differs from accepted T7 bytes")
    checks = {"app_trace_byte_exact": True}
    for name, ignored in (("app-admission-diagnostics.csv", {"scenario"}),
                          ("ns3-aggregates.csv", {"scenario", "source_file_sha256"})):
        left = BASE.csv_rows(reference / name)
        right = BASE.csv_rows(directory / name)
        normalize = lambda rows: [{key: value for key, value in row.items() if key not in ignored}
                                  for row in rows]
        if normalize(left) != normalize(right):
            raise ValueError(f"Seed128 changed T7 values: {name}")
        checks[name.replace(".csv", "").replace("-", "_") + "_equal_except_labels"] = True
    return {"status": "passed", "reference_manifest_sha256": BASE.digest(reference / "manifest.json"),
            "source_commit": old["ns3_source_commit"], "reference_directory": str(reference), **checks}


def observer_summary(path: Path) -> dict:
    rows = BASE.csv_rows(path)
    selections, contexts, ota = {}, {}, []
    ota_members = set()
    for row in rows:
        if row["schema"] != "csr-ns3-feedback-observation-v1":
            raise ValueError("Unknown feedback observer schema")
        key = int(row["decision_id"])
        if key < 1 or row["frame_type"] not in ("ACK", "DACK"):
            raise ValueError("Missing feedback observation identity")
        time_s = float(row["time_s"])
        if not math.isfinite(time_s) or time_s < 0:
            raise ValueError("Invalid feedback observation time")
        selected_rate = int(row["selected_rate_key_kbps"])
        selected_power = float(row["selected_power_dbm"])
        if selected_rate not in (8, 16, 32, 64, 128, 500, 1000) or not math.isfinite(selected_power):
            raise ValueError("Invalid selected feedback radio settings")
        if not (int(row["min_rate_key_kbps"]) <= selected_rate <= int(row["max_rate_key_kbps"])):
            raise ValueError("Selected feedback rate outside configured limits")
        if not (float(row["min_power_dbm"]) <= selected_power <= math.ceil(float(row["max_power_dbm"]))):
            raise ValueError("Selected feedback power outside configured limits")
        if row["stage"] == "feedback_selection":
            if key in selections:
                raise ValueError("Duplicate feedback selection identity")
            selections[key] = row
        elif row["stage"] == "ack_response_context":
            if key not in selections or key in contexts:
                raise ValueError("Missing or repeated DATA response context")
            contexts[key] = row
        elif row["stage"] == "ota_segment":
            if key not in selections:
                raise ValueError("Feedback OTA member without selection")
            aggregate, index, count = int(row["aggregate_id"]), int(row["segment_index"]), int(row["segment_count"])
            if aggregate < 1 or not 1 <= index <= count or (aggregate, index) in ota_members:
                raise ValueError("Duplicate or invalid feedback OTA member")
            if (int(row["actual_rate_key_kbps"]) not in (8, 16, 32, 64, 128, 500, 1000)
                    or not math.isfinite(float(row["actual_power_dbm"]))):
                raise ValueError("Invalid actual feedback radio settings")
            ota_members.add((aggregate, index))
            ota.append(row)
        else:
            raise ValueError("Unknown feedback observation stage")
        if key in selections:
            identity = ("node_id", "peer_id", "frame_type", "hop_sequence", "packet_uid", "has_ack_window",
                        "ack_bitmap", "dack_bitmap", "selected_rate_key_kbps", "selected_power_dbm")
            if any(row[name] != selections[key][name] for name in identity):
                raise ValueError("Feedback identity changed between selection and observation")

    def distribution(records: list[dict], rate: str, power: str) -> list[dict]:
        counts = Counter((row["frame_type"], int(row[rate]), float(row[power])) for row in records)
        return [{"frame_type": kind, "rate_key_kbps": speed, "power_dbm": tx, "count": count}
                for (kind, speed, tx), count in sorted(counts.items())]

    changed_rate = sum(row["actual_rate_key_kbps"] != row["selected_rate_key_kbps"] for row in ota)
    changed_power = sum(float(row["actual_power_dbm"]) != float(row["selected_power_dbm"]) for row in ota)
    return {"schema": "csr-ns3-feedback-observation-summary-v1", "status": "passed",
            "rows": len(rows), "selection_count": len(selections), "ordinary_data_context_count": len(contexts),
            "ota_feedback_member_count": len(ota),
            "ota_aggregates_containing_feedback": len({row["aggregate_id"] for row in ota}),
            "all_ota_members_linked_to_selection": True,
            "distinct_decisions_transmitted": len({int(row["decision_id"]) for row in ota}),
            "actual_vs_selected_rate_change_count": changed_rate,
            "actual_vs_selected_power_change_count": changed_power,
            "selection_distribution": distribution(list(selections.values()), "selected_rate_key_kbps", "selected_power_dbm"),
            "ota_member_distribution": distribution(ota, "actual_rate_key_kbps", "actual_power_dbm"),
            "incoming_vs_selected_rate_difference_count": sum(row["incoming_rate_key_kbps"] !=
                    row["selected_rate_key_kbps"] for row in contexts.values()),
            "incoming_vs_selected_power_difference_count": sum(bool(row["incoming_power_dbm"]) and
                    float(row["incoming_power_dbm"]) != float(row["selected_power_dbm"]) for row in contexts.values()),
            "scope": "Selection is feedback construction after ApplyLinkControl, not successful MAC admission; OTA rows count actual members including repeats. Control-exact incoming context is unavailable."}


def execute_case(case: dict, source: Path, output: Path, runner: Path, pristine: Path, timeout: int) -> dict:
    directory = output / case["case_id"]
    directory.mkdir()
    scenario = ROOT / case["scenario_file"]
    workflow = module("tranche8_upstream_execution", source / "utils/run-opnet-aggregate-differential.py")
    parsed = workflow.load_scenario_run(scenario)
    record = {"schema": "csr-tranche7-benchmark-reference-case-v1", "tranche8_diagnostics": True,
              "case_id": case["case_id"], "case": case, "status": "running", "started_utc": BASE.utc_now(),
              "runner_sha256": BASE.digest(runner), "ns3_source_commit": BASE.PIN,
              "full_ns3_rebuild_performed": False, "matlab_executed": False, "opnet_executed": False,
              "stages": {}, "compressed_artifacts": [], "control_compressed_artifacts": []}
    try:
        runs = [("", runner, True), ("observer-off-", runner, False)]
        if case["seed"] == 128:
            runs.append(("pristine-", pristine, False))
        for prefix, executable, observed in runs:
            stage = T7.run_stage(runner_command(executable, scenario, case, directory, prefix, observed),
                                directory / (prefix + "ns3-run.log"), timeout)
            record["stages"]["run_ns3" if observed else prefix + "run_ns3"] = stage
            if stage["exit_code"]:
                raise ValueError("ns-3 diagnostic execution failed")
            # These process outputs have closed. Prevent ordinary accidental
            # writers from reusing them while other control executions run.
            for name in (prefix + "ns3-trace.csv", prefix + "app-admission-diagnostics.csv",
                         prefix + "ns3-run.log"):
                (directory / name).chmod(0o444)
            if observed:
                (directory / "ns3-link-decisions.csv").chmod(0o444)
        record["nonperturbation"] = compare_bytes(directory, "", "observer-off-")
        if case["seed"] == 128:
            record["nonperturbation"]["source_runner_vs_observer_off"] = compare_bytes(directory, "pristine-", "observer-off-")
        command = [sys.executable, "-B", "-I", str(source / "utils/aggregate-ns3-trace.py"),
                   str(directory / "ns3-trace.csv"), str(directory / "ns3-aggregates.csv"),
                   "--scenario", case["scenario"], "--bucket-width", str(case["bucket_width_s"]),
                   "--stop-time", str(case["duration_s"]), "--legacy-trace-size-exclusion-bits", "0",
                   "--require-zero-size-mismatches", "--provenance", str(directory / "ns3-aggregates.provenance.json")]
        record["stages"]["aggregate_ns3"] = T7.run_stage(command, directory / "ns3-aggregate.log", timeout)
        if record["stages"]["aggregate_ns3"]["exit_code"]:
            raise ValueError("ns-3 diagnostic aggregation failed")
        record["application_admission_totals"] = workflow.validate_app_admission_diagnostics(
            directory / "app-admission-diagnostics.csv", case["scenario"], parsed["application_profile"], parsed["flows"])
        record["exact_sequence_validation"] = workflow._load_and_validate_ns3_provenance(
            directory / "ns3-aggregates.provenance.json", directory / "ns3-trace.csv",
            directory / "ns3-aggregates.csv", case["scenario"])
        record["normalized_sidecars"] = [T7.normalized_sidecar(case, directory, "ns3")]
        record["baseline_anchor"] = baseline_anchor(case, directory)
        record["observer_diagnostics"] = observer_summary(directory / "ns3-link-decisions.csv")
        BASE.write_json(directory / "feedback-summary.json", record["observer_diagnostics"])
        compress_outputs(directory, record)
        validate_final_control_bindings(directory, record)
        record["status"] = "completed"
    except Exception as error:
        record.update(status="failed", error=str(error))
        raise
    finally:
        compress_outputs(directory, record)
        record["completed_utc"] = BASE.utc_now()
        record["files"] = [T7.file_record(path, directory) for path in sorted(directory.iterdir())
                           if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(directory / "manifest.json", record)
        for path in directory.iterdir():
            if path.is_file():
                path.chmod(0o444)
    return record


def main(argv: list[str] | None = None) -> int:
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
        parser.error("--output must not exist; diagnostic evidence is never overwritten")
    output.mkdir(parents=True)
    summary = {"schema": "csr-tranche8-link-diagnostic-reference-suite-v1", "status": "running",
               "ns3_source_commit": BASE.PIN, "started_utc": BASE.utc_now(), "plan_sha256": BASE.digest(PLAN),
               "matlab_executed": False, "opnet_executed": False, "full_ns3_rebuild_performed": False,
               "cases": []}
    try:
        BASE.check_source(source, build)
        plan = T7.load_json(PLAN)
        if plan["ns3_source_commit"] != BASE.PIN or plan["case_count"] != len(plan["cases"]):
            raise ValueError("Diagnostic plan source or case count mismatch")
        for case in plan["cases"]:
            for stem in ("scenario", "recipe"):
                if BASE.digest(ROOT / case[stem + "_file"]) != case[stem + "_sha256"]:
                    raise ValueError("Diagnostic plan input hash mismatch")
        paths = [Path(__file__), HELPER, PLAN, ROOT / "scripts/run_tranche7_ns3_reference.py",
                 ROOT / "scripts/run_tranche4_ns3_reference.py"]
        paths += sorted((ROOT / "scenarios/link_diagnostics/inputs").glob("*"))
        paths += sorted((source / "utils").glob("*.py"))
        for case in plan["cases"]:
            if case["seed"] == 128:
                paths += sorted((ROOT / "evidence/tranche-7-ns3-reference" / case["base_case_id"]).glob("*"))
        inputs = {**BASE.input_snapshot(source, build), **{str(path): BASE.digest(path) for path in paths}}
        directory = (args.build_directory or Path(tempfile.mkdtemp(prefix="csr-tranche8-build-"))).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        overlay_runner, modifications = prepare_overlay(source, directory / "overlay")
        runner, pristine = directory / "csr-tranche8-observer", directory / "csr-tranche8-pristine"
        command = BASE.compile_runner(source, build, runner, args.compiler)
        command[command.index(str(source / "csr-opnet-scenario-runner.cc"))] = str(overlay_runner)
        command.insert(command.index("-I" + str(build / "include")), "-I" + str(directory / "overlay/include"))
        compilation = T7.run_stage(command, output / "compile-observer.log", 300)
        original_compilation = T7.run_stage(BASE.compile_runner(source, build, pristine, args.compiler),
                                            output / "compile-pristine.log", 300)
        shutil.copy2(directory / "overlay/observational-overlay.patch", output / "observational-overlay.patch")
        build_record = {"schema": "csr-tranche8-link-diagnostic-reference-build-v1", "input_sha256": inputs,
                        "observer_compile": compilation, "pristine_compile": original_compilation,
                        "ns3_source_commit": BASE.PIN, "source_headers_match_preserved_build": True,
                        "standalone_runner_compiled": True, "full_ns3_rebuild_performed": False,
                        "compiler_version": BASE.checked([args.compiler, "--version"]), "overlay_modifications": modifications,
                        "observer_helper_sha256": BASE.digest(HELPER),
                        "library_provenance_limit": "Verified preserved shared libraries; only standalone pristine and observer runner translation units are compiled."}
        if runner.exists():
            build_record["runner_sha256"] = BASE.digest(runner)
        if pristine.exists():
            build_record["pristine_runner_sha256"] = BASE.digest(pristine)
        BASE.write_json(output / "build.json", build_record)
        if compilation["exit_code"] or original_compilation["exit_code"]:
            raise ValueError("Standalone ns-3 runner compilation failed")
        for case in plan["cases"]:
            record = execute_case(case, source, output, runner, pristine, args.timeout_seconds)
            summary["cases"].append({"case_id": case["case_id"], "status": record["status"],
                                     "manifest": case["case_id"] + "/manifest.json",
                                     "manifest_sha256": BASE.digest(output / case["case_id"] / "manifest.json"),
                                     "application_admission_totals": record["application_admission_totals"],
                                     "exact_sequence_validation": record["exact_sequence_validation"],
                                     "observer_diagnostics": record["observer_diagnostics"]})
            print(case["case_id"] + ": completed " + json.dumps(record["application_admission_totals"]), flush=True)
        BASE.check_source(source, build)
        if any(BASE.digest(Path(path)) != value for path, value in inputs.items()):
            raise ValueError("ns-3 sources, preserved build, inputs, or observer changed during execution")
        for case in summary["cases"]:
            case_manifest = output / case["manifest"]
            if BASE.digest(case_manifest) != case["manifest_sha256"]:
                raise ValueError("A completed ns-3 case manifest changed during execution")
            record = T7.load_json(case_manifest)
            for item in record["files"]:
                path = case_manifest.parent / item["path"]
                if BASE.digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
                    raise ValueError("A closed ns-3 reference artifact changed before suite completion")
            validate_final_control_bindings(case_manifest.parent, record)
        summary.update(status="completed", source_files_stable=True, input_files_stable=True,
                       all_observer_on_off_checks_passed=True, both_seed128_anchors_passed=True,
                       build_manifest_sha256=BASE.digest(output / "build.json"))
    except Exception as error:
        summary.update(status="failed", error=str(error))
        print(f"Tranche8 diagnostics failed: {error}", file=sys.stderr)
        return 1
    finally:
        summary["completed_utc"] = BASE.utc_now()
        summary["files"] = [T7.file_record(path, output) for path in sorted(output.iterdir())
                            if path.is_file() and path.name != "manifest.json"]
        BASE.write_json(output / "manifest.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
