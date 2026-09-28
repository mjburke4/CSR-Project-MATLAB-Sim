#!/usr/bin/env python3
"""Independently verify the final eight candidate transformations and scope."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent
kit = root / "autonomous_fourth/kit/autocase"
prior = root / "autonomous_third/kit/autocase"
manifest = json.loads((kit / "candidate_transform.json").read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checked = []
assert len(manifest["transforms"]) == 8
for t in manifest["transforms"]:
    source, target = kit / t["source"], kit / t["target"]
    assert sha(source) == t["source_sha256"]
    assert sha(target) == t["target_sha256"]
    generated = source.read_bytes()
    for edit in t["edits"]:
        old, new = edit["old"].encode(), edit["new"].encode()
        assert generated.count(old) == 1, (t["target"], edit["old"])
        generated = generated.replace(old, new, 1)
    assert generated == target.read_bytes(), t["target"]
    recovered = target.read_bytes()
    for edit in reversed(t["edits"]):
        old, new = edit["old"].encode(), edit["new"].encode()
        assert recovered.count(new) == 1
        recovered = recovered.replace(new, old, 1)
    assert recovered == source.read_bytes()
    checked.append({"target": t["target"], "sha256": sha(target),
                    "edit_count": len(t["edits"]), "forward_and_reverse_exact": True})

e = next(t for t in manifest["transforms"] if t["target"] == "+ac/CheckGateNeighbors.m")
assert len(e["edits"]) == 3
assert e["edits"][-1] == {
    "old": "if ~entry.CheckActive && (~entry.OverheardValid || now>=deadline)",
    "new": "if ~entry.OverheardValid || now>=deadline"}
f = next(t for t in manifest["transforms"] if t["target"] == "+ac/MessageFlagNeighbors.m")
assert len(f["edits"]) == 3
assert f["edits"][-1]["new"] == "entry=obj.Peers(peer);\n            if strcmp(subtype,'message')\n                entry.CheckActive=true; obj.Peers(peer)=entry;\n            end"
for name in ("CheckGateNeighbors", "MessageFlagNeighbors"):
    assert "elseif ~entry.CheckActive\n                obj.scheduleRetryAt(peer,deadline);" in (kit / "+ac" / f"{name}.m").read_text()

baseline = [p for p in (kit / "model").rglob("*") if p.is_file()]
for path in baseline:
    assert (prior / path.relative_to(kit)).is_file()
    assert sha(path) == sha(prior / path.relative_to(kit)), path

runner = (kit / "run_autonomous_tests.m").read_text()
natural_gate = runner.index("if first.completed && first.natural_prefix_passed")
e_call = runner.index("second=runCase(root,out,config,'E_check_gate','native');")
f_call = runner.index("third=runCase(root,out,config,'F_message_flag','native');")
assert natural_gate < e_call < f_call
between = runner[e_call:f_call]
assert "if " not in "\n".join(line for line in between.splitlines() if not line.lstrip().startswith("%"))
assert "elseif strcmp(name,'F_message_flag')" in runner
assert "timing=csr.sim.TransportTiming('nanoseconds',200000)" in runner
assert "simulation=csr.sim.NetworkSimulation(config,observer,timing,options)" in runner

receipt = {
    "scope_review": "pass",
    "matlab_executed_by_reviewer": False,
    "candidate_transform_sha256": sha(kit / "candidate_transform.json"),
    "runner_sha256": sha(kit / "run_autonomous_tests.m"),
    "transforms": checked,
    "unchanged_baseline_model_files": len(baseline),
    "natural_gate_precedes_E_and_F": True,
    "E_diagnostic_stop_does_not_conditionally_skip_F": True,
    "E_behavioral_delta": "Only remove active-proof exclusion from Overheard send eligibility",
    "F_behavioral_delta_from_E": "Only set CheckActive for Message, retain existing clears and independent DiscoveryCheckActive",
    "preserved": ["Overheard validity/timestamp/exponential delay", "Original not-due retry elseif", "Discovery-active Message suppression",
                  "NeighborCheck completion/failure/reset paths", "Distinct control owners", "Generic pump/HOP/MAC/PHY implementation"],
    "limits": ["MATLAB E/F runtime remains owner-side", "Baseline not-due retry rescheduling is not native timer fidelity; F changes flag state and can change reachability of that existing branch",
               "Existing inline KEY_REQUEST failed-admission fallback remains inherited and not fully validated against native outside motivating empty-queue successful-admission case",
               "No full network or performance parity established"]
}
(out / "candidate_scope_review.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(f"Eight candidate transforms exact in both directions; {len(baseline)} baseline model files unchanged; E/F scope and runner gates passed.")
