# Tranche 2 HOP reliability

The portable `csr.hop.Layer` owns DATA custody, per-neighbor admission,
16-bit sequence allocation, 64-entry receive/ACK windows, retransmission,
ACK/DACK completion, and delayed capacity release. MAC owns transmission,
packet concatenation, repeated ACK transmission, wake/sleep and access holdoff.
Fixed scenario paths supply the NWK-facing callbacks for this tranche;
autonomous routing and reliable routing controls belong to Tranche 3.

Source baseline: current ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, primarily
`model/csr-hop-layer.h`. This includes the PR #50 third-ACK growth correction.
No ns-3 packet pointer, EventId, transport header, or callback infrastructure
was translated literally.

## Implemented behavior

| Behavior | Implementation / source anchor |
|---|---|
| Admission | Initial neighbor threshold 0 permits one outstanding DATA. Global threshold 16 permits the source's final admission to pending 17. `GetDataAdmissionSnapshot` / `CanSendToHop`, lines 507–698. |
| Adaptive window | Every third positive ACK grows threshold up to 16, then a retransmitted completion resets the streak. A retransmitted third ACK can still grow the threshold. Final failure decreases threshold by one. `HandleAckFrame` / `CheckResend`. |
| Sequence / duplicate handling | Independent per-peer 16-bit transmit sequence, wrap-aware 64-bit receive registers, no redelivery of ACK-marked duplicates; DACK-marked retries can be reassessed. `CheckReceivedSeq`, `MarkDataDack`. |
| Actual-transmission timing | First resend timer is created by `notifySent`, never initial MAC enqueue. Default resend 2 s, two retries, final ACK grace 4 s. `NotifyMacFrameSent`, `CheckResend`. |
| Retry ownership | HOP creates the retry using the same peer, sequence, application packet and original DSCP. MAC never retries ordinary DATA independently. |
| ACK windows | ACK bits take precedence over overlapping DACK bits. HOP completion occurs before MAC queued-copy cancellation. `HandleAckWindow`. |
| DACK custody | Remove resend entry and release sender NWK source/destination count immediately; hold global and neighbor HOP capacity 20 s, or 40 s at the maximum retry count. Release at expiry plus one 36 MHz TIC. `HandleDackFrame` / `CheckDack`. |
| ACK / DACK selection | Final delivery always ACKs. Relay choice uses the NSDP count before enqueue; count >= 16 selects DACK. Source local ACK admission precedes local NWK delivery; relay NWK delivery precedes ACK admission. `HandleDataFrame`, lines 3515–3636. |
| No-route receive | Source behavior retained: first relay reception records sequence then suppresses feedback when no onward route; a retry is ACKed as a duplicate. The trace exposes this outcome. |
| Generic wake | Locally addressed ACK/DACK, including unknown feedback and the source-disabled single-DACK case, schedules one coalesced next-TIC queue wake. Final timeout and DACK expiry also wake NWK. |
| Final DATA failure | Releases custody/capacity and reports a DATA result; it does not automatically declare the route or neighbor failed. |

## Integration API

```matlab
hop = csr.hop.Layer(nodeId, scheduler, streams, config, callbacks);
allowed = hop.canSend(nextHopId);
[accepted, frame] = hop.send(app, nextHopId, radioAndPriorityOptions);
hop.notifySent(frame);          % Actual start of the MAC transmission
hop.receive(frame, decision);   % One successful addressed logical member
snapshot = hop.state(nextHopId);
statistics = hop.stats();
```

`send` returning false means the caller retains custody. Application fields,
including original source/destination, path and hop index, remain separate from
the frame's immediate HOP addresses. Logical frames come from `csr.hop.Frames`.
`Layer.defaults()` returns the explicit HOP settings.

| Callback | Contract |
|---|---|
| `EnqueueMac(frame)` | Return scalar logical MAC admission. |
| `CancelMac(peer, sequence)` | Remove matching pending MAC DATA copies. |
| `Deliver(app, previousHop)` | Accept receiver/relay custody. Return logical or a struct with `Accepted`; a void callback is also supported. |
| `RouteAvailable(app)` | Gate first relay delivery; fixed paths now, routing table later. |
| `NsdpCount(app)` | Receiver's current source/destination-pair count, observed before enqueue. |
| `NsdpRelease(app, reason)` | Sender's NWK custody-count release on ACK, DACK or final failure. |
| `Terminal(app, success, reason)` | HOP result, not end-to-end delivery. Success reasons are `ack`, `dack_custody`, and optional `sent_no_ack`. Failures are `retry_exhausted` / `mac_queue_full`. |
| `Wake()` | Ask NWK/scenario custody queues to attempt another admission. |
| `Event(name, frame, details)` | Optional bounded outer trace hook. Details include simulation time. |

The outer application ledger must distinguish a lost ACK from lost application
data. An already delivered packet, or a packet whose custody moved to a relay,
must not become an application drop when its preceding sender later exhausts
feedback retries. DACK reassessment can invoke receiver custody again for the
same application identity; outer queues must retain their identity checks.

## Explicit differences and deferred behavior

- Admission is transactional on MAC rejection. A full resend queue refuses
  before accepting custody. Current ns-3 can retain source bookkeeping when
  the 512-entry resend queue or downstream MAC admission fails. Replicating
  that retention can permanently strand capacity. This candidate uses a
  documented bounded-overload policy; the normal ordinary-DATA global limit
  of 17 cannot fill a 512-entry resend queue by itself.
- A queued retry pauses its retry clock until MAC confirms transmission.
  Current ns-3 retains `initialTxConfirmed` and a provisional enqueue timestamp,
  allowing another source-wide timer scan to act before that retry actually
  transmits. Original two-pass final-expiration/retry ordering is retained;
  source-exact stale-scan behavior for an unsent retry is deferred.
- If a relay's `Deliver` explicitly refuses custody, the fresh receive-window
  bit is cleared and feedback is suppressed so a later retry can be accepted.
  This bounded queue backpressure behavior differs from source queue-overflow
  loss. Final local delivery must accept custody; refusal raises an explicit
  integration error instead of silently ACKing unretained data.
- Logical no-ACK DATA is supported for controlled research tests. The baseline
  scenario/NWK path uses reliable DATA, as current source requires.
- Link-control selection is configured externally. This HOP layer does not
  yet reproduce the source adaptive rate/power link-cost algorithm. ACKs use
  the received rate and the emitting node's configured transmit power.
- NWK relay-holdoff metadata belongs to Tranche 3. Current source inspection
  does not justify turning that metadata into an additional MAC queue gate.
- Pairwise16 mode describes modeled byte overhead only. Authentication,
  encryption, replay state, discovery and reliable routing-control groups
  are not claimed implemented here.

## Validation boundary

`tests/TestHopLayer.m` prepares focused MATLAB tests for the above custody,
admission, timing, duplicate, ordering and overload behavior. Static MATLAB
syntax/lint checking is available in the engineering workspace; these tests
must execute in the owner's MATLAB environment before runtime acceptance.
Whole-network MAC/HOP scenarios and original ns-3 workflow evidence are
reported separately in the tranche validation report.
