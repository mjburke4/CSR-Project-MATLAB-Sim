# Completed grouped-control retry: seed 132

There is a specific source-level difference in HOP-to-MAC cleanup after the final ACK of a grouped routing control. No accepted production file has been changed. MATLAB runtime confirmation is pending.

## Original native evidence

The captured frame with fixture ID 132 is a retry of node 8's routing-control group `7:5;2:9`, with outer destination 7 and outer sequence 5. The fixture ID is an observer identifier, not a network application ID.

| Time (s) | Native event |
|---:|---|
| 91.494 | Original grouped control actually transmits. |
| 91.879972442 | ACK from primary peer 7, sequence 5, is partial; peer 2 remains outstanding. |
| 93.494000028 | Retry frame 132 enters node 8's MAC queue. |
| 93.557475346 | ACK from secondary peer 2, sequence 9, completes routing sequence 5 and releases its HOP/NWK owner. |
| 93.749712442 | A repeated ACK from peer 7, sequence 5, is stale; the structured retry remains queued. |
| 94.042 | Native transmits aggregate frame IDs `123;124;127;128;133;134;132`, including the retained retry. |

The source records are in `inputs/frames.csv`, `inputs/inputs.csv`, `inputs/tx.csv`, and `native/capture/run.log`. The native log explicitly records `Reliable RoutingControl completed with 2 seq=9 routingSequence=5` at 93.557475346 s. The queue admission and later transmission bracket that completion.

## Difference in the public call chain

Native `CsrHopLayer::ReceiveFromMac` calls `CancelAcknowledgedFrames` with the received ACK's peer/sequence before processing a reliable-control ACK. Native `CsrMacCore::CancelAcknowledgedFrames` skips every queued header with `HasDestinationSequences()`. It therefore retains a structured routing retry even when HOP finishes that group.

MATLAB production `csr.hop.Layer.complete` marks the secondary target acknowledged and, when all targets are complete, returns cancellation using the group's primary `e.Peer` and `e.Sequence`. `receiveFeedback` passes that pair through `CancelMac`. The production `csr.mac.Layer.cancel` removes matching queued ACK-required frames by primary destination/sequence and has no structured-destination exception. With a queued retry, that path removes it.

The difference is separate from a replay bridge problem: native bitmap cleanup calls cannot be translated blindly into MATLAB's scalar cancellation API because MATLAB's normal HOP caller filters partial and unknown ACKs first. The replay bridge must preserve the meaning of its captured inputs, while this regression exercises the unmodified production HOP/MAC call chain directly.

## Focused regression

`diagnostics/grouped/run_grouped_retry.m` runs both supported queued-retry policies. It supplies an original actual-TX notification to the production HOP API, receives the primary exact ACK, waits for the real two-second retry timer, and admits that retry into the real production MAC queue. A fixed receiver Track state holds that queued retry. The final secondary ACK then passes through production HOP and its real MAC cancellation callback.

Sequences are normalized to the new fixture's allocator; peer roles, grouped ownership, retry timing, and final-secondary-ACK order are preserved. The native history oracle expects HOP ownership to complete while one retry remains in MAC. The current source predicts a zero-depth MAC queue, one primary-destination cancellation, and `known_behavioral_difference=true`. That prediction is not labeled as an executed MATLAB result. A confirmed difference must remain a failed parity comparison; the test does not suppress cancellation to force agreement.
