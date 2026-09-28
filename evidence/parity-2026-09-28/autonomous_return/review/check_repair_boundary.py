#!/usr/bin/env python3
"""Static boundary checks for the native CSV repair and accepted-A reuse."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "autonomous/kit/autocase"
NEW = ROOT / "autonomous_return/kit/autocase"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def natural_source(text):
    # Only these native-only regions may differ. All constructor setup,
    # natural random draw branches, stream ownership, log and close code
    # remain in the comparison.
    start_marker = "            if strcmp(mode,'native')\n"
    end_marker = "                identities=unique(obj.TxRows.tx_id);"
    assert text.count(start_marker) == text.count(end_marker) == 1
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    text = text[:start] + "<NATIVE CSV IMPORT>\n" + text[end:]
    start_marker = "        function value=take(obj,node,purpose,details)\n"
    end_marker = "        function output=summary(obj)\n"
    assert text.count(start_marker) == text.count(end_marker) == 1
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[:start] + "<NATIVE SAMPLE MATCHING>\n" + text[end:]


def main():
    owner = json.loads((ROOT / "autonomous_return/data/provenance.json").read_text())
    old_model = {p.relative_to(OLD).as_posix(): sha(p.read_bytes())
                 for p in (OLD / "model").rglob("*") if p.is_file()}
    new_model = {p.relative_to(NEW).as_posix(): sha(p.read_bytes())
                 for p in (NEW / "model").rglob("*") if p.is_file()}
    assert old_model == new_model
    owner_model = {r["path"]: r["sha256"] for r in owner["manifest"]["files"]
                   if r["path"].startswith("model/")}
    assert owner_model == new_model
    old_streams = (OLD / "+ac/Streams.m").read_text()
    new_streams = (NEW / "+ac/Streams.m").read_text()
    assert natural_source(old_streams) == natural_source(new_streams)
    helpers = ["+ac/Trace.m", "+ac/Recorder.m", "+ac/MacStream.m",
               "+ac/PhySampler.m", "+ac/writeJson.m"]
    for rel in helpers:
        assert (OLD / rel).read_bytes() == (NEW / rel).read_bytes(), rel
    proof = json.loads((NEW / "ref/accepted/reuse_proof.json").read_text())
    assert proof["current_streams_sha256"] == sha((NEW / "+ac/Streams.m").read_bytes())
    assert proof["previous_streams_sha256"] == sha((OLD / "+ac/Streams.m").read_bytes())
    for row in proof["accepted_files"]:
        assert sha((NEW / "ref/accepted" / row["path"]).read_bytes()) == row["sha256"]
    for row in proof["unchanged_natural_source_files"]:
        assert sha((NEW / row["path"]).read_bytes()) == row["sha256"]
    assert proof["accepted_runtime"] == owner["runtime"]
    report = {
        "schema": "csr-native-csv-repair-peer-review-v1", "status": "pass",
        "model_artifacts": len(new_model), "all_model_artifacts_unchanged": True,
        "all_model_hashes_match_returned_owner_provenance": True,
        "unchanged_natural_helpers": helpers,
        "streams_natural_path_text_unchanged": True,
        "approved_changed_regions": ["native constructor CSV imports", "native-only take method"],
        "accepted_files_hash_verified": len(proof["accepted_files"]),
        "accepted_runtime": proof["accepted_runtime"],
        "input_hashes": {rel: sha((NEW / rel).read_bytes()) for rel in
                         ["+ac/Fixture.m", "+ac/Streams.m", "+ac/nativeImportPreflight.m",
                          "run_autonomous_tests.m", "ref/accepted/reuse_proof.json"]},
        "new_matlab_runtime_execution_verified": False,
        "scope": "Static repair boundary and prior accepted evidence reuse; owner execution of repaired B remains pending",
    }
    out = Path(__file__).with_name("repair_boundary_review.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
