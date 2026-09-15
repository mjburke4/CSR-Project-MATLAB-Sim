# Tranche 6 portable acceptance

**Accepted for the bounded portable R2025a NWK freshness correction at code
`21c0a3f024c9efffdbd11c8059f1540a67c19b1a`.** The owner's return passes all
380 tests, 18 sweeps and 28 retained scenarios, with complete application
accounting and no duplicate application deliveries. **Outage-performance
acceptance remains qualified: 60-second delivery regresses from 15/15 to
13/15.** The correction does not establish improved or autonomous recovery.

## Runtime and provenance

| Check | Verified result |
| --- | --- |
| Owner runtime | MATLAB R2025a `25.1.0.2943329`, portable backend |
| Execution | 2026-09-10 11:43:32.984–11:56:48.742 UTC; 795.758 seconds |
| Tests | 380/380 passed, including 13 outage tests; zero failed/incomplete |
| Retained scenarios | 11 T4, eight T3 and nine T2 exports; 28 total |
| Sweeps | All 18 planned configurations; seeds 128/129/130 |
| Source | All 127 files, including 90 MATLAB files, match both `21c0a3f` and the delivered candidate ZIP |
| Returned evidence | 552 ZIP members; 551 unique artifact hashes/sizes, 1,716 nested inventory assertions and 295 CSV row-count assertions verified |
| Source snapshots | 35 snapshots; 4,408 hash assertions verified |
| Shared application comparison | Five strict comparisons pass, with 15/15 generated and delivered applications |
| Excluded local objects | 48 MAT files retained on the execution machine; their bytes were not provided or inspected |

The [independent integrity review](tranche-6-return-integrity-review.md)
binds the return to the validated candidate. Nested T3/T4/T5 metadata labels
identify retained harnesses executing T6 source. The T4 live diary is excluded
from its own inventory and covered by the final enclosing inventories.
The immutable sweep plan's planned status is superseded by separate completed
case evidence; no original metadata was edited.

## Measured outcomes

Each row combines the same three seeds. All 18 configurations and all 357
application identities match the exact accepted T5 archive. Latency maxima
below include delivered packets only.

| Experiment | T5 delivered | T6 delivered | T6 drops | T6 maximum delivered latency (s) |
| --- | ---: | ---: | ---: | ---: |
| Offered load ×1 | 48/48 | 48/48 | 0 | 2.901 |
| Offered load ×2 | 90/90 | 90/90 | 0 | 4.625 |
| Offered load ×4 | 171/174 | 171/174 | 3 | 4.981 |
| Recovery freshness 60 s | 15/15 | 13/15 | 2 | 138.901 |
| Recovery freshness 180 s | 6/15 | 6/15 | 9 | 31.788 |
| Recovery freshness 300 s | 6/15 | 6/15 | 9 | 3.024 |

T6 totals are **334/357 delivered, 23 `retry_exhausted` drops and zero pending
applications**; T5 delivered 336/357. Exactly two outcomes change from delivered
to dropped. The nine offered-load cases retain their application outcomes,
latencies and recorded physical/protocol totals; some simultaneous trace rows
can appear in a different order.

Both additional losses are packet 1, generated at 450 seconds, in the
60-second cases with seeds 128 and 130. T6 submits the packet immediately and
exhausts retries at 458.727/458.831 seconds. The source neighbor expires later,
at 465 seconds; the relay returns at 540 seconds. T5 retained these packets
unsent in NWK custody until approximately 582.7 seconds, after scheduled
rediscovery began at 576 seconds. This establishes the observed terminal
mechanism. It does not isolate every earlier route/event-order change into a
single causal counterfactual.

The source-compatible DATA policy has not changed: ordinary retry exhaustion
terminates local HOP ownership without a generic route-failure callback or
automatic DATA requeue. At 180/300 seconds, the first three applications in
each case still exhaust retries during the blackout. At 60 seconds, neighbor
deactivations increase from 78 to 82 and route changes from 323 to 353.
Delivered-in-both latency increases by a mean 1.202 seconds over 13 applications.
The lost packets must remain visible when assessing performance; survivor-only
means do not establish improvement. The
[independent outcome review](tranche-6-return-outcomes-review.md) retains the
per-case traces and all outcome transitions.

## Ownership and stop boundary

Across the 18 sweeps, all 382 NWK enqueues have corresponding custody releases.
No application has both a terminal drop and a delivery. Application, HOP DATA,
NWK application custody and physical pending counts are zero. No duplicate
application delivery or unretained HOP ACK was found. One duplicate DATA reception was
suppressed, as distinct from a duplicate application delivery.

Each 300-second case retains one reliable HOP control owner/target, one shared
resend entry and three NWK control messages created at exactly the 900-second
stop. T5 retained two NWK messages; T6's additional node-1 DISCOVER follows
the corrected expiry. These are explicitly owned controls at the horizon.
Their eventual drain is unobserved. The original `DataDrained`,
`ControlsDrained` and `OwnershipDrained` false flags are preserved; the
conservative `DataDrained` calculation includes CONTROL resend entries.
The other 15 sweeps report drained ownership.

## Reference scope and disposition

The candidate's pinned-source contract passed 45/45 assertions across 11
cases. The separate real ns-3 outage reference delivered 14/15 at 60 seconds
and 6/15 each at 180/300 seconds. MATLAB T6 delivers 13/15, 6/15 and 6/15;
the 60-second losses occur at different seeds. The receive-gate placement,
security and random streams differ. Ns-3 global drop/pending categories remain
unknown; local no-ACK completions and observed empty queues cannot establish
those global classifications. These measurements support the shared retry
limitation and do not establish numerical equivalence.

The five strict shared application comparisons reuse the preserved T4 ns-3
reference at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Application equality
does not certify full protocol timing; 500/1000 kbps remain separately labeled
extensions. No new ns-3 execution occurred during this return review.

The candidate's 98/98 Python tests and 90-file static MATLAB check preceded
the owner run. Review tools needed no repair. This acceptance adds only
evidence and documentation; all 90 MATLAB files and the validated candidate
manifest remain byte-identical to `21c0a3f`. No MATLAB rerun is needed to
record this review. The earlier accepted T5 evidence remains unchanged.

The next engineering target is the route-selection/DATA-retry boundary. Keep
this source-compatible correction as the baseline and label any retention or
failure-trigger extension explicitly. R2026a portable/native execution,
6000-second workloads, recovery without manual rediscovery, full protocol
timing and native packet transport remain separate gates. PHY/ECC is preserved;
battery, supervisory behavior and BBN routing remain outside the baseline.

## Preserved artifacts

The original `tranche6_evidence.zip`, selected metadata/CSV/log bytes, descriptive
analysis, paired T5 comparisons, five shared comparisons and independent
reviews are recorded locally. The
[structured acceptance](../evidence/tranche-6-portable-acceptance.json)
contains their SHA-256 identities and exact scope. Selected files under
`evidence/tranche-6-r2025a-accepted/` map to their original ZIP paths in
`archive-selection.json`; the ZIP retains every raw artifact and original
relative path. `evidence/tranche-6-candidate.json` is deliberately the unchanged
validation-time preparation record. This review does not perform remote
publication; validated source remains `21c0a3f` after the evidence commit.
