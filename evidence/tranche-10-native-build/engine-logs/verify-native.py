#!/usr/bin/env python3
"""Verify a freshly rebuilt pinned engine with the unchanged T9 contract."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
LOGS = BASE_DIR / "engine-logs"
SOURCE = BASE_DIR / "ns"
ENGINE = BASE_DIR / "engine"
BUILD = ENGINE / "build"
REPO = BASE_DIR.parent / "csr10"
OUT = BASE_DIR / "engine-smoke"
CSR_PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
ENGINE_PIN = "6b5cd24ea80713ce16d88575869aedd6f432bdae"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def git(repo, *arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments], text=True).strip()


def clean_pins():
    assert git(SOURCE, "rev-parse", "HEAD") == CSR_PIN
    assert git(ENGINE, "rev-parse", "HEAD") == ENGINE_PIN
    assert not git(SOURCE, "status", "--porcelain", "--untracked-files=no")
    assert not git(ENGINE, "status", "--porcelain", "--untracked-files=no")
    for path in [SOURCE / "CMakeLists.txt", *sorted((SOURCE / "model").iterdir())]:
        if path.is_file():
            assert digest(path) == digest(ENGINE / "contrib/csr" / path.relative_to(SOURCE))


def run_logged(command, basename):
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True)
    log = OUT / (basename + ".log")
    log.write_text(result.stdout + result.stderr)
    record = {"command": command, "exit_code": result.returncode,
              "elapsed_seconds": time.monotonic() - started,
              "log": log.name, "log_sha256": digest(log),
              "output_captured_after_process_closed": True}
    write_json(OUT / (basename + ".json"), record)
    if result.returncode:
        raise RuntimeError(f"{basename} failed with exit code {result.returncode}")
    return record


def main():
    clean_pins()
    build_record = json.loads((LOGS / "build.json").read_text())
    assert build_record["exit_code"] == 0
    assert build_record["log_sha256"] == digest(LOGS / "build.log")
    pending_record = json.loads((LOGS / "build-pending.json").read_text())
    assert pending_record["exit_code"] == 0 and pending_record["nothing_pending"]
    assert pending_record["log_sha256"] == digest(LOGS / "build-pending.log")
    spec = importlib.util.spec_from_file_location("reference_base", REPO / "scripts/run_tranche4_ns3_reference.py")
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.check_source(SOURCE, BUILD)
    before = base.input_snapshot(SOURCE, BUILD)
    OUT.mkdir(exist_ok=False)
    binary = OUT / "ack-contract"
    contract = REPO / "scripts/ns3/tranche9_ack_contract.cc"
    command = base.compile_runner(SOURCE, BUILD, binary, "/usr/bin/g++")
    command[command.index(str(SOURCE / "csr-opnet-scenario-runner.cc"))] = str(contract)
    compile_record = run_logged(command, "compile")
    run_record = run_logged([str(binary), str(OUT / "checkpoints.csv")], "run")
    clean_pins()
    base.check_source(SOURCE, BUILD)
    assert before == base.input_snapshot(SOURCE, BUILD)
    with (OUT / "checkpoints.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 101
    assert len({row["case"] for row in rows}) == 6
    assert all(row["pass"] == "1" for row in rows)
    old_reference = REPO / "evidence/tranche-9-contract-reference/checkpoints.csv"
    assert (OUT / "checkpoints.csv").read_bytes() == old_reference.read_bytes()
    linked = subprocess.run(["ldd", str(binary)], capture_output=True, text=True, check=True)
    (OUT / "linked-libraries.txt").write_text(linked.stdout + linked.stderr)
    assert "not found" not in linked.stdout
    libraries = [{"path": str(BUILD / "lib" / f"libns3-dev-{name}-debug.so"),
                  "bytes": (BUILD / "lib" / f"libns3-dev-{name}-debug.so").stat().st_size,
                  "sha256": digest(BUILD / "lib" / f"libns3-dev-{name}-debug.so")}
                 for name in base.MODULES]
    tools = {}
    for name, command in {
        "compiler": ["/usr/bin/g++", "--version"],
        "linker": ["/usr/bin/ld", "--version"],
        "cmake": [str(BASE_DIR / "tools/bin/cmake"), "--version"],
        "ninja": [str(BASE_DIR / "tools/bin/ninja"), "--version"],
        "python": [sys.executable, "--version"],
    }.items():
        resolved = Path(command[0]).resolve()
        tools[name] = {"command": command,
                       "version": subprocess.check_output(command, text=True).strip(),
                       "executable": str(resolved), "sha256": digest(resolved)}
    exp = Path(subprocess.check_output(["/usr/bin/g++", "-print-file-name=libstdc++exp.a"], text=True).strip())
    tools["libstdc++exp"] = {"path": str(exp), "sha256": digest(exp), "bytes": exp.stat().st_size}
    manifest = {
        "schema": "csr-tranche10-native-engine-rebuild-v1", "status": "passed",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engine_rebuilt": True, "reused_historical_libraries": False,
        "historical_libraries_byte_identity_claimed": False,
        "source_commit": CSR_PIN, "source_tree": git(SOURCE, "rev-parse", "HEAD^{tree}"),
        "engine_commit": ENGINE_PIN, "engine_tree": git(ENGINE, "rev-parse", "HEAD^{tree}"),
        "engine_repository": "https://github.com/nsnam/ns-3-dev-git.git",
        "engine_main_repository": "https://gitlab.com/nsnam/ns-3-dev.git",
        "official_mirror_verification": {
            "url": "https://github.com/nsnam/ns-3-dev-git",
            "readme": "README.md", "readme_sha256": digest(ENGINE / "README.md"),
            "note": "Official nsnam GitHub mirror description and pinned README identify the main GitLab repository."
        },
        "engine_tracked_sources_unchanged": True, "csr_tracked_sources_unchanged": True,
        "copied_csr_module_files": 24, "copied_csr_module_files_match": True,
        "build_path": str(BUILD), "build_profile": "Debug", "cpp_standard": 23,
        "assertions": True, "logging": True, "warnings_as_errors": False,
        "build_jobs": 4, "enabled_modules": list(base.MODULES),
        "matlab_executed": False, "full_engine_test_suite_executed": False,
        "historical_benchmarks_rerun": False, "native_contract_executed": True,
        "scope": "Fresh nine-module engine build and unchanged T9 deterministic standalone contract. No claim of full historical benchmark or RF/statistical parity.",
        "toolchain": tools, "platform": platform.platform(),
        "configure_record": json.loads((LOGS / "configure.json").read_text()),
        "build_record": build_record,
        "nothing_pending_record": pending_record,
        "cmake_cache_sha256": digest(ENGINE / "cmake-cache/CMakeCache.txt"),
        "build_commands_sha256": digest(LOGS / "build-commands.txt"),
        "libraries": libraries,
        "smoke_contract": {
            "source": str(contract), "source_sha256": digest(contract),
            "compile": compile_record, "run": run_record,
            "checkpoint_count": len(rows), "case_count": 6,
            "checkpoint_sha256": digest(OUT / "checkpoints.csv"),
            "t9_reference_sha256": digest(old_reference), "t9_reference_bytes_equal": True,
            "binary_sha256": digest(binary), "inputs_unchanged": True,
        },
        "input_sha256": before,
        "artifacts": [],
    }
    for directory in [LOGS, OUT]:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != "manifest.json":
                manifest["artifacts"].append({"path": path.relative_to(BASE_DIR).as_posix(),
                                               "sha256": digest(path), "bytes": path.stat().st_size})
    write_json(LOGS / "manifest.json", manifest)
    print(json.dumps({"status": "passed", "engine_rebuilt": True,
                      "libraries": len(libraries), "checkpoints": len(rows),
                      "t9_reference_bytes_equal": True, "build_path": str(BUILD),
                      "manifest": str(LOGS / "manifest.json")}))


if __name__ == "__main__":
    main()
