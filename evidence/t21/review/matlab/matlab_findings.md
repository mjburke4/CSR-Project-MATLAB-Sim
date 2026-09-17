# T21 MATLAB node-8 trace analysis

No new simulation or simulator source change. Receipt hashes, all read owner artifact hashes, the full protocol rows used by the ownership episodes, and HOP/NWK ownership endpoints were checked.

| Seed | Cohort at node 8 | NWK admissions | HOP admissions | HOP sends | DACKs | Mean NWK custody (apps) | Mean awaiting first submit (apps) | Mean HOP capacity (apps) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 128 | Relayed 7 | 722 | 707 | 962 | 610 | 20.694 | 20.422 | 2.551 |
| 128 | Local 8 | 588 | 572 | 748 | 317 | 15.998 | 15.780 | 1.388 |
| 129 | Relayed 7 | 810 | 795 | 1030 | 661 | 35.304 | 35.016 | 2.716 |
| 129 | Local 8 | 526 | 510 | 684 | 283 | 15.999 | 15.796 | 1.246 |
| 130 | Relayed 7 | 778 | 747 | 1016 | 645 | 19.472 | 19.190 | 2.711 |
| 130 | Local 8 | 654 | 638 | 870 | 406 | 15.998 | 15.751 | 1.772 |

Means cover the active traffic window 300–6000 s. Counts of HOP sends include retries.

The local source-8 NWK population averages 15.998 applications in every seed, nearly continuously filling its own 16-application NSDP cap. Relayed source-7 custody is additional; the source code counts NSDP by source and destination rather than by total queue size. Node-8 relay custody averages 20.69, 35.30, and 19.47 applications for seeds 128–130, respectively. Most of both cohorts’ custody residence is waiting for first HOP submission.

All observed DATA HOP admissions use 7→8, 8→2, and 2→4. Both node-8 neighbors activate before traffic starts and none deactivate. This does not prove absence of transient route changes: only whole-run RouteChanges counts and final route snapshots are available.

Seed 130 MATLAB admits 654 local source-8 applications and 802 source-7 applications, versus 181 and 1,381 in ns-3. MATLAB node 8 therefore does not reproduce the native seed-130 local-traffic suppression. A larger native relay queue delaying local-capacity release is a hypothesis to test against native occupancy and service traces; these MATLAB observations alone do not establish its cause.

The CSV gives every 300-second cohort window at nodes 2, 7, and 8. The JSON includes complete/censored waits, DACK capacity holds, endpoint states, raw evidence hashes, and routing limits.

## Limits

- No MATLAB or native simulation was executed; all three MATLAB seeds reuse accepted evidence.
- The first 100,000 application attempt records end at about 633.32 s; no omitted per-attempt NSDP/route states are reconstructed.
- Complete per-flow admission counters and full protocol app_generate events determine all-time admissions. Scheduled attempts and admitted counts determine per-bin blocked totals; blocked-reason timing is not inferred.
- NWK custody, pre-first-submit wait, HOP capacity, and DACK hold occupancy are distinct quantities; integrals are application-seconds clipped to the observation horizon.
- Waiting intervals without a submit or release are right-censored at 6000 s. Completed-only wait distributions exclude censored intervals; occupancy includes them through stop. Pre-submit residence does not by itself identify capacity blocking: omitted per-attempt reasons are not available.
- Callback-derived occupancy is not hidden queue polling and does not establish instantaneous admission availability. An observed HOP sent callback is a DATA member service event, not a unique packet or whole-radio transmission.
- RouteChanges counters and final route snapshots exist, but route-change callbacks are not exported. Stable observed DATA next hops cannot establish that no transient route changes occurred.
- NSDP checks count own-source/destination NWK custody, while relay custody and HOP capacity are separately accounted. Occupancy alone does not prove a scheduling bias or code defect.
- Cross-engine packet identities and RNG sequences are not joined; three seeds are a descriptive variability screen, not a confidence or equivalence test.
