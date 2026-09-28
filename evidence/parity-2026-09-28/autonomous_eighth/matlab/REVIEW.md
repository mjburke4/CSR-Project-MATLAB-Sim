# Relative timer review of the eighth owner return

The returned J case passed all 45 component checks and reached 45.662638077 seconds. Its next random request was node 3's 75th PHY uniform for physical signal `21474836517`: MATLAB counted 52 payload bits and native counted 51. The BER was identical, as were the rounded-nanosecond component and interval endpoints. Before this stop, 758 random requests and 129 physical transmissions matched. The failed request was not consumed.

The bit allocator is behaving as written. The mismatch originates in an acquisition callback scheduled by adding two binary64 seconds values. MATLAB used `45.656008077000003 + 0.00663 = 45.662638077000004`; native added 6,630,000 integer ticks to tick 45,656,008,077 and returned `45.662638076999997`. That one-ULP difference puts the interval product on opposite sides of 52, so truncation correctly returns 52 versus 51. The same captured uniform produces zero errors in either local calculation; this numerical boundary is not itself evidence of an observed delivery or latency gap.

## Source-confirmed correction

The existing `TransportTiming('nanoseconds')` option quantizes only receive arrival, preamble-end and packet-end targets. Its policy deliberately leaves acquisition and other relative timers unchanged. K supplements that existing option with an isolated relative-timer helper; it does not change `TransportTiming` or the Model bit-allocation formula.

The helper rounds current clock and delay to integer nanoseconds, adds exact tick values, then divides the sum by `1e9` for the portable scheduler. Source review confirms these target sites:

- PHY acquisition after the configured SYNC-to-Track delay.
- Rejected tracked reception's 28 ns fallback return to Search.
- The existing paired PHY and MAC transmission-completion callbacks. Both use the same corrected target, and PHY remains inserted first. The PHY `TxUntil` cache uses that same deadline.

Native uses a single MAC transmission-completion event followed by the device callback. MATLAB's existing two-callback decomposition is retained. Updating only PHY would reorder the pair; K binds an isolated MAC copy whose finish event alone uses the shared helper. The generic MAC `after()` function and other MAC timers remain unchanged.

`ReceiverTimerSignalEngine`, `ReceiverTimerMac` and `ReceiverTimerSimulation` are exact source-bound copies plus those target/binding changes. All original 99 model files, prior J classes, semantic comparator policy, PHY geometry, BER, bit truncation, uniforms and strict bit-count guards remain unchanged. With missing/continuous transport timing, the candidate PHY retains its original continuous targets; the candidate simulation also leaves MAC completion on the original path.

## Batched evidence

The independent native arithmetic replay covers all 1,542 sampled components and all 4,070 recorded intervals. Integer-nanosecond targets preserve every recorded bit count. Applying the old floating acquisition addition to the same fixed history produces nine sampled-component and 15 interval-count differences. These are fixed-history arithmetic results, not a new autonomous network result.

The full capture contains 1,352 acquisition schedules and 811 transmission-completion contexts. In the returned J prefix, 230 acquisition schedules join native clock ticks exactly, but 58 binary64 endpoints differ. Its paired TX completions have 36 differing binary64 targets among 129 contexts. The correction batches the confirmed target sites; it does not run an extra network for each arithmetic instance.

Native `Time::GetSeconds` uses a fixed-point conversion. Simple tick division differs from it by one ULP at two of 10,301 captured clock values. Both conversion paths produce identical counts across the full 1,542-sample / 4,070-interval sweep. K therefore claims exact integer target ticks and observed allocation-count coverage, not universal bit-for-bit equivalence of every possible native clock conversion.

## Component and runtime boundary

The new public preflight checks full acquisition-target fixtures, the stopped allocation, the complete sampled-component geometry, actual acquisition callback timing, unchanged continuous fallback and the paired public MAC/PHY completion path. It also checks the 28 ns target arithmetic. No rejected-return instance occurs in the available J prefix; that branch's schedule contract is source-confirmed, with full autonomous exercise pending.

Each K run records `relative_timer_target` observations plus `receiver_timing.csv` and `receiver_timing_summary.json`, including after diagnostic stops. These supplement the unchanged arrival/preamble/end transport records. Targets describe scheduling decisions, not proof that each scheduled callback executed. The bounded observer records omissions without interrupting an already-mutated simulator; any omissions fail the returned evidence-completeness check.

No MATLAB runtime is available here. All prior owner evidence is preserved as history, and accepted natural A reuse still requires its exact gates. New preflights and K remain pending. No full-network ±15% accounting or latency parity is claimed by the arithmetic correction.
