# Tranche 12: fixed-chain local and relay service

Authoritative shared inputs are `scenarios/relay/plan.json`, `cases.csv`, and `draws.csv`. The native CSR source is pinned at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; the ns-3 engine is `6b5cd24ea80713ce16d88575869aedd6f432bdae`. Native reference generation determines outcomes; no expected event trajectory is an input. The accepted Tranche 11 source remains unchanged.

## Question and scope

At node 5, how does the real NWK queue share HOP/MAC service between locally originated traffic and traffic received from node 4 for gateway 1? Follow the original application identity through admission, relay custody, emitted DATA, generated ACK, and capacity release. Compare the complete observed trajectory under matched raw contention draws.

This is a **pre-admitted, fixed-route, controlled-transport diagnostic**. The finite synthetic offer driver applies the existing application NSDP limit using real NWK state. Production NWK custody and queue ordering, HOP flow control/reliability, MAC preparation/probing, aggregation and ACK service execute. The full production ApplicationGenerator is not invoked. Neighbor security admission and route convergence are preconditioned. RF collision, half-duplex reception, PHY/ECC, adaptive rate/power, unobserved campus links, and statistical population parity are excluded. A passing result cannot establish campus parity.

## Finite cases

Construct nodes in order 1, 4, 5. Node 1 is the gateway; node 5 relays node 4's traffic along 4 → 5 → 1. All traffic has final destination 1. Run cases in the CSV order:

| Case | Node 4 applications | Node 5 applications | Raw contention tapes | Stop |
|---|---:|---:|---|---:|
| relay | 20 | 0 | 4 alternates 3/7; 5 alternates 9/1 | 24 s |
| local | 0 | 20 | Same | 24 s |
| mix | 20 | 20 | Same | 24 s |
| sw | 20 | 20 | Exchange node 4 and node 5 tapes | 24 s |

Gateway raw draws are 1 in every case. Inactive application sources remain real network nodes. Each application has 16 payload bytes, DSCP 0, reliable delivery, and a per-source ID from 1 through 20. `(SourceId, Id)` is the identity; relay operations preserve it. Native application tags and MATLAB application metadata must survive real NWK/HOP processing. Do not equate a hop sequence with the application ID. Native NWK adds its real network header; MATLAB's existing production wire-size rules supply equivalent bytes. No artificial padding or duration correction is allowed.

All DATA and ACK use the fixed bare envelope at 128 kbps and +33 dBm, with native link margin 6 dB. Fixed radio limits isolate queue service; they are not a claim about normal rate or power selection. MAC slot profile is historical modulo-probe, range 31, reduction 0, with 13 ms slots and 300 ms preparation holdoff. Duty cycling is disabled; active and reported node populations are 3. Initial state is Search with SYNC false and neighbor reservation −1.

## Explicit topology and control preconditioning

Only chain neighbors are known: 1 knows 5; 4 knows 5; 5 knows 1 and 4. MAC heard observations use time zero and no reservation. As in Tranche 11, do not use native `NoteNeighborReservedSlot(-1)` to initialize untouched peers because it starts a recurring slot timer. Do not prewarm MAC timers or enqueue DATA before the measured interval.

Neighbor security admission and freshness are disabled in this fixture. Native public route APIs establish destination 1 via next hop 5 at node 4 and via next hop 1 at node 5. MATLAB public neighbor observation and serialized routing-record ingestion establish equivalent selected next hops. The injected/static destination-1 route carries capability 2. Initialization equivalence is limited to usable selected next hops; full routing metrics, self-capability state, and bootstrap control queues are not compared. Native static route metrics and MATLAB serialized UPDATE metrics may differ without affecting the sole eligible next hop or fixed radio settings. Verify actual selected routes rather than assuming initialization succeeded. There is no 4 → 1 direct transport edge and no alternate route under test.

Automatic routing control radio service is excluded explicitly. Native automatic propagation and routing-snapshot response are disabled. MATLAB `CanSendControl` refuses submission, retaining bootstrap control owners; its control retry and snapshot watchdog are set to 1,000 seconds, beyond this 24-second horizon. Settle initialization's zero-time callbacks before scheduling offers; this must not start MAC timers. Export retained bootstrap control counts and relevant settings separately for each implementation. These counts need not be equal and cannot support a routing-control parity claim. No suppressed control may silently enter the DATA/ACK radio-service comparison, consume a replay draw, or be reported as a delivered packet.

## Finite offers and production NWK queue service

Schedule offers at integer multiples of 20 ms, starting at zero, strictly before 16 seconds. Each poll invokes source 4 and then source 5 once. For a source whose case-defined demand is already admitted, return without an event. Otherwise retain the next candidate application ID, emit `offer`, and apply the existing application NSDP rule: native `CanAdmitApplicationPacket(1)`; MATLAB `applicationState(1).NsdpCount < NsdpLimit`, after asserting the state-reported limit is 16. This finite driver queries the real state but does not execute the production ApplicationGenerator; NWK `sendApplication` itself is not the application limit gate.

If blocked, emit `blocked` and retry that same candidate at a later poll. If admitted, assign the application's generation time, call real native NWK `Send` or MATLAB `sendApplication`, increment the synthetic demand count only after real insertion, and emit `admit`. Do not call HOP send directly from the offer function. Twenty applications intentionally exceed the 16-entry local application NSDP limit; expose actual blocked attempts rather than assuming the limit was reached in every case.

Production NWK owns queue pumping, HOP admission, packet handoff, relay custody, and release. Real HOP wake calls the existing NWK queue callback. There is **no application offer from HOP wake**, no extra drain loop, and no replacement of the native private queue pump. A wrapper may observe real NSDP release only by first calling the actual NWK release operation and then logging the resulting state; the real HOP resend cleanup continues afterward. MATLAB uses `releaseFromHop` to preserve the post-feedback one-TIC wake behavior.

## Raw draws and controlled transport

The input tape has columns `case,node,ordinal,min,max,draw`: 256 raw integers per node and case, exact support 0..31, one-based contiguous ordinals. Consumption occurs before production reservation avoidance. Fail on exhaustion, invalid support/value/ordinal, unsupported subsystem or shape, or unresolved draw. Native and MATLAB record every consumed draw, resolved reservation, purpose, and the explicit unused suffix for every node. Matching only a common consumed prefix does not pass.

Use actual emitted MAC frames and actual computed airtime. Forward the aggregate's addressed segments at TX start + actual duration + 1 microsecond. Preserve aggregate grouping, selected segment order, frame metadata, and actual HOP Sent callbacks. Source/destination edges are restricted to the chain. No overhearing, loss, receiver-state filtering, collision, or transport-generated ACK is provided. MAC heard/reservation observation occurs once per receiving node per aggregate before its segments reach real HOP ingress. Real HOP/NWK generates feedback and delivers or retains applications. Fixed receive observations are path loss 70 dB and SNR 20 dB.

## Common evidence

`events.csv` has exactly `plan.events_schema` (30 columns): the Tranche 11 event columns plus `nwk_waiting`, `nwk_custody`, `nsdp4`, `nsdp5`, and `dack_holds`. Reset event `order` to 1 for each case and preserve semantic emission order. Snapshot the row node and peer at the stated event boundary.

- `offer`, `admit`, `blocked`: application driver before/after the real NWK decision. Node is the original source and peer its fixed next hop. Identity is original source plus candidate ID. Hop sequence, bitmaps, and radio fields are zero because no actual emitted frame is being observed.
- `tx_start`: one row per selected actual segment before MAC selected-queue mutation and Sent notifications. Every segment in an aggregate shares its pre-mutation MAC snapshot. Record actual identity/sequence/ACK metadata and aggregate rate/power.
- `ingress_before`, `ingress_after`: receiving node, transmitting peer, actual frame identity and radio metadata. The before snapshot precedes aggregate MAC neighbor observation and real HOP ingress; the after snapshot follows those operations, including nested delivery or release callbacks. Aggregate grouping must be preserved.
- `release`: after the real NWK NSDP/custody decrement inside the HOP callback, before later HOP resend removal. Node is 4 or 5; peer is its physical next hop. `app_source` is the original source from the callback; application ID, hop sequence, bitmaps, and radio fields are zero because native release exposes no unique application ID.
- `deliver`: inside the actual gateway NWK application-delivery callback. Node 1, peer 5, original source/ID; hop sequence, bitmaps, and radio fields zero. Count unique delivered identities and retain duplicates as discrepancies.
- `checkpoint`: snapshot node 1/peer 0, node 4/peer 5, then node 5/peer 1 at 16 seconds, with identity and radio fields zero. This records actual DACK-held capacity after the offered-work interval.
- `final`: the same snapshots at 24 seconds, before disposal, with identity and radio fields zero. Production timers remain active between 16 and 24 seconds; do not manually drain or clear queues.

`admitted` counts only driver admissions originating at the row node; gateway admissions are zero. `nwk_waiting` counts only DATA still waiting for HOP handoff (native queue size; MATLAB unsubmitted owners). `nwk_custody` counts outstanding original and relayed DATA until real release: native NSDP(4,1)+NSDP(5,1), MATLAB actual PendingCustody. `nsdp4` and `nsdp5` are each row node's real counts for source 4 or 5 to final destination 1. Their sum must agree with custody in this bounded fixture. `dack_holds` is actual HOP DACK-held capacity, distinct from resend owners; At stable checkpoint/final snapshots, HOP pending must equal live resend owners plus DACK holds. Release callbacks intentionally precede some HOP resend removal, so that intermediate snapshot is not subject to the stable-state equality. Native DACK-list size is exposed by a read-only helper in the isolated test overlay; the pinned production header is unchanged. Bootstrap controls are excluded from these DATA quantities and disclosed separately. MAC/HOP counters use real negative sentinels; unavailable peer-specific quantities are zero when peer is zero. Bitmaps remain exact integer decimal values.

Output `draws.csv` is `case,node,ordinal,time_ns,min,max,draw,resolved,purpose`; `usage.csv` contains case/node/supplied/consumed/unused. Case summaries include admitted and delivered identities by original source, node 5 forwarded source-4 identities, real release totals, final data custody/queues and bootstrap control residuals. Structural checks require correct finite identities, no invented direct 4 → 1 path, no silent drops, consistent data accounting, complete tape accounting, and empty real NWK data custody/waiting and HOP resend queues at successful completion. The 16-second checkpoint retains the actual DACK-held capacity: preliminary native runs exposed four holds in mix and one in sw. These observed outcomes are not scenario inputs. Continuing the same workload without further offers to 24 seconds tests their real 20-second expiry. Final HOP pending, resend owners, and DACK holds must be zero; a residual is reported and fails its structural check rather than being silently cleared or extending the horizon again.

Compare complete ordered event and draw tables. Allow at most 1 ns in timestamp comparison and disclose every nonzero difference. All other populated fields compare exactly; unequal row counts and unmatched suffixes remain discrepancies. Full event parity is separate from structural completion. The two Tranche 11 clock-boundary counter residuals remain documented; separate tiny clock diagnostics characterize such boundaries without changing the simulator scheduler or silently quantizing event times.
