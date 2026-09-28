# MATLAB clock and control-order diagnosis

No model or kit file was edited during this analysis. All checks below are source inspection or independent binary64 arithmetic, not MATLAB execution.

## PHY first stop

The returned common case stops on node 4 PHY sample 2 at 11.500323527005154 s: payload allocation requests 184 bits while native requests 183. Source, physical transmission signature, interval lineage, rounded-nanosecond geometry and BER match. The mismatch is the endpoint supplied to the unchanged truncating allocator:

| Quantity | MATLAB continuous callback | Native integer-nanosecond callback |
|---|---:|---:|
| Physical signal start | 10.465023527005155 | 10.465023527005155 |
| Physical payload start | 11.476863527005154 | 11.476863527005154 |
| Allocator interval end | 11.500323527005154 | 11.500323527000001 |
| Payload duration × rate | 184.00000000000028 | 183.99999995958294 |
| Truncated payload bits | 184 | 183 |

The endpoint differs by 5.153211191100127 ps. No epsilon or relaxed bit-count comparison is justified. The existing `csr.sim.TransportTiming('nanoseconds')` retains raw physical geometry and quantizes receiver callbacks. Its `/1e9` conversion reproduces all 1,542 consumed native PHY sample bit counts when applied to the captured intervals; using multiplication by `1e-9` instead produces 19 mismatches. The companion native audit confirms all 1,960 arrival, 1,658 preamble-end and 1,958 completed end callback targets. Two additional end callbacks are beyond capture. Native GetSeconds and floating division differ by one ULP for two of 10,139 audited tick values; this does not change any captured sample bit count. The existing option is therefore a justified controlled experiment, not a universal claim that its doubles are identical to every native clock conversion.

This first stop is not evidence that one bit explains the autonomous network discrepancy. Node 4 already failed SYNC eligibility (SNR -13.972516094342254 dB versus threshold -10.746479018585131 dB). With the same BER 0.015116561887016548 and uniform 0.45559117029490032, independent inverse-binomial arithmetic gives two errors for both 183 and 184 payload bits.

## Earlier control admission ordering

The same short return also exposes an earlier difference, before the PHY stop. Nodes 3 and 5 successfully decode gateway DISCOVER. Native admits the resulting no-ACK KEY_REQUEST while still in Track, then Track→Search triggers MAC preparation and draws reservation counters 27 and 10 respectively. MATLAB announces neighbor control creation while Track, but its zero-delay NWK pump executes only after PHY has returned to Search. The resulting MAC enqueue sees an already active slot clock and completed holdoff, so it leaves preparation inactive until a later slot.

The source boundary is `csr.nwk.Layer.queueControl` → `wake`, which schedules a separate same-time `pump` callback. Native `CsrNetLayer::SendKeyRequest` directly calls `m_hop->SendKeyRequest`, and HOP directly replaces the prior queued request for that neighbor and enqueues the fresh frame. MATLAB MAC already has the correct immediate preparation on Track→Search if a packet is present. Changing generic MAC enqueue/scheduling would compensate at the wrong layer.

A bounded candidate should submit only the newly created KEY_REQUEST owner synchronously after preserving existing replacement and capacity checks. It must not pump unrelated controls, pending DATA or reliable routing; callback failure and reentrant completion must preserve current ownership rules. Keep the production model unchanged by generating isolated candidate classes and compare timing-only C against timing-plus-KEY_REQUEST candidate D in one owner command. Existing accepted natural A and returned B remain historical evidence, not newly executed cases.

## Reproduction and limits

Run `python autonomous_third/matlab/analyze_clock_boundary.py` for the arithmetic audit. Inputs and hashes are recorded in `clock_arithmetic_summary.json`; all sampled component comparisons are in `clock_arithmetic_all_samples.csv`. The native callback/clock-conversion audit is separate under `autonomous_third/native`.

No full coupled case with quantized callbacks or inline KEY_REQUEST has run in MATLAB yet. Neither targeted result establishes the 15% full-network accounting/latency target.
