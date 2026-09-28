# Corrected 6,000-second return: independent accounting review

Scope: seeds 131 and 132 only. No new simulation. Native means the pinned ns-3 C++ reference. The comparison target is ±15% per source for delivered counts and delivered-only mean latency.

## Verification

Recomputed application identities, epoch-derived latencies, admission-counter closure, all numeric source accounting and fixed-age fields, per-source gates, and case-summary totals/weights. **26,526 numerical checks passed; none failed.** Native final fate is unresolved for undelivered identities; MATLAB pending describes final model outcome, not proof of a live queue copy.

## Pair totals

| Model | Attempts | Admitted | Delivered | Known drops | Model pending | Unresolved fate | Delivered mean (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| old_matlab | 3,420,000 | 25,306 | 23,839 | 759 | 708 | — | 146.901 |
| matlab | 3,420,000 | 25,072 | 23,698 | 760 | 614 | — | 135.156 |
| native | 3,420,000 | 25,090 | 24,055 | unknown | unknown | 1035 | 64.497 |

Current pair delivered count is **−1.48%** relative to ns-3, but raw delivered mean latency is **+109.56%**. Original MATLAB on these same two seeds was **+127.77%**. These are deliberately selected difficult seeds; the five-seed historical +21.53% is a different population and must not be compared directly.

Common seed/source cells weighted by native delivered counts give **96.177 s MATLAB vs 64.497 s ns-3 (+49.12%)**, improved from **112.858 s (+74.98%)** for old MATLAB. This excludes 1,353 MATLAB seed-131 deliveries from sources 2/7/8 with no native counterparts (old exclusion 1,304). It is descriptive standardization, not a parity gate.

At ±15%, delivery count passes **2/9** defined cells (old 5/9), latency passes **3/9** (old 3/9), and both pass **2/9** (old 3/9). Three more cells have zero native deliveries and undefined relative errors. Both metrics pass only source 3 in each seed.

## Complete source outcomes

Each row/model has 285,000 scheduled attempts. Not-admitted = 285,000 − admitted; a rejected interrupt does not create a persistent application.

| Seed/source | MATLAB admitted/delivered/drop/pending | ns-3 admitted/delivered/unresolved | Count delta | Mean delay MATLAB / ns-3 (s) | Delay delta |
|---|---:|---:|---:|---:|---:|
| 131/2 | 536/425/74/37 | 0/0/0 | undefined | 441.98 / undefined | undefined |
| 131/3 | 8628/8612/1/15 | 8190/8172/18 | +5.38% | 10.16 / 10.94 | -7.14% |
| 131/4 | 551/446/80/25 | 1897/1567/330 | -71.54% | 252.93 / 87.55 | +188.91% |
| 131/5 | 1428/1400/12/16 | 2543/2522/21 | -44.49% | 62.93 / 36.61 | +71.91% |
| 131/7 | 870/639/144/87 | 0/0/0 | undefined | 1320.63 / undefined | undefined |
| 131/8 | 424/289/73/62 | 0/0/0 | undefined | 947.31 / undefined | undefined |
| 132/2 | 400/294/64/42 | 569/444/125 | -33.78% | 521.68 / 454.69 | +14.73% |
| 132/3 | 8522/8504/2/16 | 8600/8582/18 | -0.91% | 10.29 / 10.37 | -0.75% |
| 132/4 | 596/490/77/29 | 498/397/101 | +23.43% | 230.17 / 274.22 | -16.06% |
| 132/5 | 1745/1721/8/16 | 1462/1428/34 | +20.52% | 51.40 / 63.54 | -19.11% |
| 132/7 | 1133/703/179/251 | 819/584/235 | +20.38% | 1401.94 / 857.84 | +63.43% |
| 132/8 | 239/175/46/18 | 512/359/153 | -51.25% | 1036.37 / 671.71 | +54.29% |

## Equal observation time

At the 1,200-second deadline, use the same half-open generation interval **[300,4800)** and **225,000 scheduled attempts per source** in every model. Older/newer MATLAB and native each have different admitted populations; the scheduled-attempt denominator stays equal. Pending and terminal drops remain failures to deliver by the deadline, not fabricated latencies.

| Seed/source | Old MATLAB timely / admitted | Current MATLAB timely / admitted | ns-3 timely / admitted |
|---|---:|---:|---:|
| 131/4 | 396 / 470 (84.26%) | 355 / 421 (84.32%) | 1270 / 1516 (83.77%) |
| 131/7 | 282 / 997 (28.28%) | 191 / 766 (24.93%) | 0 / 0 |
| 131/8 | 131 / 231 (56.71%) | 215 / 333 (64.56%) | 0 / 0 |
| 132/4 | 345 / 402 (85.82%) | 408 / 475 (85.89%) | 326 / 382 (85.34%) |
| 132/7 | 145 / 905 (16.02%) | 170 / 1014 (16.77%) | 536 / 657 (81.58%) |
| 132/8 | 154 / 522 (29.50%) | 103 / 230 (44.78%) | 307 / 373 (82.31%) |

Seed 132/source 7 improves delivered mean from **1,636.61 to 1,401.94 s**, but 1,200-second completion among admitted traffic barely changes **16.02%→16.77%**, versus **81.58%** native. Its 170 timely deliveries remain well below 536 native.

Seed 132/source 8 improves delivered mean from **1,451.66 to 1,036.37 s**, while delivered count falls **407→175** and deadline deliveries fall **154→103**. Its better deadline fraction reflects a much smaller admitted population, and does not show increased timely throughput.

Source 4 moves in opposite directions by seed: seed 131 delivers 446 vs 1,567 native and is +188.91% slower; seed 132 delivers 490 vs 397 native and is −16.06% faster. Pooling these histories conceals distinct competition and reachability conditions.

## Limits and next interpretation

This arithmetic audit confirms that the returned comparison is internally consistent. It cannot identify a missing protocol mechanism by itself. Improvements in delivered averages are not sufficient when source allocations and unfinished traffic differ. Read this with the separate discovery and causal NWK/HOP reconstructions before choosing a code fix. No new simulation or code change was performed for this accounting review.

Reproduction: run `python return6000/review/accounting/recompute.py` from the workspace containing `return6000/data/` and the two original recovered ZIPs. Input member and file hashes are recorded in `summary.json`. `checks.csv` contains individual verification results.
