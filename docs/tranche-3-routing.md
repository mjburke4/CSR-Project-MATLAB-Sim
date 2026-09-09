# Tranche 3 ARL routing core

Source reference: `mjburke4/CSR-Project-NS3-part2` at
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, principally
`model/csr-nwk-layer.h`, `model/csr-arl-routing-message.{h,cc}` and focused
`csr-nwk-self-capability-smoke.cc`, `csr-nwk-grouped-route-propagation-smoke.cc`,
`csr-nwk-same-pass-info-coupling-smoke.cc` and admission tests.

`csr.nwk.Routes` implements candidate state and selection. The NWK layer owns
scheduled discovery, neighbor admission, reliable routing-message transport,
application custody, and same-time process scheduling. `csr.nwk.linkCost`
implements the source's link policy from measured path loss; it does not
predict receive success or replace the existing PHY/ECC model.

## Public interface

```matlab
routes = csr.nwk.Routes(nodeId, capability, options);
routes.setNeighbor(peerId, active, linkCost, nowSeconds);
effects = routes.apply(peerId, sequence, recordCells, linkCost, nowSeconds);
route = routes.select(destinationId);
route = routes.relay(destinationId);
routes.learnReverse(applicationSourceId, peerId, nowSeconds);
[recordCells, changedDestinationIds] = routes.drainChanges();
snapshotCells = routes.snapshot(changedDestinationIds);
```

- `Routes.defaults()` supplies `MaxPathHops=32` and `LocalInfo`.
- `setNeighbor` materializes a measured direct candidate. Admission is an
  explicit `active` input; receiving a routing record does not admit a peer.
- `invalidateNeighbor(peer, now)` reports an explicit failure/inactivity event.
  It discards cached transit and resets direct capability and INFO even if the
  peer was never admitted. In contrast, `setNeighbor(peer,false,...)` on an
  already-inactive peer represents an observation and preserves cached state.
- `apply` accepts a cell array of logical codec records and returns a scalar
  struct with `RequestSnapshot` (logical), `AppliedRecords`, `IgnoredRecords`,
  and `InfoChanged` (logical). Unknown peers start inactive. Malformed logical
  records raise an error; well-formed unsupported destinations/paths and stale
  records are ignored. The codec/reassembly layer validates wire messages
  before calling this method.
- `select` returns `[]` or the selected forwarding candidate. Even an
  unsuccessful destination lookup preserves source list-creation order.
- `relay` returns `[]` or a candidate with an extra `UsedReverse` logical.
  It gives capable forward routes priority, followed by usable reverse routes,
  then any remaining selected ordinary forward/direct candidate.
- `learnReverse` accepts only a known reporting neighbor. An inactive peer's
  reverse record is unusable until the peer becomes active. The source has no
  separate reverse-route expiry timer.
- `noteNoPath(peer, destination, now)` returns whether it removed a reverse
  route. It ignores the broadcast target, materializes any other destination's
  source list order, and preserves every forward candidate. A reverse path is
  removed only when its recorded next hop matches the reporter; unrelated
  reports are informational. This follows source CHECK_NO_PATH behavior.
- `drainChanges` consumes all pending route flags. It returns optional INFO
  first, then UPDATE/DELETE records in newest-created destination order, with
  the permanent self destination last. The coordinator calls it once at the
  beginning of a process pass, obtains exclusions, sends requested snapshots,
  then sends these grouped incremental records. No-recipient passes still
  consume changes; routing sequence allocation belongs to the coordinator.
- `snapshot(exclusions)` emits INFO, eligible self UPDATE, selected capable
  route UPDATEs in candidate insertion order, and a final FLUSH. The exclusions
  suppress records being sent as changes in the same process pass.
- `setCapability(value)` queues a source-owned self UPDATE or DELETE only when
  the local capability changes. Construction with nonzero capability starts
  with that self change pending.
- `setLocalInfo(info)` coalesces actual operating-limit changes into the next
  `drainChanges`. It changes advertised local limits; link policy settings
  remain the caller's responsibility.
- `neighbors()` returns neighbors in newest-created order. Each has `PeerId`,
  `Active`, `LinkCost`, `InfoValid`, `InfoSequence` and `Info`.
  `neighborInfo(peer)` returns valid remote INFO or `[]`.
- `applicationGateway()` returns the last encountered destination whose
  selected route advertises capability 2, or `[]`; this matches the source
  gateway application's scan rather than selecting a gateway by minimum cost.
- `reachableDestinations()` lists selected reachable destinations in
  newest-created destination order.

Candidates contain `DestinationId`, `NextHop`, `Capability`, `HopCount`,
`Cost`, `Path`, `Immediate`, `Valid`, `SelectionDeferred`, `LinkCost`,
`AdvertisedCost`, `SequenceValid`, `Sequence`, and `LastUpdatedSeconds`.
Numeric protocol fields use exact-valued doubles within their validated wire
ranges. `Candidates` is publicly readable with private assignment.

Logical codec records use `Operation` strings `INFO`, `UPDATE`, `DELETE`,
`FLUSH`, and `REQUEST`. UPDATE has `NodeId`, `Capability`, `HopCount`, `Cost`,
and a row `Path`. DELETE has `NodeId`. INFO has an `Info` struct with
`MinSpeedKbps`, `MaxSpeedKbps`, `MinPowerDbmX10`, `MaxPowerDbmX10`,
`LinkMarginDbX10`, `LowPowerDbmX10`, `TempLowCx10` and `TempHighCx10`.

## Source behavior retained

Candidates are keyed by destination and next hop. Selection requires a valid
candidate and active peer. It minimizes total route cost, then hop count;
exact ties retain the prior selected peer or the first encountered candidate.
Node identifiers do not break ties. Costs add the peer's measured link cost to
the advertised route cost with source uint32 wrap, then force zero to one.

Local capability is separate from forwarding candidates: the self UPDATE has
zero hops/cost and an empty path. Receiver-side self UPDATE changes the
existing measured direct candidate's capability. A self DELETE removes the
advertised capability while preserving physical reachability. Ordinary=0,
Routable=1, Gateway=2. Only nonzero-capability destinations are advertised.
An ordinary local node can still advertise capable routes learned from others;
transit admission policy is independent from this role field.

A transit UPDATE prepends its reporter to the advertised path. The permissive
wire codec supports a uint16 hop count, while this source wrapper admits at
most 32 resulting path hops. Local-node loops become invalid sequence-bearing
candidates; broadcast path identifiers and over-limit paths are ignored. A
malformed reporter self UPDATE is ignored.

Each candidate, including DELETE/FLUSH tombstones, keeps its reporter sequence.
Equal, older, and ambiguous half-range sequence numbers cannot replace it;
normal uint32 wrap is supported. Snapshot UPDATEs precede FLUSH, so a trailing
FLUSH invalidates only older reporter candidates while retaining same-sequence
updates and INFO. It does not erase direct reachability. New UPDATEs that
replace the selected candidate queue propagation even if the final route is
identical, matching source remove/reinsert notification behavior.

A complete INFO+FLUSH snapshot that omits its reporter's self record denotes
ordinary capability zero. It clears a previously advertised gateway/routable
capability on the measured direct route without removing physical reachability.
If bounded outbound admission fails after draining changes, the coordinator
restores the dirty destination/INFO flags before returning to the scheduler.

Transit UPDATEs received from an inactive peer are cached but deferred from
selection. Admission recomputes only the direct-neighbor destination; a later
source-owned recomputation for a transit destination releases its eligible
cached candidates. Active-to-inactive transitions delete the reporter's
transit candidates, clear remote INFO, and reset direct capability/sequence.
Readmission therefore starts with an ordinary direct candidate and needs fresh
self/transit UPDATEs to regain their advertisements. A changed link cost on an
already active peer recomputes valid candidate costs; deferred alternatives
are released only for destinations that already had a selected route before
that recomputation. Unchanged observations do not release deferred transit.
The caller should use `setNeighbor` to report actual observations/transitions,
not poll it merely to read peer state.

## Link policy

```matlab
[cost, detail] = csr.nwk.linkCost(pathlossDb, failureCount, options);
```

Default options follow source NWK defaults: `RxS0BaseLevelDbm=-115`,
`LinkMarginDb=10`, min/max rate 8/128 kbps, min/max power 0/30 dBm, and
`LowPowerDbm=14`. Rate thresholds above the required 8 kbps transmit power are
0, 3, 6, 9, 12, 20 and 23 dB for 8, 16, 32, 64, 128, 500 and 1000 kbps.
Configured min/max rates constrain that choice. Transmit power is clamped
before the source scaled-distance and failure-cost adjustments, and is rounded
up for the returned transmit setting. The default maximum remains 128 kbps;
500/1000 require an explicit higher maximum.

`detail` has `RateKeyKbps`, `TxPowerDbm`, `EstimatedDistance`, `SpeedMarginDb`,
`TotalMarginDb` and the resolved `Config`. Estimated distance is the source's
cost proxy and is not a geometric range estimate for the actual simulation.

Source timing belongs to the coordinator: discovery hello interval 5 s,
optional neighbor freshness timeout/check 20/2 s, routing request timeout 8 s
with two retries, and snapshot watchdog 20 s. No battery, BBN routing or
supervisory subsystem is introduced.

## Validation boundary

`tests/TestRoutes.m` exercises selection ties and hop counts, sequence replay
and wrap, tombstones, loop handling, source path limits, snapshot/FLUSH order,
self-capability changes, inactive caching, loss/readmission, reverse routing,
gateway selection, grouped change ordering, and fixed link-policy examples.
These are MATLAB unit tests. Availability of the tests and a static parse are
not evidence that MATLAB executed them; release-specific runtime evidence is
recorded by the tranche validation runner.

Development check on 2026-09-08: MISS_HIT 0.9.44, MATLAB R2022a parser profile,
reported all three new route/link-policy/test files clean. A standalone C++
program using `ComputeLinkCost` extracted verbatim from the pinned source
confirmed these golden values; these checks did not execute MATLAB:

| Path loss (dB) | Max rate (kbps) | Failures | Cost | Chosen rate (kbps) | Power (dBm) | Distance proxy |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 128 | 0 | 29 | 128 | 7 | 75 |
| 130 | 128 | 0 | 1393 | 16 | 28 | 223 |
| 140 | 128 | 0 | 6274 | 8 | 30 | 251 |
| 100 | 1000 | 0 | 6 | 1000 | 18 | 125 |
| 100 | 128 | 12 | 116 | 128 | 7 | 75 |
