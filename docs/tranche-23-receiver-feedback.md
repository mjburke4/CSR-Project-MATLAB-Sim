# Tranche 23 receiver-feedback diagnostic

## Objective and baseline

Determine whether identical decoded arrivals at node 8 produce matching
ACK/DACK decisions, relay/local admission and custody accounting in MATLAB
and the pinned ns-3 production implementation. T22 accepted 89 focused tests
and 364 adaptive-window checkpoints; no window-update fix was justified.
T23 preserves all 390 accepted T22 source bindings, including 178 MATLAB files.

The working campus target is ±10%, evaluated separately by flow and metric.
The prior three-seed screen had network delivery within that band in all three
seeds, while per-flow exceptions remained. T23 makes no new campus or OPNET
performance claim.

## Controlled contract

Sender 7 supplies relay DATA to receiver 8, which forwards toward destination
1 through neighbor 2. Node 8 also attempts local applications using the real
application admission gate. Prescribed downstream transmissions and ACK/DACK
completions drive the real NWK/HOP ownership callbacks. No NSDP count is set by
the fixture. Autonomous MAC/RF transmission, discovery and security ingress
are outside this test.

| Case | Question |
|---|---|
| relay_boundary | Does pre-enqueue relay pressure ACK the 16th packet and DACK the 17th? |
| local_relay_independence | Does the local quota stay independent of relay custody? |
| ack_duplicate | Is an ACKed duplicate answered without another NWK delivery? |
| dack_duplicate_pressure | Does a DACKed replay take another custody owner under pressure? |
| dack_reassessment_after_release | After three releases, does the DACKed replay become ACKed and take another owner? |
| release_idempotence | Do repeated ACK/DACK completions release ownership once, with DACK capacity held until expiry? |
| local_delivery_bypass | Does delivery to node 8 avoid relay-pressure DACKs and duplicate custody? |

The frozen plan contains 123 actions. Each action is followed by a declared
one-microsecond settling interval before its state checkpoint. This drains
NWK pumps and HOP +TIC wakes; it does not claim same-tick callback-order parity.
Feedback is captured when actually enqueued, with its real timestamp and full
64-bit windows recorded as hexadecimal strings. Comparison uses exact integer
state and hexadecimal bits, with a 1 ns time tolerance.

Eighteen common milestones contain 81 assertions. Two additional native-only
milestones contain four assertions about replay custody. Those native-only
observations are not imposed on MATLAB as passing test expectations.

## Reference provenance and finding

Current upstream `ns3main` was inspected and remains pinned at
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; the engine is pinned at
`6b5cd24ea80713ce16d88575869aedd6f432bdae`. All 110 CSR and 4,012 engine
tracked sources and nine retained T22 libraries were reverified. The T23
fixture was freshly compiled; the unchanged engine libraries were reused.

All seven native cases completed: 123 checkpoints, 91 feedback frames and
20 milestones. Observer-on/off outputs match byte-for-byte, and actual MAC/RF
transmission count is zero. The fixture uses production HOP and NWK logic.

The native replay under pressure increases custody from 17 to 18 owners.
After three ACK releases, the reassessed replay increases custody from 14 to
15 owners and is ACKed. Source review shows MATLAB's NWK Seen map suppresses
repeated ownership for the same application identity. The owner MATLAB run
will establish its observed counts and any associated feedback differences.
Neither implementation is changed to force agreement.

## Implementation and gates

- `+csr/+validation/receiverFeedbackContract.m`: integrated public MATLAB
  NWK/HOP fixture and raw state/feedback collection.
- `tests/TestReceiverFeedbackContract.m`: 12 new focused tests for common
  milestones, actual ownership, admission and truthful comparison receipts.
- `scripts/ns3/tranche23_receiver.cc`: native controlled fixture.
- `scripts/run_tranche23_ns3_reference.py`: build/input provenance and native
  observer comparison.
- `scripts/generate_tranche23_contract.py`: frozen action and milestone inputs.
- `run_tranche23_validation.m`: 79 tests across five classes, source/reference
  checks, main replay and failure-preserving return archive.
- `scripts/analyze_tranche23_return.py`: independent returned evidence review,
  exact comparison recomputation, common milestones and integrity checks.

Source changes, malformed evidence, missing cases or failed focused tests
block diagnostic acceptance. Intact native/MATLAB differences outside the
common assertions remain explicit findings and do not cause the runner to
abort. The return checker reports every differing field; it never applies the
campus tolerance to deterministic states or declares numerical parity.

## Next decision

If MATLAB confirms the replay custody difference, identify its frequency in
the accepted campus traces and assess whether a narrowly scoped experimental
option is warranted. A production behavior change would need its own tests
and matched performance evidence. If the controlled implementations agree,
retain the baseline and investigate the next observed divergence instead.
Do not start another full campus run solely because this diagnostic completes.
