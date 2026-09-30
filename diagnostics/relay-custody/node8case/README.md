# Relay-copy custody repair: seed 132, 0–1,200 seconds

Restart **MATLAB R2025a (25.1.0.2943329), Windows**, extract this complete ZIP into
a fresh folder, set Current Folder to its `node8case` folder, and run:

```matlab
report = run_node8_tests;
```

The test runs automatically and prints the return ZIP path. Allow one to several
hours; runtime depends on the computer. Long quiet periods are expected. Return
the printed **`out_node8_*.zip`**, even if the test reports a divergence or error.
The ZIP includes completed preflights and available partial network evidence.

## Test-helper correction

This revision corrects the optional-argument count in `RelayCustodyProbe`. The
previous helper overwrote the queue-full test's requested limit of 1 with 512.
The returned run passed all 17 prior preflight groups, all four accounting
cases, and 20 of 22 custody groups; both queue-full groups failed before the
network started. The helper now preserves supplied limits and each group
checks its effective configuration before running. Network-model code, native
inputs, comparison rules, and the requested replay are unchanged from that run.

## Repair and purpose

The previous replay found a concrete difference at node 4. At 694.821813632 s,
ns-3 accepted another source-7 relay copy after a DACK-marked retry, while MATLAB
suppressed it by application identity. The missing queue occurrence changed HOP
admission at 894.464292500 s and transmission contents at 895.115 s.

This candidate gives each accepted relay copy separate queue and custody
ownership, including its completion or release. Final delivery and latency remain
counted once per unique application. The repair also handles sibling-copy and
late-custody accounting. It does not count each relay copy as a newly generated
or newly delivered application.

The same verified native capture is reused as common input; no new ns-3 capture
was required. MATLAB generates its own queue admissions, routes, receiver states,
feedback, retries and deliveries. No reference queue entry, custody outcome or
network state is injected.

## What runs

- The 17 existing preflight groups, plus focused relay-copy custody tests, run
  before the network. Integrated accounting also exercises sibling-copy failure,
  last-copy failure, same-hop recovery and unique final delivery.
  The original typed native import and first MAC-request
  check remain in place. The full 1,200-second fixture is checked separately.
- One seven-node network starts at time zero and stops at 1,200 seconds.
- Original application traffic starts at 300 seconds: 45,000 opportunities per
  source and **270,000 opportunities** across sources 2, 3, 4, 5, 7 and 8.
- The selected DATA retry policy remains `native-provisional`; the model default
  remains `actual-tx`.
- A semantic random-request or transmission-context mismatch stops the network
  and preserves partial evidence. An endogenous random-request timestamp
  difference also prevents acceptance. A separate completion gate checks every
  physical TX count, source/ordinal, global order and integer-nanosecond timestamp.
  Its comparator preflight checks the historical 400-second TX table and rejects
  five deliberate time/count/order/source/duplication mutations.

## Provenance and historical evidence

The runner verifies every file in the current `FILES.json` before and after the
run. It independently compares the candidate with the accepted v2 source manifest:
only the explicitly listed relay-custody/accounting repair files may differ, and
only the listed focused-test files may be added. All other prior model and
candidate files must match their accepted hashes exactly. Active MATLAB classes
must resolve inside this freshly extracted kit.

The old 330-second natural tables are retained and checked for historical
integrity. **They are not reused as acceptance evidence for this changed model.**
No new 330-second natural network is run. The 330-second configuration used by
isolated component preflights does not launch a natural network simulation.
The return report identifies the candidate behavior change explicitly.

## Evidence and accounting

The return retains application-attempt, protocol, PHY, receiver timing,
transport timing, service, feedback and ordered-event evidence. Omitted required
records prevent acceptance. The ordered recorder streams to disk; no extra
sampling or simulation callback is added by this runner.

Independent analysis of the return will compare ordered relay occurrences,
custody releases and unique-application accounting, including the previous
694.822-s and 895.115-s boundaries. Those times are diagnostic reference points;
they do not inject or force a queue or delivery result.

Node-8 queue checkpoints remain 400, 600, 675, 900 and 1,200 seconds, where reached.
The traces do not directly record every skipped NWK-pump candidate or coalesced
wake decision; those must not be reported as observed decisions.

Every admitted-but-undelivered application remains **unresolved**. Raw
native-provisional `Dropped` and `Pending` counters are retained separately.
HOP-owner expiry does not prove final application loss, and aggregate counters
do not classify every live physical copy. Unique delivery accounting remains
separate from relay-copy and custody-occurrence counts.

## Acceptance target and limits

The engineering target remains **±20%**, using the same source-by-source delivery
count and delivered-latency definitions. The latest autonomous 6,000-second
measurement predates this repair: 5 of 9 defined source/seed cases pass both
measurements, while source-weighted latency is about +40.7%. Three further cells
are undefined because native delivery is zero. This candidate has not yet been
measured against that milestone.

The ±20% target does **not** relax this replay's strict common-input comparisons.
Canonical comparison uses **0 ≤ time < 1,200 seconds**; callbacks exactly at the
endpoint are saved separately. There is no drain interval. A completed replay
establishes its stated bounded checks, subject to independent raw-trace review;
it does not establish autonomous 6,000-second parity or agreement across seeds.

The kit has static and independent reviews. MATLAB is unavailable in the
preparation environment, so execution of this repaired candidate remains pending.
Do not edit source or reference files. Historical documents may describe older
candidates or targets; the current manifest, runner and this README describe this
relay-copy custody candidate and the ±20% engineering target.
