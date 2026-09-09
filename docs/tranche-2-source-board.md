# Tranche 2 source and ownership board

Source baseline: `mjburke4/CSR-Project-NS3-part2` main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (PR #50). The current
main retains the PHY/ECC model accepted for Tranche 1. Its latest MAC change
excludes rejected preambles from synchronization expiry; its latest HOP change
lets a third positive ACK grow the window before resetting the streak for a
retransmitted completion. Neither change should be lost during integration.

This tranche joins application traffic, fixed-path forwarding, HOP reliability,
MAC access, and the existing physical signal engine. Autonomous route discovery,
admission, reliable routing control, and cryptographic security remain Tranche 3.
A configured path is a test/scenario input, not evidence of routing convergence.

| Owner | CSR behavior required for this tranche | Primary source and existing smoke evidence |
| --- | --- | --- |
| MAC | Separate DATA/control queue (512) and ACK queue (256); drop new DATA before priority insertion; descending DSCP with FIFO ties; cumulative ACK replacement resets its transmit count; MAC sends an ACK up to five times. | `model/csr-mac-core.h`; `model/csr-net-device.h`; ACK-queue, queue-limit, and slot-parity smokes |
| MAC + PHY | Idle/Search/Track/Tx; half duplex; pseudo carrier sense through synchronization; 13-ms slot ticks and 300-ms independent holdoff; slot and reservation counters freeze during SYNC, Track, and Tx. Duty cycle is 0.988 s with an initial 8.9-ms Search window and 7.8-ms post-receive Search. | `model/csr-net-device.h`; `docs/opnet-mac-receive-contention.md`; receive-contention and reservation-lifecycle smokes |
| MAC | Current fine active-node slot table and reservation avoidance; each OTA transmission advertises and retains a future reservation; successful overhearing updates link/reservation knowledge. Post-Tx wait is `15 + 1.5 * activeNodes + 0.5` seconds and does not replace HOP retransmission timing. | slot-parity, reservation-lifecycle, preamble-selection smokes |
| MAC | ACK-before-DATA concatenation; first nonfitting DATA head blocks later entries; strict wire-size bounds 256/512/1024/2048/4096 bytes at 8/16/32/64/128 kbps; 16-member DATA stop; high-rate head sent alone. Aggregate rate uses the slowest selected member. | `CsrMacCore::DoTx`, `FitsConcatFrame`; concat smoke |
| HOP | Reliable ordinary DATA; at most two HOP retransmissions. Initial expiry cannot start before actual MAC transmission. Retries retain DSCP, and the final ACK grace is twice the ordinary two-second resend interval. ACK/DACK removes queued retransmission copies at MAC. | `model/csr-hop-layer.h`; sent-time and retry-DSCP smokes |
| HOP | Global pending threshold 16 admits a final transfer to 17; neighbor threshold starts at zero (one effective outstanding packet). Positive ACK frees capacity; three ACKs may grow the window; retransmission and DACK feedback alter its growth state. | flow-control and sent-time smokes; latest PR #50 |
| HOP + forwarding | ACK/DACK uses a 64-sequence, 16-bit-wrap window; ACK wins overlapping masks. ACKed duplicates are not redelivered but receive feedback. DACK-marked retries remain eligible for reassessment. Local application delivery always ACKs; relay DACK uses the pre-enqueue source/destination count at threshold 16. | DACK-hold, no-route-relay, and NWK/HOP integration smokes |
| HOP + forwarding | DACK transfers custody, releases sender source/destination flow count immediately, and holds sender HOP global/neighbor capacity until 20 seconds (40 at max retry). Expiry releases capacity and wakes queued work. Ordinary DATA retry exhaustion does not declare a routing link failed. | DACK-hold and sent-time smokes |
| Integration | App delivery is independent of sender acknowledgment: lost ACK may exhaust sender reliability while application delivery remains successful. Duplicates, retry transmissions, receiver-signal observations, and delivered application packets need distinct metrics. | HOP receive/completion ownership and Tranche 1 physical-observation contract |

Port behavior through MATLAB callbacks, logical frame records, bounded queues,
and the existing scheduler. Do not transliterate ns-3 `Object`/`TypeId`, `Ptr`,
`Packet` allocation and tags, `NetDevice` boilerplate, global `Simulator`,
`Callback` registration, `TraceSource` plumbing, or console diagnostics. Logical
wire lengths and stable node/sequence identities matter; framework-specific
in-memory serialization does not constitute the CSR wire format.

The independent gate should reject broken retry ownership, premature expiry,
capacity leaks, duplicate application delivery, hard collision drops replacing
PHY/ECC, nonexistent sleep/wake acquisition, or claims that fixed paths establish
routing. Minor event ordering, historical DSCP slot variants, exact aggregate
preamble traversal quirks, and source-global timer-scan coalescing can be explicit
parity backlog entries where aggregate behavior is preserved. Source no-route
custody policy (record first sequence, suppress its ACK, then ACK its duplicate)
must be addressed with the actual routing layer in Tranche 3.

Runtime evidence must distinguish original ns-3 smoke execution, static MATLAB
review, owner-run R2025a MATLAB tests, and any native R2026a tests. No MATLAB
execution is implied by this source board.
