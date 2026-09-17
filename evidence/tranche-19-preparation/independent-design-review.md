# T19 independent experiment and source review

Scope: read-only review against accepted `csr18` and candidate `csr19`.
Native source pin: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
The owner wants practical agreement within a few percent, not exact numerical equality.

## Recommended experiment

Run the original seven-node, six-flow, real-PHY 6,000-second campus workload twice,
seed 128, changing only `Hop.DataQueuedRetryPolicy`: `actual-tx` versus
`native-provisional`. Retain every earlier event so later congestion and admission
state is real history. T18's 900-second prefix reversed source 5's full-run surplus,
so a fresh late-window restart or multiple early short cases cannot replace this.

Require a fresh default-policy case and compare its complete core traces with the
accepted T17 run. T17 is a regression reference; it does not replace the fresh
paired baseline. Pair outcome changes establish the effect of this policy in this
MATLAB workload and seed. They do not establish cross-simulator random-stream
alignment or robustness over seeds. If useful improvement exists, a second full
paired seed is the next confirmation, not an obligation to spend that runtime now.

Report total and per-source delivery differences from native ns-3. A +/-5% band is
an explicit descriptive interpretation of “a few percent,” not an acceptance
threshold, promised accuracy, reason for parameter fitting, or basis to silently
change the default. Show absolute deltas beside percentages, especially when
native counts are small. A closer network total can coexist with worse flow
balance. Preserve 600-second buckets or another frozen bucket width so early and
late trajectory effects remain visible, without changing the workload horizon.

Owner budget: approximately two prior T17 campus runs plus full portable tests.
Allow roughly 2–2.5 hours initially; print observed timing because changed retry
behavior can change callback counts. Preserve completed tests and each campus
case as independently sealed stages. Reuse only complete identity-bound evidence
from the same candidate, source/reference inventories, scenario/plan, exact MATLAB
runtime, policy, and evidence hashes. Never resume half a simulator by treating
partial files as a completed case. A structural or provenance failure blocks
acceptance; a numerical mismatch is a measurement.

## Evidence design

Do not use the existing full `AckServiceDiagnostics` object for the complete
campus horizon: it records every attempted application. T18's 900-second prefix
used 252,712 service records, including 180,000 attempts, while its inherited
constructor caps records at 1,000,000. The full workload makes 1,710,000 attempts.
Keeping the existing complete protocol and PHY traces plus aggregate admission
counters is materially lighter.

The protocol trace can reconstruct DATA capacity from `hop_admit` (+1) and
`hop_ack`, `hop_failed`, `hop_dack_expired` (-1). `hop_dack` retains HOP capacity
until expiry. Reconstruct NWK custody from `network_enqueue` (+1) and
`network_custody_release` (-1), with retained packet origin from `app_generate`.
Label these event-derived ownership/capacity reconstructions, not hidden queue
state samples or complete late admission-attempt observations. Keep row ordinal
as well as time; callbacks at one timestamp can have meaningful ordering.

The accepted T18 prefix independently confirms these endpoint identities at all
seven nodes. At nodes 2/3/4/5/7/8 the reconstructed final HOP pending values are
6/16/1/17/2/4 and custody values are 55/16/91/51/16/34, matching the exported
per-node counters. The gateway values are zero. T19 return review should require
nonnegative reconstructed ownership, unique matching release lifecycles, and
agreement with final HOP/NWK counters in each policy case. Zero trace omissions
are essential to these claims.

The first 100,000 admission rows remain a bounded prefix. Full per-flow attempt,
admitted and blocked counts come from `application_admission_statistics.csv`;
full admission timing comes from `app_generate`. Do not infer a complete timeline
of blocking reasons after the retained admission prefix.

Useful outputs: final per-flow attempted/admitted/delivered/dropped/pending counts;
full-horizon/bucketed local-versus-relay HOP admissions and ownership residence;
4->5 retry enqueue/actual sent/wait/expiration lifecycles; HOP release reason and
DACK-hold occupancy; node 5 source/relay custody residence; and default-versus-T17
core equivalence. An expiry-before-current-retry-TX event supports the intended
mechanism; a downstream delivery shift by itself does not prove the hidden
source-selection rule changed.

## Initial core source audit

Current candidate `+csr/+hop/Layer.m` preserves the original default schedule and
callback path. DATA retries alone retain confirmation under `native-provisional`;
CONTROL retries still clear confirmation. A retry enqueue records provisional
`LastTxSeconds` but installs no new timer. Actual sent indications install the
existing independent list-wide scan. Final-expiration pass still precedes retry
admissions, and final grace, NSDP release, capacity release, thresholds and wake
order remain unchanged.

Native `NotifyMacFrameSent` uses the handle of the most recently *installed*
resend scan, not the earliest due event or whether any scan is pending. An unmatched
sent notification installs a fallback scan only after that most recently installed
handle is no longer pending. Candidate serial-plus-pending tracking correctly
represents that rule: an older scan cannot clear the newest pending flag, and
if a newer installation fires before an older pending scan, the newest handle is
no longer pending and fallback is allowed. The flag is cleared before the scan,
matching scheduler removal before callback execution. No owner is resurrected.

The experimental bundle therefore includes retained DATA provisional time and
DATA unmatched-sent fallback. It intentionally does not import native unmatched
CONTROL fallback or provisional CONTROL expiration. MATLAB still cancels queued
DATA on terminal retirement and preserves accepted transactional overload rules;
this is a bounded native-inspired DATA timing experiment, not full native HOP
behavior equivalence.

Mechanism tests should cover initial transmission gating, queued DATA retries
consuming retry/final deadline only when an existing scan fires, no enqueue timer,
actual transmission resetting the deadline, same-time final-before-retry ordering,
ACK/DACK cleanup, no owner resurrection, unchanged CONTROL gating, omitted versus
explicit default equivalence, invalid policy validation, and both timer deadline
orders for the most-recent-handle fallback. Runtime MATLAB evidence is pending.
