# Relay custody occurrence repair

The validated seed-132 replay exposes the first queue-state difference at node 4, 694.821813632 seconds: source-7 attempt 2873 is offered to NWK again by the HOP DACK receive-window behavior. Native admits another copy and increases that source/destination's NSDP count from 26 to 27. The earlier MATLAB implementation suppresses the copy through its end-to-end `Seen` map; removing that guard alone leaves the application-key `pendingPosition` collapse and release hazard.

This patch modifies exactly the production `csr.nwk.Layer` and active candidate `ac.DiscoveryMembershipNwk` custody paths. Historical diagnostic NWK variants remain frozen.

## Identity and ownership

- Original `App.Id`, `SourceId`, `FlowOrdinal`, `FlowIndex`, generated time, traversal, and payload are preserved.
- Each successful NWK enqueue allocates `App.NwkCustodyId` as a fresh local `uint64`. `App.NwkCustodyNodeId` is the accepting node. The pair is local simulation metadata and does not change modeled wire bytes.
- Each enqueue replaces any inherited upstream token. Repeated applications therefore have distinct local tokens, and matching serials at different nodes cannot release one another.
- NWK's relay `Seen` check and application-key enqueue suppression are removed. HOP's existing sequence/ACK/DACK window still determines whether a decoded frame is offered to NWK. Final-destination `Seen` and simulation unique-application delivery accounting stay in place.
- `CustodyAccepted` and `SendData` receive the accepted node's stamped application. Existing `Frames.data` retains the entire application value, so ACK/DACK/failure callbacks carry the correct local token without HOP changes.
- Release matches local node, nonzero `uint64` token, and original source/application identity. Missing, foreign, stale, or mismatched tokens cannot release a queued sibling. There is deliberately no tokenless application-key fallback.
- An unmatched ordinary release does not schedule a new pump. `releaseFromHop` preserves the existing rule that HOP owns the later wake.
- The pump snapshots occurrence-bearing applications and relooks up the exact occurrence after a `SendData` callback. A nested release/requeue followed by a rejected send cannot reset or remove the replacement/sibling occurrence.
- Public read-only `custodyCount(app)` counts all retained occurrences of one end-to-end application, including submitted HOP owners. Unique-application accounting may use this to avoid marking a live sibling lost. It is distinct from source/destination-pair `nsdpCount`.

## Evidence boundaries

`core_static_review.json` checks clean MATLAB parsing and exact equality of nine custody-relevant method bodies between production and active candidate. The existing physical-byte and transmission-signature constructors use explicit fields and do not serialize the new token as additional bytes. The existing ordered event recorder writes full frames/applications, retaining the token for post-run custody reconstruction without another observer.

No MATLAB runtime execution is claimed here. Focused public-boundary custody tests and the unchanged seed-132 0–1,200-second common-input capture remain the execution gates. No timing, receiver state, or native input is patched.
