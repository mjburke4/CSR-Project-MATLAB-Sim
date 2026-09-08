# Tranche 2 MAC access and wake state machine

`csr.mac.Layer` is the release-independent owner of transmit access, the two
MAC queues, reservations and receiver wake timers. The PHY signal engine owns
signal acquisition and PHY success/failure. HOP owns DATA retry state. No
MATLAB wireless toolbox API is embedded in this class.

The implementation was inspected against current ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, principally
`model/csr-mac-core.h` and the inline MAC and duty-state implementations in
`model/csr-net-device.h`. Supporting source regressions inspected include
`csr-mac-slot-parity-smoke.cc`, `csr-mac-reservation-lifecycle-smoke.cc`,
`csr-mac-ack-queue-smoke.cc`, `csr-mac-concat-smoke.cc`, and
`csr-mac-preamble-selection-smoke.cc`.

## Interface and ownership

Construct with `Layer(nodeId, scheduler, streams, config, callbacks)`. The
configuration is either a complete scenario with a `Mac` section or the MAC
section itself; `Layer.defaults()` supplies the shared defaults. Call `start`
once. `enqueue(frame)` returns whether a frame was admitted; `cancel(peer,
sequence)` removes queued copies of acknowledged DATA. `receive(envelope,
decision)` records a successfully decoded sender and its reservation once per
physical reception, including overhearing.

| Callback | Contract |
|---|---|
| `Transmit(envelope,duration)` | Start exactly one physical transmission of the aggregate. |
| `Sent(member)` | Report each selected member at actual TX start, after `Transmit`; HOP can arm its DATA timer here. |
| `SetReceiverState(state)` | Request Search or Idle in the PHY. |
| `ReceiverState()` | Return the current PHY state; slot/sleep callbacks reconcile it. |
| `HasSync()` | True while a source-admitted preamble is present. |
| `Event(name,frame,details)` | Optional bounded observation hook; some timer events have an empty struct frame. |

The PHY adapter calls `receiverChanged(state)` for actual Search/Track
transitions. For a successful tracked reception, the engine delivers decoded
members while still in Track; HOP can enqueue an ACK before the engine returns
to Search. That transition activates transmit preparation immediately.

Envelopes contain ordered `.Segments` cells. Every member has the agreed HOP
fields and complete modeled `WirePayloadBytes`. The aggregate sums those full
sizes, selects the slowest member rate, and uses the largest power among
members at that slowest rate. All selected members use the shared rate,
power and preamble. Root simulation code assigns a unique physical identity;
HOP sequence identity is independent.

## Implemented behavior

- DATA queue: 512 entries, reject the new arrival before stable descending
  DSCP insertion. An arriving high priority packet never displaces an older
  queued packet. Equal priority retains FIFO ordering.
- ACK/DACK queue: 256 entries, ACK-first packing, five total transmissions
  (initial plus four retries) owned by MAC. Exact destination/sequence ACKs
  deduplicate. A cumulative window replaces the first entry for that peer and
  resets its transmission count even when the queue is full.
- Access: independent 300 ms holdoff and 13 ms relative Search slot timer.
  Countdown and neighbor reservations advance only in Search without SYNC.
  Track, Tx and SYNC freeze countdown. PREP_TX may activate under SYNC but may
  not transmit through it. Counter zero must advance to minus one before TX.
- Idle queued traffic requests the next global 13 ms RTS boundary, deferring
  to a periodic wake when it falls within half a slot. Idle-to-Search then
  establishes a relative slot phase and restarts holdoff.
- Fine active-node range table, optional already-multiplied slot reduction,
  guarded strict `range - reduction > 1`, and current free-slot ordinal scan.
  Neighbors' current counters are avoided rather than their original slots.
- Every transmission advertises and retains its newly selected next
  reservation, even if queues empty. A first decoded packet creates the
  neighbor after reservation processing, so its first reservation is ignored.
- Concatenation: ACKs first, then DATA priority order; stop at the first
  non-fitting entry. Complete wire bytes must be strictly less than
  256/512/1024/2048/4096 at 8/16/32/64/128 kbps. A high-rate aggregate without a
  source-defined limit admits only its head; if a later low-rate member lowers
  the aggregate rate, the corresponding source limit applies.
- Preamble freshness uses `15 + 1.5*localActiveNodes + 0.5` seconds. The source
  aggregate destination walk is preserved, including the order-dependent
  unknown-destination reset. Reported active nodes expand slot range but do
  not expand this freshness threshold.
- Source-aligned periodic wake at 0.988 s, initially Idle; initial no-signal
  Search lasts 1.1 ms boot plus 7.8 ms. Track-to-Search uses only 7.8 ms.
  Transmit preparation and post-TX wait keep Search awake. A drained
  transmission starts the same `15 + 1.5*N + 0.5` second post-TX wait.

`snapshot()` exposes queue depths, queue drops, ACK replacements/repetitions,
transmissions, aggregate membership count, preambles, queue delay accumulation
and reservation state. A transmit count means physical aggregates; segment
count is separate.

## Explicit scope and parity boundaries

- Historical OPNET slot-selection variants are deferred. The baseline uses
  current ns-3's fine free-slot profile. No supervisor or energy model is
  instantiated; `SlotReduction` is an explicit scenario parameter.
- The MATLAB aggregate has a strict maximum of 16 total members. Current ns-3
  checks this limit only after DATA insertion, so an ACK-only aggregate can
  exceed 16 when its byte budget allows. This bounded implementation
  difference is explicit; normal 8 kbps ACK packets hit the byte limit first.
- `ReservationSlotOverride` fixes the chosen slot for controlled tests. It
  does not install ns-3's special 100 ms common-epoch alignment used only by
  its differential collision fixture. Production scenarios leave it at -1.
- The original source can indefinitely block an oversized queue head when
  multiple entries trigger concatenation. MATLAB retains that behavior and
  exposes `PackingBlocked` plus pending depth. Its one-second retry does not
  bypass the head. Use an admissible frame size or disable concatenation for
  a deliberately oversized research fixture.
- Queues mutate before the `Sent` callback so callbacks may safely enqueue
  new work. This differs from the C++ callback's internal container-mutation
  ordering; the sent membership and physical sent time are preserved.
- Relay-holdoff SNMP metadata is deferred with NWK control integration. The
  inspected current ns-3 field belongs to NWK custody/control behavior and
  is not a transmission suppression mechanism in MAC; no MAC gate is invented.
- MATLAB random streams are deterministic per node/subsystem but are not
  ns-3 RNG streams. Identical numeric seeds do not promise identical slots.

`tests/TestMacLayer.m` prepares integrated access/queue/timer checks, including
actual-TX callback timing, SYNC/Track suppression, ACK retry ownership,
priority, packet sizes, preamble order, wake transitions, and reservations.
Prepared tests and static lint are not a claim that MATLAB executed here.
