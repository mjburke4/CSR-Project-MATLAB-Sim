# Independent final T19 core and mechanism-test review

**Reviewed; no remaining source blocker in the four hashed files recorded in
`final-core-review.json`. MATLAB execution remains pending.**

Compared both production changes directly with accepted `csr18`, reviewed the
pinned native HOP source, and manually followed all 16 deterministic test cases
through the existing scheduler and HOP frame APIs. This is source review and
manual event reasoning, not a claim that MATLAB tests executed.

## Resolved blocker

The new test harness initially labeled DATA enqueues using `frame.Id`, which the
HOP frame constructor deliberately initializes to zero. The final-pass ordering
test searched for application ID 2, so it would fail despite correct behavior.
The policy agent corrected labels to `frame.App.Id` for DATA and
`frame.Control.Id` for CONTROL. The ordering test now identifies the intended
retry. No production behavior changed to fix the fixture.

A stale observer-on/off requirement in the policy notes was also corrected to
runtime default-policy baseline comparison; T19 introduces no observer.

## Core conclusions

The `actual-tx` branch retains the original scheduling callback, eligibility,
event names, counters, and ownership-release paths. The normalized configuration
now includes `Hop.DataQueuedRetryPolicy='actual-tx'`; that is an expected metadata
change. Raw CSV protocol/PHY/admission/node/scenario evidence and statistics
should reproduce accepted T17. `summary.json` itself cannot have the same bytes,
because runtime and the normalized configuration field differ; compare its
statistics and explicitly normalized configuration/metadata instead.

The experimental branch retains confirmation after DATA retry enqueue and records
its provisional enqueue time, while creating no new enqueue timer. Initial DATA
and every CONTROL retry still wait for actual transmission. Actual sent resets
`LastTxSeconds`, and independent global scans preserve final-expiration pass
before retry admissions. ACK, DACK, doubled final hold, release/cancel ordering,
admission thresholds and next-TIC wake remain their existing implementations.

The serial/pending marker represents native's most recently installed event
handle correctly. An older callback cannot clear a newer pending handle. A
newer installation that fires earlier than an older pending final-grace timer
must allow unmatched-DATA fallback afterward; the inverse-deadline test now
covers that case. Clearing the marker before the scan matches scheduler removal
of the active event before callback invocation. No missing resend owner is
recreated. Best-effort and unmatched CONTROL paths retain prior behavior.

The experiment is explicitly a DATA policy bundle (provisional confirmation and
related unmatched-sent fallback), not complete native HOP equivalence. Accepted
MATLAB terminal queue cancellation and transactional overload differences remain.

## Test walkthrough

The 16 tests use the existing APIs correctly after the fixture repair. The
controlled TIC is 1 microsecond; comparisons around final timeout and DACK expiry
retain strict before/after points. External CONTROL actual sends provide scans
without consuming DATA capacity. Tests distinguish a scan from timer creation
on retry enqueue, cover actual TX resetting the final deadline, verify ACK/DACK
single release, exercise a synchronous stale sent callback during cancellation,
and confirm deletion pass ordering and retained CONTROL retry gating. The
local/relay-origin capacity test verifies reopened capacity accepts the next
caller; it neither encodes nor asserts a service preference.

Both direct HOP construction and scenario validation accept the same exact policy
names, normalize a scalar string to a character row, and reject invalid type,
shape and spelling. The default-versus-explicit-default test compares the same
frames, counters and callback ordering rather than relying on a numeric result.

## Plan and return implications

The plan uses two fresh original-campus 6,000-second cases at seed 128 and full
portable regression, as recommended. It retains native reference evidence at
the unchanged main/engine pins. The aggregate export uses historical 60-second
buckets; descriptive comparison timelines use separately declared 300-second
windows. No reset discards late-state history. The 100,000 attempt-row prefix is
bounded, while full per-source counters and admitted identities remain available.

The +/-5% target is descriptive and does not block a structurally valid result.
One seed supports a bounded policy intervention; downstream random-number
consumption can change, so there is no packet-level common-random-number claim.
Full MATLAB regression and both full-horizon owner runs are still required.
