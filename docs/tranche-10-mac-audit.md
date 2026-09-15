# Tranche 10 MAC timing source audit

The audit identifies two bounded MATLAB timing defects against the clean
authoritative ns-3 source at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
Both corrections are implemented in `csr10/+csr/+mac/Layer.m`. Their effect on
the accepted Tranche 9 contention outcomes remains unmeasured until the owner
runs MATLAB. The receiver, PHY/ECC, radio policy and random streams are unchanged.

The original source path had expired. Initial reads used the retained passive
observer overlay. The receiver specialist reconstructed and hash-verified all
24 source/runner files, and the primary agent then restored the full clean Git
checkout at `t10/ns`. Final conclusions below use that clean checkout. The JSON
companion binds the exact source and accepted trace hashes.

## Confirmed strict-future RTS defect

`CsrMacCore::ScheduleIdleRts` in `model/csr-net-device.h` computes the next
global TSLOT with integer native clock steps. The result is always strictly
after the current instant. MATLAB previously used
`(floor(now / period) + 1) * period` without checking the result.

For `now = 15 * .013`, binary double arithmetic produces
`0.19499999999999998`; division by `.013` gives `14.999999999999998`.
The old expression schedules the RTS at the current instant, instead of
0.208 seconds. A prescribed free slot of 1 then shifts the first DATA
transmission by 13 ms: 0.520 rather than 0.533 seconds.

| Arrival expression | Old RTS (s) | Native/corrected RTS (s) |
| --- | ---: | ---: |
| `15 * .013` | 0.195 | 0.208 |
| `.195` | 0.208 | 0.208 |
| `30 * .013` | 0.390 | 0.403 |
| `51 * .013` | 0.663 | 0.676 |
| `60 * .013` | 0.780 | 0.793 |
| `.195 - 1e-9` | 0.195 | 0.195 |
| `.195 + 1e-9` | 0.208 | 0.208 |

The correction advances one additional grid index only if the calculated
boundary is less than or equal to `Now`. It adds no numerical tolerance and
preserves arrivals one nanosecond before or after the boundary.

The guarded RTS still uses a double grid product: for example, its nominal
`.403` may be represented as `.40299999999999997`. This correction addresses
strict-future scheduling, not every RTS/other-timer tie. Periodic-wake,
holdoff and global clock representation remain separate from the recurring
slot epoch correction below.

## Confirmed recurring-clock/FIFO defect

The portable event scheduler itself orders exactly equal timestamps by event
insertion ID, as intended. The problem occurs before insertion: MAC previously
rearmed each TSLOT with `Now + .013`. Twenty-four repeated additions reach
`0.31200000000000017`, while a prescribed Track transition at literal `.312`
is earlier. Native integer nanosecond time places both at exactly .312.

The order matters when a reservation counter is 1 and holdoff has expired:

| Prescribed Track event at .312 | Native order | Counter while Track | First TX after Search resumes at .400 |
| --- | --- | ---: | ---: |
| Inserted at setup | Track, then TSLOT | 1 | .416 |
| Inserted from a .311 callback | Existing TSLOT, then Track | 0 | .403 |

The old MATLAB recurring clock runs Track first in both cases. The new clock
stores a MAC-local integer nanosecond epoch and tick index, so the default
13-ms timer uses `(epoch_ns + index * period_ns) / 1e9`. Rearming still occurs
before per-state work. Track/Search/Tx retain the epoch; entering Idle cancels
the old timer, and the next Search entry establishes one new epoch.

Only the MAC slot epoch is rounded to nanosecond resolution, with a nominal
maximum shift of 0.5 ns. The global scheduler and all PHY observation/event
times retain their existing representation. Custom periods that are not
exact integer nanoseconds, or times outside the exact integer horizon, retain
the prior continuous `Now + period` path. Dedicated MATLAB tests cover both
fallbacks and confirm that scheduling does not change `scheduler.Now`.

## Matched contract scope

New public entry point:
`csr.validation.contentionContract(outputDirectory)`.

The fresh native reference passes **279/279 checkpoints across 15 fixtures**.
Nineteen prepared MATLAB tests exercise the contract cases and clock fallback
behavior; actual MATLAB execution remains pending.

- Seven literal/computed/before/after RTS boundary arrivals.
- Initial Search, an existing SYNC, and an initial Track receiver.
- Separate SYNC and Track busy episodes with a stable relative slot phase.
- Both insertion orders at the same .312-second Track/TSLOT boundary.
- Idle cancellation and Search restart, verifying the old .026 timer cannot
  survive and the first new relative tick occurs at .038.

Each fixture uses the real public MAC API, the historical modulo slot profile,
local population three and a fixed range reduction of 29. With range 2,
neighbor counters occupy slots 0 and 2 at selection, so every legal random
draw resolves to slot 1. These are prescribed neighbor/receiver inputs, with
no RF channel or matching-random-stream claim. Neither simulator's existing
forced-reservation option is used. The native option also rephases a timer to
a future 0.1-second epoch, so those two existing controls remain unsuitable
for a matched comparison.

The native fixture source is `scripts/ns3/tranche10_contention_contract.cc`;
the MATLAB implementation is `+csr/+validation/contentionContract.m`.
CSV row identities and values are checked against
`evidence/tranche-10-contract-reference/checkpoints.csv`, with 1-ns tolerance
for numerical values. Discrete state/count differences remain a full unit
and cannot be hidden by that time tolerance. No old Tranche 9 contract was
changed.

## Accepted seed-129 history and limits

The accepted Tranche 9 traces show matching initial wake and holdoff epochs,
but different initial reservation draws:

| Observation | MATLAB | ns-3 |
| --- | --- | --- |
| Sources 2/3 enter Search | 300.001 s | 300.001 s |
| Sources 2/3 finish holdoff | 300.301 s | 300.301 s |
| Source 2 first selected slot | 9 | 3 |
| Source 3 first selected slot | 1 | 7 |
| First DATA transmitter | Node 3 at 300.326 s | Node 2 at 300.352 s |

This divergence precedes the first DATA reception, cumulative ACK scheduling
and admission-capacity release. The historical slot ranges, endpoint support,
collision probing and Search/Track/SYNC gates match in the audited source.
The two simulators deliberately use independent random streams, so matching
seed labels do not prescribe the same initial draws. The receiver specialist
also found that the observed first acquisition timing follows the same 6.63-ms
rule applied to those different arrival histories.

These observations do not prove that all remaining differences are random.
They do show why neither new timing correction can be presented as an already
proven cure for source 2's 510-versus-353 delivery residual. Replaying all six
accepted diagnostic cases and the planned 6,000-second campus benchmark must
measure the real effect and regression risk.

## Deferred wake lookup distinction

`Layer.m` also computes a future periodic wake with floating division at
startup and in the Idle RTS deferral comparison. The native unconditional
periodic-wake setup uses integer steps, but its separate
`GetNextPeriodicWake` returns the current time while inside an awake window.
Those are different semantics. No shared helper or blanket wake-cycle fix is
introduced here; a separate public-input fixture is needed before proposing
that additional behavior change.

Native Tranche 10 execution passes all 279 checkpoints. The reference CSV
SHA256 is `2f27b671229782b5fe64f3bb5c8730a10a3be648ef4345e28bd8a1cbb2ff088a`;
the manifest SHA256 is
`fc69ae2ed1399c0bb2bb8f0af774fd6dd9c3d83cb70faba0d7686d7ef5ed02c1`.
MISS_HIT 0.9.44 with the MATLAB 2022a parser passes all three owned MATLAB
files. The whitespace check also passes.

The standalone `mac-counterfactual.py` records four old-arithmetic RTS
failures and both early/late FIFO cases. Its small Python event heap confirms
that the old recurring double clock loses the late-insertion distinction,
while the integer grid preserves native .403/.416-second outcomes. This is
an arithmetic/FIFO sensitivity check, not another simulator execution or a
claim that old MATLAB was rerun. The JSON companion binds that script and
its output. MATLAB/Octave remain unavailable here.
