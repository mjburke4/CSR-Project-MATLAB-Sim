# Tranche 13: controlled loss with continued relay demand

The authoritative input files are `scenarios/loss/plan.json`, `cases.csv`,
`offers.csv`, and `draws.csv`. They are fixed before native reference generation.
Source main and the engine remain explicitly pinned in the candidate evidence.
This fixture adds diagnostics to the accepted repaired Tranche 12 tree; it does
not edit production MATLAB NWK, HOP, MAC, PHY, ECC, or scheduler code.

## Question and limits

Does real NWK custody, reliable HOP DATA/feedback, MAC queue service, and admission
capacity recover when selected transmissions are lost while applications keep
arriving at both source 4 and relay 5? The fixed path is **4 → 5 → 1**, with node
5 also originating local traffic for gateway 1.

This is controlled transport. All neighbors and the only usable next hops are
preconditioned exactly as in T12. Automatic routing control radio service remains
excluded and its retained owner counts remain separately disclosed. Fixed bare
128-kbps rate key and +33 dBm, 16-byte reliable applications, real aggregation,
actual computed airtime, 1-µs propagation, and the same raw contention tapes
isolate DATA/feedback loss and recovery. The nominal rate key is not a claim
that the production modulation has exactly 128,000 physical bits per second.

The `out` case interrupts the prescribed links around relay 5. The node continues
to run its timers, admit local work, maintain queues, and transmit; this is not a
node reboot or route-convergence test. Real RF reception, collisions, half duplex,
overhearing, adaptive rate/power, security admission, full ApplicationGenerator
parity, and campus population parity remain outside this milestone. Existing
PHY/ECC and the battery/supervisory/BBN exclusions remain unchanged.

## Four bounded cases

Every case has 48 generated applications per source, 96 total. Twenty per source
are due at time zero. One additional application per source is due at every
integer second from 1 through 28. `offers.csv` records all 384 generated identities
across the four cases independently of the observed outcome.

| Case | Controlled loss |
| --- | --- |
| `ok` | No prescribed loss |
| `data` | First actual DATA-containing addressed aggregate on each of 4 → 5 and 5 → 1 |
| `ack` | First actual ACK- or DACK-containing addressed aggregate on each of 5 → 4 and 1 → 5 |
| `out` | All addressed groups on both chain links in both directions whose TX starts in [8 s, 9.5 s) |

The `ack` selector includes DACK because both are real feedback. Record which
kinds were actually selected; do not relabel DACK as a direct ACK. A DATA- or
feedback-eligible group may include companion segment kinds. The entire addressed
recipient group is lost, and every companion remains visible in the transport
evidence. Once-only DATA/feedback selectors are keyed by directed edge and first
qualifying actual transmission, not application IDs guessed from a reference.

Run for a fixed **64 seconds**. Admission polling stops strictly before 40 seconds;
production timers continue to the declared stop without a manual drain or queue
clear. Stable snapshots occur at 8, 9.5, 20, 24, and 40 seconds, followed by final
snapshots at 64 seconds. Demand therefore continues beyond the real 20-second
DACK-hold period. The 1.5-second link interruption is shorter than the configured
2-second nominal HOP resend interval; this is a bounded recovery experiment, not
an outage stress limit inferred from that relationship.

Production HOP doubles a DACK hold from 20 to 40 seconds if the packet has already
reached the maximum resend count. Preserve that rule and any resulting residual
at 64 seconds; the fixture must not shorten a hold or extend the horizon to obtain
an empty final queue.

## Generation and admission ordering

`offers.csv` columns are `case,source,app_id,due_ns`. IDs are 1 through 48 per
source. At equal due times rows use increasing application ID, then source 4 and
source 5. Schedule **all generation callbacks before all admission polls**, in
CSV order. Generation callbacks record `generate` and enqueue the identity in the
fixture's demand FIFO; they do not submit directly to HOP or NWK.

Poll every 20 ms from zero to strictly before 40 seconds, calling source 4 and
then source 5 once per poll. If a source has eligible demand, inspect its oldest
identity, emit `offer`, consult the real application NSDP gate, and emit `blocked`
or call actual NWK application submission and emit `admit`. Assert the production
limit is 16. A blocked offer retains its identity and original due time. Application
`GeneratedSeconds` is the scheduled due time, so queueing before admission remains
part of latency. IDs are not HOP sequence numbers.

Real NWK owns its queue pump, relay custody and HOP handoff. Real HOP wake invokes
the existing NWK wake callback only. **No new application demand is submitted from
a release callback or a HOP wake**, preventing reentrant admission from altering
native ordering. Observe release only after invoking the real release operation;
keep legitimate intermediate states before the HOP callback finishes cleanup.

## Aggregate loss semantics and time boundaries

At actual MAC transmission start, assign a per-case `tx_id` to the aggregate and
visit selected segments in their actual order. Group segments by addressed
receiver, assigning a per-case `group_id` in first-receiver-occurrence order.
Compute one loss decision per group, cache it, and schedule the actual aggregate
arrival using emitted duration plus 1 µs. Do not call the selector separately for
each segment or again at arrival.

At arrival, a passed group follows T12 ingress: one MAC heard/reservation update
per receiving node for the aggregate, then actual HOP ingress in selected segment
order. A dropped group emits one `loss` observation per segment and causes no MAC
heard/reservation change and no HOP ingress. Other recipient groups in the same
aggregate retain their independently cached decisions. Neither path manufactures
an ACK; all feedback comes from the real stack.

Outage membership uses logged integer-nanosecond TX start, rounded from the actual
scheduler time for this declared policy only. The scheduler is never quantized.
For every emitted receiver group in `out`, compute distance to both boundaries.
A distance **at or below 1,000 ns** is a structural ambiguity error rather than a
silently accepted timing-dependent choice. This guard prevents the known 28-ns
T12 offset from quietly moving a near-boundary transmission between loss states.
The guard is disclosed input policy, not a widened event-parity tolerance.

## Common evidence

The existing 30-column T12 event schema remains unchanged. New event names are
`generate` and `loss`; all original application identities and feedback bitmaps
remain exact. A `loss` row snapshots the receiving node and transmitting peer at
the scheduled arrival, using actual segment metadata; it has no matching ingress.
`generate` snapshots its original source with the scheduled identity before any
NWK submission. `checkpoint` and `final` preserve node order 1, 4, 5.

`transport.csv` contains one row for each actual emitted segment:

`case,tx_id,group_id,segment_index,group_segments,tx_time_ns,arrival_ns,sender,receiver,kind,app_source,app_id,hop_seq,ack_bits,dack_bits,decision,reason,boundary_distance_ns`

`segment_index` is the position in the whole aggregate, not a per-recipient index.
Every group repeats its recipient count, decision, reason, and timestamps on all
member rows. Kinds are `DATA`, `ACK`, or `DACK`; decisions are `pass` or `drop`;
reasons are `none`, `first_data`, `first_feedback`, or `outage`. Boundary distance
is −1 outside `out`. Export true ACK/DACK bitmaps as **uint64 decimal integers**,
without any intermediate `double` conversion. Multiple sequences can be covered
by one lost feedback segment; those effects belong to actual HOP processing.

`terminal.csv` records real HOP outcomes:

`case,order,time_ns,node,app_source,app_id,success,reason`

Normalized reasons are `ack`/success 1, `dack_custody`/success 1, and
`retry_exhausted`/success 0. The native trace's `dack` false flag denotes that the
completion was not a direct ACK; NWK custody was accepted. Preserve that original
native trace and explicitly normalize it to the MATLAB custody-success meaning.
DACK terminal success does not assert that HOP capacity has already been released.
This mapping is exact and source-backed: pinned native `HandleDackFrame` calls
`NotifyNsdpFromEntry`, transfers the resend owner into a DACK hold, removes the
resend entry, and emits `hop_completion` with the pair `dack`/`0`; the existing
MATLAB DACK completion releases NSDP and invokes `terminal(...,true,'dack_custody')`.
Only the three declared reason/flag pairs are accepted. An unknown pair is a
structural error, never normalized by a prefix or treated as success.
After feedback loss, an application can be delivered and later suffer a sender
retry-exhausted terminal result. Such overlap is valid evidence, not duplicate
application delivery and not proof the payload was lost.

Shared tapes provide exactly 1,024 raw draws per node and case: node 1 always 1,
node 4 alternates 3/7, and node 5 alternates 9/1. Consumption occurs before real
reservation avoidance. Invalid support, value, ordinal, unresolved draws, or
exhaustion fail the fixture. Export complete consumption and unused suffixes;
functional recovery may have a different draw trajectory and must not receive an
exact-parity label based on a matching prefix.

## Structural completion and interpretation

Independent evidence checking must reconstruct generation and FIFO admission from
shared inputs, verify all emitted aggregate segments and loss choices, and account
for all original identities. Split generated work into admitted and not admitted;
reconcile admitted work against actual unique delivery and actual retry-exhausted
terminal evidence, allowing delivered/failed overlap. Disclose all unadmitted and
undelivered identities. Never invent a terminal failure from a missing delivery or
require a fault-injected case to produce success by altering production policy.

Check unique gateway application delivery, valid chain next hops, real relay
custody, no ingress or heard updates for lost groups, continuing local admission
after 20 seconds, observed post-interruption service, and complete raw-draw
accounting. At stable snapshots, real NWK custody must equal NSDP(4,1)+NSDP(5,1),
and HOP pending must equal live resend owners plus actual DACK holds. Completion
checks inspect actual final custody, waiting DATA, HOP resends, and DACK holds;
retained bootstrap control owners are separately disclosed.

Compare delivered identities, admissions, releases, terminal outcomes, selected
losses, and recovery observations with native results. Record the full timing,
ordering, intermediate state, and consumed-draw differences separately. A small
timestamp or callback-state residual alone does not fail functional recovery;
structural failures and unexplained custody cannot be waived as numerical noise.
This diagnostic can establish bounded behavior under these loss policies, not
general stochastic or campus parity.

The native reference is actual pinned C++ execution. MATLAB acceptance requires
Mike's returned MATLAB runtime evidence; Python checker and static analysis results
are never reported as MATLAB execution.
