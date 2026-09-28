# Common-input MAC history test

`run_mac_history(root, outputDir)` runs nodes 2, 4, and 8 independently from
natural startup through 665 seconds. An exception for one node does not prevent
the other two tests. The focused comparison window is 657–665 seconds.

The fixture supplies identical enqueues, cancellations, successful-reception
metadata, active-node counts, receiver availability, SYNC, and raw MAC slot
draws. Actual transmission times are outputs, never replay commands. Native
isolated replay must reproduce the original capture before MATLAB can run.

The accepted core is unchanged. `generate_mac_adapter.py` makes one uniquely
named validation class and an exact source diff. The class retains production
queue, slot, holdoff, historical avoidance, packing, preamble, and TX behavior.
It suppresses three autonomous receiver duty actions because receiver
availability is an input at this test boundary. Duty-cycle configuration remains
enabled so the existing RTS guard near a periodic wake remains intact. One
passive callback records actual local reservation-counter decrements.

The native cancellation input is a bitmap-level queue operation. MATLAB's
public `MAC.cancel(peer, sequence)` instead receives already filtered HOP
custody decisions: cumulative feedback excludes control owners, and exact
control ACKs defer cancellation until group completion. Therefore the adapter
translates the captured bitmap into native-eligible keys in the **actual replay
queue**, excluding structured-destination frames, and invokes the unchanged
production `cancel` method for those keys. It aborts if a protected structured
frame shares an eligible cancellation key. This bridge preserves the common
queue-cancellation input; it does not claim to test HOP group completion or
change production cancellation behavior.

Four short runtime checks exercise this translation before the history replay:
structured-frame protection while preserving direct production cancellation,
16-bit sequence wrap, the highest uint64 bitmap bit, and rejection of ambiguous
protected/unprotected keys. These are bridge checks, not HOP parity claims.

The separate grouped-control cleanup diagnostic covers a concrete higher-layer
case found during fixture review: after a queued routing retry's final group
ACK, native HOP completes the owner while leaving the structured MAC retry
queued, whereas MATLAB HOP requests cancellation using the group's primary
peer/sequence. The conditional history replay deliberately supplies the native
queue-cancellation inputs and cannot establish equivalence for that HOP
completion behavior. No accepted production file is changed by either test.

The test compares every warmup and target TX row: exact nanosecond, consumed
slot, newly advertised slot, ordered input frame IDs, wire bytes, rate key,
preamble bits, and duration. Power uses a 1e-9 dB representation tolerance.
Raw draw count, per-node ordinal, time, requested support, and value must match;
all supplied pre-stop draws must be consumed. Diagnostic MAC events expose
queue depths, state, SYNC, preparation, holdoff, and the live counter. These
intermediate MATLAB events are diagnostic; they are not silently substituted
for the independent native TX/draw reference.

The receiver tape cannot overwrite or terminate a MAC-predicted TX. Such
availability inputs are recorded as ignored. ACK/DACK bitmaps are read as text
and converted by exact uint64 digit accumulation. Captured frame IDs retain
enqueue/replacement identity through aggregate selection. The fixture is
explicitly checked to carry link-control rate and power on every frame.

This is a conditional MAC scheduling test. A pass does not establish the
full network ±10% milestone or independent receiver-duty lifecycle parity.
Execution errors still write available TX, MAC events, draw usage, input
application records, and the first comparison difference. Core/runtime file
binding, the top-level batch runner, and output archiving are handled by
`run_mac_batch`.

MATLAB is not installed in the preparation environment. Static fixture checks
and native replay are completed there; MATLAB runtime acceptance remains the
purpose of the supplied batch.
