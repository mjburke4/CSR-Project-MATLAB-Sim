# Current-policy parity status: November 6, 2026

This checkpoint summarizes accepted retained measurements and the next matched-input
component test. It does not change the production model, existing diagnostic
entrypoints, PHY/ECC, numerical target, or historical campaign outcomes.

## Current descriptive result

Compare current-policy MATLAB seeds 135/136/137 with accepted native seeds 135/137
plus supplemental native seed 140. Each history covers [0,6000 s); the engines'
natural RNG trajectories are unpaired, including equal numerical seeds. The
MATLAB diagnostic uses explicit `opnet-reference` NWK retained-custody admission
and `native-provisional` DATA queued-retry policy. The portable-bounded default
and all HOP, MAC and application NSDP limits are separate from this policy.

All 18 source/metric point estimates are within the existing +/-20% numerical
target: six sources, each with admissions, first deliveries and pooled delivered
latency. Aggregate first deliveries are 35,678 MATLAB versus 35,479 native
(+0.56%). The largest delivery gap is source 4 at -12.62%; the largest latency
gap is source 5 at -10.94%. Source 8 deliveries differ -7.08%.

Counts are normalized by run count (three per engine). Pooled latency is the sum
of first-delivery latencies divided by first-delivery count, not the average of
run means. Admitted-but-undelivered applications remain censored. Source 8's
MATLAB delivery counts are 125, 352 and 114; the native counts are 313, 176 and
147. This variability and the small number of histories limit generalization.
Packets and time bins are not independent run replicates.

This is descriptive agreement, not formal parity acceptance, statistical
equivalence, a causal model-fix effect, or a claim that RNG variation is the only
remaining cause. The original fixed-eight campaign keeps its failed,
infrastructure-invalid, rejected and unattempted outcomes; supplemental seed 140
does not replace them. No new mandatory confidence-interval rule is introduced.

The [sanitized aggregate summary](../evidence/current-policy-2026-11-06/SUMMARY.json)
contains the exact source-level inputs and ratios. Run
`python evidence/current-policy-2026-11-06/verify_summary.py` from the repository
root to verify its saved arithmetic without executing either simulator.

## Matched congestion fixture: main agreement and a boundary distinction

The native corrected attempt 2 passed its reviewed focused contract: 25 main
congestion checkpoints, two separate exact-28-ns boundary checkpoints, and 25
checker assertions. The independent review checked additional state invariants;
the 25 checker assertions alone are not an all-fields comparison at every row.
Attempt 1 is retained as a setup-only grouped-control fanout adapter failure
before DATA, not a scientific model failure.

The native result exercises separate own/relay NSDP, offer-17 gating, immediate
DACK custody release with held HOP credit, older-relay FIFO selection, independent
queue wakes, delayed sent confirmation of a queued retry, and third-ACK threshold
ordering. Its separate equal-time boundary processes the pre-registered ACK before
the retry.

MATLAB completed one owned attempt launched November 6 at 15:08:49.043 UTC. It
exited zero in 30.522 seconds with its owned job empty, no forced termination,
and 25 main checkpoint assertions passed. An independent retained-output review
accepted the focused MATLAB contract. The completed raw two-engine comparison
now matches all 25 shared main semantic checkpoints and 34 ordered common
input/DATA-output events, with 299 comparison checks passing. Independent review
reproduced full waiting FIFO, mapped live/held/submitted owner identities, retry
and confirmation flags, and per-flow NSDP/custody and HOP credit conservation.

The accepted main scope includes both independent queue-wake owners and formulas,
confirmed LastTx and provisional-retry behavior, and DATA-scan deadlines under
each engine's raw clock. It is not rounded timestamp equality. A separate
read-only comparator rerun reproduced its outputs byte-for-byte; no simulation
was rerun for that comparison.

The separate HOP-only MATLAB boundary emitted a retry at
2.000000027777778 s before the ACK at 2.000000028 s. The ACK then canceled the
queued retry and left no resend or held-credit owner. Native used equal-time
28 ns timing and processed its earlier-registered ACK without emitting a retry.
Both finish without owners or pending HOP credit, but the final clean-ACK streak
is 0 in MATLAB and 1 in native. This is a narrow timing-edge state difference,
not an equality pass or an established cause of the campus delivery gap. The final zero ACK streak in the main fixture
does not separately isolate retry-reset from threshold-growth-reset behavior.

The fixture excludes real MAC scheduling, PHY/channel randomness, radio selection
and whole-network equivalence. Native unsent LastTx is a zero sentinel; MATLAB's
is Inf. Both entries are unconfirmed and timer-ineligible. Synthetic prerequisite
route costs, security representation and setup times differ, as do raw HOP
sequence offsets; application identity mapping is explicit. Three early retained
timer deadlines differ by approximately 0.5 seconds because of setup. The latest
retained resend timer handle is not a list of every independently scheduled event.
The extra MATLAB setup_zero checkpoint and all original attempts remain retained.

Native 28 ns ticks and MATLAB raw binary64 1/36e6 s timing remain visible without
a cross-engine equality tolerance. Third-ACK reset ordering is source-supported;
the main fixture's final streak 0 does not isolate the additional retry reset.
The local MATLAB closure assessment does not add independent engine-creation
verification. This focused result does not explain the campus source 8 delivery
gap, establish equal natural RNG trajectories, or demonstrate a model-fix effect.

## Source package and reproducibility boundary

The November source is not a drop-in replacement for the historical candidate.
The [isolated current-policy package plan](../diagnostics/relay-custody/current-policy/README.md)
pins exact tested seed137 source deltas and preserves constructor, writer-budget
and endpoint boundaries. It is a plan, not a runnable package or an executed new
adapter. No source files or current-policy execution recipe are installed by this
documentation checkpoint. The previous seed137 snapshot ran on MATLAB R2026a
Update 5; that execution does not validate a newly relocated package.

[Provenance](../evidence/current-policy-2026-11-06/PROVENANCE.json) binds retained
reviews and original execution evidence by hash. Those artifacts are not public
downloads, and hashes do not make this a self-contained full-run reproduction.
Private native source, raw traces and original machine-specific execution inputs
are not published. No simulator was rerun for repository packaging; the focused
component executions above are separately recorded research evidence.

No active deterministic defect has been established as the cause of the remaining
source 8 gap. The evidence does not justify blind queue, FIFO, feedback-power,
clock or PHY/ECC tuning. Broader conclusions require evidence beyond this focused
component contract. Earlier dated status documents and ledger entries remain
historical records, not superseded or silently reclassified passes.
