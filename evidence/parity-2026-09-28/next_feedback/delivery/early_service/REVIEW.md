# First source-8 delivery: native MAC service precedes the receiver-state split

Native's first source-8 DATA packet is delayed **before its first transmission**, while node 8 repeatedly sends feedback to source 7. It is not delayed by failed DATA receptions or retries. The September 23 accepted owner replay already covers this precise MAC boundary: no additional conditional MAC run is needed. The initial proposal for a node-8 replay was superseded after that older, broader return was recovered.

| Boundary | Native ns-3 | Corrected autonomous MATLAB |
|---|---:|---:|
| Application identity / HOP sequence | 884 / 14 | 6 / 13 |
| DATA MAC admission | 300.000000028 s | 300.000000000 s |
| First DATA transmission, 8→2 | 316.719000000 s | 300.144000000 s |
| Successful first reception at node 2 | 316.963815346 s | 301.381275346 s |
| Admission-to-first-TX wait | 16.718999972 s | 0.144000000 s |
| First source-7 DATA reception at node 8 | 300.336812442 s | 301.740812442 s |

These are each engine's first source-8 applications; their local IDs and hop sequences are not cross-engine identities. The first-receipt difference is 15.582540 seconds. Native uses a short preamble for its first DATA frame; MATLAB's first DATA transmission has a long preamble. The native DATA transmission succeeds immediately at node 2, with no earlier transmission of its MAC frame 444. Its node-8 HOP completion records `resend_count=0`.

## Native queue history

At 300.001 seconds native node 7's raw slot draw is 6 and node 8's is 18. Node 7 transmits DATA frame 443 at 300.092 seconds; node 8 receives it and enqueues feedback frame 445 at 300.336812442 seconds. This is before node 8's first transmit opportunity at 300.482 seconds. Its own DATA frame 444 is already queued.

From 300 seconds until its first DATA transmission, native node 8 transmits **34 feedback frames to node 7**. Twenty successive feedback queue generations, with **19 replacements**, keep that feedback entry present. Three generations are replaced without ever transmitting. Each replacement resets the repeat count. The final generation, DACK frame 607 for highest sequence 31, is admitted at 315.299812442 seconds and transmits five times:

```text
315.341  315.458  315.978  316.277  316.472 seconds
```

It then retires. Node 8 transmits its queued DATA frame 444 at the next opportunity, **316.719 seconds**. `native_node8_ack_queue_ledger.csv` preserves every update and transmission, including the remaining repeat count and whether frame 444 is still queued. The receiver-state, SYNC, received-frame, enqueue and cancellation inputs are preserved separately in `native_node8_mac_inputs_300_first_data.csv`; the raw draw tape is also extracted. These are original inputs, not invented wake events.

The corresponding autonomous MATLAB run takes the opposite early ordering: node 8 sends its own first DATA at 300.144 seconds, before node 7 transmits at 301.496 seconds and before node 8 receives that source-7 DATA at 301.740812442 seconds. Its ACK queue has no source-7 DATA feedback to prioritize before its own first transmission. The ordinary MATLAB long-run trace does not contain the raw draw or complete slot-state fields needed to call this an erroneous slot decision.

## Wire sizes and aggregation

The native fixture directly records 41 wire bytes for cumulative feedback and 217 wire bytes for DATA. The current issued MATLAB production code gives the same sizes for these inputs:

- `+csr/+hop/Frames.m`, lines 22–23: DATA wire bytes are `ApplicationPayloadBytes + 32 + securityBytes`. The current first DATA's recorded application bytes are 185 and the scenario uses the bare profile, giving **217**.
- `+csr/+hop/Frames.m`, lines 44–45: cumulative feedback wire bytes are `25 + 16*HasAckWindow + securityBytes`, giving **41** with a window and bare profile.
- `+csr/+mac/Layer.m`, lines 69–73: the rate-key-8 aggregate limit is **256 bytes**.
- `+csr/+mac/Layer.m`, lines 559–573: selection considers ACK entries first and requires the combined size to be **strictly below** the limit. **41 + 217 = 258**, so the queued DATA cannot accompany this feedback.

This is a verified size/selection correspondence for the identical replay inputs. It is not a claim that native and MATLAB use identical application-payload accounting: the native compatibility payload field and MATLAB application-byte field have different definitions, while the wire frame here is 217 bytes in both.

## Verification against the previously accepted replay

The September 24 short owner return exercised node 5 only, but the separately recovered **September 23 `out_mh_20260923_121427` return covers nodes 2, 4 and 8 from 0–665 seconds**. Its node-8 report passes all warmup transmissions, target transmissions and raw draws, with all 7,468 supplied inputs processed. The early interval belongs to its checked warmup, even though its named target interval was 657–665 seconds. Coverage checks establish matching current MAC/adapter behavior and identical node-2/8 0–330-second inputs, draws and frames after frame-ID mapping. The older node-8 frame **172** is the newer short fixture's frame **444**; the existing owner output already records its exact first transmission at **316719000000 ns**.

Check these focused assertions in the **already returned output**, in addition to its recorded full transmission/draw gates:

1. Frame 444 enqueues at **300000000028 ns**, recorded input event order **13956**.
2. Exactly **34** node-8 feedback transmissions to node 7 occur in **[300000000000,316719000000) ns**.
3. Frame 444 first transmits at **316719000000 ns**, as the only aggregate member, with 217 bytes, rate key 8, 104 preamble bits, duration 244800000 ns, consumed slot 13 and next slot 1.
4. Every native receiver/SYNC/enqueue/cancellation input and raw draw is consumed consistently, with the complete warmup and target TX tapes matching. Do not initialize an artificial empty MAC at 300 seconds.

Node 2 is covered by that same older accepted owner batch. An independent exact assertion, expressed in the newer fixture's frame IDs, is its first DATA frame 439: enqueue **300000000028 ns** (input order 13951), first TX **301639000000 ns**, 217 bytes, preamble 104 bits, duration 244800000 ns, consumed slot 30 and next slot 8. Another later service point is frame 619, enqueued **316756000028 ns**, first transmitted **319215000000 ns**. Apply the established identity mapping before comparing older frame labels.

There is no appropriate negative node-2 MAC-membership assertion for the first source-8 relay: application 884 reaches node 2's NWK at 316.963815346 seconds but is not admitted to its HOP/MAC until **423.689293688 seconds**, outside this fixture. Native MAC frame 624 belongs to node 3, not that relay. Every node-2 DATA frame actually enqueued during 300–330 seconds appears in the native transmission tape by 330 seconds.

No production change is justified by these different autonomous histories. The already accepted conditional replay supports the observed explanation that arrival order, repeat feedback occupancy and resulting traffic allocation produce the early service difference. Repeating it would add no needed coverage. The unresolved question concerns how the autonomous simulators produce different receiver availability, traffic and random-draw histories before those MAC inputs.

## What the autonomous long-run capture can and cannot answer

The corrected MATLAB protocol CSV contains exactly `TimeSeconds, Event, NodeId, PeerId, PacketId, ApplicationBytes, Reason, FrameKind, Sequence, Dscp, QueueDepth, ControlType, HopCount`. It records **when** `mac_state` and `mac_prepare` callbacks occur, but the export discards their supplied `State`, `ReservationSlot` and `ReservationCounter` details. A `mac_state` row therefore does not identify Idle, Search or Track. Transmitting state can sometimes be associated with the adjacent `tx_start`, which is not a complete state history.

| Required autonomous cause field | Available in corrected long-run output? |
|---|---|
| MAC Idle/Search/Track state values and previous state | No; callback event names and timestamps only |
| Sleep/wake timer cause, scheduled deadline and timer cancellation | No |
| Preparation-active / holdoff / post-TX-wait flags | No |
| Own selected reservation slot and countdown at prepare/TX | No; details discarded |
| Neighbor reservation table and reported/active-node count at each choice | No; final snapshots do not provide the history |
| Raw MAC random draw, ordinal, requested range and post-avoidance selected slot | No |
| Complete SYNC-present and receiver-state callback input sequence | No |
| PHY signal/track/interval/end timestamps, identities and physical outcomes | Yes, including `phy_track`; these do not supply the missing Idle/Search/wakeup cause history |
| Enqueue/replace/first-TX/receipt/completion times and application identities | Yes |
| Global callback order shared across protocol and PHY tables | No explicit shared event-order field |

`NetworkSimulation.m` lines 98–109 define the exported schemas, and lines 698–727 select the retained protocol fields. `mac/Layer.m` lines 415–424 supply prepare details that are discarded; lines 655–669 supply state labels that are discarded. The MAC's `pickSlot` reads active population, neighbor reservations and an RNG draw (lines 427–452), but the ordinary trace records none of those choice inputs. `RandomStreams.m` explicitly uses independently owned MATLAB `mt19937ar` streams and states that a numerically equal seed does not imply ns-3 stream equivalence. No raw draw history for this autonomous run is exported.

These are schema gaps, not omitted-record failures: the run can have zero omitted trace records while still lacking these fields. The existing accepted replay tests MAC response after supplying recorded native receiver-state/SYNC and RNG inputs; it does not test how MATLAB autonomously generates those inputs. This inventory supports a future narrowly scoped autonomous-observation decision, without commissioning or constructing another redundant conditional MAC replay here.

The previous runner is `source5_replay/run_source5_mac_replay.m`; its adapter is `source5_replay/mac_adapter/matlab/run_mac_history.m` with `+mac_replay/MacLayer.m`. Their hashes are recorded in the September 24 short return's `run_provenance.json`. Reproduce this offline analysis with `python3 next_feedback/delivery/early_service/analyze_early.py`; it runs no simulator.
