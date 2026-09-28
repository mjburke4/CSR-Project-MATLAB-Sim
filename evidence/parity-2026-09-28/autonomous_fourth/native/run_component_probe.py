#!/usr/bin/env python3
"""Compile and execute only the direct component probe against the pinned build."""
import json
import subprocess
from pathlib import Path

out = Path(__file__).resolve().parent
root = out.parents[1]
build = root / "autonomous/native_env/engine/build"
cmd = ["g++", "-std=c++23", "-O0", "-g", "-DNS3_ASSERT_ENABLE", "-DNS3_BUILD_PROFILE_DEBUG",
       "-DNS3_LOG_ENABLE", "-I" + str(build / "include"), str(out / "check_ownership_probe.cc"),
       "-L" + str(build / "lib"), "-Wl,-rpath," + str(build / "lib"),
       "-lns3-dev-csr-debug", "-lns3-dev-core-debug", "-lns3-dev-network-debug", "-lstdc++exp",
       "-o", str(out / "check_ownership_probe")]
(out / "compile_command.json").write_text(json.dumps(cmd, indent=2) + "\n")
with (out / "compile.log").open("w") as log:
    subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
with (out / "check_ownership_probe.log").open("w") as log:
    subprocess.run([str(out / "check_ownership_probe")], check=True, stdout=log, stderr=subprocess.STDOUT)
print("Native component ownership probe passed; no network run.")
