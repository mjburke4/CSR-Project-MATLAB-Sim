#!/usr/bin/env python3
"""Seal this receiver replay and produce its portable source/evidence ZIP."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def entry(root, path):
    return {"path": path.relative_to(root).as_posix(),
            "sha256": digest(path), "bytes": path.stat().st_size}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    required = [root / "run_receiver_contention.m", root / "baseline_binding.json"]
    for folder in ("core", "inputs", "reference"):
        required.extend(p for p in (root / folder).rglob("*") if p.is_file())
    required.extend((root / "matlab").rglob("*.m"))
    required.append(root / "matlab" / "adapter_provenance.json")
    required = sorted(set(required))
    assert (root / "reference" / "events.csv") in required
    write(root / "RUN_FILES.json", {"schema": "csr.receiver-run-files.v1",
                                   "files": [entry(root, p) for p in required]})
    suffixes = {".py", ".m", ".csv", ".json", ".md", ".h", ".cc", ".patch", ".log", ".gz"}
    included = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if "__pycache__" in path.parts or path.name == "PACKAGE_FILES.json":
            continue
        if "progress" in path.name or any(part.startswith("out_rc_") for part in path.parts):
            continue
        included.append(path)
    write(root / "PACKAGE_FILES.json", {"schema": "csr.receiver-package.v1",
                                       "files": [entry(root, p) for p in included]})
    included.append(root / "PACKAGE_FILES.json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in included:
            archive.write(path, "rxplay/" + path.relative_to(root).as_posix())
    print(json.dumps({"file": str(args.output.resolve()), "bytes": args.output.stat().st_size,
                      "sha256": digest(args.output), "files": len(included),
                      "runtime_bound_files": len(required)}, indent=2))


if __name__ == "__main__":
    main()
