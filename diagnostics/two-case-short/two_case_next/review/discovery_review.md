# Returned discovery replay review

The four success mismatches are caused by the replay feeding completion-owned Search outputs back into the receiver before its receive-completion callback. No production PHY change is supported by this return.

The 25 target outcomes agree on arrival nanoseconds, collision counts, and error counts. Success agrees in 21 cases. All four mismatches are native successes changed to MATLAB `prior_stage` failures.

| Seed | TX | Source → receiver | Native completion (s) | Replayed Search precedes continuous completion |
|---|---:|---|---:|---:|
|131|6239|4 → 5|72.308832444|0.469 ns|
|132|6330|4 → 2|57.581793632|0.365 ns|
|132|7402|4 → 2|62.590313632|0.365 ns|
|132|8414|4 → 2|67.800813632|0.365 ns|

Each listed receive completion has an exact-time Search row in the imported state tape. `run_discovery_replay` prequeues those rows as external state changes. `DiscoverySignalEngine` computes propagation and completion continuously. `setReceiverState` overwrites Track with Search, while `makeDecision` requires Track. The reported `prior_stage` failure, together with the other decision fields, identifies this state-order condition. Even quantizing completion would leave a FIFO-order problem because external state actions were inserted before the TX callbacks create receive-completion events.

Native seed-131 capture provides the ordering proof: physical TX 17179869190 (fixture TX 6239) reaches node 5 at 72.267012444s, is acquired at 72.273642444s, and is accepted at 72.308832444s while the receiver remains Track. `CsrNetDevice::EndReceiveSignal` evaluates/delivers the packet and only then invokes `ReturnToSearchAfterReceive`. The replay has promoted that output transition to an earlier input.

All 278 skipped external inputs are also explained. Independent reconstruction using the exact airtime arithmetic reproduces 43 seed-131 skips and 235 seed-132 skips; every skipped Search is at its own transmitter's native TX-end timestamp. They are duplicate completion events, not interior-TX behavior differences. Some other TX-end records do not skip because floating addition places the engine completion a fraction of a nanosecond earlier.

The seed-131 selected 4→2 outcomes remain 16/16 native failures and 16/16 MATLAB failures, so this return does reproduce that observed propagation failure for the selected transmissions. The sole seed-131 mismatch is the 4→5 positive request at 72.308832444s. Seed 132's three positive controls are affected by the same replay defect and cannot presently be used to reject the production implementation.

Correct the harness by preserving state-event ownership: bind completion-owned returns to Search to their receive/TX completion and check them after engine handling; continue injecting real external wake/sleep requests. Preserve native callback timing and order explicitly. Do not add an arbitrary epsilon or indiscriminately suppress all Search inputs while Track. Then repeat the same short MATLAB test. This analysis does not claim that a corrected run passes or that complete network parity has been demonstrated.

Detailed event rows and arithmetic are in `evidence.json`.

## Harness repair prepared

The converter now verifies the fresh native differential state history against the immutable archived fixture and classifies actual transitions. Only Idle→Search and Search→Idle become external PHY inputs. All Track/Tx transitions and returns to Search remain expected outputs. Native observer wake/sleep records independently confirm all 122 seed-131 external inputs. This classification is based on state ownership, never on the expected receive-success flags.

For seed 131, the repaired bundle includes 122 external duty inputs for receiver 2, 412 actual state transitions for receivers 2 and 5, and 501 request-hook records retained for audit. Both the 223-entry PHY draw tape and 162 transmissions remain byte-identical. Seed 132 uses the same actual-transition classification for its checked receiver 2; it is explicitly an archived observational control because native PHY draws are not available for that case.

The MATLAB runner now checks expected state before applying any exogenous input, logs actions and emitted state transitions, records error time/stack, compares full state histories for checked receivers, and reports the 22 primary targets separately from the 3 archived controls. A real conflict stops that case with diagnostics instead of forcing the receiver state. The production SignalEngine and its draw-tape copy are unchanged.

Verification completed here: converter regression over the real capture; all 122 native wake/sleep observer crosschecks; a duplicate request cannot become a new state input; mutations to actual state history or TX size are rejected; MISS_HIT parses/lints the modified MATLAB runner. The corrected MATLAB replay has not been executed here.
