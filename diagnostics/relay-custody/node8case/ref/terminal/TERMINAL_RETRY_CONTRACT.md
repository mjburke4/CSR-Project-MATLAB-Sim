# DATA retry expiration and queued-copy contract

The returned 6,000-second candidate exposes a confirmed MATLAB/ns-3 behavioral mismatch: native final HOP expiration releases HOP/NWK ownership but leaves independently queued MAC retry copies available to transmit. MATLAB `failEntry` also cancels every queued copy for that peer/sequence. With `native-provisional` retry admission, expiration can occur after one physical transmission while both admitted retries are still waiting; cancellation then removes transmission opportunities that native retains.

This finding is bounded to the DATA expiration and subsequent-feedback paths. It does not establish how much of the complete-network latency difference this mismatch causes, or establish ±15% parity.

## Evidence chain

The immutable native source is commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` in `mjburke4/CSR-Project-NS3-part2`. `terminal_source_proof.json` records 21 exact excerpts and whole-file hashes; `retrieved_source_provenance.json` records Git blob identities for supporting files retrieved during this review. `audit_terminal_source.py` checks the relevant signatures against the actual files. This is a source audit, not a fresh native or MATLAB simulation.

| Operation | Native source behavior | Returned MATLAB behavior |
| --- | --- | --- |
| Admit retry | `CheckResend` increments retry count, updates provisional timestamp, and passes `e.frame->Copy()` to MAC. Initial confirmation remains true. | Existing `native-provisional` DATA option preserves confirmation and provisional time. |
| Final timeout | `CheckResend`, lines 4411–4723: release NSDP, decrement DATA outstanding/pending and adaptive threshold, erase HOP resend owner, schedule NWK wake. No MAC cancellation. | `failEntry`, lines 535–557: same broad release work, then unconditional `cancelMac(peer,sequence)` and terminal callback. |
| Separate MAC ownership | `EnqueueTxFrame` in `csr-net-device.h`, lines 2241–2304, stores the passed packet in a separate MAC queue entry. `DoTx` selects queued entries without consulting the HOP resend list. | `ReceiverTimerMac.cancel`, lines 180–195, removes all matching ack-required peer/sequence entries from the data queue. |
| NSDP callback | `CsrNetLayer::SetHop` wires `DecrementNsdp(source,destination)`; the callback decrements a count and emits diagnostics. It does not touch MAC queues. | `releaseFromHop` removes corresponding NWK pending custody. |
| Late MAC sent indication | Native `NotifyMacFrameSent`, lines 588–619, tolerates absent HOP owner and may schedule the fallback global scan; it never recreates ownership. | Existing DATA `native-provisional` unmatched-sent fallback already supports this behavior. |
| Late exact ACK | Native calls `CancelAcknowledgedFrames` even with absent HOP owner; HOP completion itself is a no-op when owner absent. | `complete()` returns an empty cancellation for unknown owner, leaving no late-feedback MAC cleanup. |
| Late cumulative ACK/DACK | Native completes HOP mutations then always sends the ACK/DACK bitmap to MAC cleanup, regardless of owner existence. | MAC cancellations are only collected from live HOP completions. |
| Single non-window DACK | No HOP completion or MAC cleanup; generic NWK wake still occurs. | Keep this no-op behavior. |
| Structured ROUTING copy | Native MAC feedback cleanup skips `HasDestinationSequences()` frames. | Current HOP live-owner logic deliberately suppresses ROUTING cancellation. A blanket new unknown-feedback cancellation would regress this protection. |

Native code comments describe final grace as following a final retransmission, but the executable condition uses `lastTxTime`, which the retry admission pass updates provisionally. Therefore the condition can expire while MAC copies are still queued. The behavior is not inferred merely from comments.

## Actual candidate example

Seed 132, node 5, next hop 1, HOP sequence 246, MATLAB packet 909 (source 5):

| Event | Time (s) |
| --- | ---: |
| Application generation / NWK enqueue | 562.160000000000 |
| HOP admission | 575.045111113778 |
| First and only physical TX before expiry | 593.203000000000 |
| First queued retry | 595.203000027778 |
| Second queued retry | 597.205000027778 |
| HOP failure and MAC cancellation of both queued retries | 601.508000027778 |

The NWK wait is 12.885111113778 s; the subsequent wait to first physical TX is 18.157888886222 s. The two later retry admissions are not two physical transmissions. All 11 node-5 failures in the captured 600–675 s window have this one-TX/two-queued-retry/two-cancel pattern. See the service agent's `candidate_s132_node5_terminal_cancellations.csv` and selected application timeline for actual returned rows.

The existing native 6,000-second traces independently confirm consequences beyond code inspection:

| Seed | HOP no-ACK retirements | Retired owners observed transmitting a later head DATA frame | Distinct applications first delivered after a retirement |
| --- | ---: | ---: | ---: |
| 131 | 1,297 | 990 | 979 |
| 132 | 1,418 | 1,079 | 1,029 |

The native TX linkage uses node/peer/HOP sequence and admission time, with no sequence reuse observed. Head-DATA TX counts are lower bounds because aggregates may hide non-head members. A no-ACK HOP retirement is not evidence of final application loss. An application can have multiple retired hop owners, so owner and application counts have different denominators. See `../service/native_terminal_summary.json` and the native terminal-owner CSVs for the independent trace audit.

## Narrow correction and meaningful regression coverage

Keep this first candidate isolated, with existing `actual-tx` behavior and unrelated control paths preserved:

1. For DATA, `native-provisional`, and reason `retry_exhausted`, retire the HOP owner and release NSDP/window exactly once without canceling the independently queued MAC copies. Do not use this exception for queue-admission failure or reliable controls.
2. Add a DATA-only MAC cleanup route for late feedback with no HOP owner. Exact ACK and cumulative ACK/DACK remove matching DATA copies; cumulative ordering completes all HOP mutations first. Preserve the 16-bit sequence window, ACK precedence over overlapping DACK bits, structured ROUTING exclusion, and single-DACK no-op.
3. Keep no-ACK HOP retirement distinct from final application fate. Existing `FeedbackIdentitySimulation.delivered()` and `custodyAccepted()` recover previously dropped records on late delivery/custody, but a stop with a live queued or in-flight copy must be classified unfinished rather than irrevocably lost. The report/export boundary needs a test for this case.

Run the following together in a small component batch before another long autonomous test:

- Reproduce one actual sent callback, two provisional retry admissions driven by public global scans, then HOP expiry while both retries remain in the real MAC queue. Check one NSDP release, one capacity release, no owner recreation, and two surviving copies.
- Drain the first orphan copy through real MAC service; verify the sent callback has no owner and cannot double-release or recreate custody. Verify fallback scan scheduling only when the latest timer is no longer pending.
- Exercise late exact ACK, cumulative ACK, cumulative DACK, overlapping ACK/DACK bits, 16-bit wraparound, and unknown feedback. Confirm matching orphan DATA disappears while another peer/sequence remains untouched.
- Confirm single non-window DACK leaves orphan copies alone, and queued structured ROUTING stays intact under the new DATA-only path.
- Verify first delivery after HOP retirement changes final application outcome to delivered and counts latency from original generation; also verify a stop before orphan transmission leaves an unfinished application, not a terminal loss.
- Retain existing 92 checks and the 330-second common-input acceptance test to bound regressions. Do not infer whole-network parity from these component checks.

No production source edits or new simulations were performed by this source audit.
