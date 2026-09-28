# Returned seed 131: complete causal latency and source allocation

The corrected MATLAB seed-131 run still creates a connected six-source traffic population, while the bound ns-3 reference admits only sources 3, 4 and 5. The per-source latency gaps therefore occur under substantially different competing traffic. This return demonstrates neither 15% network parity nor a new specific admission-rule defect.

## Evidence and method

The historical, audited MATLAB causal parser was executed with unchanged matching logic on the returned applications and complete protocol trace. Only its input case/archive and final all-case source-binding section were adapted. It reconstructed all **11,811 delivered applications**, with no missing or ambiguous paths. The maximum floating-point phase closure error is 5.06e-12 s; rounding shared event boundaries to integer nanoseconds yields **exact closure on every path**. Raw application-generation, receipt and drop counters close against the exported outcomes. No protocol or PHY rows were omitted. The separate attempt-detail log remains limited to 100,000 rows; complete source counters cover all attempts.

Each winning path follows source creation, accepted relay custody, and final receipt. NWK wait is custody arrival through successful HOP admission; subsequent service is HOP admission through downstream accepted receipt. Upstream ACK ownership after successful receipt is excluded, preventing overlapping latency sums. Native historical evidence supports this combined post-admission service, not a complete comparable first-TX/retry subdivision.

## Current versus original outcomes

| Source | Old MATLAB delivered / admitted | Current MATLAB delivered / admitted | ns-3 delivered / admitted | Current MATLAB drop / pending |
|---|---:|---:|---:|---:|
| 2 | 369 / 497 | 425 / 536 | 0 / 0 | 74 / 37 |
| 3 | 8,512 / 8,527 | 8,612 / 8,628 | 8,172 / 8,190 | 1 / 15 |
| 4 | 467 / 575 | 446 / 551 | 1,567 / 1,897 | 80 / 25 |
| 5 | 1,565 / 1,592 | 1,400 / 1,428 | 2,522 / 2,543 | 12 / 16 |
| 7 | 748 / 1,091 | 639 / 870 | 0 / 0 | 144 / 87 |
| 8 | 187 / 247 | 289 / 424 | 0 / 0 | 73 / 62 |

Current MATLAB totals: 12,437 admitted = 11,811 delivered + 384 terminal drops + 242 model-pending. Every source has 285,000 scheduled attempts. The native zero-admission sources are blocked by unknown topology for all 855,000 of their combined attempts. Native undelivered outcomes remain unresolved, not classified as drops or live pending copies.

## Delivered latency decomposition

All entries are seconds. Each pair is **NWK wait + subsequent service**, summing to delivered mean latency.

| Source | Old MATLAB | Current MATLAB | ns-3 |
|---|---:|---:|---:|
| 2 | 402.85 + 34.22 = 437.07 | 404.98 + 37.00 = 441.98 | Undefined |
| 3 | 0.036 + 10.257 = 10.293 | 0.031 + 10.127 = 10.157 | 0.113 + 10.826 = 10.939 |
| 4 | 201.71 + 30.55 = 232.27 | 220.12 + 32.80 = 252.93 | 64.50 + 23.04 = 87.55 |
| 5 | 29.61 + 27.14 = 56.75 | 34.95 + 27.98 = 62.93 | 13.15 + 23.45 = 36.61 |
| 7 | 1,194.45 + 35.94 = 1,230.39 | 1,283.76 + 36.87 = 1,320.63 | Undefined |
| 8 | 887.84 + 36.61 = 924.45 | 908.93 + 38.39 = 947.31 | Undefined |

Current source 4's excess over ns-3 is 165.38 s: **155.62 s NWK** plus 9.76 s post-admission. Its own node-4 queue contributes 161.46 s versus 44.29 s native; node 5 contributes another 58.66 s versus 20.21 s. Source 5's excess is 26.32 s: **21.80 s NWK** plus 4.52 s post-admission.

Using the ns-3 delivered counts as common-source weights (sources 3, 4, 5 only), the mean is **52.04 s current MATLAB versus 26.01 s native**, a +100.08% gap. Its 26.03-s difference comprises **24.32 s additional NWK waiting** and 1.71 s additional subsequent service. Old MATLAB under those weights was 48.22 s. This diagnostic excludes 1,353 current MATLAB deliveries from sources absent in native, and does not control their competing traffic. It cannot establish causal attribution or whole-network acceptance.

## Source 4 is sharing service with sources that native never admits

Winning delivered paths through each node provide a directly observed load distinction:

| Node | ns-3 total delivered paths | Current MATLAB total delivered paths | ns-3 own-source share | Current MATLAB own-source share |
|---|---:|---:|---:|---:|
| 4 | 1,567 | 1,799 | 1,567 / 1,567 (100%) | 446 / 1,799 (24.8%) |
| 5 | 4,089 | 3,199 | 2,522 / 4,089 (61.7%) | 1,400 / 3,199 (43.8%) |

MATLAB node 4 therefore serves more ultimately delivered applications in total than native, while serving many fewer of its own source. The 1,353 additional source-2/7/8 deliveries traverse nodes 4 and 5. This is a concrete competing-load difference, not proof of an unfair scheduling implementation. These counts concern delivered paths only; failed and unfinished traffic can impose additional service load.

Source 7's current 1,283.76-s NWK wait accumulates principally at node 8 (647.82 s), node 2 (284.71 s), and node 4 (189.71 s). This is a multihop backlog, not a thousand-second MAC transmission. Source 8's 908.93-s NWK wait is concentrated at node 2 (387.93 s), its own node (236.57 s), and node 4 (226.87 s).

## Discovery remains the first consequential population distinction

MATLAB discovery completes in order: node 1 at 25.000 s, node 3 at 40.426 s, node 5 at 55.759 s, node 4 at 71.192 s, node 2 at 86.465 s, node 8 at 101.883 s, and node 7 at 117.314 s. All six application sources begin admitted creation at 300 s, with zero topology or route admission blocks. Active neighbor pairs and final gateway routes support the chain **7→8→2→4→5→1**, alongside source 3's direct gateway link. Native's all-run unknown-topology rejections at 2/7/8 show that it does not expose nodes 4/5 to the same source population.

The existing short common-input studies must remain part of the diagnosis: autonomous scheduling and random histories can differ even with the same numerical seed. The full returned run identifies a consequential reachability difference and downstream queueing effects; it does not newly prove that MATLAB omits an ns-3 mechanism.

## Decision

Seed 131 does not satisfy the 15% target. The cleanup fix has not removed the reachability/population distinction or the common-source queueing gap. Do not tune retry or waiting constants to these means. The highest-value remaining diagnosis is the **native discovery stall and its input/event history**, interpreted alongside the already completed discovery replays, before assigning seed-131 source-4/5 differences to NWK admission logic. Any new code change needs a concrete difference in behavior under the same relevant inputs and state. No simulation or production change was made for this analysis.

Reproduction: run `python3 return6000/review/phase131/analyze.py` from the recovered workspace. Inputs are the returned ZIP and historical accounting archive; outputs include source/node phase CSVs, complete packet/hop ledgers, discovery events, and hash-bound verification JSON.
