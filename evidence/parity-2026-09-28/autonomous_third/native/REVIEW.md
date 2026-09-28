# Native review of the node-4 payload-bit divergence

The reported 184-versus-183 difference has a specific arithmetic cause:
**MATLAB closes this receive interval at the continuous physical end, whereas
ns-3 closes it at the integer-nanosecond callback time.** Both implementations
truncate the positive duration-times-rate product. The physical payload
boundary and PHY rate match; the callback endpoint differs by 5.153 ps.

This is a mismatch in time representation at a source-model boundary. It is
not evidence for changing the bit-floor rule, rounding packet lengths, or
relaxing the common-input guard. It is also not established as the first
global behavior difference: this return reports the first failing draw
context, and the per-node draw guard does not prove global callback order.

## Exact arithmetic

The pinned native C++ probe reproduces the captured arithmetic with the
original `CsrRateKeyToBps` and explicit-uniform `SampleSourceBinomial` methods.
It neither runs a network nor consumes a random value.

| Quantity | Native | MATLAB continuous expression |
|---|---:|---:|
| Raw physical start (s) | 10.465023527005155 | Same |
| Raw physical end (s) | 11.500323527005154 | Same |
| Payload start (s) | 11.476863527005154 | Same |
| Interval end used (s) | 11.500323527000001 | 11.500323527005154 |
| Rate (bit/s) | 7843.1372549019607 | Same |
| Payload duration × rate | 183.99999995958294 | 184.00000000000028 |
| Truncated payload bits | 183 | 184 |
| Header duration × rate | 47.999999999994017 | Same |
| Truncated header bits | 47 | 47 |

Native `SendFramesToPeers` retains continuous `signal.startSec` and
`signal.endSec`. `BeginReceiveSignal` separately sets `intervalStartSec` to
`Simulator::Now().GetSeconds()`. `EndReceiveSignal` closes intervals at that
clock value, clamped by the physical end. The PHY then uses the continuous
signal start to calculate header and payload boundaries.

That mixture matters. Quantizing **every physical signal field** makes this
microprobe return 184 again. Quantizing only the callback endpoint while
retaining raw geometry returns the native 183. The complete IEEE binary64
values are in `arithmetic_values.csv`.

## Consequence of this occurrence

With the recorded probability 0.015116561887016548 and uniform
0.45559117029490032, the native explicit-uniform sampler returns **2 payload
errors for both 183 and 184 tested bits**. The shared 47-bit header and its
recorded uniform return 2 header errors. Thus this local arithmetic
counterfactual has 4 total errors in both cases; the protected packet has 232
bits and the configured 10% ECC limit is 23 errors.

More directly, the native first gateway signal at node 4 is already rejected
before payload delivery: its SNR is -13.972516094342254 dB, below the sampled
SYNC threshold -10.746479018585131 dB; the recorded receiver remains Idle and
the prior-stage record marks it rejected/missed by state. This instance does
not establish a delivery difference. The MATLAB replay stopped at the
strict request guard before consuming its payload uniform; the counterfactual
above is an arithmetic calculation, not a completed MATLAB receive result.

## Existing callback-timing experiment

The existing `TransportTiming('nanoseconds')` option has the correct scope for
testing this cause: it retains continuous physical geometry while scheduling
receiver start, preamble-end and end callbacks on nanosecond boundaries.
An independent reconstruction from the native scenario coordinates and
actual transmitted frame identities found:

| Check | Matching / compared |
|---|---:|
| Raw physical start and end reconstruction | 1,960 / 1,960 each |
| Receiver arrival callback nanoseconds | 1,960 / 1,960 |
| Observed preamble-end callback nanoseconds | 1,658 / 1,658 |
| Observed receive-end callback nanoseconds | 1,958 / 1,958 |
| Component-sum plans versus native relative scheduling | 1,960 / 1,960 each endpoint |

Two received signals end after the capture stop and therefore have no
observed receive-end callback. No missing outcome is counted as a match.

The separate MATLAB-side arithmetic audit also reproduces all 1,542 captured
PHY sample bit counts using the existing option's `ns / 1e9` conversion and
raw physical boundaries. That audit holds native traffic and interval
history fixed; it is not a coupled-network execution.

The independent native review reconstructs header and payload counts for
**all 4,070 native intervals**, including intervals whose BER does not consume
a random sample. The original interval seconds and the existing option's
callback-time division produce identical counts for all 4,070 intervals.
These are reconstructed counts; direct sampled-count observations cover
1,542 components. `all_interval_arithmetic.csv` records the distinction.

A C++ check of 10,139 distinct captured clock values confirms that native
`GetSeconds()` uses fixed-point conversion, not ordinary binary64
multiplication. `ns / 1e9` differs by one binary64 ULP at two tick values:
29,068,008,077 ns and 36,994,979,163 ns. Neither changes the captured PHY sample
bit counts in the fixed-history reconstruction. `ns * 1e-9` differs at 3,751
clock values and produces 19 sample-count mismatches in the separate audit.
Consequently, keep the existing division conversion for the bounded
experiment; do not call it a universal bitwise clone of native `GetSeconds`.

The evidence supports one coherent receiver-callback timing experiment,
retaining strict draw-context checks and continuous physical geometry. It
does not justify a production correction yet, nor establish that this
precision effect explains the long-run latency gap. MAC/HOP callbacks,
acquisition/duty timers and global order remain separate boundaries.

## Reproduction

With the already restored pinned native engine:

```sh
python3 autonomous_third/native/run_arithmetic_checks.py
```

The command compiles only the local arithmetic microprobe, runs it, and
reconstructs callback plans from the existing capture. No simulation or
production/fixture edit occurs. `callback_timing_summary.json`,
`callback_plan_comparison.csv`, `clock_values.csv`, and
`arithmetic_values.csv` provide the detailed evidence.
