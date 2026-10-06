# Retry ownership repair: bounded review checkpoint

Native reference: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. MATLAB base: `b644fae1bdb4ddffc539bf98a29560944e590c12`.

Hypothesis and evidence: terminal HOP failure incorrectly gave snapshots and REQUESTs additional NWK retry owners, while automatic UPDATE ownership was incorrectly capped at three cycles. Exhausted REQUEST state also blocked later explicit recovery. Native control handling distinguishes these origins (NWK header lines 3138-3183, 9388, 9576, 9596-9675, 10412-10579).

Change: retain residual NWK ownership only for automatic changes, without a fixed cycle cap; preserve unacknowledged active-peer pruning and packet sequence; expire REQUEST state after its final response interval. Snapshot timers and HOP reliability remain responsible for their own recovery.

Scope: three files under `diagnostics/relay-custody/node8case/+ac`, plus focused tests and evidence. Root `+csr` and older diagnostic checkpoints are unchanged. Historical FILES.json records describe their original snapshot, not this revision. The standalone candidate and this public diagnostic have identical repaired NWK, probe and wire-preflight files. The bounded candidate additionally contains an earlier idle-RTS TerminalMac correction; it is NOT included in this PR. Therefore its system metrics are supporting candidate evidence, not a benchmark of this exact repository closure.

Run `run_repair_checks(outputFolder)` from `diagnostics/relay-custody/node8case/retry-tests` in MATLAB with a new output folder. The tests use controlled callbacks and natural no-ACK HOP timers, not a calibrated full-network benchmark. See repository_checks.json for execution on the exact published source.

Bounded candidate validation: seed 320006, baseline and repaired 360 seconds each; multisection diagnostic 290 seconds. Network runs completed in 203.743, 216.745 and 129.137 wall seconds (about ten minutes including launch and monitoring). Pair configuration is identical after replacing the source-location field; referenced scenario files have identical SHA256. All frozen input hashes verified. Baseline's first 6,561 random-request rows match the preserved 6,000-second pilot byte for byte.

| Metric | Baseline | Repaired |
|---|---:|---:|
| Offered | 18,000 | 18,000 |
| Admitted | 297 | 294 |
| Unique delivered | 113 | 117 |
| Unresolved at cutoff | 184 | 177 |
| Raw dropped / pending | 4 / 180 | 4 / 173 |
| Delivered mean latency, s | 16.821985 | 14.729223 |
| Whole-window goodput, bit/s | 464.555556 | 481 |

First lifecycle divergence: after 422 identical records, at 50.1370000278 seconds baseline node 1 reacquires failed snapshot sequence 9 with new control ID 25; repaired source omits it. Automatic residual ownership remains observed. Application uniqueness, every relay-copy custody enqueue/submit/release, and live HOP control owners reconcile against counters; no required evidence was omitted. No resource threshold was crossed.

Regression/uncertainty: total deliveries +3.54% and latency -12.44% do not establish parity or statistical improvement. Source 4 deliveries fall 10 to 4 (-60%); source 5 rises 20 to 26; sources 2, 7 and 8 deliver zero at this short cutoff. The altered traffic changes subsequent contention and random draw consumption. A steady-state paired native benchmark remains unrun.

Multisection acceptance NOT MET: synthetic public-NWK priming at 220 seconds adds 64 destinations, and a synthetic REQUEST at 225 seconds causes node 1 to admit a two-section snapshot (sequence 17) to node 5. Neither section is received/ACKed by 290 seconds. Four HOP control owners remain at cutoff and reconcile correctly. No seed/horizon replacement was attempted. Offline unchanged-Reassembly replay reconciles all integrated completion counters, including declared synthetic inputs; it does not prove the missing snapshot completed. Overall bounded AUDIT.passed is false for this coverage gap, not an ownership assertion failure.

Audit corrections: initial offline MATLAB auditor failed because restoredefaultpath ran inside a nested-function static workspace; a helper scope fixed the auditor only. Initial configuration equality assertion included different absolute source paths; equality now requires identical scenario bytes before normalizing only that field. Network runs were not repeated or modified. Earlier component partial-ACK setup was corrected to emit its intended grouped update; the corrected case passed without implementation changes.

Next gate: obtain natural multi-section completion coverage and a prespecified native/MATLAB parity benchmark before claiming the full validation tranche passes. No PHY/ECC change, policy tuning, merge or auto-merge is part of this checkpoint.
