# Independent relay-custody repair review

The confirmed 694.821813632 s discrepancy requires independent local NWK ownership per accepted relay occurrence. Application identity (`Id`, source, original generation time and flow attempt) must remain unchanged. Destination delivery remains unique per application.

## Baseline failure paths

- `DiscoveryMembershipNwk.receiveData` suppresses accepted relay copies through `Seen(appKey)`.
- `enqueueApplication` suppresses a second occurrence by `pendingPosition(app)`.
- `pump`, `release`, `releaseFromHop` and `terminal` locate the first application-key match. Merely allowing duplicate entries would submit or release the wrong sibling.
- HOP completes DATA by `(peer, sequence)` and retains the complete value-copy `Frame.App`. Its callback transport can carry a local NWK ownership token without changing wire identity or HOP sequence logic.
- HOP calls `NsdpRelease` before `Terminal` for ACK, DACK and owner failure. The second callback must be harmless after the exact occurrence is removed; it cannot fall back to another copy.
- `TerminalSimulation.custodyAccepted` ignores equal-hop arrivals. `dropApplication` considers only the single application status and custody node. These are not automatically safe when two accepted copies coexist at one node. A sibling-aware read-only custody count plus equal-hop recovery is required if the existing provisional application-status scheme is retained.
- `TerminalSimulation.delivered` already suppresses repeated unique delivery through the application record status. Preserve this guard and the separate destination `Seen` guard.

## Required boundary checks

1. Fresh receiver-local token on each successful enqueue, with node identity and monotonic local serial; incoming sender token is replaced.
2. Distinct FIFO entries and HOP handoffs for equal application identities; positive-DSCP ordering stays unchanged.
3. Exact-token release is idempotent. Wrong-node, stale, missing or malformed ownership tokens cannot remove a sibling.
4. Application-level NSDP and queue capacity count every accepted occurrence.
5. First-sibling ACK/DACK/no-ACK/failure and repeated stale callbacks leave the second live occurrence intact.
6. A failed copy cannot mark the application provisionally dropped while another relevant NWK custody occurrence is live. A same-hop late accepted copy can recover a previously provisional drop.
7. Gateway DATA duplicates preserve one received application, payload total and latency contribution.
8. New metadata cannot alter PHY/wire serialization, semantic signatures, RNG order, scheduling, route discovery or HOP retransmission policy.

This review is static until the corrected MATLAB test package is run by the user. Existing native capture remains the reference.
