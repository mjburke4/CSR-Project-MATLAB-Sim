"""Independent, read-only arithmetic checks of the ten archived packet ledgers.

This script does not import the population analyst's code or parse raw traces.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "longrun_recovery/extracted/latency-review/latency-review"
OUT = ROOT / "longrun_review/method_crosscheck.json"
SOURCES = [2, 3, 4, 5, 7, 8]
SEEDS = [128, 129, 130, 131, 132]


def mean(values):
    return math.fsum(values) / len(values) if values else None


def percent(m, n):
    return None if m is None or n is None or n == 0 else 100 * (m / n - 1)


def main():
    checks = []
    files = []
    populations = {}
    for engine in ["matlab", "native"]:
        for seed in SEEDS:
            path = ARCHIVE / (f"matlab/packets-{seed}.csv" if engine == "matlab"
                              else f"native/output/s{seed}-packets.csv")
            files.append({"path": str(path.relative_to(ROOT)),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            populations[engine, seed] = rows = []
            for raw in csv.DictReader(path.open()):
                delivered = raw.get("outcome") == "delivered" if engine == "matlab" else raw["delivered"] == "True"
                row = {"source": int(raw["source"]),
                       "generated": float(raw["generated_s"] if engine == "matlab" else raw["send_time_s"]),
                       "outcome": raw["outcome"] if engine == "matlab" else ("delivered" if delivered else "unresolved"),
                       "delivered": delivered}
                if delivered:
                    row.update(delay=float(raw["delivered_delay_s"] if engine == "matlab" else raw["latency_s"]),
                               nwk=float(raw["nwk_admission_wait_s"] if engine == "matlab" else raw["nwk_wait_s"]),
                               service=float(raw["post_admission_to_causal_receipt_s"] if engine == "matlab" else raw["post_admission_s"]))
                    assert abs(row["delay"] - row["nwk"] - row["service"]) < 1e-8, (engine, seed, raw)
                    assert min(row["delay"], row["nwk"], row["service"]) > -1e-8
                    assert row["generated"] + row["delay"] <= 6000 + 1e-8
                rows.append(row)
            checks.append({"engine": engine, "seed": seed, "admitted_rows": len(rows),
                           "delivered_closure_pass": True})
    cells = []
    for seed in SEEDS:
        for source in SOURCES:
            cell = {"seed": seed, "source": source}
            for engine in ["matlab", "native"]:
                rows = [r for r in populations[engine, seed] if r["source"] == source]
                delivered = [r for r in rows if r["delivered"]]
                cell[engine] = {"admitted": len(rows), "delivered": len(delivered),
                                "outcomes": {o: sum(r["outcome"] == o for r in rows)
                                             for o in (["delivered", "dropped", "pending"] if engine == "matlab" else ["delivered", "unresolved"])},
                                "mean_s": mean([r["delay"] for r in delivered]),
                                "nwk_mean_s": mean([r["nwk"] for r in delivered]),
                                "service_mean_s": mean([r["service"] for r in delivered])}
            cell["residual_percent"] = percent(cell["matlab"]["mean_s"], cell["native"]["mean_s"])
            cells.append(cell)
    pools = {}
    for engine in ["matlab", "native"]:
        rows = [r for seed in SEEDS for r in populations[engine, seed]]
        delivered = [r for r in rows if r["delivered"]]
        pools[engine] = {"admitted": len(rows), "delivered": len(delivered),
                         "outcomes": {o: sum(r["outcome"] == o for r in rows)
                                      for o in (["delivered", "dropped", "pending"] if engine == "matlab" else ["delivered", "unresolved"])},
                         "mean_s": mean([r["delay"] for r in delivered]),
                         "equal_run_mean_s": mean([mean([r["delay"] for r in populations[engine, s] if r["delivered"]]) for s in SEEDS])}
    zero_support = [(c["seed"], c["source"]) for c in cells if not c["native"]["delivered"]]
    assert zero_support == [(131, 2), (131, 7), (131, 8)]
    mu = [r["delay"] for seed in SEEDS for r in populations["matlab", seed]
          if r["delivered"] and (seed, r["source"]) in zero_support]
    mc = [r["delay"] for seed in SEEDS for r in populations["matlab", seed]
          if r["delivered"] and (seed, r["source"]) not in zero_support]
    q = len(mu) / pools["matlab"]["delivered"]
    support = {"zero_native_support_cells": zero_support,
               "matlab_unmatched_delivered": len(mu), "matlab_unmatched_mean_s": mean(mu),
               "matlab_common_mean_s": mean(mc),
               "matlab_unmatched_share": q,
               "common_term_s": (1-q) * (mean(mc) - pools["native"]["mean_s"]),
               "unmatched_term_s": q * (mean(mu) - pools["native"]["mean_s"])}
    assert abs(support["common_term_s"] + support["unmatched_term_s"] - pools["matlab"]["mean_s"] + pools["native"]["mean_s"]) < 1e-9
    source_mix = source_within = 0.0
    for source in SOURCES:
        stats = {}
        for engine in ["matlab", "native"]:
            ds = [r["delay"] for seed in SEEDS for r in populations[engine, seed] if r["source"] == source and r["delivered"]]
            stats[engine] = len(ds) / pools[engine]["delivered"], mean(ds)
        wm, mm = stats["matlab"]
        wn, mn = stats["native"]
        source_mix += (wm - wn) * (mm + mn) / 2
        source_within += (wm + wn) * (mm - mn) / 2
    assert abs(source_mix + source_within - pools["matlab"]["mean_s"] + pools["native"]["mean_s"]) < 1e-9
    fixed_age = []
    for horizon in [60, 300, 600, 1200]:
        for cell in cells:
            result = {"horizon_s": horizon, "seed": cell["seed"], "source": cell["source"]}
            for engine in ["matlab", "native"]:
                rows = [r for r in populations[engine, cell["seed"]]
                        if r["source"] == cell["source"] and r["generated"] < 6000-horizon - 1e-8]
                result[engine] = {"eligible_admissions": len(rows),
                                  "delivered_by_age": sum(r["delivered"] and r["delay"] <= horizon + 1e-8 for r in rows)}
            fixed_age.append(result)
    ensemble_checks = 0
    ensemble_dir = ROOT / "longrun_review/ensemble"
    if ensemble_dir.exists():
        def check(actual, expected):
            nonlocal ensemble_checks
            ensemble_checks += 1
            assert ((actual is None and expected == "") or
                    (actual is not None and math.isclose(actual, float(expected), rel_tol=1e-12, abs_tol=1e-8))), (actual, expected)

        for row in csv.DictReader((ensemble_dir / "per_seed_source_accounting.csv").open()):
            c = next(c for c in cells if c["seed"] == int(row["seed"]) and c["source"] == int(row["source"]))[row["engine"]]
            for a, b in [("admitted", "admitted"), ("delivered", "delivered"), ("mean_s", "mean_delivered_latency_s"),
                         ("nwk_mean_s", "mean_nwk_wait_s"), ("service_mean_s", "mean_post_admission_s")]:
                check(c[a], row[b])
            check(285000 - c["admitted"], row["not_admitted"])
        for row in csv.DictReader((ensemble_dir / "fixed_age_delivery.csv").open()):
            e = row["engine"]
            horizon = int(row["horizon_s"])
            seeds = [int(row["seed"])] if row["seed"] else SEEDS
            sources = [int(row["source"])] if row["source"] else SOURCES
            cohort = [r for s in seeds for r in populations[e, s]
                      if r["source"] in sources and r["generated"] < 6000-horizon-1e-8]
            attempt_count = (5700-horizon)*50*len(seeds)*len(sources)
            deadline_count = sum(r["delivered"] and r["delay"] <= horizon for r in cohort)
            check(attempt_count, row["scheduled_attempts"])
            check(len(cohort), row["admitted"])
            check(deadline_count, row["delivered_by_age"])
            check(deadline_count / attempt_count, row["deadline_fraction_of_scheduled_attempts"])
            check(deadline_count / len(cohort) if cohort else None, row["deadline_fraction_of_admitted"])
        maps = {(e, s): {(r["source"], round((r["generated"]-300)*50)): r for r in populations[e, s]}
                for e in ["matlab", "native"] for s in SEEDS}
        for row in csv.DictReader((ensemble_dir / "scheduled_attempt_intersection.csv").open()):
            seed = int(row["seed"])
            source = int(row["source"]) if row["source"] else None
            m, n = maps["matlab", seed], maps["native", seed]
            keys = [k for k in m.keys() & n.keys() if source is None or k[0] == source]
            delivered = [k for k in keys if m[k]["delivered"] and n[k]["delivered"]]
            check(len(keys), row["jointly_admitted"])
            check(len(delivered), row["jointly_delivered"])
            check(mean([m[k]["delay"] for k in delivered]), row["matlab_mean_jointly_delivered_s"])
            check(mean([n[k]["delay"] for k in delivered]), row["native_mean_jointly_delivered_s"])
        for row in csv.DictReader((ensemble_dir / "standardized_latency.csv").open()):
            strata = []
            if row["scope"] == "seed_source":
                strata = [{e: (c[e]["delivered"], c[e]["mean_s"]) for e in ["matlab", "native"]}
                          for c in cells if c["matlab"]["delivered"] and c["native"]["delivered"]]
            else:
                for source in SOURCES:
                    stratum = {}
                    for e in ["matlab", "native"]:
                        ds = [r["delay"] for s in SEEDS for r in populations[e, s] if r["source"] == source and r["delivered"]]
                        stratum[e] = len(ds), mean(ds)
                    strata.append(stratum)
            if row["weighting"] == "native_delivery_weights":
                weights = [st["native"][0] for st in strata]
            elif row["weighting"] == "pooled_delivery_weights":
                weights = [st["native"][0]+st["matlab"][0] for st in strata]
            else:
                weights = [1]*len(strata)
            for e in ["matlab", "native"]:
                check(math.fsum(w*st[e][1] for w, st in zip(weights, strata))/sum(weights), row[e+"_standardized_mean_s"])
    report = {"schema": "independent-longrun-ledger-method-check-v1", "status": "pass",
              "raw_trace_reparse": False, "source_files": files, "checks": checks,
              "pooled": pools, "pooled_residual_percent": percent(pools["matlab"]["mean_s"], pools["native"]["mean_s"]),
              "equal_run_residual_percent": percent(pools["matlab"]["equal_run_mean_s"], pools["native"]["equal_run_mean_s"]),
              "support": support, "pooled_source_decomposition": {"mix_s": source_mix, "within_s": source_within},
              "per_seed_source": cells, "fixed_age_admitted_crosscheck": fixed_age,
              "defined_cell_count": sum(c["residual_percent"] is not None for c in cells),
              "ensemble_aggregate_crosschecks_passed": ensemble_checks,
              "cells_within_10_percent": sum(c["residual_percent"] is not None and abs(c["residual_percent"]) <= 10 for c in cells)}
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ["status", "pooled", "pooled_residual_percent", "support", "defined_cell_count", "cells_within_10_percent"]}, indent=2))


if __name__ == "__main__":
    main()
