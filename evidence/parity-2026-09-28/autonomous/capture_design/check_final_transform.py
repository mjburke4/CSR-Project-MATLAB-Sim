#!/usr/bin/env python3
"""Verify final kit transformations recover exact baseline source bytes.

This is a static provenance check. It is not MATLAB execution or a claim that
the instrumentation is behavior-neutral at runtime.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json


ROOT = Path(__file__).resolve().parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(kit: Path, baseline: Path):
    spec = importlib.util.spec_from_file_location(
        "passive_observers", ROOT / "autonomous/design/instrument_observers.py")
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    transforms = json.loads((kit / "source_transform.json").read_text())
    model = kit / "model"
    final_bytes = {p.relative_to(model).as_posix(): p.read_bytes()
                   for p in model.rglob("*") if p.is_file()}
    baseline_bytes = {p.relative_to(baseline).as_posix(): p.read_bytes()
                      for p in baseline.rglob("*") if p.is_file()}
    assert set(final_bytes) == set(baseline_bytes), {
        "missing": sorted(set(baseline_bytes) - set(final_bytes)),
        "extra": sorted(set(final_bytes) - set(baseline_bytes))}
    restored = dict(final_bytes)
    applied = []
    for edit in reversed(transforms["random_and_export_edits"]):
        path, before, after = edit["path"], edit["before"], edit["after"]
        text = restored[path].decode("utf-8")
        assert text.count(after) == 1, ("non-unique reverse anchor", path, after[:100])
        restored[path] = text.replace(after, before, 1).encode("utf-8")
        applied.append(path)

    builders = {"+csr/+sim/EventScheduler.m": observer.scheduler,
                "+csr/+mac/Layer.m": observer.mac,
                "+csr/+phy/SignalEngine.m": observer.phy}
    rows = []
    for path in sorted(final_bytes):
        original = baseline_bytes[path]
        observer_insertions = 0
        if path in builders:
            assert digest(original) == observer.PINS[path]
            patcher = builders[path](original.decode("utf-8"))
            observed = patcher.finish().encode("utf-8")
            assert restored[path] == observed, ("observer-only source differs", path)
            text = restored[path].decode("utf-8")
            for anchor, inserted in reversed(patcher.edits):
                assert text.count(inserted) == 1, ("observer reverse anchor", path)
                text = text.replace(inserted, anchor, 1)
            restored[path] = text.encode("utf-8")
            observer_insertions = len(patcher.edits)
        assert restored[path] == original, ("baseline restoration differs", path)
        if final_bytes[path] != original:
            rows.append({"path": path, "baseline_sha256": digest(original),
                         "final_sha256": digest(final_bytes[path]),
                         "restored_sha256": digest(restored[path]),
                         "observer_insertions": observer_insertions,
                         "sampler_or_export_edits": applied.count(path)})
    return {"schema": "csr-autonomous-final-transform-review-v1", "status": "pass",
            "baseline_artifacts": len(baseline_bytes),
            "unchanged_artifacts": len(final_bytes) - len(rows),
            "transformed_artifacts": rows,
            "all_model_artifacts_restore_to_exact_baseline_bytes": True,
            "runtime_verified": False,
            "scope": "Static source provenance and reversible transformation only",
            "source_transform_sha256": digest((kit / "source_transform.json").read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=ROOT / "autonomous/kit/autocase")
    parser.add_argument("--baseline", type=Path, default=ROOT / "return6000/kit/csr6000/model")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("final_transform_review.json"))
    args = parser.parse_args()
    report = check(args.kit, args.baseline)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
