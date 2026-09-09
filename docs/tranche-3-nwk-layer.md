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

`release` removes the pending row. `terminal` reports failures even after a prior
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

At local scan completion, the coordinator sends one-hop `SNMP_DONE` records to
requesters and serially requests scans from active direct peers using
`SNMP_START`. A local request history prevents a completed scan from circulating
indefinitely. These records are direct controls and are never forwarded as
multihop application DATA. A 60-second report watchdog advances to the next peer
if a DONE report is absent. Explicit `startDiscovery` after a completed scan
starts a new local epoch and resets that coordinator history, enabling recovery
experiments after an outage. An in-progress scan is not restarted.

Neighbor activation creates the direct candidate, requests a remote snapshot,
and schedules an outbound snapshot. Explicit neighbor failure invalidates its
direct capability and cached transit routes even if the peer was still awaiting
admission. It clears partial reassembly and requests belonging to that peer.
Ordinary observations preserve inactive candidate caches pending admission.

## Routing records and reliability

One coalesced same-time route process consumes `drainChanges` once. Snapshots
exclude destinations changed in that process; grouped incremental records
follow. A snapshot contains INFO, advertised UPDATEs, and a final FLUSH.
The exact codec preserves section boundaries, signed INFO values, 24-bit IDs,
16-bit hop counts, and 32-bit costs. Reassembly applies no partial record stream.
Inactive reporters can populate caches while their traffic starts an admission
check; cached candidates do not become usable simply because bytes arrived.

REQUEST attempts start at activation and repeat every eight seconds, with two
retries by default. Each retry discards incomplete peer reassembly, matching the
source request transaction reset. A received complete snapshot ends the request
cycle. `SnapshotTimeouts` is an inbound missing-snapshot diagnostic; it does not
declare a healthy neighbor failed. The source's separate outbound snapshot ACK
watchdog is represented here by bounded reliable-control ownership, so the two
watchdogs are not claimed to be timing-equivalent.

Routing transactions retain their sections in a bounded backlog while the
shared control queue is full. Each control owner holds at most ten recipients.
Partial HOP ACKs remove recipients only from the coordinator's remaining set;
the original HOP transmission attempt remains intact. Final HOP failure creates
a new control ID for active residual peers in a later scheduler event, after
HOP has released its owner. If any destination cannot obtain HOP control space,
the entire group waits. Defaults bound attempts to three cycles and bound both
the materialized-control queue and routing-transaction backlog to 64 entries.
Backlog overflow is counted and traced explicitly. These portable bounds are
not a claim of indefinitely retaining the source's failed route advertisements.

KeyUpdate and NeighborCheck completion is delivered to `Neighbors` only after
HOP terminal ACK/failure. KeyRequest and discovery are unacknowledged controls;
their successful transmit callback confirms airtime, not delivery. No control
owner consumes application NSDP or DATA flow-window counts.

## Radio and security modeling boundary

Received PHY path-loss observations feed the recovered `linkCost` calculation.
Adaptive radio mode selects rate and transmit power from that calculation; fixed
mode retains the application radio settings. Grouped transmissions choose the
slowest target rate, with the highest power among targets at that rate.

The coordinator uses the local configured operating limits for link cost and
separately retains peer INFO, matching the audited ns-3 policy. It does not
invent an intersection of advertised operating ranges or replace PHY acceptance.

Compact control accounting charges the existing 17-byte MAC model, an eight-byte
modeled HOP envelope, five bytes per additional grouped target, and the body
below. HOP sequence observations stay 16 bits; the modeled eight-byte header is
kept separate from a claim of exact ns-3 compatibility-header serialization.

| Control | Modeled body bytes, including security size |
| --- | ---: |
| DISCOVER | 12-byte Hello + 7 |
| KEY_REQUEST | 7 |
| KEY_UPDATE | 51 |
| NEIGHBOR_CHECK | 11-byte Routes + 5; NoPath adds a compact three-byte target |
| ROUTING | Exact six-byte-prefixed ARL section + 5 |
| SNMP_START / SNMP_DONE | 6 + 3 per advertised node |

The byte counts model overhead only. Key lifecycle admission is behavioral;
there is no authentication, encryption, or over-the-air key material here.
The source control compatibility envelopes have different metadata and sizes,
so compact control airtime is a documented parity boundary.

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
