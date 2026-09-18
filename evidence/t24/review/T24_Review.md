# Tranche 24: campus custody census

**T24 is complete as an offline diagnostic. No new MATLAB run is required. Repeated custody entries do not account for the large node-8/source-7 backlog in the examined campus runs. Keep the current simulator default.**

## What was measured

T23 showed that a DACK-marked replay can create a second relay custody entry in native ns-3, while MATLAB accepts the replay without adding another owner. T24 follows that mechanism in the accepted 6,000-second, real-PHY campus traces for seeds 129 and 130. It reconstructs application identities, individual queue entries, downstream HOP admissions, NSDP releases, and later DACK capacity releases. Occupancy averages cover the active traffic window, 300–6,000 seconds.

The existing ±10% delivery and delay screen is unchanged. T24 supplies no new campus performance result and does not claim numerical parity.

## Node 8: the backlog consists of distinct applications

All source-7 relay entries at node 8 are unique within each run. There are no repeated enqueues, simultaneous duplicate owners, or repeat-owner service or capacity use at this node and flow.

| Seed | Engine | Source-7 entries at node 8 | Repeated entries | Submitted downstream | Custody remaining at stop |
|---|---|---:|---:|---:|---:|
| 129 | ns-3 | 849 | 0 | 834 | 15 |
| 129 | MATLAB | 810 | 0 | 795 | 16 |
| 130 | ns-3 | 1,361 | 0 | 1,043 | 318 |
| 130 | MATLAB | 778 | 0 | 747 | 31 |

The native seed-130 queue has 318 distinct waiting applications: 1,361 arrivals minus 1,043 downstream submissions. Its mean source-7 custody is 237.19 applications, versus 19.47 in MATLAB, exactly reproducing the earlier T21 measurements. In MATLAB seed 129, the 16 retained owners comprise 15 waiting applications and one already submitted application; those endpoints must not be conflated.

Node 8's local source-8 traffic also has no repeated queue entries in either engine. Native seed 130 admits 181 local applications and submits 165, compared with MATLAB's 654 and 638. Both retain 16 local owners at stop. The relay and local flows have separate NSDP accounting; they share downstream service and HOP capacity. The observed imbalance concerns distinct admitted traffic and its service history.

## Rare repeats elsewhere are real and receive service

Across the native network, 10 repeated relay entries occur in seed 129 and 9 in seed 130, at nodes 2, 4 and 5. All are created while an earlier owner of the same application is still retained. No application has more than two simultaneous owners at one node in these traces.

| Native census | Seed 129 | Seed 130 |
|---|---:|---:|
| All relay queue entries | 5,903 | 5,981 |
| Repeated entries | 10 (0.169%) | 9 (0.150%) |
| Direct same-HOP DACK replays | 6 | 5 |
| Repeats propagated from upstream copies | 4 | 4 |
| Repeated entries submitted downstream | 10 | 9 |
| Repeat completions: ACK / DACK / no-ACK | 8 / 2 / 0 | 7 / 1 / 1 |
| Repeat entries still owning NSDP or HOP capacity at stop | 0 | 0 |
| HOP capacity held by repeat entries, owner-seconds | 158.821 | 120.467 |
| Share of all-node DATA HOP capacity owner-seconds | 0.0619% | 0.0456% |

Capacity owner-seconds integrate retained DATA owners, including delayed DACK holds. They are not radio airtime. The repeat entries contribute 1,640.564 and 1,706.565 NSDP owner-seconds respectively. The strictly simultaneous extra-owner portions are 1,627.850 and 1,642.826 owner-seconds: a repeated entry can remain after the earlier entry releases, so the two measures are different.

The network-wide denominator does not hide a large measured burden within an affected flow: the largest repeat share of one node/source flow's HOP capacity owner-seconds is 0.487% in seed 129 and 0.716% in seed 130. The largest corresponding NSDP custody shares are 0.860% and 0.703%. These are observed occupancy shares, not bounds on a hypothetical delivery change.

This confirms that the T23 ownership difference can occur and consume downstream service in actual campus traces. Its observed burden is small here, and its direct contribution to the focused node-8/source-7 queue is zero. It does not justify an immediate production change. This census does not prove that removing downstream repeats would leave later stochastic event histories unchanged, and it cannot assign a final unique delivery to a particular duplicate owner.

The complete MATLAB traces have zero repeated queue entries at every node in both seeds. MATLAB's final duplicate-receive counters are all zero for seed 129; nodes 4, 5 and 8 each record one duplicate callback for seed 130. These aggregate counters do not identify the source, packet or time, and are not interpreted as additional queue owners.

## Verification and preserved scope

- Two independent native reconstructions inspect 11,338,973 ordered events. Enqueue/forward/feedback identities, NSDP snapshots, queue conservation, and capacity-release accounting reconcile. Results and raw repeat examples are included.
- The MATLAB census checks 1,241,622 protocol records against receipt-bound raw files, final queue counters and accepted T21 occupancy values. The original T20 return ZIP matches its accepted SHA-256.
- All 404 T23 source bindings, including 181 MATLAB files, remain unchanged. The NWK and HOP production files also match the T20 owner receipts. The 77-member T21 reference package passes its closed manifest check.
- Current ns-3 `main` was checked on 2026-09-18 and still matches `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, the accepted trace pin. The native engine pin remains `6b5cd24ea80713ce16d88575869aedd6f432bdae`.
- No fresh MATLAB, ns-3 or OPNET simulation was executed. Existing owner evidence came from MATLAB R2025a, 25.1.0.2943329, using the portable backend. No new regression-test execution or MATLAB release validation is claimed.
- Historical native seed 128 lacks the detailed custody telemetry needed for this census. Its omitted measurements are unavailable, not zero.
- Unfinished lifetimes are right-censored at 6,000 seconds. A HOP no-ACK completion is not automatically an end-to-end application drop. DACK releases NSDP before its later HOP capacity release.
- PHY/ECC, continuous timing, the `actual-tx` retry policy, admission thresholds and queue behavior remain unchanged. No repository publication is part of T24.

## Engineering decision and next useful test

Retain the T23 custody difference as a documented behavior discrepancy. Do not implement duplicate ownership in MATLAB solely to address the node-8 campus gap: there are no duplicate entries at that location to explain it in either examined native run, and T22/T23 already found agreement in the controlled sender-window and feedback decisions.

The next useful performance test is a bounded extension of the unchanged campus ensemble: two new, predefined seeds, 131 and 132, retaining the accepted results for 128–130. Compare per-flow admission, unique delivery and conditional delivery delay; keep the existing ±10% individual-seed flags and add pooled ratios and uncertainty across seeds. This would test whether the source-7/source-8 imbalance persists across histories. Matching scenario and nominal seed does not pair the engines' random draws, and five seeds alone would not establish statistical equivalence. T25 is a recommendation; its runs have not been started or packaged in this tranche.

## Files and reproduction

`analysis/custody_census.py` reconstructs native owner lifetimes and service; `analyze_matlab.py` checks MATLAB ownership; `review/` contains the independent reconstruction and gate review. The package also contains the derived CSV/JSON evidence, pinned source snapshots, input verification, updated parity ledger and reproduction instructions. All work is analysis tooling; the accepted simulator installation requires no update.
