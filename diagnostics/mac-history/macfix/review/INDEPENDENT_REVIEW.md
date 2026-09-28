# Independent MAC batch review

Status: ready for the four-part MATLAB run, including a focused regression expected to expose the HOP/MAC cancellation difference described below. MATLAB execution remains pending; no MATLAB pass or full-network parity claim is made.

## Evidence checked

- All 99 bundled core files are byte-identical to the accepted receiver-replay core. The check is recorded in `core_binding_review.json`.
- The native observer preserves 362,584 original trace rows across all 30 fields. Its comparison uses full rows and unequal-length detection, not a truncated prefix comparison.
- Independently compared the issued native reference against the captured source: all 1,761 transmissions and 2,018 raw draws agree exactly. All three native replay processes have zero exit codes and completion markers.
- Independently compared all 50,033 relevant native MAC state, reservation, transmission, and queue-statistic rows, excluding only the global event index. Every row and remaining field agrees. Input hashes in the fidelity receipt match the issued fixtures. See `native_fidelity_review.json`.
- Reviewed the 694-case slot-selection runner and native fixture receipt, including five expected production probe-exhaustion cases. MATLAB compares case identities, row counts, expected failure classes, ranges, and selected slots.
- Reviewed the HOP window test against the production public APIs and timer values. Its per-policy expectations are 11 acknowledgments, three failures, one DACK/expiry, and ten retransmissions. This is explicitly a MATLAB regression with a native-history/source-derived oracle.

## Runtime and experiment checks

The MATLAB harness checks native fidelity before execution, retains failures separately for nodes 2, 4, and 8, and compares every warm-up and target-window transmission. It checks transmission times, consumed and advertised slots, bytes, rate, power, preamble, duration, and ordered frame identities. Raw draw timing, ordinals, bounds, values, missing/extra rows, and unused draws are checked. Missing or additional transmissions cannot pass through a common-length-only comparison.

The receiver tape contains Idle/Search/Track availability and SYNC inputs; it contains no own-transmission command. Predicted own transmissions cannot be terminated by a recorded receiver input. Queue processing, slot selection, countdowns, and actual transmissions remain computed. Explicit nested getters expose changing receiver and SYNC state to the MAC.

The generated validation MAC differs from the accepted implementation by its class/constructor name, three explicit receiver lifecycle ownership changes, a passive reservation-decrement observer, and a native-input cancellation bridge. The observer schedules no event, draws no random number, and changes no protocol state. The bridge translates native bitmap cleanup requests into eligible scalar calls to the unchanged production `cancel` method, preserves structured-destination frames, and rejects ambiguous keys before mutation. Four preflight cases check structured preservation, unchanged direct cancellation, 16-bit wrap, the highest bitmap bit, and ambiguous-key rejection. Duty-cycle configuration remains enabled to preserve the Idle RTS near-wake guard. The fixture scheduler uses integer nanoseconds. These boundaries are documented; autonomous receiver duty cycling and the production continuous-time scheduler are outside this comparison.

The batch wrapper verifies bound files, runs the independent groups despite a group's failure, retains structured partial results, and archives them for return. Exact 64-bit decimal bitmap parsing is present; the fixture includes values up to UINT64_MAX.

## Issues resolved during review

1. Optional empty peer fields were initially parsed as required numbers; parsing is now conditional.
2. Frame imports initially omitted the native destination, power, and destination-list column names; the aliases now match the fixture.
3. Native control packet types were initially mapped incorrectly; the mapping now follows the pinned native enum, including KEY_REQUEST cancellation.
4. The history result initially lacked the wrapper's `pass` field; it now exports its behavioral comparison result.
5. Receiver/SYNC callbacks now use explicit nested getters, avoiding ambiguity from anonymous capture of scalar values.
6. The native fidelity gate and the integer-nanosecond scope are explicit.

## Additional cancellation-boundary finding

Native `CancelAcknowledgedFrames` is a bitmap cleanup request and explicitly skips frames with structured destination/sequence lists. MATLAB HOP filters feedback before calling its scalar MAC `cancel` API. Translating every native bitmap bit directly into that scalar API would remove a queued grouped routing frame on a partial or stale ACK. The replay bridge must preserve the native input meaning rather than changing the accepted core to accommodate its tape.

A separate, concrete production-path difference also appears in the frame-132 history: node 8 transmits group `7:5;2:9` at 91.494 s, queues its retry at 93.494000028 s, and receives the final group ACK from node 2, sequence 9, at 93.557475346 s. Native completes the HOP group but retains its queued structured frame, which transmits at 94.042 s. MATLAB's production HOP `complete` returns the primary `(7,5)` cancellation when the group finishes; production MAC `cancel` removes a queued frame with that primary destination and sequence. This source-level difference warrants a focused completion/cancellation regression and must not be concealed by the tape adapter. MATLAB has not yet executed that regression.

The native raw `cancel_ack` at 93.749712442 s is a later stale ACK; it is not the original completion event. At 75.562973632 s, frame 77's primary ACK is explicitly partial, and MATLAB's normal HOP caller would issue no cancellation.

The fourth batch test, `diagnostics/grouped/run_grouped_retry.m`, exercises the unmodified production HOP and MAC call chain for both queued-retry policies. It does not use the cancellation bridge. It checks a real HOP-timer retry admitted into the real MAC queue, followed by final secondary-ACK completion. The native-history expectation is queue retention; a removed retry produces a completed but failed parity comparison and a `known_behavioral_difference` result. Detailed provenance and the normalized fixture design are in `GROUPED_CONTROL_FINDING.md`.

This review cannot substitute for execution in MATLAB R2025a or newer.
