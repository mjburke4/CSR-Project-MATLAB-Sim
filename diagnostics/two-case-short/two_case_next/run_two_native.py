#!/usr/bin/env python3
"""Run both bounded native captures against the pinned original histories.

The two processes are independent. A failure in either keeps the whole batch
open but does not cancel the other case. No production checkout is modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from finalize_captures import promote

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-mac-native", type=Path,
                        default=HERE / "accepted_mac_native",
                        help="SHA-bound accepted MAC capture baseline (bundled by default)")
    parser.add_argument("--native-source-repo", type=Path, required=True,
                        help="original native CSR source repository at the pinned commit")
    parser.add_argument("--source-model", type=Path,
                        help="original CSR model headers; default: SOURCE_REPO/model")
    parser.add_argument("--engine-repo", type=Path, required=True,
                        help="ns-3 engine checkout at the pinned commit")
    parser.add_argument("--engine-build", type=Path, required=True,
                        help="matching Debug ns-3 build directory")
    parser.add_argument("--out", type=Path, required=True,
                        help="new output directory with results for both cases")
    parser.add_argument("--serial", action="store_true",
                        help="run one after the other on memory-limited hosts")
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        parser.error("--out must be a new directory, so results cannot be confused")
    schema = HERE / "schema_review"
    for case in ("discovery131", "source5_132"):
        check = subprocess.run([sys.executable, str(schema / "validate_two_case.py"),
                                str(schema / (case + ".manifest.json"))],
                               capture_output=True, text=True)
        if check.returncode != 0:
            parser.error(f"pinned {case} reference failed validation: {check.stdout} {check.stderr}")
    out.mkdir(parents=True)
    model = (args.source_model or args.native_source_repo / "model").resolve()
    commands = {
        "discovery131": [sys.executable, str(HERE / "discovery_capture/run_seed131_capture.py"),
                         "--base-native", str(args.accepted_mac_native.resolve()),
                         "--native-source-repo", str(args.native_source_repo.resolve()),
                         "--engine-repo", str(args.engine_repo.resolve()),
                         "--engine-build", str(args.engine_build.resolve()),
                         "--scenario", str(schema / "scenario_s131.csv"),
                         "--reference", str(schema / "native_s131_prefix_0_85.csv.gz"),
                         "--output", str(out / "seed131")],
        "source5_132": [sys.executable, str(HERE / "source5_capture/run_bounded_capture.py"),
                        "--source-model", str(model),
                        "--engine-build", str(args.engine_build.resolve()),
                        "--scenario", str(schema / "scenario_s132.csv"),
                        "--reference-trace", str(schema / "native_s132_prefix_0_330.csv.gz"),
                        "--out", str(out / "seed132")],
    }
    processes = {}
    for case, command in commands.items():
        log = (out / (case + ".log")).open("w")
        processes[case] = (subprocess.Popen(command, stdout=log,
                                            stderr=subprocess.STDOUT), log)
        if args.serial:
            processes[case][0].wait()
            log.close()
    if not args.serial:
        for process, log in processes.values():
            process.wait()
            log.close()
    dpath = out / "seed131/receipt.json"
    spath = out / "seed132/reference/fidelity.json"
    discovery = json.loads(dpath.read_text()) if dpath.is_file() else {}
    source5 = json.loads(spath.read_text()) if spath.is_file() else {}
    result = {
        "schema": "csr-two-case-native-batch-v1",
        "discovery131": {
            "exit_code": processes["discovery131"][0].returncode,
            "verified": discovery.get("status") == "verified_exact_native_prefix"
                        and discovery.get("gate", {}).get("exact_prefix") is True,
            "prefix_rows": discovery.get("gate", {}).get("rows"),
            "log": "discovery131.log",
        },
        "source5_132": {
            "exit_code": processes["source5_132"][0].returncode,
            "verified": source5.get("all_passed") is True
                        and source5.get("source_capture", {}).get("exact_prefix") is True,
            "prefix_rows": source5.get("source_capture", {}).get("rows"),
            "log": "source5_132.log",
        },
        "matlab_replays": "pending",
        "full_network_parity_claim": False,
    }
    result["both_captures_verified"] = all(
        v["verified"] and v["exit_code"] == 0 for v in
        (result["discovery131"], result["source5_132"]))
    for case in ("discovery131", "source5_132"):
        if not result[case]["verified"] or result[case]["exit_code"] != 0:
            result[case]["shared_manifest"] = "pending"
            continue
        try:
            validated = promote(HERE, out, case)
            result[case]["shared_manifest"] = "verified" if validated[
                "accepted_manifest"] else "rejected"
        except (AssertionError, KeyError, OSError, ValueError, RuntimeError) as error:
            result[case]["shared_manifest"] = "rejected"
            result[case]["manifest_error"] = str(error)
    result["both_captures_verified"] = result["both_captures_verified"] and all(
        result[case]["shared_manifest"] == "verified"
        for case in ("discovery131", "source5_132"))
    (out / "batch.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["both_captures_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
