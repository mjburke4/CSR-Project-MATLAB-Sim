#!/usr/bin/env python3
"""Restore the pinned CSR/ns-3 Debug environment used by the short captures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

PINS = {
    "csr": ("https://github.com/mjburke4/CSR-Project-NS3-part2.git",
            "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b",
            "b611b233fb369569b98f0914ece24d029ccc2f42"),
    "engine": ("https://github.com/nsnam/ns-3-dev-git.git",
               "6b5cd24ea80713ce16d88575869aedd6f432bdae",
               "f30343185fb057e3a9cdd54f496cca0cef49ae23"),
}
MODULES = ("csr", "spectrum", "buildings", "propagation", "mobility",
           "antenna", "network", "stats", "core")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def output(command):
    return subprocess.check_output(list(map(str, command)), text=True).strip()


def check_source(root):
    result = {}
    for name, (url, commit, tree) in PINS.items():
        repo = root / name
        actual = output(["git", "-C", repo, "rev-parse", "HEAD"])
        actual_tree = output(["git", "-C", repo, "rev-parse", "HEAD^{tree}"])
        dirty = output(["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"])
        if actual != commit or actual_tree != tree or dirty:
            raise RuntimeError(f"Pinned tracked source verification failed: {repo}")
        result[name] = {"url": url, "commit": actual, "tree": actual_tree,
                        "tracked_files_clean": True}
    return result


def build_commands(root, jobs):
    engine = root / "engine"
    cmake = root / "toolchain/cmake/data/bin/cmake"
    ninja = root / "toolchain/bin/ninja"
    configure = [str(cmake), "-S", str(engine), "-B", str(engine / "cmake-cache"),
                 "-G", "Ninja", "-DCMAKE_MAKE_PROGRAM=" + str(ninja),
                 "-DCMAKE_BUILD_TYPE=Debug", "-DNS3_ENABLED_MODULES=" + ";".join(MODULES)]
    configure += ["-DNS3_" + option + "=OFF" for option in
                  ("EXAMPLES", "TESTS", "WARNINGS_AS_ERRORS", "PRECOMPILE_HEADERS",
                   "CCACHE", "GTK3", "GSL", "SQLITE", "EIGEN", "VISUALIZER")]
    configure += ["-DNS3_ASSERT=ON", "-DNS3_LOG=ON"]
    build = [str(cmake), "--build", str(engine / "cmake-cache"), "--parallel", str(jobs)]
    return configure, build


def write_provenance(root, commands):
    source = check_source(root)
    libraries = {}
    for module in MODULES:
        path = root / "engine/build/lib" / f"libns3-dev-{module}-debug.so"
        if path.read_bytes()[:4] != b"\x7fELF":
            raise RuntimeError(f"Invalid shared library: {path}")
        symbols = output(["nm", "-D", "--defined-only", path]).splitlines()
        if not symbols:
            raise RuntimeError(f"Empty shared library: {path}")
        linked = output(["ldd", "-r", path])
        if "not found" in linked or "undefined symbol" in linked:
            raise RuntimeError(f"Missing runtime library: {path}\n{linked}")
        libraries[path.name] = {"sha256": sha(path), "bytes": path.stat().st_size,
                                "defined_symbols": len(symbols), "ldd": linked}
    versions = {
        "g++": output(["g++", "--version"]).splitlines()[0],
        "cmake": output([root / "toolchain/cmake/data/bin/cmake", "--version"]).splitlines()[0],
        "ninja": output([root / "toolchain/bin/ninja", "--version"]),
    }
    record = {"schema": "csr-native-environment-restore-v1", "status": "built_and_linked",
              "sources": source, "platform": platform.platform(), "toolchain": versions,
              "commands": commands, "libraries": libraries,
              "configure_log_sha256": sha(root / "configure.log"),
              "build_log_sha256": sha(root / "build.log"),
              "capture_prefix_validation": "must be run separately by capture drivers"}
    (root / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, commit, _) in PINS.items():
        repo = root / name
        if not repo.exists():
            subprocess.run(["git", "clone", "--no-checkout", "--filter=blob:none", url, str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "--detach", commit], check=True)
    check_source(root)
    cmake = root / "toolchain/cmake/data/bin/cmake"
    ninja = root / "toolchain/bin/ninja"
    if not cmake.is_file() or not ninja.is_file():
        subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(root / "toolchain"),
                        "cmake==3.31.10", "ninja==1.13.2"], check=True)
    link = root / "engine/contrib/csr"
    if not link.exists():
        link.symlink_to(root / "csr", target_is_directory=True)
    if link.resolve() != root / "csr":
        raise RuntimeError("contrib/csr does not point to the pinned CSR checkout")
    commands = {}
    for name, command in zip(("configure", "build"), build_commands(root, args.jobs)):
        print(f"Running {name}; log: {root / (name + '.log')}", flush=True)
        started = time.monotonic()
        with (root / (name + ".log")).open("w") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        commands[name] = {"argv": command, "elapsed_seconds": time.monotonic() - started,
                          "exit_code": completed.returncode}
        empty_objects = [p for p in (root / "engine/cmake-cache").rglob("*.o")
                         if p.stat().st_size == 0] if name == "build" else []
        if empty_objects:
            # An interrupted compiler can leave an empty generated object that
            # Ninja later treats as complete. Rebuild only those generated files.
            recovery = {"reason": "zero-byte generated objects", "tracked_source_changes": False,
                        "removed_generated_files": [str(p) for p in empty_objects]}
            (root / "generated-object-recovery.json").write_text(json.dumps(recovery, indent=2) + "\n")
            shutil.copy2(root / "build.log", root / "build-initial-failed.log")
            for path in empty_objects:
                path.unlink()
            retry = build_commands(root, 2)[1]
            with (root / "build.log").open("w") as log:
                subprocess.run(retry, stdout=log, stderr=subprocess.STDOUT, check=True)
            commands["build_recovery"] = {"argv": retry, "exit_code": 0}
        else:
            completed.check_returncode()
    record = write_provenance(root, commands)
    print(json.dumps({"status": record["status"], "build": str(root / "engine/build")}, indent=2))


if __name__ == "__main__":
    main()
