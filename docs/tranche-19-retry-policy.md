# Tranche 19 DATA queued-retry timing experiment

The accepted policy remains the default. The experiment changes only DATA
retry timing and the DATA unmatched-sent fallback scan. It does not change
local/relay priority, PHY/ECC, continuous-time scheduling, scenario traffic,
retry limits, or admission thresholds.

```matlab
config.Hop.DataQueuedRetryPolicy = 'actual-tx';           % accepted default
config.Hop.DataQueuedRetryPolicy = 'native-provisional'; % experimental
```

Both the scenario configuration validator and direct HOP construction accept
only these exact values (character row or scalar string). The normalized
configuration stores a character row.

## State transition being isolated

| Transition | `actual-tx` | `native-provisional` |
|---|---|---|
| Initial DATA admitted to MAC | Unconfirmed; no retry timer | Same |
| Initial actual DATA TX reported | Confirmed; actual TX time becomes LastTx; install list-wide scan | Same |
| Retry handed to MAC | LastTx becomes enqueue time; unconfirmed until actual TX | LastTx becomes provisional enqueue time; initial confirmation retained |
| Another actual-TX timer scans the resend list | Queued retry is ineligible | Queued retry may retry again or expire if its provisional deadline passed |
| Retry actually transmits | LastTx becomes actual TX time; install list-wide scan | Same |
| Final timeout | Release existing NSDP/HOP custody, cancel queued copies, terminal callback, next-TIC NWK wake | Same release path, potentially reached before last queued retry transmits |

Neither policy installs a timer merely because a retry was queued. Without
another actual-TX-triggered scan, the native variant may retain a queued retry
indefinitely as well. The normal retry age is `ResendSeconds`; the final grace
is twice that age. Eligibility comparisons use the nominal age; timer
callbacks run at actual TX plus the age plus `TicSeconds`.

All expired entries are processed before any new resend admissions during a
scan. ACK still releases both NSDP and HOP capacity immediately. DACK releases
NSDP immediately but retains HOP capacity until its hold expires, including
the existing doubled hold after reaching the resend limit.

## Scan trigger and stale TX handling

The experimental mode also matches the pinned native unmatched-DATA-sent
fallback: an ACK-required DATA sent indication with no current resend owner
installs a scan at sent time plus `ResendSeconds` plus one TIC only if the
most recently installed scan is no longer pending. It does not recreate the
owner or release capacity twice. The last-installed scan can be earlier than
an older still-pending final-grace scan; it is not the latest deadline or an
"any timer pending" test. A serial and a pending bit preserve this distinction.
Older timer callbacks remain independently scheduled.

Matched CONTROL actual-TX callbacks still cause shared list scans and update
that last-installed marker. CONTROL retry entries continue to wait for each
actual MAC TX; their initial/queued confirmation semantics are unchanged.
Unmatched CONTROL sent indications retain the previous MATLAB behavior.
Best-effort DATA and CONTROL paths are unchanged.

Thus the comparison tests a bounded DATA timing policy bundle, not a purely
single-line change: retained initial confirmation and the related native
DATA fallback scan both belong to the experimental arm. Trace attribution
must distinguish retry enqueue, actual TX, terminal expiry, and subsequent
admission. An aggregate delivery change alone does not prove which scan
trigger or capacity-release path caused it.

## Native source and limits

Source pin: `mjburke4/CSR-Project-NS3-part2` commit
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

The audited `csr/model/csr-hop-layer.h` behavior is in
`NotifyMacFrameSent` (actual timestamps, independent list scans, latest-handle
fallback), `EnqueueResend` (initial confirmation false), and `CheckResend`
(initial confirmation retained at retry enqueue, provisional timestamp,
final-expiration pass before resend pass).

This is not full native HOP equivalence. Existing MATLAB CONTROL retry
confirmation, MAC-queue admission/rejection, terminal cancellation, and
capacity-release callback behavior are retained. Sequence ownership remains
the existing peer/sequence mechanism; T19 adds no generation tag or changed
on-air frame. A late actual-TX report for a still-live owner updates that
owner's timestamp as the native callback does. A report after cancellation
cannot resurrect its owner. Source lifecycle/wrap issues outside that scope
are not silently corrected.

The default scheduling callback, event names, counters, and ownership-release
paths are unchanged; a new normalized configuration field is expected.
Runtime default-policy baseline comparisons are still necessary before
claiming byte-identical simulation evidence.

## Deterministic mechanism tests

`tests/TestQueuedRetryPolicy.m` uses a controlled MAC callback harness, not a
real-PHY benchmark. Its 16 tests cover policy validation/default evidence,
withheld initial and retry actual-TX notifications, externally triggered
list scans, final expiry while a retry remains queued, actual TX replacing a
provisional deadline, ACK/DACK release, cancellation with a selected stale
copy, inverse scan deadline order, full deletion before resend admission,
CONTROL isolation, and MAC retry rejection. Capacity reopening is checked
with both local and relayed application origins competing for the same next
hop; the test adds no source-priority rule.

These tests require MATLAB execution. Static analysis alone is not a pass
record for the MATLAB mechanisms or the full-campus experiment.
