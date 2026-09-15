# Tranche 7 handoff and returned benchmark status

The owner run at `28ed878` is now accepted for the bounded portable R2025a
benchmark milestone: 467/467 tests, 18 sweeps, 28 retained scenarios and three
benchmarks completed. All 103 MATLAB files match. Campus delivered 11,727
applications versus 11,769 in ns-3; individual flows, latency buckets and
finite-stop backlog remain distinct. The full run took 88 minutes. See the
[acceptance record](tranche-7-portable-acceptance.md) for measured results
and qualifications. The implementation and preparation details below retain
their original candidate scope.

The objective is a repeatable MATLAB campus benchmark with comparable ns-3
and archived OPNET measurements. This candidate starts from local T6
acceptance commit `b53653ed822d85db2fd4d351fb4a49bb1dd739ec`, whose executed
MATLAB baseline is `21c0a3f024c9efffdbd11c8059f1540a67c19b1a`. T6 acceptance
and its recovery limitations remain historical evidence. The working branch
is `agent/tranche-7-campus-benchmarks`; remote publication is pending.

| Default case | Simulated duration | Purpose | Comparisons |
| --- | ---: | --- | --- |
| `campus_multihop_6000` | 6,000 s | Original seven-node, six-flow campus workload | MATLAB / fresh ns-3 / archived OPNET |
| `two_node_admission_1200` | 1,200 s | Isolate offered attempts, the NSDP admission cap and finite-stop backlog | MATLAB / fresh ns-3 |
| `three_node_contention_360` | 360 s | Two concurrent sources, contention and admission pressure | MATLAB / fresh ns-3 |

The two smaller fixtures are explicitly synthetic experiments derived from
the audited campus tuple. The exact earlier latency/visible-node OPNET
experiments remain deferred until their executable/envelope bindings are
audited. The recovered 60,000-second hidden-node input is retained but not
runnable: it needs different per-node antenna heights and approximately
149.25 million application attempts. The prior synthetic 6,000-second line
test is a separate experiment and is not renamed as campus.

## Implementation

- `csr.sim.ApplicationGenerator` separates scheduled attempts from admitted
  packets, implements source-ordered discovery/topology/destination/NSDP
  gates, caches gateway selection per flow, and supports an admitted cap.
- `csr.mac.SlotSelection` implements named historical selection rules;
  `Mac.SlotProfile` leaves the current selector as the default.
- Historical import is explicit and verifies the application/MAC/HOP tuple
  and executable hash. It preserves the canonical CSV, original radio
  ranges, geometry, seed, offered traffic and node application metadata.
- Bare DATA and ACK size profiles coexist with the production profile.
  Read-only NWK observations expose admission state and qualified neighbor
  population without changing freshness, routes or retry ownership.
- `csr.scenario.benchmarkSuite` reads the hash-bound catalog.
  `run_tranche7_validation` executes regressions and benchmarks, enforces
  structural accounting, and packages source/reference hashes and traces.
- `csr.analysis.benchmarkAggregates` exports the eight common application
  series on the original bucket grid. Python tools validate returned
  evidence and produce descriptive comparisons.

## Execution evidence and acceptance

The actual fresh ns-3 runs admitted/delivered **12,417/11,769** for campus,
**11,380/11,364** for two nodes, and **946/914** for contention. Every observed
delivery matches an admitted source application and its size. Differences
between admitted and delivered counts are not automatically classified as
drops: the reference does not certify all terminal custody ownership.

The campus trace and aggregate SHA-256 values exactly reproduce the earlier
source publication. OPNET comparison aligns 800 common points; 780 are
numeric, 641 differ, and 20 retain authoritative missing values. OPNET was
not rerun; its original binary vector output was extracted again. The ns-3
runner was freshly compiled against verified preserved engine libraries,
not a newly rebuilt entire engine. Build-path and artifact packaging repairs
are recorded with hashes in the reference evidence.

Candidate-time Python execution and MATLAB static checks are recorded in
`evidence/tranche-7-local-checks.json`. The later owner R2025a evidence and
review are recorded in `evidence/tranche-7-portable-acceptance.json`.
This review workspace has no MATLAB/Octave runtime. R2026a and native
execution remain unvalidated. The owner command and evidence return
instructions are in [validation](tranche-7-validation.md).

## Remaining boundaries and next decision

This milestone measures model differences rather than asserting numerical
equivalence. Reverse ACK rate/power control and HOP peer-S0/failure feedback
remain partial in MATLAB; RNGs, custody/queue policies and finite-stop
effects also differ. See [the source audit](tranche-7-source-audit.md) and
`parity-ledger.csv`. No PHY/ECC repair, retry-policy redesign, cryptographic
implementation, battery, supervisory layer or BBN routing is included.

The returned archive passed structural and provenance review. Next, repeat
the smaller diagnostics across multiple seeds and trace reverse-link ACK
rate/power decisions before choosing a protocol correction. Campus flow
residuals reach 17.10% and contention bucket-delay means differ by 9.79%;
the close aggregate campus totals alone do not attribute a cause. Do not
tune PHY parameters merely to fit aggregate OPNET numbers.
