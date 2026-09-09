# Tranche 4: accepted portable research scenarios and shared-input validation

Objective: make the accepted PHY/MAC/HOP/NWK stack usable for reproducible
network experiments and start direct MATLAB/ns-3 application comparisons.
The branch is `agent/tranche-4-research-validation`, based on merged PR #3,
`c37a39e2d03d0f675271fb37ac2c4c0bcafd9f4b`. The source main was checked on
2026-09-09 and remains pinned to
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

Code `6fdf238` is accepted for the bounded R2025a portable scope: 333/333 tests,
all 11 new exports and eight T3/nine T2 regressions completed. All 83 MATLAB
source hashes match. Five actual shared comparisons pass application equality;
latency and radio transmission-count differences remain explicit. See
[portable acceptance](tranche-4-portable-acceptance.md). R2026a, 6000 seconds,
seed sweeps and full protocol parity remain separate gates. No MATLAB runtime
was available in the engineering workspace; MATLAB execution was on the owner
machine. The prior 330/331 run remains in the [repair record](tranche-4-r2025a-repair.md).

## Capabilities and architecture

| Component | Responsibility |
| --- | --- |
| `csr.scenario.researchNetwork` | Nine synthetic physical network experiments; seed and duration options; explicit discovery stimuli |
| `csr.scenario.importNs3` | Strict supported subset of canonical `csr-opnet-scenario-v1`; fixed current profile, explicit payload conversion and source/input identity |
| `scenarios/shared/` | Five identical CSV inputs for MATLAB and the frozen ns-3 runner |
| `csr.analysis.researchSummary` | Structural accounting, queue bounds, trace completeness, delivery/goodput and nearest-rank latency percentiles |
| `csr.validation.Artifacts` / `exportResearchCase` | Source/BER/input hashes, complete case inventories, runtime metadata and portable evidence exports |
| `run_tranche4_validation` | Regression, shared and research runs; seed sweeps; explicit long/native gates; unique run directories and failure evidence |
| `scripts/run_tranche4_ns3_reference.py` | Fresh standalone source runner compilation against preserved libraries, execution and provenance |
| `scripts/compare_matlab_ns3.py` | Validate both evidence sets; compare generated/delivered applications and per-flow latency; flag differences without inventing exact timing parity |

Research layouts include two nodes, a four-node line, hidden nodes, six-node
mesh, relay blackout/recovery, a non-transit leaf, separate 500/1000-kbps
extensions and a 6000-second workload. They use OPNET three-path propagation
and Earth line-of-sight closure. Staggered administrative discovery exposes
each node because retained SNMP controls are not forwarded across arbitrary
hops. The recovery fixture applies an explicitly labeled receive blackout;
it does not simulate motion or claim fully autonomous rediscovery.

The shared cases use fixed rate and power, current MAC/application profiles,
production-sized behavioral admission, aligned duty cycling and a deterministic
SYNC threshold. The 15-byte configured-size exclusion maps a 79-byte source
configuration to 71 NWK bytes and 64 application payload bytes. Different
runtime packet IDs are joined within each simulator and compared by application
generation identity. Historical generator/MAC/security tuples are rejected by
this initial bridge, rather than silently treated as current behavior.

## Actual validation

Five ns-3 shared cases completed, each generating and delivering three
applications. The archived evidence contains complete traces, application
diagnostics, commands, source/library hashes, row counts and successful exits.

| Case | Generated / delivered | OTA transmissions | Receiver accepts / drops |
| --- | ---: | ---: | ---: |
| two_node_8 | 3 / 3 | 66 | 66 / 0 |
| two_node_128 | 3 / 3 | 66 | 66 / 0 |
| line_3_8 | 3 / 3 | 123 | 150 / 96 |
| high_rate_500 | 3 / 3 | 120 | 120 / 0 |
| high_rate_1000 | 3 / 3 | 120 | 120 / 0 |

The 0/4000/8000-m line uses actual physical closure and forwarding through
node 2. Its end-to-end link exceeds the Earth horizon. Receiver drops are
observations at all non-self nodes; they do not imply application loss.

Only the frozen standalone runner was freshly compiled. Engine and CSR shared
libraries were preserved; their exact hashes and source-header compatibility
were checked before and after execution. A fresh complete ns-3 build and a
rerun of all 38 workflows are outside this evidence.

The Python suite passes 42 tests covering the runner contract, identity and
byte mappings, late custody recovery, changed delivery outcomes and rejection
of corrupted/incomplete/mismatched artifacts. Python synthetic comparator
fixtures are labeled as tool tests, not MATLAB execution. MISS_HIT checks the
MATLAB source with its MATLAB 2022a syntax profile. The candidate manifest
records the final counts and source hashes.

Independent integration review corrected relative-path inventories, failed
native-execution reporting, and the compact ZIP's MAT-file inventory. MAT
objects remain on the owner machine and are listed separately from bundled
CSV/JSON/log evidence. A clean static review cannot replace the MATLAB run.

## Boundaries and next step

The [acceptance record](tranche-4-portable-acceptance.md) separates the five
matching application comparisons from measured timing and control residuals.
Six research cases drain; the leaf's five policy drops are intentional.
Hidden-node/recovery have terminal control failures, and recovery's aggressive
freshness causes route churn and up to 135.9404 seconds of application delay.
Expand [validation](tranche-4-validation.md) to R2026a, 6000 seconds and seeds
before interpreting these fixtures as broad performance benchmarks.

No existing protocol, PHY/ECC or scheduler implementation was changed in this
tranche. Bounded custody/control queues, retry policies, behavioral security,
historical application-generator differences and RNG differences remain as
documented in Tranche 3. Full native CSR packet transport, full feedback-driven
link adaptation, equivalent OPNET aggregates and large-network certification
remain separate work. Battery, supervisory behavior, BBN routing, GUI,
Simulink and waveform-level work remain excluded.

The next practical tranche is research usability and performance: parameter
sweeps around a chosen work scenario and the highest-impact discrepancies
found by this comparison harness. Tranche 4 is accepted and published for
review with owner authorization. The [publication record](../evidence/tranche-4-publication.json)
preserves the local-to-published commit mapping and identical file trees.
