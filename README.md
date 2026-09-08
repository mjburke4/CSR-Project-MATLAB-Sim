# CSR MATLAB Network Simulator

Behavioral port of `mjburke4/CSR-Project-NS3-part2`, currently pinned to main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (2026-09-07, PR #50).

## Current milestone: Tranche 1 candidate; Tranche 0 accepted on R2025a

The integrated candidate adds CSR path loss, closure and passband matching,
receive power/noise, all-peer signal delivery, Search/Track acquisition,
half-duplex reception, capture/interference, complete BER tables, interval error
allocation and inclusive ECC. It retains the controlled foundation fixture,
scenario configuration, deterministic event/RNG ownership, bounded traces,
statistics and MAT/CSV/JSON exports. MATLAB has not yet executed this T1 code.

**The owner's corrected R2025a run passed 24/24 tests and completed the
acceptance scenario.** MATLAB 25.1.0.2943329 reported six packets delivered,
384 application bytes received, no drops or pending packets, and 307.2 bit/s
goodput. Test-suite time was 1.3764 seconds; this is not simulation runtime.
This accepts Tranche 0's portable foundation. R2026a and native wireless
integration remain untested. Evidence is the owner's console output, recorded
in `evidence/matlab-r2025a-acceptance.json`; runtime source hashes and exported
files have not been independently inspected. The prior count-type failure
remains documented in `evidence/matlab-r2025a-user-validation.json`.

Choose `csr.scenario.phyNetwork(...)` for the new PHY pipeline or
`csr.scenario.smallNetwork()` for the controlled T0 regression. T1 receivers
remain awake; transmissions still serialize FIFO at each source. Slot access,
reservations, ACK/DACK, retries, routing and security processing are the next
tranches. A collision observation does not automatically mean packet loss:
the source acquisition/error/ECC pipeline decides the result. A decoded
non-destination packet increments overhearing, never application delivery.

An optional R2026a `wireless-clock` backend uses an actual framework node to
drive the CSR event heap. CSR remains the sole RF transport. A separate native
packet/channel probe exists; full native CSR packet transport is deferred.
Both native paths require their own MATLAB execution gate.

## Run in MATLAB R2025a or R2026a

From the repository root in MATLAB:

```matlab
run_tranche1_validation
```

Or from PowerShell with MATLAB on PATH, after changing to the repository:

```powershell
matlab -batch "run_tranche1_validation"
```

This runs **72 prepared portable tests**, including the original 24, followed
by nine PHY scenarios. Results go to `results/tranche1_validation/`, including
`scenario_summary.csv` and per-scenario application/PHY traces. T1 success is
pending this actual MATLAB run. The clean PHY test expects six application
deliveries plus six successfully decoded overheard observations; all 12
receiver observations must not be counted as application deliveries.

`run_validation` remains the portable test-suite entry point and ends with
the original controlled fixture. Its previously reported R2025a T0 results
were six delivered packets, zero drops/pending, and 384 application bytes.
That prior result does not validate the newly added PHY implementation.

Experiment settings are data, not protocol edits:

```matlab
cfg = csr.scenario.phyNetwork('clean');
cfg.Seed = 2026;
cfg.Radio.RateKeyKbps = 500;
cfg.Nodes(2).RadioProfile.TxPowerDbm = -10;
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
| 1 | CSR PHY/channel/traffic candidate; optional native clock and packet probe | High | MATLAB runtime gates pending |
| 2 | Reliable MAC/HOP multi-node exchange | High | 1; specs can start during 1 |
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
[Tranche 1 handoff](docs/tranche-1-handoff.md).

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
for T1 and passed; see `evidence/tranche-1-ns3-workflows.json`. No MATLAB
execution occurred in this workspace.

The code is staged as one cohesive foundation. Remote publication, PR creation,
merging, and branch deletion require owner authorization. Ordinary local edits,
tests and internal commits proceed within an authorized tranche.
