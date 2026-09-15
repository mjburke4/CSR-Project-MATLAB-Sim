#!/usr/bin/env python3
"""Observe nine matched outage stimuli using pinned ns-3 CSR and real PHY.

Only a standalone observation fixture is compiled. Preserved ns-3 libraries
are hashed and reused; no full engine rebuild or MATLAB execution is claimed.
The post-PHY gate runs after source MAC bookkeeping and before HOP, a documented
coupling difference from MATLAB's pre-MAC eligibility gate.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tranche4_reference_shared", ROOT / "scripts/run_tranche4_ns3_reference.py")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
HARNESS = ROOT / "scripts/ns3/tranche6_outage_reference.cc"
SEEDS = (128, 129, 130)
FRESHNESS = (60, 180, 300)
COUPLING_DIFFERENCES = [
    "The ns-3 hook runs after successful physical decoding and MAC last-heard, "
    "pathloss and reservation updates, before HOP/NWK receipt. MATLAB gates "
    "before its MAC bookkeeping; blackout MAC side effects therefore differ.",
    "ns-3 uses its actual production pairwise16/group cryptographic state; "
    "MATLAB uses behavioral production security and size-only envelopes.",
    "The same seed identities do not create common random draws across ns-3 "
    "and MATLAB; random engines, stream assignment and event order differ.",
    "Native ns-3 behavior is retained for freshness, admission and retry/custody. "
    "Results describe the pinned implementation and are not a numerical-parity gate.",
]


def case_catalog() -> list[dict]:
    return [{"name": f"recovery_freshness_s{freshness}_seed{seed}",
             "freshness_seconds": freshness, "seed": seed}
            for freshness in FRESHNESS for seed in SEEDS]


def scenario_contract(case: dict) -> dict:
    if case not in case_catalog():
        raise ValueError("Unsupported bounded outage case")
    return {
        "schema": "csr-tranche6-outage-stimulus-v1", **case,
        "matlab_fixture": "csr.scenario.researchNetwork('route_recovery')",
        "matlab_sweep": "csr.scenario.researchSweep recovery_freshness",
        "duration_seconds": 900, "freshness_period_seconds": 5,
        "nodes": [{"id": node, "position_meters": [(node - 1) * 3800, 0, 1],
                   "capability": 2 if node == 1 else 1, "transit_enabled": True}
                  for node in (1, 2, 3)],
        "manual_discovery": [{"time_seconds": t, "node": node,
                              "duration_seconds": 30}
                             for t, node in ((10, 1), (45, 2), (80, 3),
                                             (315, 1), (320, 2), (325, 3),
                                             (576, 1), (581, 2), (586, 3))],
        "blackout": {"disabled_node": 2, "start_seconds": 405,
                     "end_seconds": 540, "interval": "[start,end)",
                     "eligibility": "Drop when decoded source OR receiver is disabled node",
                     "gate_location": "after physical decode and MAC bookkeeping; before HOP"},
        "application": {"source": 3, "destination": 1,
                        "times_seconds": [450, 486, 522, 558, 594],
                        "payload_bytes": 64, "dscp": 0, "ack_required": True,
                        "application_route_or_discovery_gating": False},
        "radio": {"min_rate_kbps": 8, "max_rate_kbps": 128,
                  "min_power_dbm": 0, "max_power_dbm": 30,
                  "link_margin_db": 10, "frequency_hz": 400000000,
                  "bandwidth_hz": 1000000, "antenna_height_meters": 1,
                  "stochastic_sync_threshold": True,
                  "phy": "unmodified CSR OPNET three-path and BER/ECC engine",
                  "custom_phy_error_model": False,
                  "duty_cycle": "source OPNET-aligned, phase zero, first wake 0.988 s",
                  "hop_wire_profile": "production-pairwise16"},
        "rng": {"ns3_run": 1, "device_streams": [0, 2, 4],
                "matlab_random_draw_equality_claimed": False},
        "coupling_differences": COUPLING_DIFFERENCES,
        "numerical_parity_certified": False,
    }


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def analyze_trace(rows: list[dict], snapshots: list[dict]) -> tuple[dict, list[dict]]:
    """Classify observations without equating an earlier hop failure to global loss."""
    if not rows or any(row.get("schema") != "csr-differential-trace-v1" for row in rows):
        raise ValueError("Missing or invalid canonical reference trace")
    if [int(row["event_index"]) for row in rows] != list(range(len(rows))):
        raise ValueError("Reference event indices are not contiguous")
    sent = [row for row in rows if row["event"] == "app_send"]
    if [(row["sequence"], float(row["time_s"])) for row in sent] != [
            (str(i + 1), float(t)) for i, t in enumerate((450, 486, 522, 558, 594))]:
        raise ValueError("Reference did not generate the five exact scheduled applications")
    if any(row["src"] != "3" or row["dst"] != "1"
           or int(row["size_bytes"]) != 71 for row in sent):
        raise ValueError("Unexpected application endpoints or NWK packet size")
    if [(float(row["time_s"]), row["node"]) for row in rows
            if row["event"] == "manual_discovery"] != [
            (float(t), str(n)) for t, n in ((10, 1), (45, 2), (80, 3),
                                           (315, 1), (320, 2), (325, 3),
                                           (576, 1), (581, 2), (586, 3))]:
        raise ValueError("Manual discovery stimuli differ from the matched contract")
    if [(row["event"], float(row["time_s"]), row["node"]) for row in rows
            if row["event"] in ("link_disable", "link_enable")] != [
            ("link_disable", 405.0, "2"), ("link_enable", 540.0, "2")]:
        raise ValueError("Blackout events differ from the matched contract")
    post_phy = [row for row in rows if row["event"] == "post_phy_eligibility_drop"]
    if any(not 405 <= float(row["time_s"]) < 540 or
           (row["node"] != "2" and row["src"] != "2") for row in post_phy):
        raise ValueError("Eligibility drops occurred outside the two-endpoint blackout")
    terminal = []
    for send in sent:
        sequence = send["sequence"]
        flow_rows = [row for row in rows if row["sequence"] == sequence
                     and row["src"] == "3" and row["dst"] == "1"]
        deliveries = [row for row in flow_rows if row["event"] == "nwk_delivery"]
        failures = [row for row in flow_rows if row["event"] == "hop_completion"
                    and row["reason"] == "no_ack"]
        latency = float(deliveries[0]["time_s"]) - float(send["time_s"]) if deliveries else None
        if latency is not None and latency < 0:
            raise ValueError("Application delivery precedes generation")
        terminal.append({"app_sequence": sequence, "generated_s": send["time_s"],
                         "outcome": "delivered" if deliveries else (
                             "undelivered_retry_exhaustion_observed" if failures else
                             "undelivered_no_terminal_trace"),
                         "delivered_s": deliveries[0]["time_s"] if deliveries else "",
                         "latency_s": latency if latency is not None else "",
                         "delivery_count": len(deliveries),
                         "no_ack_completion_count": len(failures),
                         "no_ack_nodes": ";".join(row["node"] for row in failures),
                         "no_ack_times_s": ";".join(row["time_s"] for row in failures)})
    final = [row for row in snapshots if float(row["time_s"]) == 900]
    if [row["node"] for row in final] != ["1", "2", "3"]:
        raise ValueError("Missing exact stop-time snapshots")
    counts = Counter(row["event"] for row in rows)
    outcomes = Counter(row["outcome"] for row in terminal)
    observations = {
        "app_generated": 5, "app_delivered_unique": outcomes["delivered"],
        "app_delivery_events": counts["nwk_delivery"],
        "duplicate_app_deliveries": sum(max(0, r["delivery_count"] - 1) for r in terminal),
        "undelivered_with_retry_exhaustion": outcomes["undelivered_retry_exhaustion_observed"],
        "undelivered_without_terminal_trace": outcomes["undelivered_no_terminal_trace"],
        "hop_no_ack_completions": sum(row["no_ack_completion_count"] for row in terminal),
        "link_failure_callbacks": counts["observed_link_failure_callback"],
        "post_phy_eligibility_drops": len(post_phy),
        "tx_start": counts["tx_start"], "phy_rx_accept_before_gate": counts["rx_accept"],
        "phy_rx_drop": counts["rx_drop"],
        "maximum_delivered_latency_seconds": max(
            (r["latency_s"] for r in terminal if r["delivery_count"]), default=None),
        "minimum_delivered_latency_seconds": min(
            (r["latency_s"] for r in terminal if r["delivery_count"]), default=None),
        "first_delivery_seconds": min(
            (float(r["delivered_s"]) for r in terminal if r["delivery_count"]), default=None),
        "first_after_restore_seconds": min(
            (float(r["time_s"]) for r in rows if r["event"] == "nwk_delivery"
             and float(r["time_s"]) >= 540), default=None),
        "stop_nwk_queue": sum(int(r["nwk_queue"]) for r in final),
        "stop_hop_pending_data": sum(int(r["hop_pending_data"]) for r in final),
        "stop_hop_resend_queue": sum(int(r["hop_resend_queue"]) for r in final),
        "stop_mac_queue": sum(int(r["mac_queue"]) for r in final),
        "terminal_interpretation": "A no-ACK completion proves local HOP exhaustion, not "
            "global packet loss when later delivery or downstream custody exists. Unresolved "
            "applications remain explicitly unresolved; queue snapshots are aggregate.",
    }
    return observations, terminal


def compress_file(path: Path) -> Path:
    destination = path.with_name(path.name + ".gz")
    with path.open("rb") as source, destination.open("wb") as sink:
        with gzip.GzipFile(filename="", mode="wb", fileobj=sink, mtime=0) as compressed:
            shutil.copyfileobj(source, compressed)
    path.unlink()
    return destination


def file_record(path: Path, base: Path) -> dict:
    return {"path": path.relative_to(base).as_posix(), "sha256": BASE.digest(path),
            "bytes": path.stat().st_size}


def compile_command(build: Path, destination: Path, compiler: str) -> list[str]:
    command = BASE.compile_runner(ROOT, build, destination, compiler)
    command[command.index(str(ROOT / "csr-opnet-scenario-runner.cc"))] = str(HARNESS)
    return command


def compact_case_summary(case: dict, observations: dict) -> dict:
    return {"case": case["name"], "freshness_s": case["freshness_seconds"],
            "seed": case["seed"], "generated": observations["app_generated"],
            "delivered": observations["app_delivered_unique"],
            "observed_undelivered_retry_exhaustion": observations["undelivered_with_retry_exhaustion"],
            "undelivered_unresolved": observations["undelivered_without_terminal_trace"],
            "dropped": "unknown", "pending": "unknown",
            "first_delivery_s": observations["first_delivery_seconds"],
            "first_after_restore_s": observations["first_after_restore_seconds"],
            "delivered_latency_min_s": observations["minimum_delivered_latency_seconds"],
            "delivered_latency_max_s": observations["maximum_delivered_latency_seconds"],
            "terminal_accounting": "local HOP exhaustion observed; exact global drop/pending ownership not exported by pinned ns-3"}


def execute_case(case: dict, output: Path, runner: Path, build_sha256: str) -> dict:
    destination = output / case["name"]
    destination.mkdir()
    contract = scenario_contract(case)
    BASE.write_json(destination / "scenario.json", contract)
    manifest = {"schema": "csr-tranche6-outage-reference-case-v1", "status": "running",
                "started_utc": BASE.utc_now(), "ns3_source_commit": BASE.PIN,
                "execution_completed": False, "matlab_executed": False,
                "full_ns3_rebuild_performed": False, "case": case["name"],
                "build_manifest_sha256": build_sha256, "runner_sha256": BASE.digest(runner),
                "coupling_differences": COUPLING_DIFFERENCES}
    command = [str(runner), f"--seed={case['seed']}",
               f"--freshness={case['freshness_seconds']}",
               "--trace=" + str(destination / "trace.csv"),
               "--snapshots=" + str(destination / "snapshots.csv")]
    manifest["command"] = command
    try:
        started = time.monotonic()
        with (destination / "run.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    text=True, timeout=300)
        manifest["elapsed_seconds"] = time.monotonic() - started
        manifest["exit_code"] = result.returncode
        if result.returncode:
            raise RuntimeError(f"Outage reference runner exited {result.returncode}")
        if "CSR Tranche 6 outage reference complete:" not in (destination / "run.log").read_text():
            raise ValueError("Reference runner omitted completion marker")
        rows = BASE.csv_rows(destination / "trace.csv")
        snapshots = BASE.csv_rows(destination / "snapshots.csv")
        observations, terminal = analyze_trace(rows, snapshots)
        write_csv(destination / "applications.csv", terminal)
        write_csv(destination / "event_counts.csv", [
            {"event": event, "count": count}
            for event, count in sorted(Counter(row["event"] for row in rows).items())])
        selected = [r for r in rows if r["event"] in (
            "app_send", "nwk_delivery", "hop_completion", "manual_discovery",
            "link_disable", "link_enable", "post_phy_eligibility_drop",
            "observed_link_failure_callback", "nwk_enqueue", "nwk_forward")
            or "neighbor" in r["event"] or "route" in r["event"]]
        write_csv(destination / "event_timeline.csv", selected, list(rows[0]))
        manifest["uncompressed_trace_sha256"] = BASE.digest(destination / "trace.csv")
        manifest["trace_row_count"] = len(rows)
        manifest.update(status="completed", execution_completed=True, observations=observations)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        for name in ("trace.csv", "run.log", "event_timeline.csv"):
            if (destination / name).exists():
                compress_file(destination / name)
        manifest["completed_utc"] = BASE.utc_now()
        manifest["files"] = [file_record(p, destination) for p in sorted(destination.iterdir())
                             if p.is_file() and p.name != "manifest.json"]
        BASE.write_json(destination / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--ns3-build", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--build-directory", type=Path)
    args = parser.parse_args(argv)
    source, build, output = args.source.resolve(), args.ns3_build.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be new or empty; accepted evidence is never overwritten")
    cases = case_catalog()
    if set(args.case) - {c["name"] for c in cases}:
        parser.error("Requested case is absent from bounded outage catalog")
    if args.case:
        cases = [c for c in cases if c["name"] in args.case]
    output.mkdir(parents=True, exist_ok=True)
    summary = {"schema": "csr-tranche6-outage-reference-suite-v1", "status": "running",
               "started_utc": BASE.utc_now(), "ns3_source_commit": BASE.PIN,
               "matlab_executed": False, "full_ns3_rebuild_performed": False,
               "coupling_differences": COUPLING_DIFFERENCES, "cases": []}
    try:
        BASE.check_source(source, build)
        inputs = BASE.input_snapshot(source, build)
        own_inputs = {str(p): BASE.digest(p) for p in
                      (HARNESS, Path(__file__).resolve(), ROOT / "scripts/run_tranche4_ns3_reference.py")}
        directory = (args.build_directory or Path(tempfile.mkdtemp(prefix="csr-tranche6-reference-"))).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        runner = directory / "csr-tranche6-outage-reference"
        command = compile_command(build, runner, args.compiler)
        build_record = {"schema": "csr-tranche6-outage-reference-build-v1",
                        "ns3_source_commit": BASE.PIN, "standalone_fixture_compiled": True,
                        "full_ns3_rebuild_performed": False, "command": command,
                        "compiler_version": BASE.checked([args.compiler, "--version"]),
                        "input_sha256": inputs, "fixture_input_sha256": own_inputs,
                        "library_provenance_limit": "Preserved shared libraries are byte-hashed; "
                            "installed CSR headers match the clean pinned source. The engine "
                            "was not rebuilt in this run."}
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (output / "compile.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        build_record["exit_code"] = result.returncode
        if runner.exists():
            build_record["runner_sha256"] = BASE.digest(runner)
        BASE.write_json(output / "build.json", build_record)
        if result.returncode:
            raise RuntimeError(f"Standalone fixture compilation exited {result.returncode}")
        for case in cases:
            result = execute_case(case, output, runner, BASE.digest(output / "build.json"))
            summary["cases"].append({"name": case["name"], "status": result["status"],
                                     "manifest": case["name"] + "/manifest.json",
                                     "manifest_sha256": BASE.digest(output / case["name"] / "manifest.json"),
                                     "observations": result["observations"]})
            print(f"{case['name']}: {result['observations']['app_delivered_unique']}/5 delivered; "
                  f"{result['observations']['hop_no_ack_completions']} no-ACK completions", flush=True)
        BASE.check_source(source, build)
        if inputs != BASE.input_snapshot(source, build) or any(
                BASE.digest(Path(path)) != digest for path, digest in own_inputs.items()):
            raise ValueError("Reference source, preserved build or fixture inputs changed during execution")
        summary.update(status="completed", source_files_stable=True, fixture_files_stable=True)
        write_csv(output / "summary.csv", [
            {"case": c["name"], **{k: v for k, v in c["observations"].items()
                                    if k != "terminal_interpretation"}}
            for c in summary["cases"]])
        write_csv(output / "case_summary.csv", [
            compact_case_summary(case, result["observations"])
            for case, result in zip(cases, summary["cases"], strict=True)])
    except Exception as error:
        summary.update(status="failed", error=str(error))
        print(f"Reference validation failed: {error}", file=sys.stderr)
        return 1
    finally:
        summary["completed_utc"] = BASE.utc_now()
        summary["files"] = [file_record(p, output) for p in sorted(output.iterdir())
                            if p.is_file() and p.name != "manifest.json"]
        BASE.write_json(output / "manifest.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
