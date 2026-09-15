# Independent Tranche 9 service inspection

The returned MATLAB run validates the intended reservation behavior and exposes
a real local scheduling change. It does **not** improve any of the six case
delivery totals or close the seed-129 residual. Five cases retain exactly the
same aggregate Statistics object; seed 131 changes latency only.

This analysis reads the uploaded ZIP, the accepted T8 ZIP, and the frozen
candidate at `t9r/src`, commit `99fff0381fe9621ccd76fbdce41eac9aba5a9469`.
It performs no simulator or test rerun. Independent source/runtime/inventory
acceptance is the primary reviewer's gate. `inspection.json` binds input hashes
and records detailed counts, rows, local identities, and timing; `flows.csv`
contains every source-to-gateway comparison.

## Delivery outcomes

| Case | T8 MATLAB | T9 MATLAB | ns-3 |
| --- | ---: | ---: | ---: |
| c129 | 948 | 948 | 822 |
| c128 | 928 | 928 | 914 |
| c130 | 894 | 894 | 916 |
| c131 | 895 | 895 | 883 |
| c132 | 917 | 917 | 920 |
| a129 | 11,354 | 11,354 | 11,227 |

All per-source admitted, delivered, dropped, and pending counts also remain
unchanged from T8, and the six complete application-admission traces are byte
identical. ns-3 unmatched sends retain their own source semantics; they are not
silently reclassified as MATLAB pending packets or terminal drops.

At c129 source 2, MATLAB still delivers **510 versus 353** in ns-3: +157,
or +44.4759% relative to ns-3. The first 20 seconds still account for +117 of
that difference: **152 versus 35** deliveries. Source 3 delivers 438 versus
469, including 108 versus 129 in the early window. The reported earlier 17%
campus discrepancy is not a bound on these different, short diagnostic flows.

Sources: both ZIPs' `b/<case>/analysis/applications.csv`,
`raw/application_admission_trace.csv`, and `raw/summary.json`; pinned native
`evidence/tranche-9-ns3-reference/<case>/ns3-trace.csv.gz`.

## What the correction actually changes

The six service traces contain **120,835 rows**, **1,373 paired cancellation
callbacks**, and five cancellations that actually remove an early queued DATA
copy. All five preserve `PreparationActive`, reservation slot and counter
while queue depth falls 1 to 0. There are no early control-type removals and no
early queued-copy removals in a129. The owner contract summary reports all
101 checkpoints passing.

| Case | Node | Cancellation time (s) | Counter | Next DATA TX, T8 → T9 (s) |
| --- | ---: | ---: | ---: | --- |
| c129 | 3 | 302.573544 | 21 | 302.926 → 302.926 |
| c128 | 3 | 302.807544 | 2 | 302.835 → 302.835 |
| c130 | 2 | 303.873544 | 13 | 304.044 → 304.044 |
| c131 | 3 | 303.821544 | 0 | 303.901 → 303.823 |
| c132 | 2 | 303.769544 | 6 | 303.849 → 303.849 |

In the four positive-counter cases, the old implementation reactivated
preparation on the next slot without drawing a new reservation. The correction
eliminates one redundant `mac_prepare` event per case; all other protocol rows
are byte-for-byte unchanged. The a129 protocol trace is entirely unchanged.

Counter zero is different. In c131, the old slot tick decremented zero to -1
while preparation was inactive, invalidated the reservation and selected
another slot. The corrected implementation transmits queued DATA at that
tick: **78 ms earlier** for local application packet 4 from node 3. This is
direct evidence of the intended scheduling correction, beyond the controlled
contract fixture.

Eight received packet times change in c131. Two packets arrive earlier and
six later; net latency sum increases by **0.052 seconds** across 895 deliveries.
Mean latency moves from **1.7154320223 to 1.7154901228 seconds** (+58.1 microseconds,
+0.0033869%). These are measured values, not a pass/fail tolerance. The same
delivered identities and all application admission times remain unchanged.
The OTA ACK schedule, destinations, sequences, selected rates and powers are
unchanged too; only five `DecisionId` references differ because reception order
changed. No throughput improvement is demonstrated.

Sources: T9 `raw/service_trace.csv` cancellation before/after rows; T8/T9
`raw/protocol_trace.csv`, `raw/actual_feedback.csv`, and
`analysis/applications.csv`; frozen `+csr/+mac/Layer.m` methods `slotTick`,
`prepare`, and `schedulePending`. DATA comparisons explicitly exclude CONTROL
packet IDs, which occupy a distinct, potentially colliding local namespace.

## Seed-129 ACK and admission sequence

| Observation | MATLAB T9 (s) | ns-3 (s) |
| --- | ---: | ---: |
| First source-2 DATA delivery | 302.519104 | 301.401104 |
| First source-3 DATA delivery | 301.375104 | 302.493104 |
| First source-2 ACK over the air | 302.549 | 303.849 |
| ACK capacity release | 302.573544 | 303.873544 |
| Next application admission | 302.574 | 303.874 |

MATLAB receives node 3 first, prepares gateway slot 10 at 301.375104, then
receives node 2. ns-3 receives node 2 first and prepares slot 28 at 301.401104.
The native ACK decision 52 is then held through another DATA reception and a
duplicate DATA reception; decision 54 replaces it before the 303.849 TX.
It is inaccurate to call this a single unchanged ACK waiting in the queue.
MATLAB's decision 48 for node 2 is first queued at 302.519104 and transmits at
302.549. The original early divergence precedes the cancellation correction.

In MATLAB, service observations 2651–2666 show capacity/custody release,
HOP completion, paired cancellation and the Track-to-Search transition at
302.573544, followed by the next queued HOP admissions at
302.573544027774: approximately the configured **27.7778 ns TIC** later.
Native traces show the corresponding deferred handoff at **+28 ns**, matching
their integer-nanosecond time resolution. The controlled HOP contract also
passes. No sampled evidence supports another admission-capacity-release
policy change.

All 2,900 ordinary MATLAB OTA ACK segments and 2,888 native ordinary OTA ACK
segments across the six cases use the **128-kbps profile / +33 dBm**. The
operational profile rate is 133,333.333... bit/s. These counts need not match
between independent contention histories; the rate/power selections do.

Sources: T9 `b/c129/raw/service_trace.csv`, `link_decisions.csv`,
`actual_feedback.csv`, `application_admission_trace.csv`; native c129
`ns3-service.csv.gz` and `ns3-link-decisions.csv.gz`; the frozen candidate's
`evidence/tranche-9-early-findings.json` for original-decision replacement and
receiver-busy lineage, rechecked against the reference traces.

## Recommended next work

Keep the source-correct reservation fix. Subject to the independent integrity
gate, T9 supports portable structural and contractual acceptance while leaving
numerical parity open. The planned next benchmark milestone can remain a single
6,000-second campus execution with retained regression checks; this return does
not promise campus delivery improvement.

For a further focused residual investigation, follow the **first contention
and receiver-busy history**: initial DATA launch order, duty-cycle/receiver
availability, reservation draw/counter lineage and ACK replacement before the
first capacity release. Use matched deterministic receive/neighbor stimuli or
an explicitly controlled event replay to test a concrete suspected mismatch.
The existing forced-slot setters also differ in timer-rephasing behavior and
cannot be used as if they create equivalent stimuli. Do not tune radio power,
rate, or admission capacity to force the seed-129 packet counts to agree.

Equal seed integers do not provide equal random streams across simulators.
The five contention samples are descriptive; this review establishes neither
population equivalence nor that every remaining discrepancy is stochastic.
