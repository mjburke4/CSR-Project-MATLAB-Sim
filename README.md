# CSR MATLAB Network Simulator

Behavioral port of `mjburke4/CSR-Project-NS3-part2`, currently pinned to main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (2026-09-07, PR #50).

## Current milestone: portable Tranche 2 MAC/HOP accepted

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

These are historical results for the accepted revisions, not execution of the
new Tranche 2 candidate. Choose `csr.scenario.phyNetwork(...)` for PHY-only runs or
`csr.scenario.smallNetwork()` for the controlled T0 regression. T1 receivers
remain awake; transmissions still serialize FIFO at each source. Slot access,
reservations, ACK/DACK and retries are supplied by the new
`csr.scenario.macHopNetwork(...)` path. Routing and security processing remain
later work. A collision observation does not automatically mean packet loss:
the source acquisition/error/ECC pipeline decides the result. A decoded
non-destination packet increments overhearing, never application delivery.

An optional R2026a `wireless-clock` backend uses an actual framework node to
drive the CSR event heap. CSR remains the sole RF transport. A separate native
packet/channel probe exists; full native CSR packet transport is deferred.
Both native paths require their own MATLAB execution gate.

## Run in MATLAB R2025a or R2026a

From the repository root in MATLAB:

```matlab
run_tranche2_validation
```

Or from PowerShell with MATLAB on PATH, after changing to the repository:

```powershell
matlab -batch "run_tranche2_validation"
```

This runs all current portable tests, the controlled T0 fixture and nine
MAC/HOP scenarios: reliable link, ACK loss, DATA loss, DACK, contention, relay,
queue pressure, 500 kbps and 1 Mbps. Results go to
`results/tranche2_validation/`, including `scenario_summary.csv`, per-node
MAC/HOP counters, protocol/PHY traces, configuration and runtime metadata.
The default backend needs no wireless toolbox.

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
cfg = csr.scenario.macHopNetwork('relay');
cfg.Seed = 2026;
cfg.Traffic.Path = [2 3 1];
cfg.Traffic.PacketCount = 10;
cfg.DurationSeconds = 150;
result = csr.runScenario(cfg);
csr.analysis.exportResults(result, 'results/my_experiment');
```

`ApplicationPayloadBytes` is unambiguous application size. Bare modeled
wire payload adds 32 bytes (17 MAC + 8 HOP + 7 NWK); OTA preamble, 48 header
bits, and 32 FCS bits are added by airtime. Imported legacy `flow_packet_bytes`
has different semantics and is not an accepted input format yet. IDs preserve
the CSR 24-bit domain; 0xFFFFFF is reserved for broadcast, which is deferred.

## Architecture and next tranches

The CSR model calls a small clock/RNG/channel boundary. The portable backend
uses base MATLAB. The optional R2026a adapter owns its native subclasses;
the protocol core never subclasses `wnet.Node`.

| Tranche | Working endpoint | Complexity | Depends on |
|---|---|---|---|
| 0 | Accepted controlled three-node transfer on R2025a | Low | Complete for portable R2025a |
| 1 | Accepted portable CSR PHY/channel/traffic on R2025a | High | Portable gate passed; native gate separate |
| 2 | Accepted portable MAC/HOP with fixed-path relays | High | Portable gate passed; native gate separate |
| 3 | Autonomous ARL routing and multihop delivery | High | 2; route/serialization work parallel to 1–2 |
| 4 | Configurable research scenarios and differential runs | Medium | 1–3 |
| 5 | Material parity closure and research tooling | High, bounded by priorities | 4 |

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
