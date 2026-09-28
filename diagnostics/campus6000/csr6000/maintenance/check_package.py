#!/usr/bin/env python3
"""Static owner-kit checks. Does not execute MATLAB or any network simulation."""
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TREE = "fcf84980619b6902660eb9192b4d71f3f912cafd8fb74074fc752560372d1b4e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    model = ROOT / "model"
    source_files = sorted(model.rglob("*.m"))
    tree = hashlib.sha256("".join(
        f"{sha(p)}  {p.relative_to(model).as_posix()}\n" for p in source_files
    ).encode()).hexdigest()
    assert len(source_files) == 96 and tree == EXPECTED_TREE
    binding = json.loads((ROOT / "review/native_binding.json").read_text())
    references = []
    for seed, expected_admitted, expected_delivered in [(131, 12630, 12261), (132, 12460, 11794)]:
        bound = next(c for c in binding["cases"] if c["seed"] == seed)
        scenario = ROOT / f"inputs/s{seed}.csv"
        assert sha(scenario) == bound["scenario_sha256"]
        records = rows(scenario)
        run = [r for r in records if r["record"] == "run"]
        assert len(run) == 1 and int(run[0]["seed"]) == seed
        assert float(run[0]["duration_s"]) == 6000
        flows = [r for r in records if r["record"] == "flow"]
        assert sorted(int(r["flow_src"]) for r in flows) == [2, 3, 4, 5, 7, 8]
        assert all(int(r["flow_dst"]) == 1 and float(r["flow_start_s"]) == 300
                   and float(r["flow_interval_s"]) == .02 for r in flows)
        ref = ROOT / f"reference/s{seed}"
        manifest = json.loads((ref / "manifest.json").read_text())
        assert manifest["status"] == "completed"
        assert manifest["ns3_source_commit"] == "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
        apps = rows(ref / "applications.csv")
        assert len(apps) == expected_admitted
        assert len({(int(r["source"]), int(r["attempt_index_0based"])) for r in apps}) == len(apps)
        delivered = [r for r in apps if r["status"] == "delivered"]
        assert len(delivered) == expected_delivered
        duplicate_events = 0
        for r in apps:
            assert int(r["seed"]) == seed and int(r["cutoff_ns"]) == 6000 * 10**9
            assert int(r["generated_time_ns"]) == 300 * 10**9 + int(r["attempt_index_0based"]) * 20000000
            count = int(r["delivery_event_count"])
            if r["status"] == "delivered":
                assert count >= 1
                duplicate_events += count - 1
                assert int(r["first_delivery_time_ns"]) - int(r["generated_time_ns"]) == int(r["latency_ns"])
            else:
                assert r["status"] == "unresolved_at_cutoff" and count == 0
                assert r["first_delivery_time_ns"] == "" and r["latency_ns"] == ""
        assert duplicate_events == (0 if seed == 131 else 4)
        counters = rows(ref / "app-admission-diagnostics.csv")
        assert len(counters) == 6
        for c in counters:
            assert int(c["attempts"]) == 285000
            source = int(c["source"])
            assert int(c["admitted"]) == sum(int(a["source"]) == source for a in apps)
            blocked = sum(int(c[k]) for k in ["blocked_discovery", "blocked_topology",
                          "blocked_gateway_route", "blocked_destination", "blocked_nsdp"])
            assert int(c["admitted"]) + blocked == 285000
        references.append({"seed": seed, "admitted": len(apps), "unique_delivered": len(delivered),
                           "additional_delivery_events": duplicate_events,
                           "scenario_sha256": sha(scenario),
                           "applications_sha256": sha(ref / "applications.csv")})
    files = [ROOT / "run_6000_batch.m", *sorted((ROOT / "private").glob("*.m"))]
    assert (ROOT / "private/batch_case_analysis.m") in files
    assert (ROOT / "private/batch_analysis_selfcheck.m") in files
    command = [sys.executable, "-m", "miss_hit.mh_lint", "--ignore-config", "--brief",
               "--input-encoding", "utf-8", *map(str, files)]
    result = subprocess.run(command, capture_output=True, text=True)
    (ROOT / "review/syntax.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    report = {"schema": "csr-current6000-static-preflight-v1", "status": "pass",
              "candidate_matlab_files": len(source_files), "candidate_matlab_tree_sha256": tree,
              "native_references": references, "syntax_files_checked": [str(p.relative_to(ROOT)) for p in files],
              "syntax_tool": "MISS_HIT 0.9.44", "syntax_exit_code": result.returncode,
              "production_changes": 0, "matlab_executed": False, "new_simulations": 0,
              "owner_preflight": "Synthetic reporting checks plus both real native ledger schemas run in MATLAB before simulation.",
              "scope": "Static syntax, frozen-source identity, actual reference ledger schema/counters and scenario binding; no MATLAB runtime acceptance claim."}
    (ROOT / "review/preflight.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
