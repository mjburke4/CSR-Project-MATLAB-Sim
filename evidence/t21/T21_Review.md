# Tranche 21: explain the remaining flow differences

**Existing-trace investigation completed. The working numerical target is now ±10%. No new MATLAB or ns-3 simulations were needed, and no production source was changed.**

## Revised target

This is a new engineering screening band for T21. T20’s accepted results and its original ±5% report remain unchanged. Structural correctness and evidence integrity remain separate requirements. Three seeds do not establish statistical equivalence.

| Measure | Within ±5% | Within ±10% |
| --- | ---: | ---: |
| Admissions, network totals | 3/3 | 3/3 |
| Admissions, individual flows | 9/18 | 12/18 |
| Unique deliveries, network totals | 3/3 | 3/3 |
| Unique deliveries, individual flows | 7/18 | 13/18 |
| Mean delivered delay, network totals | 1/3 | 2/3 |
| Mean delivered delay, individual flows | 9/18 | 13/18 |

The delivery differences, with ns-3 as denominator, are:

| Source | Seed 128 | Seed 129 | Seed 130 |
| --- | ---: | ---: | ---: |
| 2 | +0.24% | -2.92% | +9.72% |
| 3 | -0.74% | +0.48% | +0.48% |
| 4 | -16.95% | -6.57% | -6.37% |
| 5 | +20.09% | +5.03% | -12.70% |
| 7 | -7.14% | +0.66% | -29.57% |
| 8 | -9.74% | -2.17% | +263.16% |

All six flows in seed 129 now meet the delivery band. The remaining delivery exceptions are sources 4/5 in seed 128 and sources 5/7/8 in seed 130. Whole-network delivery is within 0.55% in each seed; pooling all three produces +0.320%. Only sources 2 and 3 meet ±10% in every seed. Four of six pooled flow-delivery ratios meet ±10%, but pooling must not hide a single-seed exception.

## Node 8: sustained relay backlog in native seed 130

The measurements distinguish original source 7 traffic relayed by node 8 from node 8’s own source 8 traffic. Occupancy means cover 300–6000 s. Completed first-submit/admission waits use the same lifecycle endpoints in each engine, but are different packet populations; right-censored waits remain separately recorded.

| Seed | Original source at node 8 | MATLAB mean retained apps | ns-3 mean NSDP apps | MATLAB mean pre-HOP wait (s) | ns-3 mean pre-HOP wait (s) | MATLAB / ns-3 owners at stop |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 129 | 7, relayed | 35.30 | 29.61 | 250.43 | 198.98 | 16 / 15 |
| 129 | 8, local | 16.00 | 16.00 | 175.73 | 173.13 | 16 / 16 |
| 130 | 7, relayed | 19.47 | 237.19 | 141.85 | 1029.12 | 31 / 318 |
| 130 | 8, local | 16.00 | 16.00 | 138.24 | 480.88 | 16 / 16 |

Native seed 130 enqueues 1,361 source 7 applications at node 8 and forwards 1,043 to HOP, leaving 318 waiting. MATLAB enqueues 778 and submits 747, leaving 31. Native node 8 ends with 334 waiting applications across these two sources: 318 relayed and 16 local. Native relay occupancy peaks at 361. This is a sustained arrival-versus-service imbalance, not a count of dropped packets.

Both engines keep node 8’s own NSDP population almost continuously at its 16-application limit. The limit is per original source/destination, not one shared 16-packet pool: relay source 7 owners do not directly consume source 8’s NSDP quota. They compete for downstream queue service and HOP capacity, delaying releases that admit the next local application. No explicit local-versus-relay priority branch was found in the retained source contracts.

Native seed 130 gateway routes have no changes after 103.09 s, before traffic starts at 300 s. The native backlog is not coincident with a later route switch. MATLAB observed DATA next hops consistently follow 7→8→2→4, but its final route snapshots and aggregate route-change counters cannot exclude every transient route change.

MATLAB also exhibits a local-suppression regime: in seed 129 during 2100–2400 s, node 8 admits only 6 local applications while 41 relayed source 7 applications enter HOP; relayed applications waiting for first submission average 84.55 applications. The much stronger native seed 130 regime therefore cannot by itself be labeled a unique native or MATLAB scheduling bug.

## Upstream adaptive admission window

Native 7→8 HOP admissions increase from 854 in seed 129 to 1,365 in seed 130. Their completion counts are 50 ACK / 799 DACK / 5 no-ACK versus 28 ACK / 1,333 DACK / 4 no-ACK. Mean completed HOP capacity retention, including the delayed DACK hold, is 20.45 s versus 21.41 s. The extra upstream traffic is not explained by shorter per-packet capacity retention.

At native admissions, the permitted outstanding threshold is mostly 2 in seed 129 (609/854 admissions, observed range 0–4). Seed 130 has 581 admissions at threshold 3, 430 at 5 and 202 at 7, with observed range 0–7. The effective permitted outstanding window is threshold +1. More admitted traffic at these larger window values is consistent with node 8 being fed faster than it can drain. This is an observed mechanism, not a controlled counterfactual proving the origin of the cross-engine gap.

A source-derived replay of MATLAB’s ordered callbacks reconstructs its threshold and ACK accumulator. In seed 130, 654 of 787 HOP admissions occur at threshold 1 or 2, and the reconstructed state spends 5,090 of 5,700 active-traffic seconds at those levels. All observed admissions satisfy reconstructed neighbor/global limits, and final DATA, DACK-hold and resend populations reconcile. These values are derived from the unchanged source rules and exported events; they are not additional hidden-state measurements. The contrast supports different adaptive-window histories, without demonstrating a mismatch in the update rules.

The exact pinned native HOP header was re-fetched and matches its previously audited SHA-256. Its adaptive rules agree with MATLAB: every third qualifying ACK grows the threshold up to 16; a retried ACK resets the ACK accumulator after the increment/test; DACK resets that accumulator without shrinking the threshold; final DATA failure decreases the threshold toward 0. Different event histories can therefore retain different permitted windows under the same rules. The known queued-retry timing distinction remains separate and was not changed.

## Source 4 disposition

Source 4 meets ±10% in seeds 129/130 (−6.57%,−6.37%); seed 128 remains −16.95%. The ratio of three-seed sums is −9.85%, which does not erase the seed 128 exception.

The delivery difference equals the admission difference minus the difference in applications still undelivered at stop. For 128,129,130 respectively: −71=−59−12; −28=+2−30; −29=−37−(−8). The gap therefore does not have one uniformly worse admission or completion component.

All 199 final source 4 MATLAB drops were linked to the same application’s final HOP failure:62/75/62 across the seeds, mainly at 4→5. Node 4 transmitter failures from relayed sources are kept separate. Native source 4 no-ACK completions at 4→5 still lead to 11 deliveries in seed 129 and 2 in seed 130, demonstrating why hop-level no-ACK events cannot be counted as end-to-end application drops.

For seed 129, source 4’s mean NWK-enqueue→HOP-admission wait at node 4 is 177.95 s in MATLAB and 177.66 s in ns-3; for 130 it is 173.97 s and 164.79 s. These observations do not justify a blanket source 4 queue-policy change.

## Engineering decision

Retain actual-tx, continuous timing and the existing PHY/ECC. T21 provides a reproducible diagnosis rather than a simulator patch. The practical network-delivery target is met in all three seeds; per-flow and delay parity remain qualified by the listed exceptions.

If another behavior tranche is pursued, make it a controlled 7→8 adaptive-window contract comparison: preserve initial state and ACK/retry/DACK/failure event order, then test whether the implementations update threshold, ACK accumulator and outstanding capacity identically. Use the observed seed 130 startup history to select the contract. Change production behavior only for a demonstrated contract mismatch; do not cap the window or retune PHY solely to force these three results to agree.

## Verification and limits

- All 376 issued source bindings and 98 reference bindings are unchanged; accepted 716/716 MATLAB tests are reused, not re-executed.
- Independent review recomputed all 63 revised-target comparisons and checked packet conservation, interval clipping, complete/censored ownership areas, receipt hashes, and native before/after state snapshots.
- Native traces contain 11,786,557 events across the three seeds and retain exact accepted raw hashes. Historical 128 lacks the detailed custody events needed for equivalent native occupancy reconstruction; unavailable measurements are not zero.
- MATLAB’s detailed admission prefix ends at 633.32 s. Full protocol generation records and complete counters support later admissions; omitted per-attempt blocking states are not invented.
- DACK releases NSDP before later HOP capacity release. Those endpoints and their population counts remain distinct.
- Native duplicate delivery events remain separate from unique application deliveries. Native unmatched sends alone do not identify terminal drops.
- Cross-engine packet identities and random draws are not paired. Conditional delay populations and pooled ratios remain explicitly labeled.
- No fresh OPNET runs, MATLAB runs or native runs were performed.

Detailed scripts, CSV tables, event joins, source bindings and independent review records accompany this report.
