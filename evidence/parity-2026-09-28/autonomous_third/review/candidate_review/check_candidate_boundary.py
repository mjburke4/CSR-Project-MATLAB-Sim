#!/usr/bin/env python3
"""Independent static source-boundary review; not a MATLAB execution test."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / "autonomous_third/kit/autocase"
OLD = ROOT / "autonomous_return/kit/autocase"
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in root.rglob("*") if p.is_file()}


def main():
    model = tree(KIT / "model")
    assert model == tree(OLD / "model") and len(model) == 99
    native = tree(KIT / "ref/native")
    assert native == tree(OLD / "ref/native")
    manifest = json.loads((KIT / "candidate_transform.json").read_text())
    targets = []
    for item in manifest["transforms"]:
        source = KIT / item["source"]
        target = KIT / item["target"]
        assert digest(source) == item["source_sha256"]
        assert digest(target) == item["target_sha256"]
        reversed_text = target.read_text()
        for edit in reversed(item["edits"]):
            assert reversed_text.count(edit["new"]) == 1
            reversed_text = reversed_text.replace(edit["new"], edit["old"])
        assert reversed_text == source.read_text()
        targets.append(item["target"])
    assert targets == ["+ac/InlineKeyNwk.m", "+ac/InlineKeySimulation.m"]
    nwk = (KIT / "+ac/InlineKeyNwk.m").read_text()
    begin = nwk.index("            if scheduleWake && strcmp(kind,'KEY_REQUEST') && ~reliable\n")
    end = nwk.index("            if scheduleWake, obj.wake(); end", begin)
    branch = nwk[begin:end]
    assert "obj.pump(" not in branch and "pumpControls" not in branch and "SendData" not in branch
    assert branch.count("obj.controlPosition(controlId)") == 2
    assert branch.index(".Submitted=true;") < branch.index("obj.Callbacks.SendControl(")
    assert "if ~submitted && position>0, obj.Controls{position}.Submitted=false; end" in branch
    assert "if submitted, return; end" in branch
    assert nwk.index("accepted=numel(obj.Controls)<obj.Config.ControlQueueLimit;") < begin
    assert nwk.index("obj.Callbacks.CancelControl(peers(1),kind);") < begin
    new_runner = (KIT / "run_autonomous_tests.m").read_text()
    old_runner = (OLD / "run_autonomous_tests.m").read_text()
    def reuse(text):
        start = text.index("function [reused,item,details]=reuseNatural(")
        return text[start:text.index("function item=runCase(", start)]
    assert reuse(new_runner) == reuse(old_runner)
    natural_helpers = ["+ac/Streams.m", "+ac/Trace.m", "+ac/Recorder.m", "+ac/MacStream.m", "+ac/PhySampler.m"]
    for path in natural_helpers:
        assert digest(KIT / path) == digest(OLD / path)
    c_index = new_runner.index("second=runCase(root,out,config,'C_timing','native');")
    d_index = new_runner.index("third=runCase(root,out,config,'D_inline_key','native');")
    assert c_index < d_index
    between = new_runner[c_index:d_index]
    assert "if second" not in between and "second.completed" not in between
    assert "if strcmp(mode,'native'), timing=csr.sim.TransportTiming('nanoseconds',200000); end" in new_runner
    paths = targets + ["+ac/KeyProbe.m", "+ac/keyRequestPreflight.m", "run_autonomous_tests.m", "candidate_transform.json"]
    report = {
        "schema": "csr-inline-key-candidate-peer-review-v1",
        "status": "static_boundary_pass",
        "model_artifacts_unchanged": len(model),
        "native_reference_files_unchanged": len(native),
        "candidate_sources_reverse_to_exact_originals": targets,
        "inline_branch_scope": "Newly appended no-ACK KEY_REQUEST with scheduleWake only; after unchanged replacement/capacity checks",
        "general_queue_pumps_added": False,
        "submitted_marked_before_callback": True,
        "owner_id_refound_after_callback": True,
        "rejected_send_retains_original_wake_fallback": True,
        "accepted_A_reuse_function_unchanged": True,
        "natural_helpers_unchanged": natural_helpers,
        "D_not_conditioned_on_C_completion": True,
        "C_and_D_use_same_existing_nanosecond_callback_option": True,
        "public_api_preflight_cases": 7,
        "matlab_preflight_executed": False,
        "C_D_network_runs_executed": False,
        "input_hashes": {path: digest(KIT / path) for path in paths},
    }
    (OUT / "candidate_boundary_review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
