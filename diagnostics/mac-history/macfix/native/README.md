# Native MAC history replay

This fixture records and replays seed 132 for nodes 2, 4, and 8, from simulation initialization through 665 seconds. The comparison window is 657 <= t < 665 seconds. The complete warmup reconstructs MAC queues, neighbor reservations, timers, and prior random draws; no late-time state snapshot is injected.

The original scenario, source pins, and source hashes are bound by `../reference/fidelity.json`. `capture/prefix-equality.json` verifies that passive capture reproduces every original differential-trace row before 665 seconds: 362,584 rows and all 30 fields. The source repository files are unchanged. `prepare_overlay.py` creates an isolated instrumented copy of the headers.

## Boundary

Inputs are HOP-to-MAC enqueue and cancel calls, active/reported node counts, decoded neighbor observations, receiver-state updates, SYNC availability, and raw slot-selection integers before reservation avoidance. Each enqueued packet has a passive tag identifying that exact input, preserved by packet copies. The serialized compatibility packet, envelope annotation, decoded metadata, and tag identity are provided in `../inputs/frames.csv`.

The replay runs the production MAC's queueing, packing, priority, ACK repetition, reservation selection and countdown, holdoff, Idle RTS, transmission, and completion functions. It computes TX duration using the production PHY airtime function. The receiver's own wake/sleep/post-TX availability decisions are supplied from the recording. In the native replay overlay, `RefreshDutyState`, `OnMacTxFinished`, and `SchedulePendingTxWake` do not independently schedule receiver transitions. The native duty-enabled flag, aligned wake phase, and periodic-wake calculation remain configured for the MAC's near-wake Idle RTS guard. This is a MAC scheduling boundary test, not a test of independently regenerated receiver availability.

Actual transmissions are outputs; no original own-TX schedule is injected. A successful replay must consume every slot draw at the original nanosecond, ordinal, and requested range. It must reproduce every transmission's time, consumed slot, next advertised slot, byte count, rate, power, preamble, airtime, and ordered input frame IDs. The independent full MAC trace comparison also covers every state change, preparation, countdown, holdoff, and MAC queue statistic, excluding only the full simulator's global event index.

All external inputs are prequeued in ascending `(time_ns,event_order)` order. The original simulator's unrelated events are absent. Full original-versus-isolated fidelity proves this insertion convention does not change the observed MAC history in this fixture; it is not a universal claim about arbitrary equal-time inputs.

## Observed gates

| Node | Full warmup TX | Target-window TX | Raw slot draws | Full MAC trace rows |
|---|---:|---:|---:|---:|
| 2 | 607 | 11 | 682 | 17,380 |
| 4 | 589 | 14 | 689 | 16,848 |
| 8 | 565 | 14 | 647 | 15,805 |
| Total | 1,761 | 39 | 2,018 | 50,033 |

All comparisons passed with zero timing tolerance and no unused draws. All 1,160 queued input frames carry explicit link-control rate and power. All transmissions use rate key 8, whose actual bit rate is `4 / 0.00051`, not 8,000 bit/s. The CSV converter asserts that rate restriction rather than silently assuming another rate mapping.

## Reproduction in the original workspace

The scripts expect the existing engine and CSR sources at `startup131/environment/{engine,csr}` and the original seed-132 scenario/reference under `original_extracted/t25up/evidence/tranche-25-ns3-reference/s132`. They use the existing Debug ns-3 shared libraries and GCC C++23; they do not rebuild the entire engine.

Run sequentially from the workspace root, allowing each process to finish before reading or packaging its outputs:

```sh
python3 mac_replay/native/prepare_overlay.py
python3 mac_replay/native/build_capture.py
python3 mac_replay/native/convert_capture.py
python3 mac_replay/native/build_replay.py
python3 mac_replay/native/verify_fidelity.py
```

The MATLAB batch uses the provided inputs and references and does not need the native engine or these build scripts. MATLAB acceptance remains pending until the returned runtime results are checked.
