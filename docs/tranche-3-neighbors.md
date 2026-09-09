# Tranche 3 neighbors and local discovery

Source: `mjburke4/CSR-Project-NS3-part2` main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, principally
`model/csr-nwk-layer.h`, `csr-nwk-discovery-ordering-smoke.cc`,
`csr-nwk-arl-admission-security-smoke.cc`, and
`docs/arl-admission-hop-security.md`.

`csr.nwk.Neighbors` implements the ARL neighbor lifecycle around a supplied
control transport. A fresh neighbor is not active until the remote group key
has been received, the reciprocal KeyUpdate has been acknowledged, and a
received or acknowledged NeighborCheck supplies admission proof. Enqueuing a
control packet completes none of these steps. The transport must report real
control receptions and reliable completions; a scenario must not activate
peers merely because they share a configured physical link.

At the component boundary this is labeled `behavioral-admission`. The complete
network scenario requires the atomic
`behavioral-production-pairwise16-size-only` profile described in
[the profile contract](tranche-3-profiles.md). KeyRequest, KeyUpdate and
NeighborCheck represent source-backed state transitions. No cryptographic
authentication, key bytes, replay window, production protection, or security
parity is claimed. The source authenticates received controls before these
callbacks; the eventual security provider belongs at that boundary. The
per-peer `Generation` field is simulator callback metadata that rejects old
completions after failure; it is not a source wire field.

## Interface

Constructor: `csr.nwk.Neighbors(nodeId,scheduler,options,callbacks)`.
The scheduler is the existing portable `csr.sim.EventScheduler`. Unicast IDs
are integers 0 through 16777214; 16777215 is the broadcast destination.
`defaults()` returns only neighbor options, stored as `config.Nwk.Neighbor`.

| Method | Meaning |
| --- | --- |
| `start()` | Start the optional freshness monitor once. Does not initiate discovery. |
| `startDiscovery(delay,duration)` | Schedule local discovery; defaults 0 and 30 seconds. Returns false when scheduled/active. |
| `observe(peer,metrics)` | Refresh reception time and retain caller-supplied link metrics; does not admit the peer when admission is enabled. |
| `receiveControl(kind,peer,payload)` | Process one received admission/discovery control. |
| `controlCompleted(kind,peer,payload,success)` | Process a reliable ACK or final transport failure using the original local payload. |
| `isActive(peer)`, `activePeers()` | Query usability; active peers use newest-created-first ordering. |
| `failNeighbor(peer)` | Deactivate and notify routing, including previously inactive reporters with cached transit routes. |
| `noteInactiveTraffic(peer)` | Start CHECK_MESSAGE and missing-key work for inactive DATA/routing input. |
| `securityReset(peer)` | Clear old admission/key/discovery-sequence state after an authenticated restart-counter change. |
| `snapshot()` | Return node/discovery state, `Peers` struct array, counters and security-profile label. |

`snapshot().Peers` entries expose `Id`, `Active`, `Stale`,
`LastHeardSeconds`, `Metrics`, `ReceivedKey`, `SentKey`, in-flight flags,
discovery state, failure count, retry deadlines and generation. The timer IDs
and generation are observation metadata. A snapshot does not replace a packet
exchange or claim wire-format equivalence.

| Callback | Arguments and ownership |
| --- | --- |
| `SendControl(kind,peerIds,payload,reliable)` | Returns logical enqueue acceptance. Transport sends the packet; reliable controls later invoke `controlCompleted`. |
| `NeighborChanged(peer,active)` | NWK admits the direct route or deletes that reporter's transit candidates and recomputes affected destinations. |
| `DiscoveryFinished(knownNodes)` | Reports currently active direct peers. NWK adds reachable routing destinations and manages START/DONE orchestration. |
| `Event(name,peer,details)` | Optional observation callback. |

| Control kind | Payload | Reliability |
| --- | --- | --- |
| `DISCOVER` | `Subtype='broadcast'` or `'chirp'`; uint32 `Sequence`; row `ActivePeers` (chirp only) | Unreliable broadcast |
| `KEY_REQUEST` | `SecurityProfile='behavioral-admission'`, local `Generation` | Unreliable unicast; NWK retries |
| `KEY_UPDATE` | Same lifecycle metadata | Reliable unicast |
| `NEIGHBOR_CHECK` | `Subtype='discovery'`, `'message'`, `'overheard'`, `'verify'`, or `'no_path'`; uint32 `Sequence`; logical `Active`; profile and local generation | Reliable unicast |

Routing owns `no_path` route invalidation and an optional `TargetId` payload;
Neighbors does not interpret its target. Received Discovery, Message and
Verify checks may admit the receiver after two-sided keys. Received Overheard
initiates Message. Acknowledged checks admit the sender after two-sided keys.
Unknown control kinds are ignored so NWK may dispatch routing/SNMP separately.

Security-count reset intentionally does not use the ordinary failure teardown.
It clears admission and key/discovery validity while preserving the source's
in-flight key-send ownership, retry event, generation, key request/send timing
histories, and overheard-check validity/timing history. This distinction is
covered by a focused regression because clearing those transients would look
reasonable but would diverge from the audited source path.

## Timing and autonomous startup

Production defaults are three local Discovery broadcasts at 0, 5 and 10
seconds relative to discovery start, followed by completion at 15 seconds.
The nominal 30-second duration is a fallback cap. Completion immediately
returns the local state to idle; there is no cooldown. Sequence arithmetic is
32-bit serial arithmetic, and a locally generated sequence skips zero.
Only a new broadcast sequence schedules a Discovery NeighborCheck. The check
waits for the reciprocal outbound KeyUpdate ACK. Discover received while a
remote key is missing resets the key-request/key-send retry delays to 5
seconds. Retry eligibility then doubles request/send/overheard delays. Reliable
NeighborCheck exhaustion retries admission after 5 seconds.

The ns-3 gateway defaults to local startup at 10 seconds. The NWK coordinator
must call `startDiscovery(10,30)` for gateways and drive subsequent local
discoveries through START/DONE control. A three-node autonomous case should
start only its gateway: each routable node's discovery-completion scan starts
its direct neighbor. Source SNMP is best effort and is not relayed through an
intermediate HOP when its final destination differs from that receiving node.
START/DONE, its 60-second watchdog, destination-list ordering and route refresh
remain NWK coordinator responsibilities.

Freshness monitoring defaults off because the source requires an explicit
monitor-start call. When enabled it checks every 2 seconds and expires a peer
only when reception age is strictly greater than 20 seconds. Active-to-inactive
transitions coalesce one same-time Chirp; its active peer list excludes every
peer failed in that pass. A Chirp causes Verify after 20 milliseconds only
when its sender was previously active and omitted the local node.

Routing must restore only the direct destination at admission. A cached
transit update received before admission remains selection-deferred until a
later destination recomputation. Failure removes learned transit candidates;
readmission cannot resurrect them without fresh route input. Neither neighbor
freshness nor the outer discovery node-type hint grants gateway capability.

## Validation boundary

`tests/TestNeighbors.m` covers discovery cadence/cap/restart, actual-ACK-only
key distribution, admission proof ordering, retry timing, duplicate and wrapped
sequences, retry after failed checks, stale callback rejection, strict freshness,
coalesced chirps, callback notification for inactive reporters, and security
reset state. These are deterministic component fixtures. MATLAB execution and
end-to-end PHY convergence must be recorded separately; writing the tests is
not a claim that they ran on R2025a or R2026a.
