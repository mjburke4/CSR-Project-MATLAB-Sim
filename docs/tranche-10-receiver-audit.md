# Tranche 10 receiver audit and controlled comparisons

The c129 early path does not establish another receiver-policy defect. Both implementations use the same acquisition delay, admitted-preamble gate, Track ownership and successful receive-release order. They apply those rules to different initial transmissions and reservations. Leave PHY/ECC, BER and radio policy unchanged.

This audit reads accepted T9 evidence and pinned ns-3 `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; it does not rerun the diagnostic. The original native directory was unavailable. Reversing the verified T9 observational overlay recovered all 24 model/runner files, including 15 independently checked contract headers. Every recovered file subsequently matched the fresh pinned checkout. `evidence/tranche-10-receiver-audit.json` and `evidence/tranche-10-source-recovery.json` retain the hashes.

## The initial receiver sequence

| Observation | MATLAB T9 | Pinned ns-3 |
| --- | ---: | ---: |
| Node 2 first reservation | 9 | 3 |
| Node 3 first reservation | 1 | 7 |
| First DATA transmitter | 3 | 2 |
| First DATA TX | 300.326 s | 300.352 s |
| Gateway periodic wake | 300.352 s | 300.352 s |
| First signal arrival | 300.326004 s | 300.352004 s |
| First Track entry | 300.358630 s | 300.358634 s |
| First DATA completion | 301.375104 s | 301.401104 s |
| Gateway first ACK reservation | 10 | 28 |

MATLAB already has the node-3 preamble in its admitted SYNC table when the gateway wakes. It acquires 6.63 ms after wake. Native node-2 DATA begins at wake and takes 4 microseconds to propagate 1200 m, so acquisition occurs 6.63 ms after arrival. The native arrival timestamp above is derived from its recorded TX time and unchanged propagation law; the Track trace agrees with it. The 26 ms completion difference follows the two-slot TX difference and equal 1.0491 s frame airtime.

Subsequent source-2/source-3 receptions freeze the gateway reservation in different orders. The native slot-28 countdown survives two Track intervals and an ACK replacement before its first ACK TX at 303.849 s. MATLAB's slot-10 opportunity produces an ACK at 302.549 s. The first gateway DATA receptions in these sequences have no collision or bit-error observations. This is evidence against an ACK rate/power correction in this example, but does not prove every remaining difference is stochastic.

## Source comparison

| Rule | MATLAB | Native | Finding |
| --- | --- | --- | --- |
| SYNC admission and 6.63 ms acquisition | `SignalEngine.hasSync`, `beginSignal`, `scheduleAcquisition` | `UpdateSyncPresence`, `BeginReceiveSignal`, `ScheduleAcquisition` | Same admitted active-preamble gate |
| Candidate choice | `SignalEngine.acquire` | `AcquireSignal` | Same arrival-order selection and age gate for a stronger candidate |
| Preamble expiration | `SignalEngine.endPreamble` | `EndReceivePreamble` | Both clear SYNC and cancel the pending acquisition event |
| Successful physical completion | `SignalEngine.endSignal`; MAC `onStateChange` | `EndReceiveSignal`, `ReturnToSearchAfterReceive` | Delivery while Track, immediate Search, 7.8 ms no-signal sleep when no owner keeps Search |
| Rejected completion fallback | `returnRejectedToSearch` | `ReturnRejectedReceiveToSearch` | Source TIC delay and intervening MAC-state ownership retained |

The current sampled path uses source-aligned unconditional wakes, so native compatibility-mode randomized duty phases are outside this comparison. MATLAB uses independent `mt19937ar` streams and explicitly does not promise ns-3 stream equivalence. Same seed 129 is a reproducible label in each simulator, not a shared draw sequence.

## Prepared receiver contracts

The new `receiverTimingContract` and `tranche10_receiver_contract.cc` drive actual public receiver/device APIs with one fixed transmission. The MATLAB side includes the real MAC wake/sleep bridge; the C++ side uses `EnableOpnetAlignedDutyCycling`, `SendToPeer`, the receive callback and public state/decision getters. No test-only production hooks are needed.

All fixtures use 1200 m, 617 modeled wire bytes, long preamble, 128-kbps profile and +33 dBm. The source propagation/BER/ECC equations and threshold mean remain unchanged. The explicit controlled setting disables random SYNC-threshold sampling. Header/payload BER and errors must be zero under these chosen, already observed link conditions. There is no custom error hook, forced reservation, HOP ACK generation or contention outcome claim.

| Fixture | TX | Expected Track | Comparison purpose |
| --- | ---: | ---: | --- |
| Preamble before wake | 0.962 s | 0.994630 s | Admitted SYNC survives Idle; acquisition starts at wake |
| Preamble at wake | 0.988 s | 0.994634 s | Propagation precedes acquisition even at wake |
| Preamble just after wake | 0.990 s | 0.996634 s | Acquisition beats the 8.9 ms search deadline and cancels sleep |
| Acquisition canceled by sleep | 0.991 s | 1.982630 s | Initial sleep cancels acquisition; surviving long preamble is acquired at the next unconditional wake |

Each fixture checks state immediately before/after lock, preamble expiration, physical completion and no-signal sleep. Delivery must occur while Track and Search must resume at completion. Lock probes are one nanosecond on either side of the source deadline; they bracket the transition rather than inventing an unobserved exact callback timestamp. Seven MATLAB tests cover four fixtures and an expected 154 native-matched checkpoints.

The C++ and MATLAB checkpoint keys match statically. Time values compare within 1e-12 s; all state/count/pass and zero-BER values compare exactly. Native CSV values use 17 significant digits. Native execution passes **154/154 checkpoints** across the four fixtures (38 + 38 + 38 + 40). The contract uses the freshly rebuilt, recorded native engine. All four declared native artifact hashes and sizes and the compiled contract source hash verify. MATLAB execution remains pending. Focused MISS_HIT 0.9.44 static lint passes for both new MATLAB files using its MATLAB 2022a parser. This is not MATLAB execution. The seven MATLAB tests remain prepared; only the native checkpoints and static parser have executed.

For the residual contention investigation, apply an identical prescribed SYNC/Track occupancy schedule and a unique-free-slot neighbor construction to both real MACs. Run both observed receiver histories through both models, preserving the same queue stimuli and avoiding their inequivalent forced-slot setters. That can isolate countdown/scheduling behavior without claiming matched RF randomness. The MAC specialist separately found a strict-future Idle RTS floating-point boundary; it is a bounded scheduling correction, not an explanation for the different c129 initial reservation draws.

Source line pointers in pinned `model/csr-net-device.h`: periodic wake 1010, SYNC presence 1184, acquisition scheduling 1200, Track-to-Search release 1215, incoming signal 1576, preamble expiration 1712, acquisition selection 1741, receive completion 1917. Corresponding unchanged `+csr/+phy/SignalEngine.m` methods begin at 69, 188, 200, 307, 315, 425, 469 and 475. Full path/hash/method mappings are in the JSON audit.

Native checkpoints SHA256: `a3562a3f23e5603359610b150e20551f5a671298d7db529e037d842ce7206c1a`. Native reference manifest SHA256: `174762d34299aef0e9383c19bc9275c32535abfd21213d370c0677a84408ac07`. The manifest binds the fresh engine provenance, source headers, compiled contract, run commands and closed output files.
