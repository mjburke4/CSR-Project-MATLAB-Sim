# Tranche 6 returned R2025a outcome review

Candidate `21c0a3f` completed the reported **380/380 MATLAB tests and all 18 sweeps**. This independent review finds complete terminal application accounting and no duplicate application deliveries. It does **not** establish an outage-delivery improvement: total delivery decreases from **336/357 to 334/357**, with 23 retry-exhaustion losses and no pending application custody.

All nine offered-load cases retain the same per-application outcomes, delivery latencies and recorded physical/protocol totals as accepted Tranche 5. Raw traces are not byte-identical; some simultaneous records are ordered differently. All 18 configurations and all 357 application identities match the baseline.

| Experiment | Tranche 5 delivered | Tranche 6 delivered | Pinned ns-3 delivered |
| --- | ---: | ---: | ---: |
| Offered load ×1 | 48/48 | 48/48 | Not run in this reference |
| Offered load ×2 | 90/90 | 90/90 | Not run in this reference |
| Offered load ×4 | 171/174 | 171/174 | Not run in this reference |
| Recovery freshness 60 s | 15/15 | 13/15 | 14/15 |
| Recovery freshness 180 s | 6/15 | 6/15 | 6/15 |
| Recovery freshness 300 s | 6/15 | 6/15 | 6/15 |

## The two new losses

| Case | Application generated | T5 first HOP submission | T5 delivery | T6 first HOP submission | T6 terminal retry failure | Source neighbor expiry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 s, seed 128, packet 1 | 450.000 s | 582.677 s | 585.940 s | 450.000 s | 458.727 s | 465.000 s |
| 60 s, seed 130, packet 1 | 450.000 s | 582.707 s | 584.199 s | 450.000 s | 458.831 s | 465.000 s |

The blackout lasts from 405 through 540 seconds. These two packets enter HOP at 450 seconds and make three source transmissions before retry exhaustion around 458.8 seconds. The 465-second neighbor expiry occurs after the packet is already lost. In the T5 run, the same packets remained unsent in NWK custody until after rediscovery. T6 seed 129 instead expires the source neighbor at 405 seconds; its first packet stays queued and delivers at 588.901 seconds. These are observed lifecycle differences; changed event ordering and route state have not been decomposed into single-cause counterfactuals.

For every 180/300-second case, packets 1–3 (generated 450/486/522 seconds) exhaust retries during the blackout; packets 4–5 deliver after restoration. Pinned ns-3 exhibits the same longer-freshness failure pattern, plus one first-packet loss in its 60-second seed-129 case. Its 60-second seed results are 5/5, 4/5, 5/5 versus MATLAB T6 4/5, 5/5, 4/5; this does not establish numerical parity.

## Timing, expiry churn and controls

| Freshness | Pre-blackout deactivations T5 → T6 | All deactivations T5 → T6 | Route changes T5 → T6 | Delivered-in-both latency change |
| --- | ---: | ---: | ---: | ---: |
| 60 s | 30 → 33 | 78 → 82 | 323 → 353 | +1.202 s (13 packets) |
| 180 s | 5 → 6 | 23 → 25 | 137 → 151 | +0.254 s (6 packets) |
| 300 s | 0 → 0 | 3 → 6 | 53 → 59 | +0.000 s (6 packets) |

At 60 seconds, deactivation churn exists well before the blackout. Delivery alone therefore does not make 60 seconds an optimal timeout. Maximum T6 delivered latency is **138.901 seconds** (versus 135.940 seconds in T5). The two lost applications would otherwise have occupied the high-latency tail, so lower delivered-only means in those seeds are not an improvement.

All three 300-second cases retain one reliable HOP control target plus three NWK control messages at the 900-second stop; T5 retained one HOP control target plus two NWK messages. The T6 trace records freshness expiry of node 1→2 and node 2→1 exactly at 900 seconds, then queues node-1 DISCOVER, node-2 ROUTING and node-2 DISCOVER work. The extra NWK message is explicitly owned stop-boundary work. No further runtime is present to prove its drain. None of these controls is pending application DATA.

## Accounting and interpretation

Across all 18 cases, raw generated/delivered/dropped identities agree with diagnostics and summary records. NWK enqueue and custody-release event counts balance, per-node pending NWK custody and HOP DATA are zero, and no application has both a terminal drop and delivery. There are no duplicate final application deliveries, no unretained HOP ACKs, and no unclassified returned application. HOP duplicate receptions are a separate retransmission behavior and are retained in the JSON counts.

The ns-3 reference observes local HOP no-ACK completion for each undelivered application and zero observed queues at the stop. Its global dropped/pending categories remain unknown. MATLAB global terminal accounting must not be imputed to ns-3 from those local observations.

Recommended disposition: **the bounded source-fidelity gate passes this outcome review**, subject to the separate source/provenance identity checks. Accept the NWK semantic correction with the measured 60-second regression recorded. **Outage-performance acceptance remains qualified/deferred**: the 60-second group is worse, and the 180/300-second groups retain their original retry-exhaustion limitation. Do not report improved outage delivery or autonomous recovery. Structural failures would block acceptance; the returned outcome review found none.

The next cohesive target is the route-selection/DATA-retry boundary: why a packet is released to a stale selected next hop and loses local custody before expiry can invalidate that path. Keep the existing source-compatible policy as the baseline. Any retention-on-failure or outage-trigger extension should be explicit, bounded, and checked for healthy-link false expiry, duplicate delivery, source/relay custody, recovery without manual rediscovery, and stop-boundary control drain.

Inputs: unchanged returned ZIP, original accepted T5 ZIP, raw sweep diagnostics/protocol traces/final node counters, and pinned ns-3 `case_summary.csv`. Input SHA-256 identities and all 18 case details are recorded in the [structured outcome review](../evidence/tranche-6-return-outcomes-review.json). This review does not independently rerun MATLAB.
