#!/usr/bin/env python3
"""Freeze and package the standalone MATLAB owner kit; never run a simulator."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder, relative_to):
    return [{"path": p.relative_to(relative_to).as_posix(), "sha256": digest(p)}
            for p in sorted(folder.rglob("*")) if p.is_file()
            and "__pycache__" not in p.parts]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT.parent / "csr-6000-batch.zip")
    args = parser.parse_args()
    for name in ("run_6000_batch.m", "private/batch_case_analysis.m",
                 "private/batch_analysis_selfcheck.m", "README.md", "READY.json",
                 "review/native_binding.json", "review/preflight.json"):
        assert (ROOT / name).is_file(), f"Missing required package file: {name}"
    model = inventory(ROOT / "model", ROOT / "model")
    assert sum(r["path"].endswith(".m") for r in model) == 96
    readiness = json.loads((ROOT / "READY.json").read_text())
    assert readiness["matlab_execution"] == "pending owner run"
    assert readiness["native_reference_reuse_verified"] is True
    preflight = json.loads((ROOT / "review/preflight.json").read_text())
    assert preflight["status"] == "pass"
    sources = [r for r in model if r["path"].endswith(".m")]
    tree = hashlib.sha256("".join(f'{r["sha256"]}  {r["path"]}\n'
                                  for r in sources).encode()).hexdigest()
    assert tree == "fcf84980619b6902660eb9192b4d71f3f912cafd8fb74074fc752560372d1b4e"
    inputs = inventory(ROOT / "inputs", ROOT) + inventory(ROOT / "reference", ROOT)
    runner_paths = sorted([ROOT / "run_6000_batch.m", * (ROOT / "private").glob("*.m")])
    runners = [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p)}
               for p in runner_paths]
    plan = {
        "schema": "csr-current6000-batch-plan-v1",
        "duration_s": 6000,
        "seeds": [131, 132],
        "comparison_tolerance_percent": 15,
        "source_manifest": model,
        "input_manifest": inputs,
        "runner_manifest": runners,
        "candidate_matlab_tree_sha256": tree,
        "native_source_commit": "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b",
        "native_engine_commit": "6b5cd24ea80713ce16d88575869aedd6f432bdae",
        "input_policy": "Direct import of original seed-specific native scenario CSVs; no seed override.",
        "scenario_options": {"HistoricalBenchmark": True, "FlowLimit": 0, "Backend": "portable"},
        "capture_budgets": {"MaxRecords": 1500000, "MaxPhyRecords": 1500000,
                            "MaxApplicationAdmissionRecords": 100000, "MaxEvents": 12000000},
        "application_attempts_per_source_per_seed": 285000,
        "application_attempts_per_seed": 1710000,
        "historical_baseline_note": "Original T25 long runs predate grouped-routing cleanup; their percentages are not current-candidate results.",
        "production_model_changed_for_this_kit": False,
        "observer_enabled": False,
        "post_horizon_drain": False,
        "common_random_numbers_claimed": False,
        "statistical_equivalence_claimed": False,
        "full_five_seed_acceptance_claimed": False,
        "scope": "Two corrected-candidate autonomous network histories, with source outcomes and fixed-age comparisons."
    }
    (ROOT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    selected = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part.startswith("out_6000") or part in {"__pycache__", ".git", ".pytest_cache"}
               for part in rel.parts):
            continue
        if p.name == "FILES.sha256.json" or p.suffix in {".pyc", ".zip", ".mat"}:
            continue
        selected["csr6000/" + rel.as_posix()] = p.read_bytes()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in selected.items()}
    manifest = {"schema": "csr-current6000-package-files-v1", "files": hashes}
    data = (json.dumps(manifest, indent=2) + "\n").encode()
    (ROOT / "FILES.sha256.json").write_bytes(data)
    selected["csr6000/FILES.sha256.json"] = data
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, payload in selected.items():
            info = zipfile.ZipInfo(name, (2026, 9, 24, 0, 0, 0))
            info.external_attr = 0o644 << 16
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=6)
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
        assert "csr6000/run_6000_batch.m" in archive.namelist()
        assert all(hashlib.sha256(archive.read(name)).hexdigest() == expected
                   for name, expected in hashes.items())
    print(json.dumps({"file": str(args.output.resolve()), "bytes": args.output.stat().st_size,
                      "sha256": digest(args.output), "files_verified": len(hashes),
                      "matlab_execution": "pending owner run"}, indent=2))


if __name__ == "__main__":
    main()
