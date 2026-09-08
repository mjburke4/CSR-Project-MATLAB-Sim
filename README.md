# CSR MATLAB Network Simulator

Behavioral port of `mjburke4/CSR-Project-NS3-part2`, currently pinned to main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (2026-09-07, PR #50).

## Current milestone: Tranche 0 accepted on R2025a

The repository started empty. The foundation provides a portable MATLAB
discrete-event skeleton with three nodes, configurable traffic, exact CSR
rate/airtime constants, bare DATA envelope sizing, controlled link delivery,
deterministic local random streams, bounded tracing, statistics, and exports.

**The owner's corrected R2025a run passed 24/24 tests and completed the
acceptance scenario.** MATLAB 25.1.0.2943329 reported six packets delivered,
384 application bytes received, no drops or pending packets, and 307.2 bit/s
goodput. Test-suite time was 1.3764 seconds; this is not simulation runtime.
This accepts Tranche 0's portable foundation. R2026a and native wireless
integration remain untested. Evidence is the owner's console output, recorded
in `evidence/matlab-r2025a-acceptance.json`; runtime source hashes and exported
files have not been independently inspected. The prior count-type failure
remains documented in `evidence/matlab-r2025a-user-validation.json`.

This is controlled direct transport: same-node transmissions serialize FIFO,
and each receive link succeeds or drops according to an explicit test
probability. It does not yet model CSR MAC/HOP, routing, link budgets,
interference/capture, BER/ECC, security, or native wireless simulator transport.
An overlapping transmission is not presently treated as a collision. Result
metadata labels this stage so these outputs cannot be mistaken for full CSR
research results.

## Run in MATLAB R2025a or R2026a

From the repository root in MATLAB:

```matlab
run_validation
```

Or from PowerShell with MATLAB on PATH, after changing to the repository:

```powershell
matlab -batch "run_validation"
```

The acceptance scenario produces 6 generated/transmitted/received packets,
0 drops, 0 pending, and 384 received application bytes in the reported R2025a
run. The final standalone scenario/export stage completed according to the
entry point and its success message. Logs, release
metadata, test outcomes, MAT results, and CSV/JSON exports are written to
`results/validation/`. Retain that directory with the experiment results.

Experiment settings are data, not protocol edits:

```matlab
cfg = csr.scenario.smallNetwork();
cfg.Seed = 2026;
cfg.Radio.RateKeyKbps = 500;
cfg.Channel.FixedDropProbability = 0.1; % controlled test loss, not BER
result = csr.runScenario(cfg);
csr.analysis.exportResults(result, 'results/my_experiment');
```

`ApplicationPayloadBytes` is unambiguous application size. T0 bare modeled
wire payload adds 32 bytes (17 MAC + 8 HOP + 7 NWK); OTA preamble, 48 header
bits, and 32 FCS bits are added by airtime. Imported legacy `flow_packet_bytes`
has different semantics and is not an accepted input format yet. IDs preserve
the CSR 24-bit domain; 0xFFFFFF is reserved for broadcast, which is deferred.

## Architecture and next tranches

The CSR model calls a small clock/RNG/channel boundary. The current portable
backend uses base MATLAB. Tranche 1 adds the real PHY/channel and an optional
R2026a native adapter; the protocol core never subclasses `wnet.Node`.

| Tranche | Working endpoint | Complexity | Depends on |
|---|---|---|---|
| 0 | Accepted controlled three-node transfer on R2025a | Low | Complete for portable R2025a |
| 1 | CSR PHY/channel/traffic and native R2026a adapter | High | 0 |
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
[R2025a acceptance](evidence/matlab-r2025a-acceptance.json).

An optional installation probe is available in a fresh MATLAB session:

```matlab
probe = csr.sim.probeWirelessScheduler();
disp(probe)
```

It resets the native simulator instance, tests zero-node callback scheduling,
and reports actual observations. It does not implement or select a wireless
backend. Public docs do not guarantee that zero-node use on R2025a succeeds.

## Validation and repository discipline

MATLAB unit, subsystem and scenario tests live in `tests/`. Current source's
Python utility and release-classifier checks were actually run here and pass;
their details are in the evidence file. Historical ns-3 C++ success is labeled
separately. The owner's R2025a run is recorded separately from local static
checks. No MATLAB or ns-3 C++ execution occurred in this workspace.

The code is staged as one cohesive foundation. Remote publication, PR creation,
merging, and branch deletion require owner authorization. Ordinary local edits,
tests and internal commits proceed within an authorized tranche.
