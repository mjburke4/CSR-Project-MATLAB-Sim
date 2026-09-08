# Tranche 1 — integrated PHY/channel/traffic

**Portable R2025a runtime gate accepted on owner-reported execution evidence:**
72/72 tests passed and all nine PHY scenarios completed. R2026a and native
execution remain unvalidated. See [acceptance](tranche-1-r2025a-acceptance.md).
Implementation commit: `3f63b811d51dc8e93548586cc7e6994981adac13`; tested runtime
source hash and exported files were not independently inspected. Source main
was rechecked at implementation time as
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; the accepted T0 checkpoint is
`6de5c0f`. Development uses `tranche/1-phy-channel-traffic`.

## Objective and implemented capabilities

Replace destination-only controlled delivery with meaningful CSR network PHY
behavior. A transmission reaches all non-self receivers; closure, passband,
power/noise, acquisition, overlapping signals, interval BER and inclusive ECC
govern each receiver. Decoded overhearing and intended application delivery
have separate counters. All-peer outcomes, pending work, reasons and bounded
PHY traces support integrated experiments.

| Capability | Implementation |
|---|---|
| Radio/channel | Source profile defaults; minimum-gain three-path and optional log-distance propagation; antenna gains/heights; closure/delegate; channel overlap; noise bandwidth scaling |
| Timing and rates | Source long/short preambles and exact rates 8/16/32/64/128/500/1000; source propagation speed in PHY fixtures; DPSK/DQPSK mapping |
| BER/error/ECC | Complete standard/DQPSK data and 4,910 collision curves; source JSR/half-chip lookup; DPSK formula; processing gains; binomial errors; current interval truncation and inclusive protected-bit ECC |
| Receive integration | Search/Idle/Track boundary, admitted-preamble handling, half-duplex, capture diagnostics, different-rate additive noise, receiver-global spread JSR and per-signal high-rate jammer state |
| Traffic/frames | Fixed periodic flows with per-flow rate/preamble/power overrides; observation IDs; explicit application/wire sizes; optional Pairwise16 overhead sizing without security processing |
| Experiment outputs | Application/node/PHY statistics, application and PHY traces, MAT/CSV/JSON exports; nine reusable scenarios |
| R2026a integration | Optional actual-node native clock driving the shared CSR queue; separate native abstract-packet/channel lifecycle probe |

New core files are `RadioProfile`, `Model`, `BerTables`, and `SignalEngine` in
`+csr/+phy`; scenario/packet/Simulation integration stays release-independent.
Native subclasses are isolated under `+csr/+sim/+native`. Table conversion and
original-C++ reference generation are reproducible Python scripts with hashes.

## Validation evidence

| Check | Actual result and boundary |
|---|---|
| Original ns-3 PHY front end, BER/ECC, live high-rate workflows | **3/3 passed**, built and executed unchanged with pinned engine `6b5cd24ea80713ce16d88575869aedd6f432bdae` |
| BER conversion/lookup check | **300,632 binary64-exact comparisons passed** against compiled original C++; data conversion/lookup evidence, not MATLAB execution |
| Additional original C++ references | **400 vectors checked in passing R2025a TestCppBerReference tests** |
| Static lint | **41 MATLAB files passed**, MISS_HIT 0.9.44, R2022a syntax profile; not release/runtime validation |
| Portable MATLAB tests | **72/72 passed** on owner R2025a, including all 24 T0 tests; 4.6861 seconds suite time |
| Native R2026a tests | **5 prepared**; separate gate, not discovered by portable runner |
| MATLAB versions executed for T1 | **R2025a 25.1.0.2943329**, owner console evidence; R2026a unvalidated |
| Integrated portable PHY scenarios | **Nine completed**, all meet gates; clean/high rates 6/6 delivery, six overheard observations; all pending zero |
| MATLAB↔ns-3 and OPNET network scenario comparison | Not yet executed; no claim of full numerical or event parity |

The independent review corrected mixed numeric node-ID handling, integer
start-time arithmetic, delegate JSON export and propagation timing, and added
an exact-horizon native scheduling check. No remaining default portable
structural blocker was identified by review. See `tranche-1-review.md` and
the `evidence/tranche-1-*` and BER provenance files.

## Run on the R2025a machine

To reproduce the accepted portable gate, extract the package to its own folder,
make that repository the MATLAB current folder, and run:

```matlab
run_tranche1_validation
```

The command runs portable tests, preserves test output, then executes and
exports clean, overhearing, same-rate collision, mixed-rate interference,
weak-link, channel-mismatch, closure, 500 kbps and 1 Mbps scenarios.
Collect `results/tranche1_validation/`, especially the test log/results,
`scenario_summary.csv` and `clean/summary.json`.

The clean PHY scenario expects six application deliveries, six overheard
decodes, twelve completed physical receive observations and no drops. Failure
fixtures expect zero intended delivery. Collision fixtures require honest
overlap accounting and packet conservation, not an unconditional loss count.
The owner-reported results meet these criteria; measured console values and
evidence scope are recorded in `tranche-1-r2025a-acceptance.md`.

On an R2026a machine with the required toolbox, separately run:

```matlab
validate_native
```

This checks native clock ordering/horizon behavior, controlled CSR execution,
and the separate native packet/channel probe. The native clock intentionally
fails if it misses a due CSR event; it does not silently execute missed work
after native simulation stops.

## Explicit differences and deferred items

- T1 receivers stay awake. Idle/Search is a controlled hook; duty cycling,
  source post-TX waiting and the operational MAC access/reliability cycle are
  T2 work. Sender FIFO serialization is not slotted CSR MAC.
- Source closure diagnostics occur at TX; this model's application completion
  callback is delayed to modeled receive completion so packet accounting uses
  one consistent callback. This changes closure-event timing and is recorded.
- Current ns-3 PHY/ECC interval behavior is retained. The reverted OPNET BER
  timing experiment and unresolved ECC-attribution statistics remain deferred.
- Physical positions are explicit 3D coordinates. Match imported 2D source
  geometry deliberately when building equivalent scenarios; radio heights
  remain separate profile inputs.
- The `wireless-clock` backend uses native scheduling, with CSR owning RF.
  Full native packet transport into the CSR interference engine is not yet
  integrated. The separate probe must not be described as that integration.
- RNG mapping v2 adds a separate SYNC-threshold stream while preserving the
  original four stream keys. Matching numeric seeds across simulators does
  not imply identical random draws.
- Per-interval bit rounding follows current ns-3; source time quantum and
  MATLAB double timestamps can still yield boundary differences to examine
  in controlled comparisons. No hidden tolerance broadening is used.
- ACK/DACK, queues/reservations/retries, autonomous routing, full control-wire
  serialization and security processing remain later tranche endpoints.

The portable gate has passed. The recommended next tranche is cohesive T2
MAC/HOP reliability. Native acceptance is tracked separately if that installation
is not available. Battery, supervisory layer and BBN routing remain out of scope.
No remote push, PR, merge or branch deletion was performed.
