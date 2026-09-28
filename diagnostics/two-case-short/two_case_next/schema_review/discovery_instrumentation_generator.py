#!/usr/bin/env python3
"""Build a reproducible local overlay from the accepted MAC capture source.

Never mutates the source checkout. The packaged files are only the four
changed source files and the new passive observer header.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

EXPECTED = {
    "capture.cc": "b859a78a9e260e87689126569aeb6693861ffb78f28da2d296ff9eaa4287cc4d",
    "overlay/ns3/csr-net-device.h": "5ab14e72414fb9e95a4ece15e5ca2d3e7b8dacd0095116d24e72e08fb9382151",
    "overlay/ns3/csr-phy-model.h": "d690b4c572491a9ea8c48735b1726770938b118dcbcd931e92920e602cae18fc",
    "overlay/ns3/mac-replay-hooks.h": "a6a791c7374b33769e096a19046ca14d82f583d7241abcd077c7d48fe09b7984",
}
PROBE_FILES = {
    "capture.cc": "probe_sources/capture.cc",
    "overlay/ns3/csr-net-device.h": "probe_sources/ns3/csr-net-device.h",
    "overlay/ns3/csr-phy-model.h": "probe_sources/ns3/csr-phy-model.h",
    "overlay/ns3/mac-replay-hooks.h": "probe_sources/ns3/mac-replay-hooks.h",
    "overlay/ns3/csr-discovery-capture.h": "probe_sources/ns3/csr-discovery-capture.h",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(base: Path, output: Path) -> dict:
    package = Path(__file__).resolve().parent
    for name, value in EXPECTED.items():
        source = base / name
        assert source.is_file(), f"missing canonical native source {source}"
        assert digest(source) == value, f"source hash mismatch {source}"
    assert not output.exists(), f"output already exists: {output}"
    (output / "overlay").mkdir(parents=True)
    shutil.copytree(base / "overlay" / "ns3", output / "overlay" / "ns3")
    shutil.copy2(base / "capture.cc", output / "capture.cc")
    for target, source in PROBE_FILES.items():
        shutil.copy2(package / source, output / target)
    identity = {
        "schema": "csr-seed131-native-overlay-v1",
        "base_native_source_sha256": EXPECTED,
        "modified_files": {
            name: digest(output / name) for name in PROBE_FILES
        },
        "simulation_window_s": [0, 85],
        "capture_window_s": [25, 85],
        "source_commit_required": "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b",
        "engine_commit_required": "6b5cd24ea80713ce16d88575869aedd6f432bdae",
    }
    (output / "overlay-identity.json").write_text(
        json.dumps(identity, indent=2) + "\n", encoding="utf-8"
    )
    return identity


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply(args.base_native, args.output), indent=2))
