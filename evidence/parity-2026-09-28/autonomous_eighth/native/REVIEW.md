# Acquisition and completion clock arithmetic

The J stop at node 3, 45.662638077 seconds, comes from the acquisition callback deadline. MATLAB adds the 6.63 ms delay to a floating-point clock value. Native adds a nanosecond `Time` delay to an integer clock. The resulting doubles differ by one ULP even though their displayed and rounded nanosecond endpoints match. The unchanged positive duration-times-rate truncation therefore returns 52 bits in MATLAB and 51 in native.

This is a timer-representation mismatch. It does not justify a floor adjustment, numerical tolerance in the bit guard, or rounding physical signal/component boundaries.

## Executed native arithmetic probe

The pinned native C++ time/PHY probe executed without running the simulator or consuming any random draw. It uses `NanoSeconds`, `Seconds`, `CsrRateKeyToBps`, and the explicit-uniform `SampleSourceBinomial` overload.

| Quantity | Native relative clock | Floating addition |
|---|---:|---:|
| Origin seconds |45.656008077000003 |Same |
| Delay nanoseconds |6,630,000 |Same intended delay |
| Deadline nanoseconds |45,662,638,077 |Same when rounded |
| Deadline double |45.662638076999997 |45.662638077000004 |
| Difference |0 |7.105427357601002e-15 s |
| Duration × rate |51.999999999954042 |52.00000000000977 |
| Truncated payload bits |51 |52 |
| Errors with recorded uniform |0 |0 |

The probability is `5.4585990544445831e-5` and uniform is `0.57293482082207758`. This occurrence produces the same error count under both bit counts. The affected node-5 signal at node 3 was already rejected after half-duplex TX; the returned MATLAB boundary shows `Rejected`, `HalfDuplex` and `MissedByState` set. No receive or delivery difference is established by this stop. The counterfactual uses the native uniform explicitly; MATLAB stopped before consuming it.

Native `ScheduleAcquisition` schedules `Seconds(m_syncToTrackSec)` relative to the current integer clock. Captured timer lifecycle event 20207 records origin 45,656,008,077 ns and deadline 45,662,638,077 ns. `AcquireSignal` obtains `Simulator::Now().GetSeconds()` and closes all live signal intervals at that value before the Track-state update. MATLAB `SignalEngine.scheduleAcquisition` currently schedules `Scheduler.Now + SyncToTrackSeconds`. The earlier `TransportTiming` experiment changed receiver arrival/preamble/end callbacks; acquisition was explicitly outside its scope.

## Full existing-capture sweep

The arithmetic reconstruction retains native traffic, event order, continuous signal geometry and component boundaries. It does not generate a corrected autonomous trajectory.

| Clock treatment | Direct observed component counts matched | Reconstructed interval count pairs matched |
|---|---:|---:|
| Original raw native interval seconds |1,542 / 1,542 |4,070 / 4,070 |
| Native callback nanoseconds converted with actual `GetSeconds` |1,542 / 1,542 |4,070 / 4,070 |
| Callback nanoseconds divided by 1e9 |1,542 / 1,542 |4,070 / 4,070 |
| Acquisition-only floating addition, including carried next-interval starts |1,533 / 1,542 |4,055 / 4,070 |

The nine sampled-count differences occur at eight acquisition closes and one following receive-end interval; moving an acquisition boundary also changes the start of the next interval. Both true-native-origin and division-origin floating counterfactuals give these nine sample and 15 interval differences. The first is exactly the returned J stop. Counts in non-consuming intervals are reconstructed from the pinned formula, not claimed as directly observed binomial sample counts.

All 1,352 captured acquisition schedules have the exact integer deadline `origin_ns + 6630000`. Floating addition differs at 335 targets when the origin is represented by `ns/1e9`; it differs at 336 when the origin uses true native `GetSeconds`. The difference between those audit counts comes from a known clock conversion ULP exception, not a different timer rule.

A native C++ conversion sweep covered 10,301 distinct observed/scheduled tick values. `ns/1e9` differs from fixed-point native `GetSeconds` at two values: 29,068,008,077 ns and 36,994,979,163 ns. Neither changes any of the 4,070 interval bit-count pairs in this fixed native history. The bounded integer-tick helper is therefore supported by this capture; it is not a universal bitwise implementation of native time conversion.

## Batched sibling timer boundaries

The source also confirms two other explicit receiver timing boundaries:

- **Rejected receive return:** native schedules an explicit 28 ns relative delay; MATLAB adds `28e-9` in floating-point. This branch has no execution in the returned J history. Its preflight is a source-derived component check, not network coverage.
- **TX completion:** native computes one duration, converts it with `Seconds(duration)`, and calls `NotifyPhyTxStart`, which schedules one `CsrMacCore::FinishTx`. That callback clears TX and invokes `OnMacTxFinished`. MATLAB represents this transition with two callbacks: PHY completion first, then MAC completion at the same deadline. Both targets and PHY `TxUntil` must use the same tick calculation while preserving that existing insertion order. Native does not have a corresponding pair of separate PHY/MAC completion callbacks.

The independent receiver audit matches all 230 returned J acquisition schedules to native and finds 58 noncanonical floating targets. Its 129 paired TX schedules contain 36 noncanonical targets; 127 pairs execute before the stop and preserve the existing PHY-first order. Across the full native capture, 811 TX durations imply 810 observed matching `OnMacTxFinished` deadlines and one completion scheduled after the 330-second capture stop. Those records support correcting the paired targets coherently rather than changing only one half of MATLAB's representation. See the separately owned `autonomous_eighth/receiver/relative_timer_audit.json` for detailed lifecycle evidence.

The proposed isolated K scope is acquisition, rejected-return 28 ns, and paired TX completion/`TxUntil` targets. It preserves the general scheduler, unrelated MAC `after` timers, payload geometry, bit arithmetic and all strict random/context guards. Actual continuation and preflight outcomes remain owner-side; no improvement in 15% network parity is claimed here.

## Reproduction and artifacts

With the pinned native environment restored, run:

```sh
python autonomous_eighth/native/run_arithmetic_probe.py
python autonomous_eighth/native/audit_intervals.py
python autonomous_eighth/native/finalize_receipt.py
```

The first executes only time/arithmetic APIs. The second reconstructs the fixed capture. `phy_component_fixture.csv` provides all 1,542 observed component contexts with raw geometry and source-reconstructed header/payload counts for public MATLAB component preflight. `acquisition_schedule_fixture.csv` provides all 1,352 actual native schedule origins/delays/deadlines. `all_interval_arithmetic.csv`, `all_sample_arithmetic.csv`, and `arithmetic_summary.json` preserve every comparison. `arithmetic_values.csv` records exact local binary64 values; `clock_values.csv` records the native conversion sweep. Compile/source/runtime hashes and execution limits are recorded separately; the compiled binary is not required in the evidence package.
