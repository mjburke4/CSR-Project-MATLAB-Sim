# Seed 132: autonomous receiver availability and preamble history

## Result

The existing evidence places the first transmission divergence at the gateway's first discovery frame, long before application traffic. It also explains why nodes 2 and 4 have opposite awake/asleep states at 300 seconds: they are reacting to different preceding control-traffic histories. The inspected receiver timer rules agree between current MATLAB and the pinned native source; this audit does not establish a new receiver-state code defect.

The two networks do not start the application interval from a common receiver history. A MAC replay that forces native receiver states cannot resolve that difference, even when it exactly reproduces MAC transmissions.

This is an offline analysis of existing captures and source. No simulation or production change was made.

## First discovery difference

Both captures show node 1 enqueuing its initial discovery work at 10 s, waking from Idle at the next slot boundary, 10.01 s, and ending its 300 ms holdoff at 10.31 s. There is no earlier RF transmission or pre-existing heard neighbor at this point. The first eligible decrement is 10.322 s.

| Quantity | MATLAB | Native ns-3 |
|---|---:|---:|
| Initial Idle→Search/prepare | 10.010 s | 10.010 s |
| Holdoff completes | 10.310 s | 10.310 s |
| Initial selected slot | 10, inferred | 11, captured |
| First discovery TX | 10.452 s | 10.465 s |

The MATLAB value is inferred from the 11 eligible countdown ticks ending at -1; its raw draw was not exported. Native `inputs/draws.csv` directly records node 1 ordinal 1, draw 11, support [0,31], at 10.01 s, and its reservation trace records 11→10→…→-1. With the empty initial neighbor table, no reservation-avoidance remapping applies. This is a difference in the selected initial reservation, not evidence of a countdown off-by-one defect. The source countdown semantics match: decrement only in Search with no SYNC after holdoff; transmit at -1.

The 13 ms gateway difference alone is not proven to cause the full subsequent divergence. Later MAC and PHY draws are also independently generated.

## First receiver-history departures along the relevant path

The table compares each node's state-transition timestamps until their first departure (tolerance 1 ns). MATLAB's ordinary trace omits state labels; each reported MATLAB Track transition is independently paired with its PHY `phy_track` row. The target nodes' prior regular wake/sleep timestamp sequences match. A timestamp-prefix match does not prove equality of all hidden state.

| Receiver | MATLAB first extra Track | Transmitter and addressed peer | Native's next transition | Native's first Track |
|---|---:|---|---:|---:|
| 4 | 19.766642444 s | 5→1, overheard | Idle at 19.768900 s | 41.502630 s |
| 2 | 41.502630000 s | 4→5, overheard | Idle at 41.504900 s | 57.310630 s |
| 8 | 56.322645346 s | 2→4, overheard | Idle at 56.324900 s | 73.118630 s |
| 7 | 61.262642442 s | 8→2, overheard | Idle at 61.264900 s | 87.938630 s |

These transitions are driven by different actual RF traffic, including overheard traffic. They do not compare receiver implementations supplied with the same arriving signals. First Track is an acquisition event, not necessarily successful protocol delivery or discovery completion.

The specific source observations and adjacent state records are in `first_state_timing_divergence.csv`, `first_state_timing_context.csv`, and `matlab_first_track_phy_context.csv`.

## Why availability differs at 300 seconds

| Node | MATLAB state at 300 s | Most recent MATLAB TX | Native state at 300 s | Most recent native TX |
|---|---|---:|---|---:|
| 2 | Idle | 267.683 s | Search | 282.789 s |
| 4 | Search | 296.361 s | Idle | 207.428 s |
| 7 | Search | 282.698 s | Search | 298.116 s |
| 8 | Search | 282.607 s | Search | 298.025 s |

Native state labels are directly recorded. MATLAB state is reconstructed from the last transition's identified cause: node 2's periodic sleep at 299.3729; node 4's TX completion at 297.40854; node 7's TX completion at 282.75308; and node 8's tracked-reception completion at 282.753092442. There is no intervening state transition before 300. The recent native transmissions are SNMP controls; MATLAB's corresponding controls are identified by the preceding `mac_enqueue` records with `ControlType=SNMP_START` (267.025635346, 295.885592444, 282.025632442 and 282.160172442 s for nodes 2, 4, 7 and 8). The availability calculation does not assume that both engines sent the same control frames.

Thus MATLAB node 2 must execute an Idle RTS wake and fresh holdoff after admission at 300, while native node 2 is already in Search. The situation is reversed for node 4. Nodes 7 and 8 are in Search in both, but retain different reservations, peer freshness and random-stream positions. Equal state names alone do not establish equal MAC state.

Actual first DATA TX times are node 2: 303.953 vs 301.639 s; node 4: 300.196 vs 300.391 s; node 7: 301.496 vs 300.092 s; node 8: 300.144 vs 316.719 s (MATLAB vs native). The MAC queue head can be ACK, so these use MATLAB `hop_sent` DATA, not the first aggregate transmission after 300.

Native node 8's slot 18 is interrupted by node 7's DATA after native node 7 selects slot 6. Its first feedback transmission at 300.482 precedes its own DATA; feedback replacement and service continue for 34 transmissions. In MATLAB, node 8 sends its own DATA at 300.144 before source 7 can complete service. That long transmission makes nodes 7 and 2 Track at 300.150642442 and 300.150645346, delaying their own countdowns until approximately 301.381 s. This supplies a direct causal link from different initial service order to different subsequent admissions and generated traffic. It does not isolate a same-input receiver defect.

## Why node 8 uses a long preamble in MATLAB

Before the MATLAB node-8 DATA at 300.144 s, its last successful reception from node 2 was at 268.730555346 s. That reception is 31.413444654 s old. In native, node 8 last heard node 2 at 283.836555346 before 300; before the actual DATA at 316.719 it hears node 2 again at 315.897815346 (only 0.821184654 s old).

Both production implementations choose preamble freshness using `15.0 + 1.5 * local_active_nodes + 0.5` seconds. Native node 8's recorded local active count is 3, making 20 s. MATLAB also uses local direct-peer population; even the complete seven-node campus population would give 26 s, below the observed 31.413 s age. Therefore MATLAB's long preamble and native's short preamble agree with their own received histories. There is no need to invoke a different preamble constant to explain this pair.

The long/short difference changes airtime (1.23726 vs 0.2448 s for these DATA frames), so it directly changes how long nearby receivers remain unavailable for transmission.

## Production source comparison

Native source was read from `autonomous/native_env/csr/model/`, restored at the pinned reference revision; instrumented earlier short-capture overlays were used only to interpret capture fields. MATLAB source is `return6000/kit/csr6000/model/`.

| Transition/rule | Native location | MATLAB location | Finding |
|---|---|---|---|
| Initial aligned Idle; first unconditional wake at 0.988 s | `csr-net-device.h: EnableOpnetAlignedDutyCycling, ScheduleOpnetPeriodicWake` | `+mac/Layer.m: start` | Same intended phase and startup state |
| Periodic wake reschedules unconditionally; only Idle enters Search; 8.9 ms no-signal window | `OpnetPeriodicWake` | `periodicWake` | Same logical rule |
| Pending Idle work uses next strictly future 13 ms boundary; nearby periodic wake owns boundary | `CsrMacCore::ScheduleIdleRts, IdleRts` | `scheduleIdleRts, idleRts` | Same general rule; nominal awake-window edge differs (see below) |
| Idle→Search restarts independent slot and 300 ms holdoff timers | `CsrMacCore::SetReceiveState, StartSearchTiming` | `onStateChange, startSearchTiming` | Same rule |
| Search→Track cancels no-signal sleep; Track→Search preserves slot phase | `AcquireSignal, ReturnToSearchAfterReceive` | `SignalEngine.acquire/returnToSearch`; MAC `onStateChange` | Same rule |
| Successful receive is delivered while Track before returning to Search | `EndReceiveSignal` | `SignalEngine.endSignal` | Same ordering in inspected current source |
| Rejected tracked receive defers fallback by one native TIC | `ReturnRejectedReceiveToSearch` | `returnRejectedToSearch`, +28 ns | Same quantized fallback intent |
| Track→Search with queued work immediately prepares; otherwise 7.8 ms search if no post-TX wait | `ReturnToSearchAfterReceive`, `SetReceiveState` | `onStateChange` | Same rule |
| Empty TX completion starts local-population post-TX wait; expiration in Track only clears guard | `OnMacTxFinished, PostTxWaitExpired` | `finishTx, postTxExpired` | Same rule |
| Sleep/expired Search post-TX guard cancels acquisition and enters Idle | `SleepReceiver, PostTxWaitExpired` | MAC `sleep/postTxExpired` → PHY `setReceiverState` | Same rule |
| Per-peer freshness controls long/short preamble | `ChoosePreambleForDest, SelectAggregatePreamble` | `choosePreamble, postTxSeconds` | Same formula; different received histories explain current case |

A bounded edge does differ in source: native `GetNextPeriodicWake(now)` returns `now` inside the nominal 8.9 ms periodic window, while MATLAB `scheduleIdleRts` calculates the strictly next 0.988 s boundary. If a post-TX expiry leaves MAC Idle inside that nominal window and new queued work arrives, native can defer an RTS to an already-passed periodic wake while MATLAB schedules the future 13 ms slot. Across the native 0–330 enqueue tape, the only enqueue time in the potentially differing 6.5–8.9 ms phase is 88.928212442 s (node 7, two queue entries); that node is Track during the receive callback, so the Idle branch is not exercised. This static edge is not the identified startup/300 s cause and has not been promoted to a production fix. A deterministic boundary test could establish the exact behavior separately if the coupled test reaches it.

These are source-level correspondences, not a new autonomous runtime acceptance gate. Native additionally exposes force-awake and nonaligned-duty modes; they are not the selected aligned-campus configuration. Current MATLAB's slot epoch is nanosecond-anchored, while its repeated periodic wake timer remains double arithmetic. The observed initial departure is 13 ms and an explicitly different slot, not a femtosecond wake drift. No speculative time-quantization change is justified by this evidence.

## Exact remaining evidence gap

The ordinary MATLAB protocol trace discarded callback detail fields for `mac_state` and `mac_prepare`; it did not record slot draws, draw ordinals, timer causes/deadlines, full receiver state snapshots, active-node counts at draw time, or every SYNC-presence change. Its PHY trace establishes track/signal/end outcomes but does not supply the shared callback order needed for a coupled event-by-event differential run. Complete row counts do not restore fields never exported.

An existing optional `AckServiceDiagnostics` observer retains `DetailsJSON` from production protocol callbacks, including state and prepare details. Enabling it in a bounded capture would preserve more information without changing receiver behavior, but it does not by itself add missing raw draws or every duty-cycle timer cause. A shared-input coupled test must control only exogenous traffic/random decisions and let receiver transitions occur autonomously. It must not inject `receiver_state` or decoded reception outcomes, as the old conditional MAC replay does.

The most discriminating autonomous test begins before gateway discovery, not at 300 s with unexplained divergent state. It can stop at the first mismatch. A second branch can cover the application-start interval with a common saved predecessor state only if state equivalence is verified, including reservations, neighbor freshness and timer ownership.

## Reproduction

From the project workspace, run `python3 autonomous/receiver/analyze_receiver_context.py`. It reads the existing return and short-capture paths and rewrites only this analysis directory. `input_manifest.csv` lists exact source/data hashes. Large original raw captures remain external prerequisites; this directory does not claim to be a complete simulator or standalone raw-data package.
