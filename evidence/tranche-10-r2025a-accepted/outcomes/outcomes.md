# Independent Tranche 10 outcome review

All counts below were independently reconstructed from the immutable MATLAB protocol traces and native application-send/network-delivery events. The reconstructed MATLAB packet identities, sources, generation times, delivery times and final states were checked against the owner-exported application tables. `derive.py` reproduces this analysis; `independent-outcomes.json` preserves exact results.

## Campus: one 6,000-second seed-128 run

| Measure | Accepted T7 MATLAB | T10 MATLAB | Pinned ns-3 |
| --- | ---: | ---: | ---: |
| Admitted/generated applications | 12,382 | 12,484 | 12,417 |
| Delivered applications | 11,727 | 11,825 | 11,769 |
| Pooled delivered-packet mean latency (s) | 103.9634 | 98.9701 | 104.1948 |
| Dropped applications | 401 | 402 | Not classified here |
| Pending at stop | 254 | 257 | Not classified here |
| Generated without observed delivery | 655 | 659 | 648 |

T10 delivers 98 more packets than T7, but its total deviation from ns-3 changes from −42 (−0.3569%) to +56 (+0.4758%). More deliveries alone are not evidence of improved parity. Pooled latency is 4.99 seconds below T7 and 5.22 seconds below ns-3, for different delivered packet populations. It is not a per-packet paired improvement.

| Source → gateway 1 | T7 generated / delivered | T10 generated / delivered | ns-3 generated / delivered | T10 delivered vs ns-3 | T10 dropped / pending |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 → 1 | 506 / 395 | 551 / 411 | 547 / 410 | +0.24% | 97 / 43 |
| 3 → 1 | 8,608 / 8,593 | 8,489 / 8,472 | 8,551 / 8,535 | -0.74% | 1 / 16 |
| 4 → 1 | 566 / 454 | 439 / 348 | 498 / 419 | -16.95% | 62 / 29 |
| 5 → 1 | 1,309 / 1,285 | 1,669 / 1,644 | 1,397 / 1,369 | +20.09% | 9 / 16 |
| 7 → 1 | 832 / 617 | 748 / 533 | 803 / 574 | -7.14% | 127 / 88 |
| 8 → 1 | 561 / 383 | 588 / 417 | 621 / 462 | -9.74% | 106 / 65 |

Node 8 narrows its delivery deficit from −17.10% to −9.74%. Node 4 changes from +8.35% to −16.95%, while node 5 changes from −6.14% to +20.09%. Thus +20.09% is now the largest absolute delivered-count deviation among these six flows. Summed absolute per-flow delivery deviations increase from 314 to 496 packets. These are measurements of this seed, not uncertainty bounds or proof of a model defect.

| Source | T7 mean packet latency (s) | T10 mean packet latency (s) | ns-3 mean packet latency (s) |
| --- | ---: | ---: | ---: |
| 2 | 445.785 | 487.330 | 456.846 |
| 3 | 10.190 | 10.328 | 10.448 |
| 4 | 253.240 | 299.154 | 269.689 |
| 5 | 68.338 | 53.464 | 67.303 |
| 7 | 799.414 | 784.557 | 777.848 |
| 8 | 677.566 | 653.139 | 645.370 |

All six campus generators make 285,000 offered attempts each. Complete MATLAB admission counters identify every blocked attempt as the NSDP/admission-capacity gate: T10 admits 12,484 of 1,710,000 attempts. The packet-generation counts therefore differ between models even with equal offered schedules. The campus admission event trace stores only its first 100,000 rows and omits 1,610,000 later attempts; complete counters and complete application traces support the totals, but do not reconstruct every later admission decision.

The final routing snapshot places node 4 → 5 → 1 on the path from nodes 2/8/7 toward the gateway. Of 403 T10 data HOP failures, 310 are on 4 → 5; T7 had 305 there of 401. HOP failures must not be relabeled as application drops: one T10 HOP failure occurs without an application-drop final outcome. These observations make node 4/5 service and admission sharing a useful diagnostic focus, but do not prove its causal mechanism.

## Five contention seeds and the admission control

| Case | T9 delivered | T10 delivered | ns-3 delivered | T10 vs ns-3 | T10 early 300–320 s / ns-3 early |
| --- | ---: | ---: | ---: | ---: | ---: |
| c128 | 928 | 928 | 914 | +1.53% | 254 / 222 |
| c129 | 948 | 948 | 822 | +15.33% | 260 / 164 |
| c130 | 894 | 894 | 916 | -2.40% | 215 / 234 |
| c131 | 895 | 895 | 883 | +1.36% | 211 / 207 |
| c132 | 917 | 917 | 920 | -0.33% | 233 / 223 |
| a129 | 11,354 | 11,357 | 11,227 | +1.16% | 212 / 216 |

Every contention seed retains exactly its T9 generated/delivered/dropped/pending counts, including each source separately. First-20-second counts are also unchanged. The pooled latency differences from T9 are approximately 0.06 ns, consistent with timing representation differences and not a demonstrated performance gain.

For c129, source 2 delivers 510 vs ns-3 353 (+157), with 152 vs 35 in the first 20 traffic seconds (+117). Therefore 74.5% of this delivery gap is concentrated in the initial window. Source 3 delivers 438 vs 469 (−31). The preserved initial imbalance remains the strongest compact diagnostic target.

Admission a129 delivers 11,357, up three from T9 and 130 above ns-3 (+1.1579%); the first-20-second counts remain 212 vs 216. Mean latency is 0.928295 s vs T9 0.929021 s and ns-3 0.959757 s. This small single-seed change does not establish a general admission improvement.

## Next diagnostic recommendation

Use a short deterministic contention replay to distinguish different random-slot sequences from policy divergence. Export one explicit sequence of contention choices and replay the same choices, offered arrivals, receiver outcomes and initial state in each implementation. Compare the first divergence across DATA delivery, ACK eligibility/replacement/transmission, HOP release and subsequent admission. Keep PHY/ECC unchanged. Equal numeric seeds alone do not supply this control.

Then extend the same bounded method to the node 4/5 campus service path, retaining competing local and relayed traffic, and measure admission/airtime allocation by original source. Avoid a new full campus run until the small experiment isolates a discrepancy worth changing. No implementation correction is justified solely to make these aggregate totals match.

This independent outcome review does not replace the root acceptance/integrity analysis, and makes no new MATLAB execution claim.
