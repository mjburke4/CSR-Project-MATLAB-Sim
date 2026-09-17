# Native findings for T21

The strongest seed-130 difference is sustained accumulation of relayed source-7 traffic at node 8. The source-7 offered load to node 8 exceeds its onward service, while local source-8 packets wait in the same NWK queue. The observations do not demonstrate an explicit scheduling preference or justify changing a policy yet.

| Native node-8 measure | Seed 129 | Seed 130 |
|---|---:|---:|
| Relayed source-7 enqueues | 849 | 1,361 |
| Relayed source-7 HOP admissions | 834 | 1,043 |
| Relayed source-7 pending NWK packets at stop | 15 | 318 |
| Local source-8 enqueues | 528 | 181 |
| Local source-8 HOP admissions | 512 | 165 |
| Local source-8 pending NWK packets at stop | 16 | 16 |
| Shared NWK queue mean, 300–6,000 s | 45.08 | 252.71 |
| Shared NWK queue maximum | 73 | 377 |
| Relay source-7 NSDP mean | 29.61 | 237.19 |
| Relay source-7 NSDP maximum | 57 | 361 |
| Local source-8 NSDP mean | 16.00 | 16.00 |
| Source-7 enqueue → first HOP admission mean | 198.98 s | 1,029.12 s |
| Source-8 enqueue → first HOP admission mean | 173.13 s | 480.88 s |

Local source-8 NSDP stays close to its limit of 16 in both seeds. Waiting before HOP admission dominates the extra observed residence in seed 130. Native source-8 admissions fall from 69 during 300–600 s to no admissions in 2,400–3,000 s and 3,900–5,100 s. This occurs without a contemporaneous gateway-route change: all reported gateway-route changes finish before traffic starts at 300 s (last change at 118.18 s for seed 129 and 103.09 s for seed 130).

The native 7→8 link also permits more concurrent service in seed 130. HOP admissions increase from 854 to 1,365; terminal feedback is 50 ACK / 799 DACK / 5 no-ACK in seed 129 and 28 ACK / 1,333 DACK / 4 no-ACK in seed 130. Completed capacity-hold mean, including delayed DACK expiry, is similar: 20.45 versus 21.41 seconds. Admission-time outstanding thresholds differ substantially: seed 129 is mostly threshold 2 (609 of 854 admissions), while seed 130 uses threshold 3 for 581 admissions, threshold 5 for 430, and threshold 7 for 202. This supports investigating the evolution of that threshold and its dependence on event history; it is not proof that its update rule differs between MATLAB and ns-3.

Unique delivered-application totals and delay are preserved below. First-delivery means exclude applications still unmatched at stop and therefore are subject to censoring.

| Native seed | Source 7 admitted / delivered | Source 7 mean delay | Source 8 admitted / delivered | Source 8 mean delay |
|---|---:|---:|---:|---:|
| 128 | 803 / 574 | 777.85 s | 621 / 462 | 645.37 s |
| 129 | 870 / 604 | 767.67 s | 528 / 368 | 646.59 s |
| 130 | 1,381 / 771 | 1,563.02 s | 181 / 133 | 1,054.74 s |

Seed 129 has six extra delivery events: five from source 7 and one from source 4. Seed 130 has four: one from source 7 and three from source 2. These events do not inflate the unique totals above.

The source-4 follow-up has an additional accounting distinction. At native node 4, 11 of 66 source-4 no-ACK completions in seed 129 and 2 of 60 in seed 130 nevertheless have a subsequent unique delivery at the gateway. The completion-outcome CSV records exact application identity and both timestamps. Treating every sender retry exhaustion as terminal application failure would discard valid downstream custody. This finding warrants comparison with MATLAB's existing application-status handling before modifying retry behavior.

The three streaming passes cover 447,584, 5,049,318 and 6,289,655 raw events. The detailed traces reconcile with zero NSDP-snapshot mismatches, zero NWK-queue snapshot mismatches, zero unmatched enqueue/admission/completion joins, and zero unmatched actual capacity releases. Native and MATLAB are independent random executions; these observations locate a difference in queue development and upstream service history, not a proven counterfactual cause.
