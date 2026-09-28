# Original 6,000-second accounting: five-seed extension

This review reuses seeds 128–132 and runs no new simulation. It independently reproduces 210 accepted count/mean checks and extends the earlier latency review with scheduled-attempt accounting, equal-weight comparisons, deadline delivery with complete follow-up, and explicit unfinished populations. The archived mix and queue-location findings are confirmed; they are not new discoveries.

## Application accounting

Attempts are the generator’s periodic admission checks, not persistent application objects. Only an admitted check creates the application whose latency is measured. Each source has 285,000 scheduled checks per run (300–6,000 s, every 20 ms). Direct attempt counters were rechecked for seeds 131–132; attempts for 128–130 are schedule-derived and explicitly labeled in the CSV.

| Engine | Scheduled attempts | Admitted | Delivered | Terminal drops | Pending | Unresolved fate |
|---|---:|---:|---:|---:|---:|---:|
| MATLAB | 8,550,000 | 62,795 | 59,273 | 2,029 | 1,493 | 0 |
| ns-3 | 8,550,000 | 62,631 | 59,376 | Unknown | Unknown | 3,255 |

Native owner completion, `no_ack`, DACK expiration, and receiver drops do not establish global terminal application fate. Its 3,255 undelivered identities remain unresolved, potentially including unobserved terminal drops. They must not all be labeled pending, assigned completed latency, or treated as ordinary survival-analysis censoring. MATLAB’s pending count is its application-status classification, not a claim that every packet remains in one particular queue.

| Source | MATLAB admitted / delivered / dropped / pending | ns-3 admitted / delivered / unresolved | MATLAB / ns-3 delivered mean (s) |
|---|---:|---:|---:|
| 2 | 2433 / 1820 / 401 / 212 | 2236 / 1756 / 480 | 476.59 / 447.77 |
| 3 | 42653 / 42569 / 7 / 77 | 42468 / 42378 / 90 | 10.28 / 10.52 |
| 4 | 2537 / 2048 / 361 / 128 | 3943 / 3264 / 679 | 263.66 / 182.47 |
| 5 | 8073 / 7942 / 51 / 80 | 8269 / 8123 / 146 | 55.56 / 56.31 |
| 7 | 4551 / 3040 / 757 / 754 | 3873 / 2533 / 1340 | 1,058.48 / 1,032.85 |
| 8 | 2548 / 1854 / 452 / 242 | 1842 / 1322 / 520 | 838.85 / 694.05 |

Detailed source/seed balances are in `per_seed_source_accounting.csv`. Aggregate delivery count is close (59,273 versus 59,376), but source-level differences remain substantial. Native seed 131 admits nothing from sources 2, 7, or 8, despite 285,000 checks each. MATLAB admits 1,835 and delivers 1,304 across those three cells.

## Delivered latency and source mix

The unchanged raw pooled delivered means are **119.095 versus 97.997 s (+21.53%)**. Equal weighting of the five run means gives 118.950 versus 98.599 s (+20.64%).

The prior exact arithmetic partition reproduces: 19.009 s of the 21.098 s pooled gap is the contribution of MATLAB’s three unmatched seed-131 cells relative to the native overall mean; 2.089 s is the common-support remainder. This is a descriptive identity, not proof that discovery causally explains 90% of the discrepancy. The source-only symmetric alternative gives 11.787 s from delivery mix and 9.311 s from pooled within-source means; these alternative partitions must not be added.

The following common-weight diagnostics retain only the 27 seed/source cells delivered in both models. The absent native means remain undefined. Reweighting uses observed deliveries, not a new physical traffic model.

| Common weighting | MATLAB mean (s) | ns-3 mean (s) | Difference |
|---|---:|---:|---:|
| native delivery weights | 106.269 | 97.997 | +8.44% |
| pooled delivery weights | 103.238 | 97.079 | +6.34% |
| equal cell weights | 415.511 | 381.383 | +8.95% |

At native delivery weights, NWK waiting averages 90.091 versus 82.927 s; post-admission service averages 16.178 versus 15.070 s. Thus the standardized +8.272 s difference still sits mainly before HOP admission.

**These values are not ±10% parity passes.** They exclude meaningful missing traffic, condition on successful completion, and allow large positive and negative source errors to cancel. Pooling by source before reweighting changes the question again: equal weight to six pooled source means gives +11.53%. The result is sensitive to the declared estimand.

## Include unfinished traffic through fixed-age delivery

For each horizon T, use the same half-open generation window [300, 6000−T) in both models. Every included scheduled check or admitted application has at least T seconds of observation. Count final delivery by generation+T; report that numerator both over scheduled checks and admitted applications. Rejected checks and unfinished or dropped applications are not assigned invented completion times. Different horizons deliberately have different eligible windows, so the rows are not one cumulative-distribution curve.

| Deadline age (s) | Scheduled checks per engine | MATLAB delivered / admitted | ns-3 delivered / admitted | MATLAB / ns-3 delivery per scheduled check |
|---|---:|---:|---:|---:|
| 60 | 8,460,000 | 46,970 / 62,135 (75.59%) | 47,168 / 61,989 (76.09%) | 0.5552% / 0.5575% |
| 300 | 8,100,000 | 49,579 / 59,494 (83.33%) | 50,886 / 59,408 (85.66%) | 0.6121% / 0.6282% |
| 600 | 7,650,000 | 49,388 / 56,259 (87.79%) | 50,600 / 56,177 (90.07%) | 0.6456% / 0.6614% |
| 1200 | 6,750,000 | 46,590 / 49,908 (93.35%) | 47,296 / 49,728 (95.11%) | 0.6902% / 0.7007% |

Whole-network deadline counts again mask source-level differences. At a 1,200-second deadline, both models have the same 225,000 scheduled checks per source in [300, 4,800):

| Seed / source | MATLAB delivered within 1,200 s / admitted | ns-3 delivered within 1,200 s / admitted |
|---|---:|---:|
| 130 / 7 | 498 / 635 (78.43%) | 199 / 1162 (17.13%) |
| 130 / 8 | 444 / 538 (82.53%) | 79 / 165 (47.88%) |
| 132 / 2 | 78 / 146 (53.42%) | 374 / 429 (87.18%) |
| 132 / 7 | 145 / 905 (16.02%) | 536 / 657 (81.58%) |
| 132 / 8 | 154 / 522 (29.50%) | 307 / 373 (82.31%) |

The opposite long-delay behavior in seeds 130 and 132 therefore survives an explicit deadline comparison with complete follow-up. The main problem is not solely an end-of-run censoring artifact. These outcome differences still do not identify an implementation defect because each model develops its own admission, route, and feedback history.

MATLAB has 1,493 pending applications at the stop: median elapsed age 367.82 s, 95th percentile 1,737.408 s, maximum 2,151.44 s; 239 exceed 1,200 s. Seed-132 source 7 alone retains 298 pending, with 131 over 1,200 s old. Native unresolved ages are retained separately in the CSV and are not comparable live-queue age statistics.

## Exact scheduled-attempt overlap is only a sensitivity check

All admitted times map uniquely to source and a zero-based 20 ms scheduled index; maximum reconstruction residual is 9.1×10⁻¹³ s. The two models jointly admit only 1,827 checks and jointly deliver 1,726, about 2.9% of each delivered population. This selected intersection has means 39.144 versus 41.549 s (−5.79%), but 1,385 of the 1,726 come from source 3. Equal scheduled checks do not imply shared random draws or trajectories. This small, selected subset cannot establish network parity.

## Scope and reproducibility

Run `python3 longrun_review/ensemble/analyze_ensemble.py --workspace <restored-workspace>` and then `python3 longrun_review/ensemble/build_report.py`. All calculations use the Python standard library. `summary.json` binds input hashes and defines estimands. `accepted_metric_checks.csv` preserves all 210 reproduction checks; `jointly_admitted_attempts.csv` retains the sparse intersection identities. No production code was edited. Native and MATLAB 131/132 companion audits validate the original trace-to-ledger mappings; 128–130 use the prior archived audit and its accepted provenance.

The evidence supports retaining the original network discrepancy as open, with explicit per-source accounting and NWK admission waiting as the dominant location. It supports no timer/window adjustment or new production fix without a specific behavioral mismatch.
