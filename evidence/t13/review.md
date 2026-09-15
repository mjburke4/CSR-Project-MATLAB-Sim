# Tranche 13: fresh-install MATLAB return review

**The focused structural milestone passes. Exact MATLAB/ns-3 trace parity remains open.** The returned archive records a completed MATLAB R2025a portable run with 88/88 tests, 264/264 structural checks, and all 384 scheduled applications delivered. No simulator source change or repeat of this same run is needed to establish that result.

## Verified execution and provenance

| Check | Result |
| --- | --- |
| Owner runtime | MATLAB 25.1.0.2943329 (R2025a), portable backend |
| Run interval | 2026-09-15 11:55:48.950–11:59:15.844 UTC |
| Elapsed time | 206.894 seconds, about 3 minutes 27 seconds |
| MATLAB tests | 88 passed, zero failed or incomplete |
| Focused structural checks | 264 passed across four 64-second cases |
| Source inventory | 271 files, including 138 MATLAB files; unchanged during execution |
| Reference inventory | 198 files; unchanged during execution |
| Tranche 12 baseline | All 259 source bindings, including 135 MATLAB files, unchanged |
| Earlier accepted core | All 225 source bindings, including 124 MATLAB files, unchanged |
| Owner ZIP | 12 members; 11 inventoried artifacts plus metadata |

The delivered evidence gate and independent inventory/service reviews checked the actual return against the exact standalone package. The candidate, input plan, native reference and full-width integer bitmaps are preserved. The reviewer did not execute MATLAB or rerun native ns-3; the MATLAB result is the owner's execution, compared with the previously executed native reference.

## Loss and recovery outcomes

Both simulators generated, admitted and delivered the same 96 application identities in each case. Every case has 144 HOP custody completions: 139 ACK and five DACK custody outcomes. Across all cases, that is 556 ACK and 20 DACK completions, with no failed terminal or unexplained application.

| Case | MATLAB delivery | ns-3 delivery | DATA retransmissions, both | Lost receiver groups, both |
| --- | ---: | ---: | ---: | ---: |
| No loss | 96/96 | 96/96 | 0 | 0 |
| DATA loss | 96/96 | 96/96 | 2 | 2 |
| ACK loss | 96/96 | 96/96 | 0 | 2 |
| Relay-link blackout | 96/96 | 96/96 | 2 | 2 |

Continued source-4 demand encounters DACK-held capacity, then admission resumes as capacity becomes available. At the final horizon, MAC ACK/DATA queues, HOP resend entries and DACK holds, and NWK DATA custody/waiting are empty. Excluded bootstrap control work remains reported at nodes 1/4/5 as 2/2/3 pending controls in each case; this is not an all-control-queues-drained result.

The ACK-loss case recovers through cumulative feedback without a DATA retransmission. The blackout's actual lost frames are two DATA frames on 5 → 1; the configured bidirectional policy does not establish that every direction was exercised. These remain controlled links with fixed routes and radio settings, not an RF, routing-reconvergence, node-reboot or campus benchmark.

## What still differs

The reported **12,091 unmatched rows** are positional trace-comparison results, not failed applications or 12,091 separate protocol faults. Known timing offsets, feedback labels, and shifted row positions contribute. The strict comparison is retained without increasing its tolerance.

For the no-loss, ACK-loss and blackout cases, all application admission times match and every application delivery is 28 ns earlier in MATLAB. ACK-loss additionally has five gateway feedback transmissions and one node-5 terminal completion about 13 ms later in MATLAB; the application delivery results remain as stated. MATLAB labels some feedback as DACK where native labels it ACK while retaining the same feedback bitmaps; those labels remain explicit differences.

The **DATA-loss case has a substantive service-timing residual**. MATLAB emits four additional feedback segments and consumes seven additional prescribed draws, with no additional DATA retransmission. Fourteen admission times differ: nine source-4 admissions are 20 ms earlier, while five source-5 admissions are 40–220 ms later. Mean generation-to-delivery latency increases by approximately 71.24 ms for source 4 and 84.84 ms for source 5. The largest per-application delivery difference is **408.759972 ms later in MATLAB**, for source 5, application 21. Eleven downstream HOP sequence assignments also change as relay and local traffic are interleaved differently; all application identities and terminal outcomes still agree.

The first observed service-changing boundary is near 3.144961 seconds. MATLAB transmits gateway ACK sequence 2, bitmap 3, before processing new DATA from source 5/application 3. Native processes the DATA first and transmits updated ACK sequence 3, bitmap 7. Source 5 therefore receives that updated feedback later in MATLAB, and its admission of application 19 moves from 3.18 to 3.22 seconds.

Source arithmetic reproduces a continuous arrival one binary64 step after the nanosecond-anchored MAC tick: `3.1449610000000003` versus `3.144961`. This is a source-backed explanation consistent with the observed order, not a directly recorded subnanosecond MATLAB timestamp. The owner CSV rounds times to nanoseconds. This one-ULP effect and the separate 28-ns startup phase offset must not be conflated.

## Next milestone

Isolate the **DATA-arrival/ACK-transmit boundary** before increasing fault complexity. Record full-precision MATLAB event times and event insertion order, exercise arrival just before, at, and just after the ACK opportunity, and replay the actual mixed ACK/DATA aggregate. Compare any localized transport-timing experiment against the unchanged baseline, then rerun Tranche 13 to measure whether service timing improves without changing delivery or custody behavior. No global scheduler, PHY/ECC, radio policy or comparison-tolerance change is justified by this return alone.

This review establishes focused structural completion. The full regression/campus gate and general numerical parity have not been rerun or established by these tests.

## Evidence identity

- Owner `t13(1).zip`: `82fb77cc5724f79f554e7c0d91169e79d89da5b47713064f003d380a2fd7d9b1`
- Delivered `csr13.zip`: `58927369d49317bdcf90ba53c2127a6bbd43743fe0671de61c7878dbeeaf4de1`
- Candidate: `3c9ba4a9d9029180b82611d71dcbb01ac6cd2ddc273ee6ecf6dec36ba81881e0`
- Source snapshot: `205a86d0ae163b7a9fbeb13c2d003900af23df26c1e3be6cb0016505d4d55fc3`
- Native CSR source: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`
- ns-3 engine: `6b5cd24ea80713ce16d88575869aedd6f432bdae`

`t13ok.zip` preserves the original return, the detailed gate output, independent audits, service comparisons, the boundary reconstruction, and the updated parity ledger. The delivered simulator package remains unchanged.
