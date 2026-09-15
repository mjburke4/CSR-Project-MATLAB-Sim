# Tranche 11 replay residual review

The repaired owner run completes the focused milestone: **52/52 MATLAB tests, 56/56 structural checks, and 32/32 applications delivered and released**. The strict replay remains unmatched because two state snapshots differ. This review did not execute MATLAB or change source.

## Exact residual

| Case | CSV data row | Case order | Time (s) | Observation | MATLAB counter | Native counter |
|---|---:|---:|---:|---|---:|---:|
| slow | 1283 | 437 | 2.011501 | Gateway ingress_before, source 3 app 4 | 15 | 16 |
| slow | 1284 | 438 | 2.011501 | Gateway ingress_after, source 3 app 4 | 15 | 16 |

These are the only differing fields across 1,756 paired event rows. Every exported timestamp is exactly equal, as are all 133 raw/resolved draw rows and 12 tape usage rows. The before/after observations belong to one incoming DATA frame, so this is one boundary-order incident represented by two rows.

## Source-backed cause

The sender starts DATA at 1.989 s. A 48-byte wire payload, short preamble, and rate key 128 yield 22.5 ms modeled airtime; propagation is 1 microsecond. In native integer time, arrival lands at **2.011501 s**, exactly on a gateway 13 ms tick. Arrival was queued during the transmission at 1.989 s; that tick was queued later, at 1.998501 s. The native scheduler uses insertion UID for equal timestamps, so arrival sees counter 16, then the tick decrements it to 15. Native differential event 287 records counter 16 at 1.998501 s and event 290 records counter 15 at 2.011501 s.

MATLAB's MAC clock uses an integer-nanosecond epoch, but the replay transport schedules ingress with `Now + duration + propagation`. Reconstructing those source expressions in IEEE-754 binary64 gives:

| Expression | Binary64 seconds |
|---|---:|
| Computed airtime | 0.022500000000000003 |
| Gateway tick | 2.011501 |
| Controlled ingress | 2.0115010000000004 |

Arrival is one ULP, **4.440892098500626e-16 seconds**, after the tick. MATLAB's scheduler compares the actual double values before considering insertion order, so both ingress snapshots see 15. Rounding observations to integer nanoseconds conceals that offset. This is a high-confidence explanation from the source, native tick trace, and numerical reconstruction; the owner archive does not contain raw scheduler doubles, and no instrumented MATLAB rerun was performed.

Source locations: `+csr/+validation/replayContract.m` controlled transmit/ingress scheduling and observation; `+csr/+mac/Layer.m` `scheduleSlotTick` and `slotTick`; `+csr/+sim/EventScheduler.m` `precedes`; `+csr/+phy/airtime.m` and `rateDefinition.m`; `scripts/ns3/tranche11_replay.cc` `Transport`; pinned native `csr-mac-core.h` `SlotTick`; pinned engine `scheduler.h` equal-time UID comparison. The JSON review binds the package sources and traces by SHA-256.

## Significance

No difference appears in the subsequent ACK transmissions at **2.219501 s**, capacity releases at **2.244042 s**, or deferred wakes at **2.244042028 s**. All four cases have identical recorded transmission, admission, blocking, release, and final pending outcomes. The shared raw draws and occupancy-probe resolutions agree completely.

The discrepancy should remain visible. Reception also resets a neighbor reservation and the same tick decrements neighbor counters; reversing those operations can leave an unexported neighbor counter one slot apart. Thus this is a real clock-boundary ordering difference with no observed downstream effect in the four cases, rather than proof that all hidden state is identical. It may matter under another workload.

The result supports the controlled MAC/HOP DATA-to-ACK-to-capacity-release chain under matched draws. It does not establish production NWK admission, real RF/half-duplex behavior, adaptive radio decisions, campus parity, or stochastic equivalence. Keep strict `MatchesNative=false`; the full acceptance gate was intentionally not run.

## Next milestone

Proceed to a short **4 -> 5 -> 1** relay/local contention benchmark. T10 showed opposing delivery changes for sources 4 and 5, making node 5's sharing of service between local and relayed traffic the useful next question.

1. Carry an exact ingress/tick tie and +/-1 ns microcase into the next fixture. Determine whether controlled link scheduling should explicitly use native integer-nanosecond time; do not globally round the continuous scheduler or alter production MAC semantics to erase these rows.
2. Compare relay-only, local-only, and mixed traffic with shared raw draws and actual production NWK admission/custody. Record original application source, node-5 queue/service selection, per-neighbor outstanding work, ACKs, capacity release, and delivery.
3. Once the deterministic chain agrees, run a small fixed multi-seed set with real receiver/transport behavior. A further 6,000-second campus run can follow a demonstrated mechanism or correction.

No production correction is justified solely by this return, and no additional long run is needed to interpret it.
