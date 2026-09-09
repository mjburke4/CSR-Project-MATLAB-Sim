# Tranche 3 network coordinator

`csr.nwk.Layer` connects ARL neighbor admission, selected routes, exact routing
payload bytes, HOP control reliability, and application custody. Its transport
callbacks feed the existing MAC queues and CSR PHY. It never reads a configured
flow path, node coordinates, or a precomputed connectivity graph to select a
next hop. Source audit baseline is ns-3
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

## Application custody

`sendApplication` retains source traffic when routes are unavailable. Enqueue
does not initiate discovery. Following the source NWK queue, every positive
DSCP arrival goes to the head and DSCP zero appends at the tail. The queue skips submitted entries,
blocked HOP peers, and destinations without a usable route so one destination
cannot stop another. Queue capacity includes submitted entries until HOP
releases custody. This explicit portable retention policy bounds queued plus
outstanding applications together.

Selected active next hops come from `Routes.relay`, including its reverse-route
fallback. Transit requires `Node.TransitForwardingEnabled`, a next hop absent from
the application's traversal, and room under the hop limit. Gateway-only source
traffic resolves the currently selected gateway at submission, preserving its
original target in `RequestedDestinationId`; relays retain that resolved target.

`receiveData` rejects DATA from an inactive neighbor and requests the admission
proof. As in the source, this network policy follows HOP receipt: the simulation
adapter acknowledges protocol receipt while recording an application policy
drop for `inactive_neighbor` or `transit_disabled`, rather than fabricating a
successful application delivery. Genuine queue refusal remains distinct and
retryable. The source's ordinary capability is independent of the explicit
transit flag: an ordinary node can relay unless that flag disables forwarding.
Such a disabled node can still advertise learned capable routes, matching the
audited source; the leaf fixture therefore tests application discard explicitly.
Its discard sends a reliable NeighborCheck `no_path` report to the previous hop,
naming the unreachable destination. A received NoPath report preserves every
forward route and removes only a matching reverse entry learned through its
reporter; broadcast targets are ignored. Source `NoteNeighborCheckSuccess`
applies the common bidirectional-key-gated admission proof to a NoPath ACK too.
`receiveData` learns a reverse route and adds
the receiver to `Traversal` while incrementing `HopCount`. Fresh relay custody
calls `CustodyAccepted` only after enqueue succeeds. Repeated application IDs
at that node return accepted without appending hops or duplicating custody.
Final delivery similarly occurs once per source/application ID.

`release` removes the pending row and schedules ordinary work. `releaseFromHop`
only removes custody: HOP owns the post-feedback +TIC wake. `terminal` reports failures even after a prior
no-ACK transmit completion released the row: actual PHY loss may arrive later.
The simulation's global application ledger decides whether a late failure
still belongs to the current custody owner or merely reflects missing feedback
after successful onward transfer. First nonlocal reception without a usable
route retains the existing HOP suppression/duplicate behavior; this is not a
new store-and-forward policy for route-unknown relays.

## Discovery and admission

Startup can target gateways, all nodes, or explicit administrative events.
Gateway startup defaults to 10 seconds. Discovery, key request/update lifecycle,
and NeighborCheck admission are owned by `Neighbors`. Receipt of a key record
and ACK of the opposite key transfer remain separate conditions.

At local scan completion, the coordinator refreshes active links and requests
fresh routes before sending one-hop `SNMP_DONE` records to requesters. DONE
carries up to ten known reachable nodes and expands the scan table. Scans are
requested serially using `SNMP_START`; retained local request history avoids
cycles. Final and one-hop destinations are distinct: an intermediate receiver
drops a control addressed onward instead of relaying it. A 60-second watchdog
advances if a DONE report is absent. A START while idle opens a new local epoch;
an in-progress scan is not restarted. SNMP is best effort, uses HOP sequence 0
and DSCP 0, and does not refresh NWK neighbor state.

Neighbor activation creates the direct candidate and schedules an outbound
snapshot. A received discovery check reporting remote `Active=true` also
schedules a REQUEST after the route-process event. Explicit neighbor failure invalidates its
direct capability and cached transit routes even if the peer was still awaiting
admission. It clears partial reassembly and requests belonging to that peer.
Ordinary observations preserve inactive candidate caches pending admission.

## Routing records and reliability

One coalesced same-time route process consumes `drainChanges` once. Snapshots
exclude pending changes and the frozen destinations changed in that process;
a later same-time event clears the frozen set. Independent per-peer snapshots
use distinct sequences and forward section order; grouped incremental records
follow in reverse group/section order. A snapshot contains INFO, advertised
UPDATEs, and a final FLUSH.
The exact codec preserves section boundaries, signed INFO values, 24-bit IDs,
16-bit hop counts, and 32-bit costs. Reassembly applies no partial record stream.
Inactive reporters can populate caches while their traffic starts an admission
check; cached candidates do not become usable simply because bytes arrived.

REQUEST attempts start from the remote-active admission proof or discovery
completion and repeat every eight seconds, with two retries by default.
Retries preserve unrelated sequence-keyed reassembly. A received complete snapshot ends the request
cycle. Separately, each peer's outbound snapshot tracks its sequence, total
sections, deduplicated ACKs and watchdog generation. A repeated REQUEST is
suppressed until every section is acknowledged or that watchdog expires.
Expiry retires only the snapshot tracker: existing HOP/section owners remain,
and a later REQUEST can start a new stream. Late old-sequence ACKs cannot
complete the new stream. Neighbor invalidation clears peer-owned tracking.
`SnapshotTimeouts` counts both inbound missing-snapshot and outbound watchdog
expirations; neither diagnostic alone declares a healthy neighbor failed.

Routing transactions retain their sections in a bounded backlog while the
shared control queue is full. Each control owner holds at most ten recipients.
Partial HOP ACKs remove recipients only from the coordinator's remaining set;
the original HOP transmission attempt remains intact. Final HOP failure creates
a new control ID for active residual peers in a later scheduler event, after
HOP has released its owner. If any destination cannot obtain HOP control space,
the entire group waits. Defaults bound attempts to three cycles and bound both
the materialized-control queue and routing-transaction backlog to 64 entries.
Backlog pressure is counted and traced explicitly; rejected snapshots stay
pending and rejected route changes restore their dirty flags for delayed retry.
Materialization does not schedule a redundant same-time pump. These portable
bounds are not a claim of indefinitely retaining failed route advertisements.

KeyUpdate and NeighborCheck completion is delivered to `Neighbors` only after
HOP terminal ACK/failure. KeyRequest and discovery are unacknowledged controls;
their successful transmit callback confirms airtime, not delivery. No control
owner consumes application NSDP or DATA flow-window counts.

## Radio and security modeling boundary

Received PHY path-loss observations feed the recovered `linkCost` calculation.
Adaptive radio mode selects rate and transmit power from that calculation; fixed
mode retains the application radio settings. Grouped transmissions choose the
slowest target rate, with the highest power among targets at that rate.
SNMP instead uses minimum local rate and maximum local power.

The coordinator uses the local configured operating limits for link cost and
separately retains peer INFO, matching the audited ns-3 policy. It does not
invent an intersection of advertised operating ranges or replace PHY acceptance.

Control accounting follows the frozen source's complete modeled packet trees,
not its compatibility-header serialization. Discovery and admission/routing
controls use standalone Hello/Routes models. Only SNMP carries the modeled
17-byte MAC and eight-byte HOP wrapper. HOP sequence observations stay 16 bits;
compatibility destination/sequence lists add no modeled bytes for grouped sends.

| Control | Complete modeled on-air bytes, including security size |
| --- | ---: |
| DISCOVER | 12-byte Hello + 7 |
| KEY_REQUEST | 11-byte Routes + 7 |
| KEY_UPDATE | 11-byte Routes + 51 |
| NEIGHBOR_CHECK | 11-byte Routes + 5; NoPath adds a compact three-byte target |
| ROUTING | 11-byte Routes + exact six-byte-prefixed ARL section + 5 |
| SNMP_START / SNMP_DONE | 17-byte MAC + 8-byte HOP + fixed 6-byte SNMP |

The byte counts model overhead only. Key lifecycle admission is behavioral;
there is no authentication, encryption, or over-the-air key material here.
Routed configurations require the atomic Pairwise16 size profile documented in
[the profile contract](tranche-3-profiles.md); application labels enforce DSCP
and provenance only, not historical generator equivalence.
Compatibility headers and SNMP node lists are retained as logical metadata,
not charged as extra wire bytes. The helper matches the source's modeled
counts. The R2025a portable runtime gate passed; equivalent cross-simulator
airtime, packet-error and end-to-end numerical comparisons remain separate.

## Interfaces and evidence

The constructor accepts node ID, scheduler, streams, full scenario configuration,
and callbacks. Public operations include startup/discovery, application send and
receive, control receive/completion, PHY observation, route/admission queries,
NSDP release, terminal result, wake, and flat selected-route/neighbor snapshots.
Callbacks `SendData`/`SendControl` only enqueue actual HOP work; neither fabricates
delivery or ACKs. Stats distinguish pending custody, waiting applications,
control owners/backlog, route changes, neighbor transitions, and discovery.

`tests/TestNwkLayer.m` exercises coordinator behavior independently of the radio.
Full-stack scenarios use `NetworkSimulation` and CSR PHY. Neither static checks
nor those test definitions establish MATLAB execution; the tranche handoff must
identify the actual R2025a/R2026a test run and its resulting evidence.
