# Tranche 9 source audit and controlled service contracts

Authoritative ns-3 source: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
MATLAB before this change: T8 acceptance commit `d0f3c56`, executed code `89b62e7`.

## Confirmed cancellation mismatch

MATLAB `+csr/+mac/Layer.m`, `cancel` and `cancelControl`, cleared `PreparationActive` whenever cancellation left both queues empty. This included a no-op cancellation while queues were already empty. The pinned ns-3 `model/csr-net-device.h`, `CsrMacCore::CancelAcknowledgedFrames` and `CsrMacCore::CancelQueuedFramesByType`, only remove matching entries. They preserve `m_txPreparationActive` and the live reservation.

That state matters at `SlotTick` / `slotTick`: when counter zero expires, an active preparation can transmit queued work immediately. An inactive preparation instead invalidates the old reservation and selects another slot. The MATLAB change removes only those two resets. Actual Idle transitions still clear preparation and holdoff through the unchanged state machine.

The deterministic reproduction starts MAC in Search, prescribes the source historical modulo slot profile, supplies local population three and a fixed range reduction of 29 (range 31 becomes 2), and populates two neighbor counters so only slot 1 is free. This is a public-API test stimulus; it does not instantiate the excluded supervisory layer. At 0.013 s the shared timer selects slot 1. Holdoff ends at 0.300 s. The 0.312 s tick leaves counter zero. Cancellation removes the sole queued DATA or KEY_REQUEST at 0.315 s. An ACK arrives at 0.320 s. Preserved preparation transmits it at the 0.325 s tick. A reset would defer service; that is a source-derived prediction for the old MATLAB code, not an executed MATLAB result.

## Native reference and MATLAB gate

The fresh standalone executable compiled against hash-verified original CSR headers and preserved ns-3 shared libraries passes **101/101** checkpoint rows across six cases:

| Case | Checkpoints | Purpose |
| --- | ---: | --- |
| mac_ack_wait | 14 | Cumulative replacement retains the initial holdoff and first opportunity. |
| mac_ack_sync | 17 | SYNC freezes countdown through 0.400 s; first TX is at 0.416 s. |
| mac_ack_track | 17 | Track freezes the same timer and Search resumes preparation without restarting holdoff. |
| mac_cancel_then_ack | 18 | DATA cancellation preserves the prepared opportunity for a subsequent ACK. |
| mac_control_cancel_then_ack | 18 | KEY_REQUEST cancellation preserves the same opportunity. |
| hop_release_order | 17 | Capacity releases before NSDP callback; resend/MAC cleanup precede one coalesced +TIC wake. Duplicate ACK does not release capacity twice. |

The receiver-state transitions and HOP ACK arrivals are prescribed. MAC sends locally with no peer channel; HOP feedback uses direct ingress. These tests do not certify RF delivery, collision/PER behavior, or identical random streams. Neighbor constraints force an identical slot regardless of each simulator's actual random draw.

Reference: `evidence/tranche-9-contract-reference/checkpoints.csv`; SHA256 `2991bbc93e5ba2c64d06a93cee278160cd9baf2fdc11b052ee5b0cb561fe4b73`. The manifest records all source/header/build/command/library identities and successful native execution. Only the standalone contract executable was rebuilt. `scripts/run_tranche9_ack_contract.py` reproduces that operation.

`csr.validation.ackServiceContract(outputDirectory)` executes real MATLAB MAC/HOP methods, emits the same checkpoint CSV and a JSON summary, and compares all row identities and values to that native reference with 1 ns numeric tolerance. Seven MATLAB unit tests enforce these contracts. No MATLAB/Octave runtime exists here; MISS_HIT 0.9.44 static analysis passes the two new files and changed MAC class. Owner execution remains the gate.

## Controls that are not interchangeable

The existing ns-3 `SetReservationSlotOverrideForDifferentialRun` also rephases the next timer to a future common 0.1 s epoch and resets a live reservation inside `ActivateTxPreparation`. MATLAB `ReservationSlotOverride` only provides the result of `pickSlot`; it retains the existing timer phase and live reservation. The new fixtures deliberately do not compare these different controls. Their production defaults remain unchanged.

## Policies audited as aligned in the sampled direct path

Cumulative ACK destination replacement resets transmission count and retains queue position in both simulators. Exact ACK duplicate suppression and five transmission attempts agree. Search TSLOT ordering, holdoff independence, and Track-to-Search activation agree. Positive HOP ACK releases pending/outstanding capacity before NSDP, keeps the resend entry alive through that callback, then removes resend/MAC ownership and requests one separate +TIC NWK wake. The three-ACK threshold-growth-before-retry-reset order agrees.

This finding does not establish that cancellation caused contention seed 129's application residual. The six-case RF diagnostic return, including early per-event observations and measured T8 comparisons, is still needed to determine effect and regressions. PHY/ECC and ACK radio policy are unchanged.

## Regression sensitivity check

A scratch-only copy of the original ns-3 headers was mutated to restore the two queue-empty preparation resets present in accepted T8 MATLAB. The unchanged new contract executable then exited 1 and failed **12 of 101 checkpoints**, exclusively in the two cancellation cases; the other four cases remained passing. Removing that deliberate mutation is the already executed 101/101 reference. This confirms fixture sensitivity to the cancellation defect. It is a native counterfactual, not execution of old or repaired MATLAB. Artifacts are in `evidence/tranche-9-mutation/` (`mutation.patch`, `result.json`, `checkpoints.csv`, compile/run logs). The authoritative ns-3 checkout was never modified.
