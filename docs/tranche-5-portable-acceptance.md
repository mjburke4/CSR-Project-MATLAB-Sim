# Tranche 5 portable acceptance

**Accepted for the bounded portable R2025a research-tooling scope at MATLAB
code `536b288`:** 367/367 tests passed, all 18 planned sweep cases completed,
and the retained 11 T4, eight T3 and nine T2 scenario exports completed.
All five shared MATLAB/ns-3 application comparisons pass using this returned
run. Acceptance establishes working research tooling and structural checks;
the sweeps expose delivery and outage-recovery limitations that remain open.

## Execution and integrity

| Check | Verified result |
| --- | --- |
| Owner runtime | MATLAB R2025a `25.1.0.2943329`, portable backend |
| Execution | 2026-09-09 17:57:20.558–18:17:16.677 UTC; 1196.119 seconds (19 minutes 56 seconds) |
| Portable tests | Exact 367 method names in 29 classes; zero failed or incomplete; 151.264 seconds summed method time |
| Source identity | All 116 source/data/tooling hashes match committed `536b288`, including all 88 MATLAB files and the exact candidate manifest |
| Returned archive | 551 files; all 550 top-level artifact hashes and byte counts verified |
| Nested evidence | 29 case manifests, 295 declared CSV row counts and all nested inventories verified |
| Local objects | 48 MAT files listed as retained on the execution machine; not independently inspected |
| Shared application comparison | Five comparisons passed for this return: 15/15 applications, matching generation identity/time, payload, DSCP and delivery |

The original `tranche5_evidence.zip`, selected CSV/metadata/logs, repaired
analysis, initial analysis failure and five comparison reports are preserved
in `evidence/tranche-5-r2025a-accepted/`. The
[structured acceptance](../evidence/tranche-5-portable-acceptance.json) binds
their hashes. The
[independent integrity review](tranche-5-return-integrity-review.md) checks
the uploaded files against the exact candidate rather than the later review
commit. The original candidate is retained byte-for-byte as
`evidence/tranche-5-validated-candidate.json`.

The comparisons reuse the retained ns-3 reference evidence at
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; no new ns-3 simulation or full
rebuild occurred. Application equality does not certify full protocol timing.
The 500/1000-kbps comparisons remain separately labeled extensions.

## Measured sweep outcomes

Each row combines the same three seeds, 128/129/130. Each parameter is changed
within its own controlled fixture family. Maximum latency is among delivered
applications only; it excludes dropped packets and is not a complete utility
or robustness score.

| Experiment | Delivered / generated | Drops | Maximum delivered latency (s) |
| --- | ---: | ---: | ---: |
| Offered-load multiplier 1 | 48 / 48 | 0 | 2.901 |
| Offered-load multiplier 2 | 90 / 90 | 0 | 4.625 |
| Offered-load multiplier 4 | 171 / 174 | 3 | 4.981 |
| Recovery freshness 60 s | 15 / 15 | 0 | 135.940 |
| Recovery freshness 180 s | 6 / 15 | 9 | 29.601 |
| Recovery freshness 300 s | 6 / 15 | 9 | 3.024 |

Across the 18 sweeps, **357 applications were generated, 336 delivered and
21 dropped through `retry_exhausted`; none remain pending**. Physical pending,
HOP pending DATA and NWK application custody are also zero. Queue admission
and control-backlog rejections are zero. The highest-load losses occurred
at seed 129 (56/58 delivered) and seed 130 (57/58); seed 128 delivered 58/58.
These runs expose a load sensitivity without establishing a saturation limit.

The recovery receive blackout is fixed at 405–540 seconds; scheduled
rediscovery starts at 576 seconds. In every 180- and 300-second freshness run,
the first three applications, generated at 450/486/522 seconds, exhaust
retries during the blackout. Only the two later applications deliver. The
60-second freshness setting retains all five for eventual delivery but has
substantial churn and delay. Longer timeouts reduce neighbor deactivations
and route changes in these fixtures, while retaining stale paths long enough
for queued transmissions to exhaust their retries. The lower survivor-only
latency therefore does not establish an improvement.

See the [independent outcome review](tranche-5-return-outcomes-review.md) for
trace reconstruction, parameter isolation and per-seed findings. The Python
report summarizes seed observations with equal weights and no confidence or
equivalence claim. Its mean of run-level latency metrics is not a pooled
packet quantile.

## Stop-boundary control ownership

All three 300-second freshness cases expire a neighbor and enqueue new
routing/discovery work at exactly **900 seconds**, the simulation stop time.
Each ends with one HOP control owner/target, one shared resend entry and two
NWK control messages. This is recorded unfinished control work at the horizon;
the evidence does not show a DATA deadlock or certify eventual control drain.

The existing `DataDrained` field conservatively requires *all* shared HOP
resend entries to be zero, including CONTROL entries. Its false value in
these three cases is retained. Application pending, HOP pending DATA and
NWK application custody are zero. `ControlsDrained` and `OwnershipDrained`
also remain false. No measured flag or trace was changed to make the run
appear drained. Fifteen other sweep cases report drained ownership.

## Review-tool repair and next work

The first Python analysis rejected valid integral file sizes written in
MATLAB JSON exponent notation. Review-tool commit `7109ae0` repairs numeric
parsing without changing hashes, byte checks, source checks or MATLAB code.
The complete Python suite passes 75/75 tests, including 28 analyzer tests.
The repaired analyzer completes on the original, untouched return. See the
[repair record](tranche-5-r2025a-evidence-review-repair.md).

**No MATLAB rerun is required for this Python-only repair.** Keep the
`536b288` ZIP as the validated MATLAB baseline. The accepted source still
preserves PHY/ECC and all protocol/simulator behavior from the merged T4 base.

The next material target is the interaction between stale routes and
retry/custody handling during outages. Compare the same controlled blackout
against the pinned ns-3 behavior before selecting a protocol correction;
preserve PHY/ECC. R2026a, optional native tests and 6000-second synthetic
workloads remain unexecuted gates. Full ACK-feedback adaptation, native packet
transport, historical generator/OPNET equivalence and full protocol timing
also remain separate work. Battery, supervisory behavior and BBN routing
remain excluded. Acceptance is recorded locally; no Tranche 5 PR is open.
