# Tranche 5 independent integration review

Review date: 2026-09-09. MATLAB base:
`7edaab558f4f00290d11e0681d883364141d547c`; retained ns-3 pin:
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

This is an implementation review of a local candidate. It is not MATLAB
execution, portable acceptance, new ns-3 execution, or network parity
certification. MATLAB and Octave are unavailable in this workspace.

## Scope and findings

The review covered `researchSweep`, `performanceSummary`,
`run_tranche5_validation`, `analyze_research_sweep.py`, the residual audit,
source snapshots, tests and handoff boundaries. The accepted protocol core
is unchanged. No blocking MATLAB integration defect was identified in the
reviewed implementation.

| Boundary | Review finding |
| --- | --- |
| Experiment controls | Offered-load cases change application counts and intervals while preserving first/last generation times. Recovery cases change freshness timeout while retaining the receive blackout, traffic and rediscovery schedule. Three seeds and 18 default cases total 13,500 simulated seconds and 357 planned applications. |
| R2025a array shapes | Options normalize to row vectors, cases remain a column struct vector, and output tables retain column variables. New test selectors and inventory masks use compatible shapes; the earlier row/column expansion failure is not reproduced in these expressions. |
| Terminal outcomes | Late delivery clears an earlier drop; late relay custody restores pending ownership. This follows `NetworkSimulation` record and recovery behavior. Final reconstructed counts must match received/dropped/pending counters. |
| Transmission units | OTA envelopes, DATA/control members and receiver observations stay separate. Reconciliation follows MAC/HOP callback counters, including concatenated and repeated feedback members. |
| Unavailable metrics | Sender airtime, CPU seconds and executed callback counts remain unavailable. No receiver interval or pending-event count is presented as those measurements. Control drainage explicitly excludes unavailable current MAC feedback queue depth. |
| Runner failures | T5 catches secondary regression-count, inventory, metadata and archive failures and rethrows the original execution exception. Failed runs retain partial evidence; they cannot satisfy the completed-run analysis gate. |
| Evidence inventory | The diary closes before final hashing. Case diagnostics are siblings of original case exports. The root archive carries CSV/JSON/logs, excluding MAT objects and nested ZIPs; only its own root metadata is exempt from its inventory. Initial/final source snapshots and per-case snapshots must agree. |
| Python/MATLAB contract | Case identifiers, singleton struct/object encodings, scalar seeds, nested portable test paths, plan membership and final source hashes are accounted for. Analysis remains descriptive and gives each seed observation equal weight. |
| Retrospective timing | Final-envelope association distinguishes an aggregate header from application identity. The residual audit labels its single-seed causal boundary and does not justify a protocol correction or a new parity claim. |

The review requested explicit Python checks for planned/completed counts,
run options versus the plan, and regression/native/test status consistency.
These are evidence consistency guards, not additional delivery or latency
acceptance thresholds. The analyzer verifies declared case identity and
archived hashes; it does not certify experimental parameter control or
independently authenticate that MATLAB executed. Parameter isolation is
covered by the source review and prepared MATLAB configuration tests.

## Local checks and remaining gate

Independent focused lint passed for seven MATLAB files: the sweep builder,
performance analysis, T5 runner, artifact utility and the evidence/performance
and sweep test classes. The five residual-association Python tests and all
24 sweep-reporter Python tests passed in independent reruns.
`git diff --check` also passed. The requested count/options/status guards are present,
including the rule that unrequested tests cannot claim a passing execution.
These checks exercise syntax/contracts and synthetic evidence, not MATLAB
execution. No unresolved blocker remains in the reviewed candidate.

Complete candidate check counts are recorded in the packaging manifests.
The owner must run
`report = run_tranche5_validation;` in a fresh R2025a extraction and return
`tranche5_evidence.zip` before this candidate can receive portable acceptance.
R2026a, optional native testing, the optional 6,000-second workloads and full
protocol timing remain separate gates. Material drops, pending ownership,
retry exhaustion and recovery delays are retained observations for review.
