# Tranche 3 HOP control transport

The HOP layer now carries reliable control groups of one to ten destinations
through the same bounded resend queue as DATA. Controls do not occupy DATA
pending slots, adaptive neighbor windows, DACK holds, or NWK source/destination
pair counts. Existing DATA failure reporting still does not declare a route or
neighbor failed.

The inspected reference is ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, principally
`model/csr-hop-layer.h`: `SendRoutingControl`, `EnqueueResend`,
`NotifyMacFrameSent`, `HandleAckFrame`, `CheckResend`, `CheckReceivedSeq`, and
the destination/sequence projection in `ReceiveFromMac`.

## Transport behavior

- Each destination has its own wrapping `uint16` transmit sequence, shared
  between DATA and addressed controls. Receive sequence windows and cumulative
  ACK bitmaps are shared as well. A grouped receiver selects its own sequence
  before checking duplicates. Addressed duplicate controls are ACKed without
  redelivery.
- A control group retains one original frame and one resend record. Positive
  feedback marks individual destinations complete. Partial ACKs leave the
  original frame's destination list, sequence list, payload and DSCP intact on
  every HOP retry. The last ACK cancels pending MAC copies using the original
  primary destination/sequence.
- Initial and retry ACK clocks start only on `notifySent`. Defaults remain a
  two-second resend interval, two retries and a four-second final grace period.
  The complete final-expiration pass precedes all retry admissions at the same
  time. A queued retry awaits its actual transmission notification.
- Control expiration reports only peers still lacking ACKs. HOP releases the
  old group before notifying NWK; NWK owns any fresh residual-destination retry.
  A retry rejected by MAC reports the same terminal ownership release.
- Broadcast destination `16777215` is allowed only as the sole destination of
  an `AckRequired=false` control. It does not use the peer-specific receive ACK
  window. Discovery freshness/duplicate policy remains with NWK. Addressed
  best-effort controls use their peer sequence but do not generate feedback.

## API and wire-size boundary

```matlab
allowed = hop.canSendControl(peerIds); % reliable admission, no DATA gates
[accepted, frame] = hop.sendControl(control, peerIds, options);
hop.notifySent(frame);
hop.receive(frame, phyDecision);
```

`control` is a scalar struct with `Id` (scalar `uint64`), `Type`, `Payload`
(scalar struct), and `WirePayloadBytes`. Supported uppercase character-vector
types are `DISCOVER`, `KEY_REQUEST`, `KEY_UPDATE`, `NEIGHBOR_CHECK`, `ROUTING`,
`SNMP_START`, and `SNMP_DONE`. Type-specific payload and routing-section
validation belongs to the NWK/control codec.

`WirePayloadBytes` is the complete logical MAC envelope byte count supplied by
the caller, including HOP, control and any modeled security overhead. The HOP
constructor copies this count exactly; it never measures a MATLAB struct or
adds security overhead a second time. `ApplicationPayloadBytes` is always zero.
The routing codec's raw section bytes are only part of this envelope.

Radio options are `RateKeyKbps`, `TxPowerDbm`, `Preamble`, `EnvelopeProfile`,
`GeneratedSeconds` and `AckRequired` (default true). These use existing PHY and
frame validation. The returned frame has `Kind='CONTROL'`, `Dscp=7`, the original
`Control`, row-vector `DestinationIds` and `HopSequences`, and the first pair in
`DestinationId`/`Sequence` for compatibility with MAC queue cancellation.

| Callback | Contract |
|---|---|
| `DeliverControl(control, previousHop)` | Receives each newly accepted addressed control once. No DATA custody, route or NSDP callbacks run for controls. Broadcast discovery is passed through for NWK freshness handling. |
| `ControlResult(control, peer, success, complete, remainingPeers)` | One positive result per newly ACKed peer; `complete` becomes true on the final ACK and `remainingPeers` is then empty. On terminal failure, one negative result per residual peer is issued, with `complete=true` only on the last callback. Every failure callback carries the complete residual set for NWK retry ownership. |
| `CancelMac(primaryPeer, primarySequence)` | Invoked for a reliable control only after the whole group completes or fails. Existing MAC cancellation already matches all acknowledged frame kinds. |

For best-effort controls, `ControlResult` success means actual transmission,
without evidence of reception. Per-peer transmission results are emitted by
`notifySent`, with `complete=true` on the final target. Admission returning
false transfers no ownership and emits no terminal result.

`stats()` adds control admission, transmission, retry, ACK, completion, failure,
receive and duplicate counters. `ControlPending` counts active groups and
`ControlPendingTargets` counts peers still lacking ACKs. `ResendQueueDepth`
counts both DATA records and control groups; existing DATA counters retain
their original meanings.

## Explicit portable policies

Admission remains transactional: a full shared resend queue refuses before
MAC admission, and a MAC rejection rolls back the control group and its
tentative sequence allocation. This extends the Tranche 2 overload policy;
source ns-3 can send an untracked 513th frame. Invalid or duplicate targets
are rejected before state changes.

The callback interface suppresses repeated partial-ACK success notifications,
although the source can repeat those notifications while a group remains
pending. This makes NWK completion accounting idempotent without changing
transmission, retry, or ACK handling. An unexpected DACK bit addressing a
control is counted and ignored; controls cannot enter DATA custody or consume
its windows. These are deliberate integration contracts rather than claims
of malformed-feedback source parity.

This tranche models logical control transport and explicit security byte
counts. It does not implement or claim cryptographic authentication,
encryption, or security replay protection.

## Validation

`tests/TestHopControls.m` supplies 22 focused MATLAB test methods covering
group admission, shared DATA/control capacity and sequences, MAC rollback,
partial ACKs, unchanged retry targets, residual failure ownership, cumulative
ACKs, receive sequence wrap, duplicate suppression, control/DATA isolation,
broadcast handling and same-time expiration ordering. Tests use named nested
fixture readers so their observations share the callbacks' mutable workspace.

The engineering workspace has no MATLAB runtime. Static syntax/lint results
are reported with the integrated Tranche 3 candidate; these tests and the
accepted Tranche 2 regression suite require actual R2025a/R2026a execution
before the control transport can receive runtime acceptance.
