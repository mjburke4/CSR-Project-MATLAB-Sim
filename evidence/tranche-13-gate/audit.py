"""Independent read-only audit of T13 emitted native evidence."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "csr13"
REF = ROOT / "evidence/tranche-13-loss-reference"


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def audit():
    plan = json.loads((ROOT / "scenarios/loss/plan.json").read_text())
    events = rows(REF / "events.csv")
    transport = rows(REF / "transport.csv")
    offers = rows(ROOT / "scenarios/loss/offers.csv")
    results = []
    for case in plan["cases"]:
        ev = [r for r in events if r["case"] == case]
        tr = [r for r in transport if r["case"] == case]
        expected = {(int(r["source"]), int(r["app_id"])) for r in offers if r["case"] == case}
        assert [int(r["order"]) for r in ev] == list(range(1, len(ev) + 1))
        identity_counts = {}
        for kind in ("generate", "admit", "deliver"):
            counts = collections.Counter((int(r["app_source"]), int(r["app_id"])) for r in ev if r["event"] == kind)
            assert set(counts) == expected, (case, kind, "identities")
            assert all(n == 1 for n in counts.values()), (case, kind, "duplicate")
            identity_counts[kind] = sum(counts.values())
        due = {(int(r["source"]), int(r["app_id"])): int(r["due_ns"]) for r in offers if r["case"] == case}
        for row in ev:
            if row["event"] in ("generate", "admit", "deliver"):
                key = (int(row["app_source"]), int(row["app_id"]))
                assert int(row["time_ns"]) >= due[key], (case, "before generation")
                if row["event"] == "generate":
                    assert int(row["time_ns"]) == due[key]
        groups = collections.OrderedDict()
        for r in tr:
            groups.setdefault(int(r["group_id"]), []).append(r)
        assert list(groups) == list(range(1, len(groups) + 1))
        used_edges = set()
        for group in groups.values():
            first = group[0]
            for field in ("tx_id", "group_segments", "tx_time_ns", "arrival_ns", "sender", "receiver", "decision", "reason", "boundary_distance_ns"):
                assert len({r[field] for r in group}) == 1, (case, "split group", field)
            assert len(group) == int(first["group_segments"])
            edge = (int(first["sender"]), int(first["receiver"]))
            kinds = {r["kind"] for r in group}
            decision, reason = "pass", "none"
            if case == "data" and edge in {(4, 5), (5, 1)} and "DATA" in kinds and edge not in used_edges:
                decision, reason = "drop", "first_data"
                used_edges.add(edge)
            elif case == "ack" and edge in {(5, 4), (1, 5)} and kinds & {"ACK", "DACK"} and edge not in used_edges:
                decision, reason = "drop", "first_feedback"
                used_edges.add(edge)
            elif case == "out":
                time = int(first["tx_time_ns"])
                distance = min(abs(time - 8_000_000_000), abs(time - 9_500_000_000))
                assert distance > plan["loss_boundary_guard_ns"]
                assert distance == int(first["boundary_distance_ns"])
                if 8_000_000_000 <= time < 9_500_000_000:
                    decision, reason = "drop", "outage"
            assert (first["decision"], first["reason"]) == (decision, reason), (case, "policy")
        def event_key(row):
            return tuple(int(row[k]) for k in ("time_ns", "node", "peer", "app_source", "app_id", "hop_seq", "ack_bits", "dack_bits"))
        def transport_key(row, ingress):
            return (int(row["arrival_ns"] if ingress else row["tx_time_ns"]), int(row["receiver"] if ingress else row["sender"]), int(row["sender"] if ingress else row["receiver"]), *(int(row[k]) for k in ("app_source", "app_id", "hop_seq", "ack_bits", "dack_bits")))
        for event, decision, ingress in (("tx_start", None, False), ("ingress_before", "pass", True), ("ingress_after", "pass", True), ("loss", "drop", True)):
            observed = collections.Counter(event_key(r) for r in ev if r["event"] == event)
            expected_events = collections.Counter(transport_key(r, ingress) for r in tr if decision is None or r["decision"] == decision)
            assert observed == expected_events, (case, event, "transport conservation")
        finals = [r for r in ev if r["event"] == "final"]
        assert len(finals) == 3
        for row in ev:
            assert int(row["nwk_custody"]) == int(row["nsdp4"]) + int(row["nsdp5"])
            if row["event"] in ("checkpoint", "final"):
                assert int(row["hop_pending"]) == int(row["resend_queue"]) + int(row["dack_holds"])
                assert int(row["hop_pending"]) == int(row["neighbor_outstanding"])
        for row in finals:
            for field in ("hop_pending", "resend_queue", "nwk_waiting", "nwk_custody", "nsdp4", "nsdp5", "dack_holds", "ack_queue", "data_queue"):
                assert int(row[field]) == 0, (case, "final", field)
        source_activity = {}
        for source in (4, 5):
            admitted = [int(r["time_ns"]) for r in ev if r["event"] == "admit" and int(r["app_source"]) == source]
            late_admits = sum(t >= 20_000_000_000 for t in admitted)
            assert late_admits > 0
            blocked_held = [r for r in ev if r["event"] == "blocked" and int(r["node"]) == source and int(r["dack_holds"]) > 0]
            queued_held = [r for r in ev if int(r["node"]) == source and int(r["nwk_waiting"]) > 0 and int(r["dack_holds"]) > 0]
            source_activity[str(source)] = {"late_admissions_at_or_after_20s": late_admits, "last_admit_ns": max(admitted), "blocked_offers_with_dack_holds": len(blocked_held), "last_blocked_held_ns": max((int(r["time_ns"]) for r in blocked_held), default=None), "observations_with_queued_data_and_dack_holds": len(queued_held)}
        attempts = collections.Counter(tuple(r[k] for k in ("sender", "receiver", "app_source", "app_id", "hop_seq")) for r in tr if r["kind"] == "DATA")
        results.append({"case": case, "identity_counts": identity_counts, "events": len(ev), "transport_segments": len(tr), "recipient_groups": len(groups), "dropped_groups": sum(g[0]["decision"] == "drop" for g in groups.values()), "dropped_segments": sum(r["decision"] == "drop" for r in tr), "retransmitted_data_attempts": sum(n - 1 for n in attempts.values()), "source_activity": source_activity, "maximum_ack_bits": max(int(r["ack_bits"]) for r in tr), "final_queues_clear": True})
    return {"passed": True, "cases": results, "bindings": {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [REF / "events.csv", REF / "transport.csv", ROOT / "scenarios/loss/plan.json"]}}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
