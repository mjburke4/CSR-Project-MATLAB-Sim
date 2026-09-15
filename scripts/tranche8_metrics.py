#!/usr/bin/env python3
"""Reconstruct descriptive Tranche 8 metrics without inventing missing state.

Packet-weighted latency and the mean of populated bucket means are deliberately
separate. ns-3 unmatched sends are not classified as retry drops or pending work.
These helpers consume verified evidence; source/inventory validation belongs to
analyze_tranche8_return.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import math
from pathlib import Path
import statistics

import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import compare_benchmark_aggregates as compare

require, integer, finite = sweep.require, sweep.integer, sweep.finite


def csv_rows(path, fields=()):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames))
                and set(fields) <= set(reader.fieldnames), f"Missing/duplicate CSV columns: {path}")
        for row in reader:
            require(None not in row and None not in row.values(), f"Malformed CSV row: {path}")
            yield row


def optional_number(value, label):
    """Missing remains None, never zero; nonfinite populated values are invalid."""
    if value is None or (isinstance(value, str) and value.lower() in ("", "nan")):
        return None
    return finite(value, label)


def bucket_index(when, duration, width):
    require(0 <= when < duration, "Application event outside strict observation window")
    quotient = when/width
    if abs(quotient-round(quotient)) <= 1e-12:
        quotient = round(quotient)
    index = math.floor(quotient)
    require(0 <= index < round(duration/width), "Application bucket outside window")
    return index


def application_summary(sent, delivered, case, *, simulator, attempts,
                        dropped=None, pending=None, drop_reasons=None):
    """sent maps identity -> (time, source, destination, common network bytes).

    delivered preserves event multiplicity, each (identity, receive time, bytes).
    Duplicate delivery events remain explicit and contribute to observed traffic
    and latency exactly as the upstream aggregate does.
    """
    duration, width = finite(case["duration_s"], "duration"), finite(case["bucket_width_s"], "width")
    require(duration > 0 and width > 0 and abs(duration/width-round(duration/width)) <= 1e-10,
            "Invalid application observation window")
    flows, buckets, received_ids = {}, defaultdict(list), set()
    received_bytes, delays, duplicates = 0, [], 0
    for identity, (when, source, destination, size) in sent.items():
        bucket_index(when, duration, width)
        require(integer(size, "network bytes") > 0, "Nonpositive application network bytes")
        flow = flows.setdefault((source, destination), {"source": source, "destination": destination,
                "admitted": 0, "delivered": 0, "delivered_unique": 0, "delay_sum_s": 0.0,
                "delay_samples": 0})
        flow["admitted"] += 1
    for identity, when, size in delivered:
        require(identity in sent, "Delivery has no matching generated application")
        generation, source, destination, sent_size = sent[identity]
        require(size == sent_size and when >= generation, "Delivery time/size mismatch")
        index = bucket_index(when, duration, width)
        delay = when-generation
        delays.append(delay)
        buckets[index].append(delay)
        received_bytes += size
        flow = flows[source, destination]
        flow["delivered"] += 1
        flow["delay_sum_s"] += delay
        flow["delay_samples"] += 1
        if identity in received_ids:
            duplicates += 1
        else:
            flow["delivered_unique"] += 1
            received_ids.add(identity)
    for flow in flows.values():
        flow["mean_packet_latency_s"] = (flow["delay_sum_s"]/flow["delay_samples"]
                                            if flow["delay_samples"] else None)
        flow["unmatched_sends"] = flow["admitted"]-flow["delivered_unique"]
    means = [math.fsum(values)/len(values) for values in buckets.values()]
    attempts = integer(attempts, "attempts")
    require(attempts >= len(sent), "Admitted count exceeds attempts")
    if simulator == "matlab":
        require(integer(dropped, "dropped") + integer(pending, "pending") + len(received_ids) == len(sent),
                "MATLAB terminal application accounting mismatch")
    return {"simulator": simulator, "case_id": case["case_id"], "base_case_id": case["base_case_id"],
            "seed": integer(case["seed"], "seed"), "duration_s": duration, "attempts": attempts,
            "admitted": len(sent), "admission_blocked": attempts-len(sent), "delivered": len(delays),
            "delivered_unique": len(received_ids), "duplicate_delivery_events": duplicates,
            "unmatched_sends": len(sent)-len(received_ids), "explicit_drops": dropped, "pending": pending,
            "drop_reasons": drop_reasons, "network_bytes_sent": sum(row[3] for row in sent.values()),
            "network_bytes_received": received_bytes, "delay_samples": len(delays),
            "delay_sum_s": math.fsum(delays), "mean_packet_latency_s": statistics.fmean(delays) if delays else None,
            "max_packet_latency_s": max(delays) if delays else None,
            "populated_delay_buckets": len(means), "bucket_latency_mean_sum_s": math.fsum(means),
            "mean_populated_bucket_latency_s": statistics.fmean(means) if means else None,
            "received_packet_rate_over_full_window": len(delays)/duration,
            "flows": [flows[key] for key in sorted(flows)]}


def verify_aggregates(path, sent, delivered, case):
    """Reconstruct all eight core series; source-only extra statistics remain excluded."""
    duration, width = float(case["duration_s"]), float(case["bucket_width_s"])
    count = round(duration/width)
    buckets = [[0, 0, 0, 0, 0.0] for _ in range(count)]
    for when, _, _, size in sent.values():
        bucket = buckets[bucket_index(when, duration, width)]
        bucket[0] += 1
        bucket[1] += size*8
    for identity, when, size in delivered:
        bucket = buckets[bucket_index(when, duration, width)]
        bucket[2] += 1
        bucket[3] += size*8
        bucket[4] += when-sent[identity][0]
    names = list(compare.CORE_SERIES)
    observed = set()
    for row in csv_rows(path, ("statistic", "time_s", "value")):
        if row["statistic"] not in names:
            continue
        index = round(finite(row["time_s"], "bucket end")/width)-1
        key = (row["statistic"], index)
        require(0 <= index < count and key not in observed
                and abs(finite(row["time_s"], "bucket end")-(index+1)*width) <= 1e-8,
                "Duplicate/off-grid aggregate bucket")
        observed.add(key)
        ns, bs, nr, br, delay = buckets[index]
        expected = [ns/width, bs/width, bs/ns if ns else None,
                    nr/width, nr, br/width, br, delay/nr if nr else None][names.index(row["statistic"])]
        value = optional_number(row["value"], "aggregate value")
        require((expected is None and value is None) or
                (expected is not None and value is not None
                 and math.isclose(expected, value, rel_tol=2e-12, abs_tol=1e-8)),
                "Aggregate value disagrees with application event reconstruction")
    require(len(observed) == 8*count, "Aggregate core grid is incomplete")


def matlab_applications(directory, case):
    sent, delivered, drops, pending = {}, [], Counter(), 0
    for row in csv_rows(Path(directory)/"analysis/applications.csv",
                        ("PacketId", "GeneratedSeconds", "SourceId", "DestinationId", "ApplicationBytes", "Outcome")):
        identity = integer(row["PacketId"], "packet identity")
        require(identity not in sent, "Duplicate MATLAB application identity")
        sent[identity] = (finite(row["GeneratedSeconds"], "generation"), integer(row["SourceId"], "source"),
                          integer(row["DestinationId"], "destination"), integer(row["ApplicationBytes"], "payload")+7)
        if row["Outcome"] == "delivered":
            delivered.append((identity, finite(row["ReceivedSeconds"], "received"), sent[identity][3]))
        elif row["Outcome"] == "dropped":
            require(row.get("DropReason"), "Dropped application has no reason")
            drops[row["DropReason"]] += 1
        else:
            require(row["Outcome"] == "pending", "Unknown MATLAB application outcome")
            pending += 1
    admissions = list(csv_rows(Path(directory)/"raw/application_admission_statistics.csv", ("Attempts",)))
    attempts = sum(integer(row["Attempts"], "attempts") for row in admissions)
    return application_summary(sent, delivered, case, simulator="matlab", attempts=attempts,
                               dropped=sum(drops.values()), pending=pending, drop_reasons=dict(drops))


def ns3_applications(directory, case):
    directory = Path(directory)
    sent, delivered, event_ids = {}, [], set()
    for row in csv_rows(directory/"ns3-trace.csv.gz", ("event_index", "time_s", "event", "src", "dst", "sequence", "size_bytes")):
        if row["event"] not in ("app_send", "nwk_delivery"):
            continue
        event = integer(row["event_index"], "event index")
        require(event not in event_ids, "Duplicate ns-3 application event index")
        event_ids.add(event)
        identity = (integer(row["src"], "source"), integer(row["dst"], "destination"),
                    integer(row["sequence"], "sequence"))
        when, size = finite(row["time_s"], "application time"), integer(row["size_bytes"], "network bytes")
        if row["event"] == "app_send":
            require(identity not in sent, "Duplicate ns-3 generated identity")
            sent[identity] = (when, identity[0], identity[1], size)
        else:
            require(identity in sent, "ns-3 delivery precedes matching generation")
            delivered.append((identity, when, size))
    rows = list(csv_rows(directory/"app-admission-diagnostics.csv", ("source", "attempts", "admitted")))
    require(len({row["source"] for row in rows}) == len(rows), "Duplicate ns-3 flow source")
    for row in rows:
        require(sum(identity[0] == integer(row["source"], "source") for identity in sent)
                == integer(row["admitted"], "admitted"), "ns-3 per-flow admitted count mismatch")
        blocked = sum(integer(value, name) for name, value in row.items() if name.startswith("blocked_"))
        require(integer(row["attempts"], "attempts") == integer(row["admitted"], "admitted")+blocked,
                "ns-3 attempt partition mismatch")
    require(sum(integer(row["admitted"], "admitted") for row in rows) == len(sent),
            "ns-3 admission diagnostics omit generated flow")
    verify_aggregates(directory/"ns3-aggregates.csv", sent, delivered, case)
    return application_summary(sent, delivered, case, simulator="ns3",
                               attempts=sum(integer(row["attempts"], "attempts") for row in rows))


def descriptive(values):
    require(all(value is not None for value in values), "Missing observation cannot enter numeric descriptive series")
    return {"count": len(values), "minimum": min(values) if values else None,
            "maximum": max(values) if values else None, "mean": statistics.fmean(values) if values else None,
            "sample_standard_deviation": statistics.stdev(values) if len(values) > 1 else None}


def multiseed_summary(rows):
    """Describe exactly the five planned seeds; provide no inferential parity gate."""
    require(rows, "No multiseed metrics")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["base_case_id"], row["simulator"]].append(row)
    output = []
    for (base, simulator), cases in sorted(grouped.items()):
        require(len(cases) == 5 and {row["seed"] for row in cases} == set(range(128, 133)),
                "Multiseed summary requires each of the five declared seeds exactly once")
        require(len({row["duration_s"] for row in cases}) == 1, "Pooled cases have different durations")
        sums = {field: sum(row[field] for row in cases) for field in
                ("attempts", "admitted", "delivered", "delivered_unique", "duplicate_delivery_events",
                 "unmatched_sends", "network_bytes_sent", "network_bytes_received", "delay_samples",
                 "delay_sum_s", "populated_delay_buckets", "bucket_latency_mean_sum_s", "duration_s")}
        sums["mean_packet_latency_s"] = sums["delay_sum_s"]/sums["delay_samples"] if sums["delay_samples"] else None
        sums["mean_populated_bucket_latency_s"] = (sums["bucket_latency_mean_sum_s"]/sums["populated_delay_buckets"]
                                                   if sums["populated_delay_buckets"] else None)
        sums["explicit_drops"] = sum(row["explicit_drops"] for row in cases) if simulator == "matlab" else None
        sums["pending"] = sum(row["pending"] for row in cases) if simulator == "matlab" else None
        output.append({"base_case_id": base, "simulator": simulator, "seeds": sorted(row["seed"] for row in cases),
                       "pooled": sums, "per_seed_delivered": descriptive([row["delivered"] for row in cases]),
                       "per_seed_packet_latency": descriptive([row["mean_packet_latency_s"] for row in cases
                                                                if row["mean_packet_latency_s"] is not None])})
    paired = []
    for base in sorted({key[0] for key in grouped}):
        if (base, "matlab") not in grouped or (base, "ns3") not in grouped:
            continue
        left = {row["seed"]: row for row in grouped[base, "matlab"]}
        right = {row["seed"]: row for row in grouped[base, "ns3"]}
        for seed in sorted(left):
            pair = {"base_case_id": base, "seed": seed}
            for field in ("admitted", "delivered", "mean_packet_latency_s", "mean_populated_bucket_latency_s"):
                m, n = left[seed][field], right[seed][field]
                difference = m-n if m is not None and n is not None else None
                pair[field] = {"matlab": m, "ns3": n, "difference_matlab_minus_ns3": difference,
                               "relative_difference_percent": 100*difference/n if difference is not None and n != 0 else None}
            paired.append(pair)
    return {"groups": output, "paired_by_seed": paired,
            "scope": "Descriptive observations for seeds 128..132 only. Simulator random streams are not assumed identical.",
            "population_equivalence_established": False,
            "latency_convention": "Packet-weighted means pool actual delivery delay samples. Bucket means equally weight each populated receive bucket."}
