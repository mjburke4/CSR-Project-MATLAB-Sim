# Tranche 1 validation handoff

The source reference is CSR ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Tranche 1 is a prepared MATLAB
implementation until its new tests and scenarios actually run in MATLAB.
The prior user-reported R2025a result (24/24 Tranche 0 tests) remains valid
for that earlier accepted commit; it does not certify these changes.

## Evidence available now

| Evidence | Execution and result | What it establishes |
| --- | --- | --- |
| Original CSR C++ BER implementation | Compiled unchanged and executed with GCC 13.3; 400 vectors recorded | Standard/DPSK/DQPSK curves, collision table samples, JSR and circular offset boundaries, rate intervals |
| Native ns-3 PHY front-end smoke | Executed, exit 0, one PASS line, zero FAIL lines | Existing source PHY propagation, power, SYNC, acquisition and interference regressions pass |
| Native ns-3 BER/ECC smoke | Executed, exit 0, one PASS line, zero FAIL lines | Existing source table, interval allocation, ECC/closure and selected-collision regressions pass |
| Native ns-3 live high-rate smoke | Executed, exit 0, one PASS line, zero FAIL lines | Existing source 500 kbps DPSK / 1 Mbps DQPSK integration regressions pass |
| MATLAB R2025a Tranche 1 | Not executed here | User runtime gate required |
| MATLAB R2026a Tranche 1 | Not executed here | Separate runtime gate required |
| Native MATLAB wireless integration | Not executed here | Separate optional adapter gate required |
| OPNET runtime or packet differential | Not executed; event exports unavailable | Source/aggregate evidence boundary remains unchanged |

The native ns-3 tests used the release-pinned engine
`6b5cd24ea80713ce16d88575869aedd6f432bdae`, a Debug build, runtime assertions
and logging enabled, and warnings-as-errors disabled. All three original
programs ran in separate fresh working directories. This is focused source
verification, not a fresh 38-workflow release certification or a 6,000-second
OPNET comparison. See `evidence/tranche-1-ns3-workflows.json` and its run logs.

`evidence/tranche-1-ns3-reference.json` records the 400 golden values and the
source/compiler/probe hashes. `tests/TestCppBerReference.m` compares MATLAB
outputs against those independently executed C++ answers. It does not
reimplement a C++ result in Python and call that an ns-3 execution.

## Run on either MATLAB machine

Open the repository root as MATLAB's current folder and run:

```matlab
run_tranche1_validation
```

This invokes `run_validation` for the original and new portable tests, then
runs and exports all nine PHY fixtures. Return the generated
`results/tranche1_validation/` directory, or the complete console output
plus `scenario_summary.csv` and `tests/` evidence. Record the actual MATLAB
release and version; a failure on one machine must not be relabeled a pass
because another release succeeds.

| Fixture | Intended application result | Additional acceptance check |
| --- | --- | --- |
| clean | 6 received, 0 dropped/pending, 384 bytes | 12 physical receives, 6 overheard; source wire timing |
| overhearing | 6 received, 0 dropped/pending, 384 bytes | Decoding at another peer does not duplicate application delivery |
| high_rate_500 | 6 received, 0 dropped/pending, 384 bytes | 500 kbps DPSK payload, S0 preamble/header timing |
| high_rate_1000 | 6 received, 0 dropped/pending, 384 bytes | 1 Mbps DQPSK payload, S0 preamble/header timing |
| weak | 0 received, 1 dropped | Signal below SYNC admission; no application bytes |
| band_mismatch | 0 received, 1 dropped | Nonoverlapping radio bands cannot deliver |
| closure | 0 received, 1 dropped | Spherical-Earth visibility gate prevents delivery |
| collision | 2 generated; received + dropped = 2 | Collision observations exist; BER/ECC owns selected-packet disposition |
| mixed_rate | 2 generated; received + dropped = 2 | Different-rate overlap reaches interference path; no lost packet custody |

These are acceptance expectations, not measured MATLAB results. Collision
alone is not synonymous with a forced drop. `Collisions` counts completed
receiver/signal observations with overlap, rather than unique collision
pairs. `PhysicalAttempts` counts one transmitted packet at each non-self
receiver; `Overheard` counts successful physical reception away from the
application destination. Finite-horizon pending work is neither delivery
nor loss. `GoodputBitsPerSecond` uses delivered application bytes divided
by the entire configured simulation duration.

The suite checks clean links, gating failures, high rates, same/different-rate
overlap, repeatability, trace bounds, and unfinished packets. PHY unit tests
add source-literal propagation, effective SNR, inverse-binomial allocation,
ECC boundary/ordering and receive-state fixtures. A seeded replay checks
reproducibility within MATLAB; numeric seed equality does not synchronize
MATLAB and ns-3 random-number streams.

## Optional native MATLAB gate

Run `validate_native` only on an installation with the advertised required
wireless symbols. The R2026a packet/clock probe and wireless-clock scenario
must be reported separately from the portable results. Missing native
capability does not prevent the R2025a portable gate from running.

The native packet transport probe does not certify integrated CSR packet
transport through `wnet.Node`. Current integrated PHY owns its propagation
and receive pipeline; the optional wireless-clock backend supplies its clock.
See `docs/native-adapter.md` for precise status and limitations.

## Reproduce the original C++ reference

With GCC and Python available, and a clean ns-3 CSR module checkout pinned to
the source commit above:

```bash
python3 scripts/source_reference_vectors.py /absolute/path/to/CSR-Project-NS3-part2
```

The command compiles `model/csr-opnet-ber-tables.cc` unchanged, runs a small
query-only harness, and rewrites the JSON golden values/provenance. No full
ns-3 engine is needed for this table-only reference. Reproduction changes
timestamps and compiler/binary hashes but should preserve the values. The
separate native workflow execution is recorded in its own manifest, because
table-only execution must not imply that a network simulator ran.

## Decision rules and remaining scope

Structural failures block Tranche 1 acceptance: missing/duplicated packet
accounting, incorrect radio gates, broken source vectors, nonreproducible
seeded runs, unbounded logs, or failure to execute the portable scenarios.
Small numerical differences need diagnosis and a recorded explanation.
Stochastic differences require enough independent seeds and confidence
intervals before asserting performance parity; a single favorable seed is
not a statistical comparison.

No complete MATLAB/ns-3 network metric comparison has run yet. The source
reference vectors and native regressions establish a useful baseline for
that comparison without claiming it is already complete. Known ns-3/OPNET
PHY/ECC interval uncertainty stays documented; this tranche retains current
ns-3 semantics rather than silently adopting the excluded experiment.

Receivers are initially awake; per-node transmission serialization is not
the CSR MAC/HOP stack. Queue ownership, access contention, ACK/DACK, retries,
and preamble policy remain Tranche 2. Autonomous routing remains Tranche 3.
