# T21: source-4 delivery shortfall

This is an offline diagnostic of the accepted T20 return and reused T19 default run. No model, default, PHY/ECC setting, or simulation output was changed; no simulation was run. The working delivery-parity band is now ±10%.

Source 4 falls within that band for seeds 129 and 130. Seed 128 remains outside it. The ratio of three-seed delivery sums is −9.85% (1,172 MATLAB versus 1,300 unique ns-3 deliveries); that pooled result must not replace the individual-seed results.

| Seed | MATLAB deliveries | Unique ns-3 deliveries | Residual | MATLAB admissions | ns-3 admissions | MATLAB undelivered | ns-3 undelivered |
|---|---:|---:|---:|---:|---:|---:|---:|
| 128 | 348 | 419 | −16.95% | 439 | 498 | 91 | 79 |
| 129 | 398 | 426 | −6.57% | 503 | 501 | 105 | 75 |
| 130 | 426 | 455 | −6.37% | 512 | 549 | 86 | 94 |

Here “undelivered” means admissions minus unique deliveries at the 6,000-second stop. MATLAB provides separate final dropped and pending states; native unmatched sends must not be called losses without further trace attribution.

The exact accounting identity is **delivery difference = admission difference − undelivered difference**:

- Seed 128: **−71 = −59 − 12**. Both fewer admissions and more undelivered applications contribute.
- Seed 129: **−28 = +2 − 30**. Admissions are nearly equal; the gap is in end-of-run delivery completion.
- Seed 130: **−29 = −37 − (−8)**. Fewer admissions account for the delivery shortfall; MATLAB actually has fewer undelivered applications and a slightly higher delivered/admitted fraction (83.20% versus 82.88%).

The three runs therefore do not support one uniformly worse admission or delivery-success mechanism. They establish a directional delivered-count shortfall for source 4, with different accounting contributors across seeds.

## Original source versus failing transmitter

Source 4 is not equivalent to node 4. Node 4 also forwards sources 2, 7, and 8. The script joins MATLAB HOP episodes to the original application source and final application outcome.

| Seed | All node-4 HOP failure episodes | Source-4 final drops on 4→5 | Source-4 final drops on 5→1 | Total source-4 final drops | Source-4 pending applications |
|---|---:|---:|---:|---:|---:|
| 128 | 310 | 58 | 4 | 62 | 29 |
| 129 | 314 | 69 | 6 | 75 | 30 |
| 130 | 323 | 58 | 4 | 62 | 24 |

All source-4 final drops are `retry_exhausted` and match a same-application HOP failure at the final application timestamp. Seed 130 has one further source-4 `hop_failed` on 5→1 whose final application outcome is delivered, so it is excluded from the final-drop columns. Likewise, the seed-128 node-4 total of 310 HOP failures includes a relayed source-8 application ultimately delivered; the earlier 309 terminal retry drops at that transmitter were a different, correctly narrower count.

## Where MATLAB source 4 waits

| Mean completed wait, seconds | Seed 128 | Seed 129 | Seed 130 |
|---|---:|---:|---:|
| Local NWK enqueue at node 4 → first HOP submission | 207.33 | 177.95 | 173.97 |
| HOP admission at node 4 → first owned actual-TX callback | 2.30 | 2.24 | 2.33 |
| Relayed NWK enqueue at node 5 → first HOP submission | 56.18 | 58.79 | 68.74 |
| HOP admission at node 5 → first owned actual-TX callback | 22.47 | 21.42 | 22.56 |

These are separate event populations and must not simply be added to derive delivered latency. Unsubmitted and unsent episodes are right-censored at 6,000 seconds and recorded separately in `source4.json`.

Source-4 local NWK custody at node 4 averages 15.999 of 16 entries during the active 300–6,000-second interval in each seed. The local admission gate is consequently almost continuously occupied. The much longer NWK waiting interval identifies pre-HOP service/admission as the main observed residence time; it does **not** establish incorrect service ordering or a causal parity defect. HOP retry exhaustion remains the principal terminal-loss location for this source, mostly at 4→5.

The independent T21 native trace reconstruction allows directly matched event definitions for seeds 129 and 130:

| Source-4 observation at node 4 | MATLAB 129 | ns-3 129 | MATLAB 130 | ns-3 130 |
|---|---:|---:|---:|---:|
| Local admissions | 503 | 501 | 512 | 549 |
| NWK → first HOP submissions | 488 | 485 | 497 | 533 |
| Mean completed NWK enqueue → first HOP submission, s | 177.95 | 177.66 | 173.97 | 164.79 |
| Mean HOP admission → ACK/DACK/failure, s | 6.81 | 5.59 | 6.65 | 5.38 |
| Local NSDP/custody mean during 300–6,000 s | 15.9986 | 15.9985 | 15.9985 | 15.9984 |

The HOP row ends at ACK, DACK, or failure (`hop_admission_to_nsdp_release_completion_s` in the native diagnostic); it excludes DACK-held capacity after DACK. It must not be compared with a capacity-retention metric that includes that hold. The nearly identical seed-129 queue wait and admission counts do not support a large pre-HOP service defect for source 4 in that seed.

The independent native packet-lineage check now resolves one part of the completion difference:

| Source-4 native completion on 4→5 | Seed 129 | Seed 130 |
|---|---:|---:|
| `no_ack` completions | 66 | 60 |
| Subsequently delivered uniquely to the gateway | 11 | 2 |
| Undelivered at the stop | 55 | 58 |

All 11 and 2 first gateway deliveries occur **after** the corresponding upstream `no_ack` completion. These are same-run original-source/destination/application-sequence joins, with event indices and timestamps retained. Native `no_ack` completions therefore cannot be classified directly as terminal application drops. In the corresponding MATLAB runs, all 69 and 58 source-4 failures on 4→5 remain dropped at the stop. This observation is consistent with the already identified difference in retry expiration and later transmission handling, but it neither proves that difference caused every delivery gap nor justifies changing the accepted default. The native applications labelled undelivered may be pending or lost; no unsupported terminal-state split is made.

## Engineering disposition

Keep the accepted default and PHY/ECC unchanged. Source 4 merits a retained exception for seed 128 and continued per-seed tracking under the ±10% goal. A code fix is not justified from these counts alone. Before any experiment targeting source 4, compare native source-labelled queue-to-HOP service, terminal retry disposition, and DACK-held capacity with these exact MATLAB populations. A candidate change must explain the differing seed-128 admission gap and seed-129 completion gap without regressing seed 130. The node-8 investigation remains a separate question; node-4 transmitter losses cannot be used as source-4 evidence without lineage.

## Reproduction and boundaries

Run from the workspace root:

```sh
python3 t21-work/source4/analyze_source4.py --native-root t21-work/native
```

Inputs and SHA-256 values are recorded in `source4.json`. The script uses accepted T20 ownership episodes plus the original returned application inventories, and includes the independent T21 native reconstruction when `--native-root` is supplied. It checks the exact accounting identity and accounts for every final source-4 MATLAB drop. It does not join packet identities between engines, infer unexported queue state, classify native unmatched sends as drops, or claim statistical equivalence from three seeds.
