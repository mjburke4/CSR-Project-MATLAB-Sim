# CSR MATLAB Network Simulator

Behavioral port of `mjburke4/CSR-Project-NS3-part2`, currently pinned to main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (2026-09-07, PR #50).

## Tranche 10 candidate: MAC timing and campus6000

**2026-09-14 retry repair:** the owner run passed all 534 contract checkpoints
and 26 retained cases, then exhausted the event limit in the six-node mesh.
`csr10r.zip` repairs a demonstrated floating-point loop in neighbor admission
retries. Extract into `C:\csr10r`, start a fresh MATLAB session, and run
`report = run_tranche10_mesh;` from that folder first. Upload the printed
`mesh.zip` for review. See [repair notes](docs/tranche-10r-repair.md).
MATLAB execution of the repair and full Tranche 10 acceptance remain pending.

The original Tranche 10 candidate and full-gate instructions follow.

Two source-confirmed MAC timer corrections are prepared: idle RTS now uses a
strictly future slot boundary, and recurring slot ticks use a bounded integer
nanosecond epoch to preserve event order. PHY/ECC, ACK radio policy and RNG
selection are unchanged. Native checks pass **279 MAC**, **154 receiver** and
the retained **101 ACK** checkpoints. MATLAB acceptance and any improvement
in delivery remain pending.

Extract `csr10.zip` into a short folder such as `C:\csr10`, then run:

```matlab
report = run_tranche10_validation;
```

The default gate runs all portable tests once, 29 retained cases, 18 sweeps,
the six Tranche 9 diagnostics, two tracing controls and the original
6,000-second campus benchmark. Allow roughly 1.5–2 hours based on the prior
laptop runs. Results use `results\t10` with compact subfolders. Upload the
printed `tranche10_evidence.zip` path for acceptance and comparison.

See the [handoff](docs/tranche-10-handoff.md),
[run instructions](docs/tranche-10-validation.md),
[MAC audit](docs/tranche-10-mac-audit.md) and
[receiver audit](docs/tranche-10-receiver-audit.md). Keep accepted older
packages for exact historical reproduction; their runner commands in this
candidate execute the corrected MAC.

## Tranche 9 accepted: prepared reservations and early ACK service

The owner R2025a run at **`99fff038` passed 514/514 portable tests**, all
**101 matched MAC/HOP checkpoints**, six small diagnostics and both tracing
controls. All 206 source hashes, including 115 MATLAB files, match the executed
candidate. The run took **23 minutes 41 seconds**.

Removing queued DATA/control frames now preserves the prepared reservation,
matching ns-3. Seed 131 demonstrates a DATA transmission 78 ms earlier, with a
small net latency increase across eight affected deliveries. All six delivery
totals are unchanged from Tranche 8. The seed-129 source-2 gap remains **510
versus 353 deliveries (+44.48%)**; numerical parity and improved performance
remain unestablished.

Extract `csr9.zip` into a short folder such as `C:\csr9` and run:

```matlab
report = run_tranche9_validation;
```

Use the frozen `99fff038` package for exact reproduction. Results use
`results\t9` and short case folders such as `b\c129`. The returned archive,
independent review and Python-only reporting repair are preserved in the
[portable acceptance](docs/tranche-9-portable-acceptance.md). No MATLAB rerun
is needed for that repair. The single 6,000-second campus rerun remains the
next milestone; initial contention and receiver-busy timing remain open.
See the [original handoff](docs/tranche-9-handoff.md),
[run instructions](docs/tranche-9-validation.md), and
[source audit](docs/tranche-9-source-audit.md). Keep the accepted `89b62e7`
package when exact Tranche 8 reproduction is needed. PHY/ECC and ACK radio
selection are unchanged.

## Tranche 8 accepted: five-seed diagnostics and passive ACK observations

The owner R2025a run at **`89b62e7` passed 485/485 portable tests**, all ten
small diagnostics and both tracing controls. The two seed-128 cases reproduce
accepted T7 statistics and all 22 unchanged CSV observations byte for byte.
All 189 source/input hashes, including 108 MATLAB files, match the candidate.
The complete run took **32 minutes 19 seconds**.

Across five seeds, mean delivered counts differ from ns-3 by **−0.053%** for
two-node admission and **+2.851%** for three-node contention. One contention
flow at seed 129 differs by **+44.48%** (510 versus 353 deliveries), largely
accumulating during the first 20 traffic seconds. These are measured limits;
numerical and statistical equivalence remain unestablished.

Ordinary DATA ACKs select and transmit at the same 128-kbps profile and
+33 dBm in both models. Startup control ACK choices differ, and no radio-policy
correction is justified by these observations alone. The next target is early
contention, ACK scheduling and admission-capacity release at seed 129.
PHY/ECC and simulator behavior remain unchanged by this acceptance.

See the [portable acceptance](docs/tranche-8-portable-acceptance.md) for
per-seed counts, packet-weighted and bucket-weighted delay, the timing
observations, independent checks and retained evidence. The original CSV
startup defect is resolved in the accepted [input repair](docs/tranche-8-input-repair.md).

To reproduce this exact source snapshot, keep the frozen `89b62e7` package
and run in portable MATLAB R2025a:

```matlab
report = run_tranche8_validation;
```

The prefix-free `csr8.zip` uses `results\t8`, compact run IDs, and case folders
such as `b\a128` and `b\c128`; full names remain in metadata. See the
[run instructions](docs/tranche-8-validation.md). The accepted T7 campus
checkout below remains the reference for its longer benchmark.

## Tranche 7 accepted: portable campus benchmark and focused ns-3 diagnostics

Tranche 7 executes the original **6,000-second, seven-node campus benchmark**,
with archived OPNET aggregates and fresh pinned ns-3 references. Two focused
diagnostics exercise admission saturation (two nodes, 1,200 seconds) and
contention (three nodes, 360 seconds). They use the audited campus profiles;
they are new synthetic fixtures and have no claimed OPNET counterparts.

```matlab
report = run_tranche7_validation;
```

The owner run at `28ed878` passed **467/467 tests**, all **18 sweeps**, the
retained **28 scenarios**, and all **three benchmarks** on R2025a. All 103
MATLAB source files match the returned evidence. The full run took 88 minutes.
Campus delivered **11,727 packets versus 11,769 in ns-3 (−0.357%)**; its mean
of populated delay bucket means differs by −0.232%. Individual campus flows
differ by up to 17.10%, and 401 applications exhausted retries while 254
remain pending at the stop time. The milestone is accepted with these
measured limits; full numerical/protocol parity remains unestablished.

Use the frozen `28ed878` checkout to reproduce the accepted source snapshot.
The command runs regression first, then the benchmarks, and prints the
returned archive path. See the [portable acceptance](docs/tranche-7-portable-acceptance.md)
for all three comparisons, archived OPNET results, runtime and provenance.

Historical generation, MAC slot selection and bare DATA/ACK size profiles are
explicit opt-ins. The PHY/ECC files and T6 freshness/retry policy are retained.
See the [handoff](docs/tranche-7-handoff.md),
[validation instructions](docs/tranche-7-validation.md),
[source audit and boundaries](docs/tranche-7-source-audit.md), and
[benchmark catalog](scenarios/benchmarks/README.md).

## Historical Tranche 6: portable freshness correction accepted with recovery limits

Tranche 6 starts from merged [PR #5](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/pull/5)
at `243ed861`. It corrects two source-confirmed freshness discrepancies:
passive DATA/ACK hearing no longer renews the NWK liveness timer, and quiet-peer
expiry preserves key/retry ownership without adding a link-failure penalty.
DATA retry exhaustion, custody/drop policy, MAC and PHY/ECC remain unchanged.

**R2025a passed 380/380 tests, all 18 sweeps and the retained 28 scenarios at
`21c0a3f`.** All 127 source hashes, including 90 MATLAB files, match that
candidate; five shared application comparisons pass. Acceptance covers the
bounded freshness correction. **60-second outage delivery regressed from
15/15 to 13/15; 180/300-second delivery remains 6/15 each.** Across all sweeps,
334/357 applications delivered, 23 exhausted retries and none remain pending.
Three cases retain control work created at the stop time. Improved outage
resilience remains unestablished. See the
[qualified portable acceptance](docs/tranche-6-portable-acceptance.md).

To reproduce the validated run, extract the frozen `21c0a3f` candidate into
a fresh folder and run in portable MATLAB R2025a:

```matlab
report = run_tranche6_validation;
```

The command executes all portable tests and the unchanged 18 load/recovery
sweeps, including the retained 28 scenario regressions. Return the printed
`tranche6_evidence.zip`. The nested T5-format runner metadata describes the
retained harness executing **Tranche 6 source**; the outer metadata and source
hashes identify the executing source. The original returned evidence and
review reports are preserved; this acceptance record changes no MATLAB code.
See the [handoff](docs/tranche-6-handoff.md),
[validation instructions](docs/tranche-6-validation.md),
[source audit](docs/tranche-6-source-audit.md), and
[independent review](docs/tranche-6-review.md).

## Historical accepted Tranche 5: research sweeps and performance diagnostics

Tranche 5 starts from merged [PR #4](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/pull/4)
at `7edaab5`. It adds controlled offered-load and recovery-freshness sweeps,
per-application outcome/latency diagnostics, and an evidence-checked Python
report with descriptive summaries across seeds. The default plan contains
18 experiments: three parameter values in each of two families, each run
with seeds 128, 129 and 130. A 6000-second synthetic line remains an explicit
option. The protocol implementation and PHY/ECC remain the accepted baseline.

**R2025a passed 367/367 tests, all 18 sweeps and the retained 28 scenarios.**
All 88 MATLAB source hashes match validated code `536b288`, and all five
shared application comparisons pass. The sweeps delivered 336/357 applications;
21 retry-exhausted drops and stop-boundary control work are measured limits.
See [portable acceptance](docs/tranche-5-portable-acceptance.md).

To reproduce the accepted Tranche 5 run, extract its frozen `536b288` package
(or check out published `db2bd08`) in MATLAB R2025a:

```matlab
report = run_tranche5_validation;
```

The command first reruns the portable regression/shared/research validation,
then the new sweep. The accepted run took 19 minutes 56 seconds. Return the
printed `tranche5_evidence.zip` for any subsequent validation.
The Python-only review repair at `7109ae0` requires no MATLAB rerun.
See [validation options](docs/tranche-5-validation.md),
[controlled sweeps](docs/tranche-5-research-sweeps.md), and the
[handoff](docs/tranche-5-handoff.md). Existing acceptance below applies to
the explicitly recorded earlier code versions.

## Accepted portable Tranche 4 research scenarios and shared-input comparisons

Tranche 4 builds on merged Tranche 3 at `c37a39e`. The corrected code at
`6fdf238` passed **333/333 tests on R2025a**, all 11 new scenario exports and
all eight T3/nine T2 regressions. All 83 MATLAB source hashes match the package.
See [portable acceptance](docs/tranche-4-portable-acceptance.md) and the
[historical repair record](docs/tranche-4-r2025a-repair.md).
The [publication record](evidence/tranche-4-publication.json) maps local and
published commit identities with identical source/evidence file trees.
It adds nine synthetic network experiments, five shared canonical ns-3 inputs,
a fail-closed application comparator and a validation runner with source/data
hashes, complete trace inventories and a compact evidence ZIP.

**All five actual shared MATLAB/ns-3 comparisons pass application equality.**
Generation, payload, DSCP and delivery outcomes match for 15 applications;
latency and OTA transmission counts differ. Full protocol parity is unproven.
R2026a, native tests, 6000 seconds and seed sweeps remain separate gates.
To reproduce the portable validation, select the repository root in MATLAB:

```matlab
report = run_tranche4_validation;
```

Upload the `tranche4_evidence.zip` printed by the runner. The default run includes
the portable regression suite, five shared inputs and six research layouts.
See [Tranche 4 validation](docs/tranche-4-validation.md) for seed sweeps and the
explicit 6000-second/native options, and the [handoff](docs/tranche-4-handoff.md)
for actual checks, scope and remaining work.

## Accepted portable Tranche 3 autonomous routing

Tranche 3 connects per-node ARL discovery, admission, routing and control
serialization to the existing HOP/MAC/PHY stack. It adds grouped reliable
controls, dynamic multi-hop custody, gateway selection, route loss/recovery,
link-cost driven radio settings and route/neighbor exports. Eight reusable
network scenarios require no configured paths.

**R2025a portable acceptance passed: 289/289 tests, all eight Tranche 3 scenarios
and all nine retained Tranche 2 scenarios.** No test failed or remained incomplete.
All 74 MATLAB source hashes and the test CSV hash match the validated package
at `ff7859a`. Every T3 queue drained with zero control/backlog rejection; the
disabled-transit fixture accounts for three intentional application drops.
See [Tranche 3 acceptance](docs/tranche-3-portable-acceptance.md) and the
[historical repairs](docs/tranche-3-r2025a-repair.md).
Twelve unchanged native ns-3 reference workflows passed separately; R2026a
and full protocol comparison remain pending; T4 adds the first five bounded
application comparisons. See the
[Tranche 3 handoff](docs/tranche-3-handoff.md) for capabilities, validation and
known differences. No R2026a-only API was added to the portable core.

Tranche 3 merged through [PR #3](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/pull/3)
at `c37a39e` on 2026-09-09. Its published code commit `3e9b4a9` has the same
file tree as owner-validated local commit `ff7859a`. The
[publication record](evidence/tranche-3-publication.json) preserves the mapping.

## Accepted portable Tranche 2 MAC/HOP

The integrated implementation connects application traffic and explicit relay paths
to HOP reliability, MAC access and the existing CSR signal engine. It adds
bounded priority queues, slots and reservations, wake/sleep behavior, ACK
repetition, concatenation, HOP retransmission, cumulative ACK/DACK windows,
flow capacity and deferred custody release. Per-node MAC/HOP counters and
protocol traces accompany the application and PHY statistics.

**The corrected owner run passed 145/145 tests and all nine MAC/HOP scenarios.**
No test failed or remained incomplete. Application pending, HOP pending,
resend queues and DACK holds are zero in every scenario summary. The queue
pressure fixture deliberately drops 18 of 20 packets; all other fixtures
delivered every generated application packet. Summed test duration is 23.9557 s.
The inspected CSVs establish portable acceptance. R2025a 25.1.0.2943329 is
associated from the preceding console; release and source hashes are not
embedded in the new CSVs. See [acceptance evidence](docs/tranche-2-portable-acceptance.md).
The initial fixture failure remains recorded in the
[result and repair history](docs/tranche-2-r2025a-fixture-repair.md).
Original ns-3 reference workflows passed 17/17. Fixed paths
support multi-hop forwarding; autonomous routing belongs to Tranche 3.
Adaptive HOP rate/power selection is deferred; configured radio settings apply.
See the [Tranche 2 handoff](docs/tranche-2-handoff.md),
[independent review](docs/tranche-2-review.md), and
[source execution evidence](evidence/tranche-2-ns3-workflows.json).

## Accepted Tranche 0 and 1 evidence

The integrated implementation adds CSR path loss, closure and passband matching,
receive power/noise, all-peer signal delivery, Search/Track acquisition,
half-duplex reception, capture/interference, complete BER tables, interval error
allocation and inclusive ECC. It retains the controlled foundation fixture,
scenario configuration, deterministic event/RNG ownership, bounded traces,
statistics and MAT/CSV/JSON exports. The owner ran this T1 implementation on
MATLAB R2025a: **72/72 tests passed and all nine PHY scenarios completed**.
Test-suite time was 4.6861 seconds. The portable Tranche 1 gate is accepted
on owner-pasted console evidence; exported files and runtime source hashes
have not been independently inspected. See
[Tranche 1 acceptance](docs/tranche-1-r2025a-acceptance.md) and its structured
[evidence](evidence/tranche-1-r2025a-acceptance.json). R2026a and native
integration remain unvalidated.

**The owner's corrected R2025a run passed 24/24 tests and completed the
acceptance scenario.** MATLAB 25.1.0.2943329 reported six packets delivered,
384 application bytes received, no drops or pending packets, and 307.2 bit/s
goodput. Test-suite time was 1.3764 seconds; this is not simulation runtime.
This accepts Tranche 0's portable foundation. R2026a and native wireless
integration remain untested. Evidence is the owner's console output, recorded
in `evidence/matlab-r2025a-acceptance.json`; runtime source hashes and exported
files have not been independently inspected. The prior count-type failure
remains documented in `evidence/matlab-r2025a-user-validation.json`.

Those earlier totals apply to their recorded revisions. The accepted Tranche 3
suite reruns all portable regressions. Choose `csr.scenario.phyNetwork(...)` for PHY-only runs or
`csr.scenario.smallNetwork()` for the controlled T0 regression. T1 receivers
remain awake; transmissions still serialize FIFO at each source. Slot access,
reservations, ACK/DACK and retries are supplied by the new
`csr.scenario.macHopNetwork(...)` path. Autonomous routing and behavioral admission are supplied by
`csr.scenario.routedNetwork(...)`; cryptographic protection remains deferred. A collision observation does not automatically mean packet loss:
the source acquisition/error/ECC pipeline decides the result. A decoded
non-destination packet increments overhearing, never application delivery.

An optional R2026a `wireless-clock` backend uses an actual framework node to
drive the CSR event heap. CSR remains the sole RF transport. A separate native
packet/channel probe exists; full native CSR packet transport is deferred.
Both native paths require their own MATLAB execution gate.

## Run in MATLAB R2025a or R2026a

From the repository root in MATLAB:

```matlab
run_tranche3_validation
```

Or from PowerShell with MATLAB on PATH, after changing to the repository:

```powershell
matlab -batch "run_tranche3_validation"
```

This runs all portable tests, the controlled T0 regression, all nine Tranche 2
scenarios and eight autonomous network scenarios. Results go to `results/tranche3_validation/`, including
scenario summaries, routes, neighbors, per-layer counters, traces and runtime
provenance. The default backend needs no wireless toolbox. The validation runner
requires the normal MATLAB JVM; do not use `-nojvm`. Previous tranche runners
remain available and discover the expanded regression suite.

Routed scenarios use the explicit production-behavioral Pairwise16 size profile;
cryptography is not implemented. Named legacy application profiles enforce zero
DSCP but do not yet reproduce historical application generators or MAC/security
profile tuples. The `gateway` fixture covers route-based gateway selection only.
See [profile boundaries](docs/tranche-3-profiles.md) before comparing historical scenarios.

Ordinary MAC/HOP fixtures retain source duty-cycle and access/retry defaults.
Loss fixtures deliberately erase selected successful receptions; the DACK
fixture lowers the NSDP threshold to exercise custody with a small traffic load.
These are diagnostic settings, not source scenario parity.

`run_validation` remains the portable test-suite entry point and ends with
the original controlled fixture. Its previously reported R2025a T0 results
were six delivered packets, zero drops/pending, and 384 application bytes.
`run_tranche1_validation` runs the current test suite and nine PHY-only scenarios.
Previous test totals apply to their recorded revisions; all runners discover
new portable tests as the repository grows.

Experiment settings are data, not protocol edits:

```matlab
cfg = csr.scenario.routedNetwork('autonomous');
cfg.Seed = 2026;
cfg.Traffic.PacketCount = 10;
cfg.DurationSeconds = 350;
result = csr.runScenario(cfg);
csr.analysis.exportResults(result, 'results/my_experiment');
```

`ApplicationPayloadBytes` is unambiguous application size. Bare modeled
wire payload adds 32 bytes (17 MAC + 8 HOP + 7 NWK); OTA preamble, 48 header
bits, and 32 FCS bits are added by airtime. Imported legacy `flow_packet_bytes`
has different semantics and is not an accepted input format yet. IDs preserve
the CSR 24-bit domain; 0xFFFFFF is reserved for control broadcast.

## Architecture and next tranches

The CSR model calls a small clock/RNG/channel boundary. The portable backend
uses base MATLAB. The optional R2026a adapter owns its native subclasses;
the protocol core never subclasses `wnet.Node`.

| Tranche | Working endpoint | Complexity | Depends on |
|---|---|---|---|
| 0 | Accepted controlled three-node transfer on R2025a | Low | Complete for portable R2025a |
| 1 | Accepted portable CSR PHY/channel/traffic on R2025a | High | Portable gate passed; native gate separate |
| 2 | Accepted portable MAC/HOP with fixed-path relays | High | Portable gate passed; native gate separate |
| 3 | Accepted portable autonomous ARL on R2025a | High | 289/289 tests and eight network scenarios; native gate separate |
| 4 | Accepted R2025a research scenarios and five application comparisons | Medium | Merged PR #4; timing/native/long-run gates separate |
| 5 | Accepted R2025a sweeps, diagnostics and measured residual audit | High, bounded by priorities | 367 tests and 18 sweeps; loss/recovery/native/long-run limits documented |
| 6 | Candidate NWK freshness correction and matched outage observations | Bounded subsystem correction | Based on merged PR #5; fresh portable MATLAB acceptance pending |

Baseline excludes battery, supervisory layer, and BBN routing. Keep major
working increments; source-exact micro-ordering only blocks when structural
or materially observable behavior is wrong.

See [source map](evidence/source-map.md), [compatibility](docs/compatibility.md),
[validation strategy](docs/validation-strategy.md),
[parity ledger](docs/parity-ledger.csv), and
[ns-3 execution evidence](evidence/ns3-validation.json), and
[R2025a T0 acceptance](evidence/matlab-r2025a-acceptance.json), and
[Tranche 1 handoff](docs/tranche-1-handoff.md), and
[Tranche 2 validation](docs/tranche-2-validation.md).

An optional installation probe is available in a fresh MATLAB session:

```matlab
probe = csr.sim.probeWirelessScheduler();
disp(probe)
```

It resets the native simulator instance and reports zero-node callback
observations. It is not used by the `wireless-clock` backend, which has an
actual native node. For the new R2026a adapter suite run `validate_native`;
see [native scope](docs/native-adapter.md).

## Validation and repository discipline

MATLAB unit, subsystem and scenario tests live in `tests/`. Current source's
Python utility and release-classifier checks were actually run here and pass;
their details are in the evidence file. Historical ns-3 C++ success is labeled
separately. The owner's R2025a run is recorded separately from local static
checks. Three original PHY/high-rate ns-3 workflows were built and executed
for T1 and passed; see `evidence/tranche-1-ns3-workflows.json`. Seventeen original
MAC/HOP/envelope workflows passed for T2; these are reference-side results,
not MATLAB or full-network numerical parity. No MATLAB execution occurred in
this workspace.

The portable PHY/channel/traffic and MAC/HOP foundations are accepted from owner runs. Remote
publication, PR creation, merging, and branch deletion require owner
authorization. Ordinary local edits, tests and internal commits proceed
within an authorized tranche.
