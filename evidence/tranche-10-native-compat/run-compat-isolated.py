#!/usr/bin/env python3
"""Bind the retained T9 suite to an explicitly rebuilt pinned native engine."""
from pathlib import Path
from datetime import datetime, timezone
import gzip
import hashlib
import json
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
REPO = Path('/workspace/scratch/1a5b1ad6ce1b/csr10')
OUT = BASE / "compat"
BIN = BASE / "compat-bin"
ENGINE = Path('/workspace/scratch/1a5b1ad6ce1b/t10/engine')
BUILD = ENGINE / "build"
SOURCE = Path('/workspace/scratch/1a5b1ad6ce1b/t10/ns')
BUILD_MANIFEST = Path('/workspace/scratch/1a5b1ad6ce1b/t10/engine-logs/manifest.json')
RECEIPT = BASE / "compat-receipt.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def loaded(path):
    return json.loads(path.read_text())


def bytes_for(path):
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes())
    return path.read_bytes()


def record(path):
    return {"path": path.relative_to(BASE).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha(path)}


def git(source, *arguments):
    return subprocess.check_output(["git", "-C", str(source), *arguments], text=True).strip()


def verify_fresh_build(manifest, expected_sha):
    assert sha(BUILD_MANIFEST) == expected_sha
    assert manifest["schema"] == "csr-tranche10-native-engine-rebuild-v1"
    assert manifest["status"] == "passed" and manifest["engine_rebuilt"] is True
    assert manifest["source_commit"] == git(SOURCE, "rev-parse", "HEAD")
    assert manifest["engine_commit"] == git(ENGINE, "rev-parse", "HEAD")
    assert not git(SOURCE, "status", "--porcelain", "--untracked-files=no")
    assert not git(ENGINE, "status", "--porcelain", "--untracked-files=no")
    for item in manifest["libraries"]:
        path = Path(item["path"])
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
    for path, expected in manifest["input_sha256"].items():
        assert sha(Path(path)) == expected


def main():
    engine_manifest, engine_sha = loaded(BUILD_MANIFEST), sha(BUILD_MANIFEST)
    verify_fresh_build(engine_manifest, engine_sha)
    assert not OUT.exists() and not BIN.exists() and not RECEIPT.exists()
    command = [sys.executable, "-B", str(REPO / "scripts/run_tranche9_ns3_service.py"),
               "--source", str(SOURCE), "--ns3-build", str(BUILD),
               "--output", str(OUT), "--build-directory", str(BIN),
               "--compiler", "/usr/bin/g++"]
    write_json(BASE / "compat-command.json", {"command": command})
    receipt = {
        "schema": "csr-tranche10-fresh-engine-compatibility-v1", "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": engine_manifest["source_commit"],
        "engine_commit": engine_manifest["engine_commit"],
        "engine_rebuilt": True, "reused_historical_libraries": False,
        "engine_build_manifest": str(BUILD_MANIFEST), "engine_build_manifest_sha256": engine_sha,
        "fresh_libraries": engine_manifest["libraries"],
        "retained_runner": str(REPO / "scripts/run_tranche9_ns3_service.py"),
        "retained_runner_sha256": sha(REPO / "scripts/run_tranche9_ns3_service.py"),
        "command": command, "matlab_executed": False, "opnet_executed": False,
        "campus_6000_seconds_executed": False,
        "scope": "Six retained T9 diagnostic cases with the fresh pinned nine-module engine. Compatibility requires all 24 accepted T8 artifact pairs and all 12 observer on/off artifact pairs to remain byte-identical.",
        "inherited_manifest_wording": {
            "unchanged": True,
            "explanation": "The unchanged T9 runner describes its input shared libraries as preserved and reports no full engine rebuild in its own execution. In this invocation those inputs are the newly rebuilt T10 libraries bound above. This outer receipt establishes that fresh-engine provenance explicitly; no historical library-byte identity is claimed."
        },
    }
    write_json(RECEIPT, receipt)
    started = time.monotonic()
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (BASE / "compat-run.log").write_text(result.stdout)
    receipt.update(exit_code=result.returncode, elapsed_seconds=time.monotonic() - started,
                   run_log_sha256=sha(BASE / "compat-run.log"),
                   output_captured_after_process_closed=True)
    try:
        assert result.returncode == 0, result.stdout[-6000:]
        verify_fresh_build(engine_manifest, engine_sha)
        suite = loaded(OUT / "manifest.json")
        assert suite["schema"] == "csr-tranche9-ack-service-reference-suite-v1"
        assert suite["status"] == "completed" and len(suite["cases"]) == 6
        for key in ("source_files_stable", "input_files_stable", "all_observer_on_off_checks_passed",
                    "all_accepted_t8_anchors_passed", "closed_artifacts_reverified"):
            assert suite[key] is True, key
        assert [case["storage_key"] for case in suite["cases"]] == ["c129", "c128", "c130", "c131", "c132", "a129"]
        assert sha(OUT / "build.json") == suite["build_manifest_sha256"]
        build = loaded(OUT / "build.json")
        for library in engine_manifest["libraries"]:
            assert build["input_sha256"][library["path"]] == library["sha256"]
        for path, expected in build["input_sha256"].items():
            assert sha(Path(path)) == expected
        on_off, accepted, retained_service, cases = [], [], [], []
        declared_checks, roundtrip_checks = 0, 0
        for item in suite["files"]:
            path = OUT / item["path"]
            assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
            declared_checks += 1
        assert {p.name for p in OUT.iterdir() if p.is_file()} == {i["path"] for i in suite["files"]} | {"manifest.json"}
        assert {p.name for p in OUT.iterdir() if p.is_dir()} == {c["storage_key"] for c in suite["cases"]}
        for summary in suite["cases"]:
            key = summary["storage_key"]
            manifest_path = OUT / summary["manifest"]
            assert sha(manifest_path) == summary["manifest_sha256"]
            declared_checks += 1
            case = loaded(manifest_path)
            assert case["status"] == "completed"
            directory = manifest_path.parent
            assert {p.name for p in directory.iterdir()} == {i["path"] for i in case["files"]} | {"manifest.json"}
            for item in case["files"]:
                path = directory / item["path"]
                assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
                declared_checks += 1
            originals = {}
            for item in case["compressed_artifacts"] + case["control_compressed_artifacts"]:
                path = directory / item["path"]
                data = bytes_for(path)
                assert len(data) == item["original_bytes"]
                assert hashlib.sha256(data).hexdigest() == item["original_sha256"]
                originals[item["original_name"]] = path
                roundtrip_checks += 1
            for item in case["nonperturbation"]["compared_files"]:
                first = originals.get(item["first_path"], directory / item["first_path"])
                second = originals.get(item["second_path"], directory / item["second_path"])
                left, right = bytes_for(first), bytes_for(second)
                assert left == right
                value = hashlib.sha256(left).hexdigest()
                assert value == item["first_sha256"] == item["second_sha256"]
                on_off.append({"case": key, "first": first.relative_to(BASE).as_posix(),
                               "second": second.relative_to(BASE).as_posix(), "bytes": len(left),
                               "original_sha256": value, "byte_equal": True})
            for item in case["accepted_t8_anchor"]["compared_files"]:
                old = REPO / item["reference_path"]
                new = originals.get(item["name"], directory / item["name"])
                assert sha(old) == item["reference_sha256"]
                left, right = bytes_for(old), bytes_for(new)
                assert left == right and len(left) == item["bytes"]
                value = hashlib.sha256(left).hexdigest()
                assert value == item["original_sha256"] == item["current_sha256"]
                accepted.append({"case": key, **item, "byte_equal": True})
            old_service = REPO / "evidence/tranche-9-ns3-reference" / key / "ns3-service.csv.gz"
            new_service = directory / "ns3-service.csv.gz"
            left, right = bytes_for(old_service), bytes_for(new_service)
            retained_service.append({"case": key, "retained_sha256": sha(old_service),
                                     "fresh_sha256": sha(new_service), "original_bytes_equal": left == right,
                                     "retained_original_sha256": hashlib.sha256(left).hexdigest(),
                                     "fresh_original_sha256": hashlib.sha256(right).hexdigest()})
            cases.append({"case": key, "application_admission_totals": case["application_admission_totals"],
                          "service_rows": case["service_diagnostics"]["rows"],
                          "service_omitted_records": case["service_diagnostics"]["omitted_records"]})
        assert len(accepted) == 24 and len(on_off) == 12
        receipt.update(status="passed", suite_manifest_sha256=sha(OUT / "manifest.json"),
                       observer_build_manifest_sha256=sha(OUT / "build.json"),
                       fresh_library_hashes_bound=True, fresh_engine_inputs_unchanged=True,
                       declared_artifact_hash_checks=declared_checks,
                       gzip_roundtrip_checks=roundtrip_checks, strict_directory_membership=True,
                       case_count=6, cases=cases, accepted_t8_artifact_pairs=accepted,
                       accepted_t8_artifact_pair_count=len(accepted), observer_on_off_pairs=on_off,
                       observer_on_off_pair_count=len(on_off), retained_t9_service_comparisons=retained_service,
                       retained_t9_service_all_equal=all(i["original_bytes_equal"] for i in retained_service))
    except Exception as error:
        receipt.update(status="failed", error=str(error))
        raise
    finally:
        receipt["completed_utc"] = datetime.now(timezone.utc).isoformat()
        paths = [BASE / "compat-run.log", BASE / "compat-command.json", Path(__file__).resolve()]
        for directory in (OUT, BIN):
            if directory.exists():
                paths += [p for p in sorted(directory.rglob("*")) if p.is_file()]
        receipt["outputs"] = [record(p) for p in paths]
        write_json(RECEIPT, receipt)
    print(json.dumps({"status": receipt["status"], "case_count": receipt["case_count"],
                      "accepted_pairs": receipt["accepted_t8_artifact_pair_count"],
                      "on_off_pairs": receipt["observer_on_off_pair_count"],
                      "t9_service_bytes_equal": receipt["retained_t9_service_all_equal"],
                      "receipt": str(RECEIPT)}))


if __name__ == "__main__":
    main()
