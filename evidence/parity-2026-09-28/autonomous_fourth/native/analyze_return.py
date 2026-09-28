#!/usr/bin/env python3
"""Extract reproducible fourth-return evidence without running a network."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n")


native_log = ROOT / "autonomous/native_capture/run/run.log"
native_lines = native_log.read_text().splitlines()
native_selected = [
    {"line": n, "text": line}
    for n, line in enumerate(native_lines, 1)
    if "time_ns=12314891086 " in line
    or ("time_ns=12402000000 " in line and ("MAC 5" in line or "TX from node 5" in line))
]
(OUT / "native_causal_excerpt.txt").write_text(
    "\n".join(f"{r['line']}: {r['text']}" for r in native_selected) + "\n"
)

cases = {}
inputs = [native_log]
for case in ("C_timing", "D_inline_key"):
    path = ROOT / "autonomous_fourth/data" / case / "ordered_events.jsonl"
    divergence = path.with_name("first_divergence.json")
    inputs += [path, divergence]
    events = [json.loads(line) for line in path.open()]
    selected = [e for e in events if e["node"] == 5 and e["kind"] == "protocol" and
                (12314891085 <= round(e["time_s"] * 1e9) <= 12314891087 or
                 (e["time_s"] == 12.402 and e["details"]["event"] == "mac_state"))]
    (OUT / f"{case}_causal_excerpt.jsonl").write_text(
        "\n".join(json.dumps(e, separators=(",", ":")) for e in selected) + "\n"
    )
    sent = [e for e in events if e["node"] == 5 and e["kind"] == "protocol" and
            e["details"]["event"] == "neighbor_control_send"]
    tx = next(e for e in selected if e["time_s"] == 12.402)
    frame = tx["details"]["frame"]
    children = []
    for f in frame["Segments"]:
        control = f.get("Control", {})
        children.append({"kind": f["Kind"], "hop_sequence": f["Sequence"],
                         "destination": f["DestinationId"], "wire_bytes": f["WirePayloadBytes"],
                         "control_type": control.get("Type"),
                         "control_payload": control.get("Payload")})
    cases[case] = {
        "node5_neighbor_sends": [{"time_s": e["time_s"], "observation_order": e["observation_order"],
                                   **e["details"]["details"]} for e in sent],
        "mismatching_tx": {"time_s": tx["time_s"], "observation_order": tx["observation_order"],
                            "wire_bytes": frame["WirePayloadBytes"], "children": children},
    }
    assert len(children) == 3 and frame["WirePayloadBytes"] == 66
    assert [c["hop_sequence"] for c in children] == [1, 3, 3]
    assert children[2]["control_payload"]["Subtype"] == "discovery"
    assert not any(e["details"]["details"].get("Payload", {}).get("Subtype") == "overheard" for e in sent)

fixture = ROOT / "autonomous/native_capture/fixture/tx_signatures.csv"
inputs.append(fixture)
native_tx = [r for r in csv.DictReader(fixture.open()) if r["tx_id"] == "21474836483"]
write_json("native_expected_tx.json", native_tx)
write_json("returned_causal_summary.json", cases)

ranges = {
    "autonomous/native_env/csr/model/csr-nwk-layer.h": [(622, 667), (958, 975), (3835, 3865),
        (3937, 4002), (4199, 4282), (4358, 4375), (4453, 4482), (4672, 4686), (7336, 7350), (7881, 7948)],
    "autonomous/native_env/csr/model/csr-hop-layer.h": [(1856, 1930)],
    "autonomous/native_env/csr/model/csr-net-device.h": [(2402, 2410)],
    "autonomous_third/kit/autocase/model/+csr/+nwk/Neighbors.m": [(120, 175), (270, 317), (330, 361)],
    "autonomous_third/kit/autocase/model/+csr/+nwk/Layer.m": [(503, 529)],
}
with (OUT / "source_excerpts.txt").open("w") as out:
    for relative, sections in ranges.items():
        path = ROOT / relative
        inputs.append(path)
        lines = path.read_text().splitlines()
        out.write(f"\nFILE {relative}\nSHA256 {sha(path)}\n")
        for start, end in sections:
            out.write(f"LINES {start}-{end}\n")
            out.writelines(f"{n}: {lines[n-1]}\n" for n in range(start, end + 1))

probe = OUT / "check_ownership_probe.log"
inputs.append(probe)
probe_text = probe.read_text()
assert "ALL_COMPONENT_CASES_PASS" in probe_text
probe_types = {}
current = None
for line in probe_text.splitlines():
    if line.startswith("CASE_BEGIN "):
        current = line.split()[1]
        probe_types[current] = []
    if "Sending targeted ARL NeighborCheck" in line:
        probe_types[current].append(re.search(r"subtype=(\w+)", line)[1])
assert probe_types == {"overheard_only": ["Overheard", "Message"],
                       "discovery_active": ["Discovery", "Overheard"]}
build_identity = ROOT / "autonomous/native_env/build.json"
inputs.append(build_identity)
write_json("evidence_receipt.json", {
    "task": "seed132 node5 TX3 missing Overheard control, fourth owner return",
    "native_csr_pin": "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b",
    "native_engine_pin": "6b5cd24ea80713ce16d88575869aedd6f432bdae",
    "network_run": False,
    "production_or_fixture_edit": False,
    "component_probe_executed": True,
    "component_probe_uses_private_state": False,
    "component_probe_calls_simulator_run": False,
    "component_probe_actual_types": probe_types,
    "component_probe_scope": "Public NWK/HOP security and HELLO callbacks with unattached MAC; real authenticated key install and ACK; no PHY, channel, delivery, or network parity claim.",
    "sources": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in inputs],
    "probe_source_sha256": sha(OUT / "check_ownership_probe.cc"),
    "compile_command": json.loads((OUT / "compile_command.json").read_text()),
})
print("Extracted native/MATLAB causal evidence and receipt; both returned aggregates are exactly ACK1 + ACK3 + Discovery3 = 66 bytes.")
