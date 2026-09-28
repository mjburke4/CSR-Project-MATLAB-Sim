# PHY relative-timer arithmetic review

The first J stop is a **callback-time arithmetic mismatch**, not a different PHY bit-allocation rule. Both implementations truncate a positive binary64 interval-length × bit-rate product. MATLAB's acquisition callback retains the result of floating-point `Now + 0.00663`; native schedules an integer-nanosecond delay and converts the resulting clock time to seconds. The one-ULP endpoint difference crosses an integer-bit boundary.

| Value at node 3, PHY draw 75 | MATLAB J | Native |
|---|---:|---:|
| Interval start, binary64 seconds | 45.656008077000003 | 45.656008077000003 |
| Interval end, binary64 seconds | 45.662638077000004 | 45.662638076999997 |
| Rounded endpoint nanoseconds | 45662638077 | 45662638077 |
| Elapsed-time × rate | 52.00000000000977 | 51.999999999954042 |
| Truncated payload bits | 52 | 51 |

The bit rate is `4 / 0.00051`, the source's actual S0 rate. The two implementations identify the same transmitter, interval, payload component, and BER. Adding an epsilon or rounding the product would change native behavior; the existing truncation must stay.

## Observed timer audit

All **230 J acquisition schedules** join a native acquisition lifecycle record by receiver, scheduling nanosecond, and deadline nanosecond. The traces agree on the timer's integer identity, but 58 MATLAB deadlines differ in their binary64 representation from `deadline_ns / 1e9`. All 230 fired, including the rejected draw's callback. Thus the current failure belongs to a repeatedly exercised timer-construction path.

| J timer path | Scheduled | Fired before stop | Binary64 deadlines differing from ns/1e9 |
|---|---:|---:|---:|
| PHY acquisition | 230 | 230 | 58 |
| PHY TX completion | 129 | 127 | 36 |
| MAC TX completion | 129 | 127 | 36 |
| PHY rejected-receive return, 28 ns | 0 | 0 | No runtime coverage |

Each of the 129 PHY TX completion schedules has a paired MAC completion with **the exact same current deadline**, and the PHY callback was inserted first. Preserve that pair and insertion order if correcting completion timing; do not quantize only one side. `TxUntil` should use the same corrected deadline as the PHY completion callback.

These deadline differences do not themselves prove additional packet or network outcomes. The 52-versus-51 acquisition stop is the directly observed semantic failure. J had already accepted 129 physical transmissions and 758 random requests; the 759th request was rejected before consuming an unrelated sample.

## Whole-fixture arithmetic checks

All 1,352 native acquisition lifecycle records have `deadline_ns = start_ns + 6,630,000`. Applying floating addition to fixed native rows gives two intentionally distinct tallies:

- **335/1,352** deadlines differ when both clock conversions use `integer_ns / 1e9`, the proposed MATLAB representation.
- **336/1,352** differ when both clock conversions use the pinned native `NanoSeconds(...).GetSeconds()` implementation.

The native C++ clock probe found two exceptional values among 10,301 checked where native `GetSeconds()` and direct division differ by one ULP: 29.068008077 seconds and 36.994979163 seconds. One is an acquisition scheduling origin, explaining the one-count difference. Direct division must therefore not be described as bitwise-identical to native clock conversion everywhere.

Nevertheless, the independent native arithmetic sweep confirms that **all 1,542 captured sampled component counts and all 4,070 reconstructed interval header/payload allocations agree** using either exact native clock conversions or integer-nanosecond division. Its fixed-history floating-acquisition counterfactual changes nine sampled component counts and 15 intervals, including a following interval whose start inherited the changed acquisition endpoint. These are arithmetic results on fixed traffic and event history, not a corrected autonomous trajectory. See [native arithmetic summary](../native/arithmetic_summary.json).

For the 811 captured physical transmissions, evaluating the current floating TX-duration addition on native start ticks differs from integer-component addition in **216 cases**. The recomputed integer deadlines join 810 native `OnMacTxFinished` lifecycle entries; the remaining deadline is 330.0548 seconds, beyond the capture horizon. This further supports testing TX completion as the same relative-timer arithmetic family. It does not establish future packet behavior.

## Source mapping and repair scope

| Path | MATLAB source | Native source | Review conclusion |
|---|---|---|---|
| Acquisition | `SignalEngine.m:241`, especially `:251` | `csr-net-device.h:1199`, `:1209` | Correct relative callback addition in the controlled native-timing mode. |
| PHY TX completion and `TxUntil` | `SignalEngine.m:166–170` | `csr-net-device.h:753`, `:2634–2657` | Same native integer-duration semantics; batch with MAC completion, preserve event ordering. |
| Paired MAC TX completion | `Layer.m:538–547`, shared helper `:732` | `csr-net-device.h:2634–2657` | `Callbacks.Transmit` enters PHY first, then MAC schedules its own completion; both must share the deadline. |
| Rejected receive return | `SignalEngine.m:530–531` | `csr-net-device.h:2110–2116` | Native schedules `CsrOpnetTic`; MATLAB's intended 28-ns delay needs integer-component addition. Source-supported, no J runtime coverage. |
| Receive start/preamble/end | `TransportTiming.m:66–86`; `SignalEngine.m:195–201` | Native receive callback scheduling | Earlier timing policy already addresses these callbacks; retain it. |
| Bit allocation | `Model.m:132–171` | `csr-phy-model.h:700–761` | Operand structure and truncation correspond; leave unchanged. |

MATLAB paths above are in `autonomous_seventh/kit/autocase/model/+csr/`, with `SignalEngine` and `Model` under `+phy`, `Layer` under `+mac`, and `TransportTiming` under `+sim`. Native paths are under `autonomous/native_env/csr/model/`.

Batch component tests for acquisition, the paired PHY/MAC TX deadline and `TxUntil`, and the unexercised 28-ns rejected return. Exercise the current failing timestamp, earlier noncanonical callbacks, representative later fixture values, and zero/short delays. Keep the selected timing mode's integer-component composition explicit: round the current clock and the relative delay separately to nanoseconds, add the integers, then convert for the portable scheduler. The existing transport timing object already bounds this arithmetic to exact-integer range.

**A global scheduler rewrite is not warranted by this mapped scope.** The portable scheduler also accepts absolute deadlines, MAC slot-grid deadlines, NWK timers, and user-facing simulation horizons; rounding every supplied time would change all those paths without proving each source's relative-versus-absolute construction or same-time ordering. Extend the existing optional native callback policy at the mapped relative-timer sites and retain the scheduler's insertion-order behavior. Broader clock integration could be reviewed separately if a remaining recorded mismatch requires it.

Keep the continuous physical signal start, preamble, end, geometry, and header/payload boundaries unchanged. Native itself stores continuous propagation-derived signal times separately from its quantized callback clock. Correcting those continuous values would alter the PHY formulas instead of matching the timer behavior.

## Reproduction and limits

```bash
python autonomous_eighth/receiver/audit_relative_timers.py
```

The script reads existing J and native evidence plus the native C++ clock-probe output. It writes [relative_timer_audit.json](relative_timer_audit.json), [observed J timers](observed_J_relative_timers.csv), [native acquisition arithmetic](native_acquisition_arithmetic.csv), and [native TX arithmetic](native_TX_finish_arithmetic.csv), including input hashes and explicit policy labels. No MATLAB runtime, production edits, or network simulation were used. Corrected network execution and the 15% full-run parity target remain unvalidated.
