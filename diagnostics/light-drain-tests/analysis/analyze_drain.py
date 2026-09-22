#!/usr/bin/env python3
"""Audit light-load/drain evidence, preserving missing/failed cases.

stdlib only. Latencies condition on unique delivered applications. Native
unreceived applications are unresolved, never inferred to be dropped/pending.
Cross-engine cohorts use scheduled flow/attempt identity, not packet sequence.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


DEFAULT_POLICY = {"max_blocked_fraction": .01, "max_waiting_queue_depth": 4,
                  "min_delivered_fraction": .95}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        yield from csv.DictReader(stream)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def quantile(values, p):
    if not values:
        return None
    values = sorted(values)
    x = (len(values) - 1) * p
    lo = math.floor(x)
    return values[lo] + (x - lo) * (values[min(lo + 1, len(values) - 1)] - values[lo])


def describe(values):
    return {"n": len(values), "mean_s": statistics.fmean(values) if values else None,
            "median_s": quantile(values, .5), "p95_s": quantile(values, .95),
            "max_s": max(values) if values else None}


def number(value, label):
    result = float(value)
    require(math.isfinite(result), "Non-finite " + label)
    return result


def detail_map(text):
    return dict(item.split("=", 1) for item in text.split(";") if "=" in item)


def verify_inventory(base):
    """Verify declared files only; do not assume a missing inventory is valid."""
    inventory = base / "files.json"
    if not inventory.is_file():
        return {"verified": False, "error": "Missing files.json", "count": 0}
    try:
        data = read_json(inventory)
        entries = data.items() if isinstance(data, dict) else ((v["path"], v["sha256"]) for v in data)
        count = 0
        for relative, expected in entries:
            path = (base / relative).resolve()
            path.relative_to(base.resolve())
            require(digest(path) == expected, "Hash mismatch: " + relative)
            count += 1
        return {"verified": True, "count": count, "inventory_sha256": digest(inventory)}
    except Exception as e:
        return {"verified": False, "error": str(e), "count": 0}


class QueueAudit:
    """NWK unsubmitted ownership, including drain-boundary and area accounting."""
    def __init__(self, start, stop, end):
        self.start, self.stop, self.end = start, stop, end
        self.last = start
        self.waiting = collections.defaultdict(collections.deque)
        self.depth = self.peak = self.enqueues = 0
        self.area = self.area_traffic = 0.0
        self.at_stop = None
        self.completed, self.released = [], []
        self.history = []

    def advance(self, t):
        require(self.start <= t <= self.end and t >= self.last, "Invalid queue event time")
        if t > self.stop and self.at_stop is None:
            self.at_stop = self.depth
        self.area += self.depth * (t - self.last)
        self.area_traffic += self.depth * max(0.0, min(t, self.stop) - min(self.last, self.stop))
        self.last = t

    def update(self, event, identity, t):
        self.advance(t)
        if event == "enqueue":
            self.waiting[identity].append(t)
            self.depth += 1
            self.enqueues += 1
            self.peak = max(self.peak, self.depth)
        elif event == "admit":
            require(bool(self.waiting[identity]), "Departure without NWK enqueue: " + identity)
            self.completed.append(t - self.waiting[identity].popleft())
            self.depth -= 1
        elif event == "release":
            if self.waiting[identity]:
                self.released.append(t - self.waiting[identity].popleft())
                self.depth -= 1
        self.history.append({"time_s": t, "event": event, "application_id": identity,
                             "waiting_depth_after": self.depth})

    def finish(self, reported=None):
        self.advance(self.end)
        if self.at_stop is None:
            self.at_stop = self.depth
        pending_ages = [self.end - t for queue in self.waiting.values() for t in queue]
        require(self.enqueues == len(self.completed) + len(self.released) + self.depth,
                "NWK ownership does not balance")
        require(math.isclose(self.area, sum(self.completed) + sum(self.released) + sum(pending_ages),
                             rel_tol=1e-10, abs_tol=1e-6), "NWK queue integral does not balance")
        if reported is not None:
            require(self.depth == reported, "Final NWK waiting count disagrees with exported statistic")
        return {"enqueued": self.enqueues, "admitted_to_hop": len(self.completed),
                "released_without_admit": len(self.released), "waiting_at_traffic_stop": self.at_stop,
                "waiting_at_end": self.depth, "peak_waiting": self.peak,
                "mean_waiting_during_traffic": self.area_traffic / (self.stop - self.start),
                "mean_waiting_during_drain": (self.area - self.area_traffic) / (self.end - self.stop),
                "completed_nwk_wait": describe(self.completed), "pending_nwk_wait_age": describe(pending_ages),
                "ownership_and_integral_conservation": True}


def app_record(identity, source, destination, generated):
    return {"id": identity, "source": int(source), "destination": int(destination),
            "generated_s": generated, "outcome": "pending", "terminal_s": None,
            "received_s": None, "latency_s": None, "events": [(generated, "pending")]}


def outcome_at(app, t):
    state = None
    for when, outcome in app["events"]:
        if when <= t:
            state = outcome
    return state


def summarize_apps(apps, attempts, stop, end, native=False):
    counts = collections.Counter(app["outcome"] for app in apps)
    cutoff = collections.Counter(outcome_at(app, stop) for app in apps)
    require(set(counts) <= {"delivered", "pending", "dropped", "unresolved"}, "Unknown application outcome")
    delivered = [app["latency_s"] for app in apps if app["outcome"] == "delivered"]
    require(attempts >= len(apps), "More admissions than attempts")
    ages = [end - app["generated_s"] for app in apps if app["outcome"] in ("pending", "unresolved")]
    terminal_times = [app["terminal_s"] for app in apps if app["outcome"] in ("delivered", "dropped")]
    unresolved = counts["unresolved"] if native else counts["pending"]
    return {"attempts": attempts, "admitted": len(apps), "blocked": attempts - len(apps),
            "blocked_fraction": (attempts - len(apps)) / attempts if attempts else None,
            "delivered": counts["delivered"], "explicit_dropped": None if native else counts["dropped"],
            "pending": None if native else counts["pending"], "native_unresolved": counts["unresolved"] if native else None,
            "outstanding_at_traffic_stop": cutoff["unresolved"] if native else cutoff["pending"],
            "unreceived_at_traffic_stop": sum(v for k, v in cutoff.items() if k != "delivered"),
            "delivered_during_drain": sum(app["received_s"] is not None and app["received_s"] > stop for app in apps),
            "delivery_fraction": counts["delivered"] / len(apps) if apps else None,
            "delivered_latency": describe(delivered), "censored_age_at_end": describe(ages),
            "all_terminal_by_end": unresolved == 0,
            "last_terminal_event_s": max(terminal_times) if terminal_times else None,
            "drain_time_to_last_terminal_s": max(0.0, max(terminal_times) - stop) if terminal_times and unresolved == 0 else None,
            "tail_sample_warning": len(delivered) < 20}


def admit_record(source, destination, flow, attempt, t, accepted, reason, identity, nsdp, queue):
    return {"source": int(source), "configured_destination": int(destination), "flow_index_zero_based": int(flow),
            "attempt_index": int(attempt), "time_s": t, "accepted": bool(accepted), "reason": reason,
            "application_id": identity if accepted else None, "nsdp_count": int(nsdp), "source_nwk_queue": int(queue),
            "cohort_key": f"{int(source)}:{int(destination)}:{int(flow)}:{int(attempt)}"}


def read_matlab(directory, case):
    apps, admissions, queues = {}, [], {}
    start, stop, end = (case[k] for k in ("traffic_start_s", "traffic_stop_s", "duration_s"))
    node_file = directory / "node_statistics.csv"
    if not node_file.exists():
        node_file = directory / "raw" / "nodes.csv"
    nodes = {int(r["Id"]): int(r["WaitingForHop"]) for r in rows(node_file)}
    for node in nodes:
        queues[node] = QueueAudit(start, stop, end)
    for r in rows(directory / "raw" / "protocol_trace.csv"):
        event, identity = r["Event"], r["PacketId"]
        t = number(r["TimeSeconds"], "trace time")
        require(0 <= t <= end, "Trace outside simulation bounds")
        if event == "app_generate":
            require(identity not in apps, "Duplicate application generation")
            apps[identity] = app_record(identity, r["NodeId"], r["PeerId"], t)
        elif event in ("app_receive", "app_drop", "relay_accept"):
            require(identity in apps, "Application outcome without generation")
            app = apps[identity]
            require(t >= app["generated_s"], "Negative application latency")
            if app["outcome"] == "delivered":
                require(event != "app_drop", "Drop following delivery")
                continue
            state = {"app_receive": "delivered", "app_drop": "dropped", "relay_accept": "pending"}[event]
            app["outcome"] = state
            app["terminal_s"] = t if state in ("delivered", "dropped") else None
            app["events"].append((t, state))
            if state == "delivered":
                app.update(received_s=t, latency_s=t - app["generated_s"])
        if int(r["ApplicationBytes"]) > 0 and event in ("network_enqueue", "hop_admit", "network_custody_release"):
            node = int(r["NodeId"])
            require(node in queues, "Unknown queue node")
            queues[node].update({"network_enqueue": "enqueue", "hop_admit": "admit",
                                 "network_custody_release": "release"}[event], identity, t)
    exported = list(rows(directory / "applications.csv"))
    require(len(exported) == len(apps), "Application CSV count disagrees with trace")
    require({r["PacketId"] for r in exported} == set(apps), "Application CSV identity set disagrees with trace")
    for r in exported:
        require(r["PacketId"] in apps, "Unknown application in applications.csv")
        app = apps[r["PacketId"]]
        require(int(r["SourceId"]) == app["source"] and int(r["DestinationId"]) == app["destination"],
                "Application CSV source/destination disagrees with trace")
        require(math.isclose(float(r["GeneratedSeconds"]), app["generated_s"], rel_tol=0, abs_tol=1e-8),
                "Application CSV generation time disagrees with trace")
        require(r["Outcome"] == app["outcome"], "Application CSV outcome disagrees with trace")
        if app["outcome"] == "delivered":
            require(math.isclose(float(r["LatencySeconds"]), app["latency_s"], abs_tol=1e-8), "Exported latency disagrees with trace")
    for r in rows(directory / "raw" / "application_admission_trace.csv"):
        admissions.append(admit_record(r["SourceId"], r["ConfiguredDestinationId"], int(r["FlowIndex"]) - 1,
                                       r["AttemptIndex"], float(r["TimeSeconds"]), r["Accepted"] in ("1", "true"),
                                       r["Reason"], r["PacketId"], r["NsdpCount"], r["NwkQueueSize"]))
    stats = list(rows(directory / "raw" / "application_admission_statistics.csv"))
    for r in stats:
        found = [a for a in admissions if a["flow_index_zero_based"] == int(r["FlowIndex"]) - 1]
        require(len(found) == int(r["Attempts"]), "Admission attempts disagree with counters")
        require(sum(a["accepted"] for a in found) == int(r["Admitted"]), "Admitted counter mismatch")
        require(int(r["Attempts"]) == int(r["Admitted"]) + sum(int(v) for k, v in r.items() if k.startswith("Blocked")),
                "Admission counter partition mismatch")
    return apps, admissions, {node: q.finish(nodes[node]) for node, q in queues.items()}, queues


def read_native(directory, case):
    apps, admissions, queues, last_stats = {}, [], {}, {}
    forwards, hop = collections.Counter(), collections.Counter()
    start, stop, end = (case[k] for k in ("traffic_start_s", "traffic_stop_s", "duration_s"))
    for r in rows(directory / "ns3-trace.csv"):
        event = r["event"]
        t = number(r["time_s"], "native event time")
        require(0 <= t <= end, "Native event outside simulation bounds")
        identity = ":".join((r["src"], r["dst"], r["sequence"]))
        if event == "app_send":
            require(identity not in apps, "Duplicate native application generation")
            app = app_record(identity, r["src"], r["dst"], t)
            app.update(outcome="unresolved", events=[(t, "unresolved")])
            apps[identity] = app
        elif event == "nwk_delivery":
            require(identity in apps, "Native delivery without generation")
            app = apps[identity]
            require(t >= app["generated_s"], "Negative native latency")
            if app["outcome"] != "delivered":
                app.update(outcome="delivered", terminal_s=t, received_s=t, latency_s=t - app["generated_s"])
                app["events"].append((t, "delivered"))
        elif event == "app_admission":
            detail = detail_map(r["detail"])
            admissions.append(admit_record(r["src"], detail["configured_destination"], detail["flow_index"],
                                           detail["attempt_index"], t, r["success"] == "1", r["reason"],
                                           identity, detail["nsdp_count"], detail["nwk_queue"]))
        if not r["node"]:
            continue
        node = int(r["node"])
        if event == "statistic_sample" and r["statistic"] == "NWK.Network Queue Size (packets)":
            last_stats[node] = int(float(r["value"]))
            queues.setdefault(node, QueueAudit(start, stop, end))
        if r["packet_type"] != "data":
            continue
        if event == "hop_admission" and r["success"] == "1":
            hop[(node, identity, t)] += 1
        if event in ("nwk_enqueue", "nwk_forward"):
            q = queues.setdefault(node, QueueAudit(start, stop, end))
            q.update("enqueue" if event == "nwk_enqueue" else "admit", identity, t)
            require(last_stats.get(node) == q.depth, "Native queue statistic disagrees after " + event)
            if event == "nwk_forward":
                forwards[(node, identity, t)] += 1
    require(forwards == hop, "Native NWK forwarding does not match successful same-time HOP admission")
    stats = list(rows(directory / "app-admission-diagnostics.csv"))
    for r in stats:
        found = [a for a in admissions if a["flow_index_zero_based"] == int(r["flow_index"])]
        require(len(found) == int(r["attempts"]), "Native admission attempts disagree with counters")
        require(sum(a["accepted"] for a in found) == int(r["admitted"]), "Native admitted counter mismatch")
        require(int(r["attempts"]) == int(r["admitted"]) + sum(int(v) for k, v in r.items() if k.startswith("blocked_")),
                "Native admission partition mismatch")
    return apps, admissions, {node: q.finish(last_stats.get(node)) for node, q in queues.items()}, queues


def validate_admissions(apps, admissions, case):
    start, stop, end = (case[k] for k in ("traffic_start_s", "traffic_stop_s", "duration_s"))
    require(0 <= start < stop < end, "Plan requires a positive traffic window and drain")
    expected = int(case["expected_attempts"])
    require(len(admissions) == expected, f"Expected {expected} attempts, found {len(admissions)}")
    starts = {int(item["source"]): float(item["start_s"]) for item in case.get("source_starts", [])}
    keys, accepted, by_flow = set(), set(), collections.defaultdict(list)
    for a in admissions:
        require(a["cohort_key"] not in keys, "Duplicate flow/attempt identity")
        keys.add(a["cohort_key"])
        require(start <= a["time_s"] < stop, "Traffic attempt outside [start, stop)")
        by_flow[a["flow_index_zero_based"]].append(a)
        if a["accepted"]:
            identity = a["application_id"]
            require(identity in apps and identity not in accepted, "Admission-to-generation identity mismatch")
            accepted.add(identity)
            app = apps[identity]
            require(math.isclose(app["generated_s"], a["time_s"], abs_tol=1e-8), "Generation differs from admitted attempt time")
            require(app["source"] == a["source"], "Admission source mismatch")
            app["cohort_key"] = a["cohort_key"]
    require(accepted == set(apps), "Generated applications do not match admitted attempts")
    if starts:
        require({a["source"] for a in admissions} == set(starts), "Attempt sources differ from plan")
    for flow, attempts in by_flow.items():
        attempts.sort(key=lambda a: a["attempt_index"])
        require([a["attempt_index"] for a in attempts] == list(range(1, len(attempts) + 1)), "Non-contiguous attempt sequence")
        flow_start = starts.get(attempts[0]["source"], start)
        nominal_count = math.ceil((stop - flow_start) / case["interval_s"] - 1e-12)
        require(len(attempts) == nominal_count, "Per-flow attempt count differs from finite traffic schedule")
        for a in attempts:
            require(a["source"] == attempts[0]["source"], "Source changes within flow")
            nominal = flow_start + (a["attempt_index"] - 1) * case["interval_s"]
            require(math.isclose(a["time_s"], nominal, rel_tol=0, abs_tol=1e-7), "Attempt schedule differs from plan")
    return True


def qualify(summary, sources, queues, policy):
    def gate(s):
        return {"negligible_blocking": s["blocked_fraction"] is not None and s["blocked_fraction"] <= policy["max_blocked_fraction"],
                "delivery_fraction": s["delivery_fraction"] is not None and s["delivery_fraction"] >= policy["min_delivered_fraction"],
                "all_terminal": s["all_terminal_by_end"]}
    source_gates = {str(s["source"]): gate(s) for s in sources}
    criteria = gate(summary)
    criteria.update(each_source_passes=all(all(v.values()) for v in source_gates.values()),
                    bounded_waiting_queues=all(q["peak_waiting"] <= policy["max_waiting_queue_depth"] for q in queues.values()),
                    no_waiting_at_end=all(q["waiting_at_end"] == 0 for q in queues.values()))
    return {"qualified": all(criteria.values()), "criteria": criteria, "per_source": source_gates,
            "policy": policy, "parity_claim": False}


def write_csv(path, records):
    if not records:
        Path(path).write_text("")
        return
    fields = list(dict.fromkeys(k for r in records for k in r))
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in records)


def find_root(path):
    path = path.resolve()
    if (path / "plan.json").exists():
        return path
    candidates = [p.parent for p in path.glob("*/plan.json")]
    require(len(candidates) == 1, "Expected evidence root containing plan.json")
    return candidates[0]


def analyze(plan, roots, output):
    output.mkdir(parents=True, exist_ok=False)
    policy = {**DEFAULT_POLICY, **plan.get("qualification", {})}
    result = {"schema": "csr-light-drain-analysis-v1", "status": "review-required", "parity_established": False,
              "quantile_method": "linear interpolation at (n-1)*p", "snapshot_semantics": "after events at t <= traffic_stop_s",
              "native_unresolved_is_not_pending_or_explicit_drop": True, "qualification_policy": policy,
              "engines": {}, "cases": [], "sources": [], "queues": [], "paired_sources": [],
              "limitations": ["Delivered latency distributions omit unresolved applications and explicit drops.",
                              "An empty NWK waiting queue does not imply MAC/HOP controls have drained.",
                              "Three seeds and sparse per-source deliveries do not establish statistical equivalence.",
                              "A common-attempt delivered cohort is selected by successful admission and delivery in both models.",
                              "A qualified run is an uncongested diagnostic under declared thresholds, not a production parity pass."]}
    ledgers = {}
    for engine, requested_root in roots.items():
        try:
            root = find_root(requested_root)
            integrity = verify_inventory(root)
            same_plan = read_json(root / "plan.json") == plan
            result["engines"][engine] = {"root": str(root), "inventory": integrity, "plan_matches": same_plan}
        except Exception as e:
            result["engines"][engine] = {"error": str(e)}
            result["status"] = "incomplete-review-required"
            continue
        for original_case in plan["cases"]:
            case = {"source_starts": plan.get("source_starts", []), **original_case}
            record = {"engine": engine, "case": case["id"], "seed": case["seed"],
                      "traffic_start_s": case["traffic_start_s"], "traffic_stop_s": case["traffic_stop_s"],
                      "duration_s": case["duration_s"], "integrity_passed": False}
            try:
                require(integrity["verified"], integrity.get("error", "Unverified inventory"))
                require(same_plan, "Evidence plan differs from requested plan")
                directory = root / case["id"]
                status = read_json(directory / "status.json")
                record["run_status"] = status.get("status")
                require(status.get("status") == "completed", "Run is not complete")
                apps, admissions, queues, queue_objects = (read_native if engine == "native" else read_matlab)(directory, case)
                validate_admissions(apps, admissions, case)
                summary = summarize_apps(list(apps.values()), len(admissions), case["traffic_stop_s"], case["duration_s"], engine == "native")
                sources = []
                for source in sorted({a["source"] for a in admissions}):
                    attempts = [a for a in admissions if a["source"] == source]
                    s = summarize_apps([a for a in apps.values() if a["source"] == source], len(attempts), case["traffic_stop_s"], case["duration_s"], engine == "native")
                    s.update(source=source, blocked_reasons=dict(collections.Counter(a["reason"] for a in attempts if not a["accepted"])))
                    sources.append(s)
                    result["sources"].append({"engine": engine, "case": case["id"], "seed": case["seed"], **s})
                for node, q in sorted(queues.items()):
                    result["queues"].append({"engine": engine, "case": case["id"], "node": node, **q})
                record.update(summary, integrity_passed=True, qualification=qualify(summary, sources, queues, policy))
                ledgers[(engine, case["id"])] = apps
                prefix = f"{engine}-{case['id']}"
                write_json(output / (prefix + "-applications.json"), list(apps.values()))
                write_csv(output / (prefix + "-admissions.csv"), admissions)
                write_csv(output / (prefix + "-queue-history.csv"), [{"node": node, **r} for node, q in sorted(queue_objects.items()) for r in q.history])
            except Exception as e:
                record.update(error=str(e))
                result["status"] = "incomplete-review-required"
            result["cases"].append(record)
    for case in plan["cases"]:
        if not all((e, case["id"]) in ledgers for e in ("matlab", "native")):
            continue
        m = {a["cohort_key"]: a for a in ledgers[("matlab", case["id"])].values()}
        n = {a["cohort_key"]: a for a in ledgers[("native", case["id"])].values()}
        common = set(m) & set(n)
        for source in sorted({a["source"] for a in list(m.values()) + list(n.values())}):
            keys = [k for k in common if m[k]["source"] == source]
            received = [k for k in keys if m[k]["outcome"] == n[k]["outcome"] == "delivered"]
            result["paired_sources"].append({"case": case["id"], "seed": case["seed"], "source": source,
                                              "common_admitted_attempts": len(keys), "delivered_in_both": len(received),
                                              "matlab_common_delivered_latency": describe([m[k]["latency_s"] for k in received]),
                                              "native_common_delivered_latency": describe([n[k]["latency_s"] for k in received]),
                                              "matlab_minus_native_latency": describe([m[k]["latency_s"] - n[k]["latency_s"] for k in received]),
                                              "tail_sample_warning": len(received) < 20})
    write_json(output / "summary.json", result)
    for filename, key in (("case-summary.csv", "cases"), ("source-summary.csv", "sources"),
                          ("queue-summary.csv", "queues"), ("paired-source-comparison.csv", "paired_sources")):
        write_csv(output / filename, result[key])
    write_json(output / "files.json", {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != "files.json"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--matlab", type=Path)
    parser.add_argument("--native", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = {engine: path for engine, path in (("matlab", args.matlab), ("native", args.native)) if path}
    parser.error("Provide --matlab and/or --native") if not roots else None
    result = analyze(read_json(args.plan), roots, args.output)
    print(json.dumps({"status": result["status"], "cases": len(result["cases"]),
                      "integrity_passed": sum(c["integrity_passed"] for c in result["cases"]),
                      "qualified": sum(c.get("qualification", {}).get("qualified", False) for c in result["cases"])}))
    return 0 if result["status"] == "review-required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
