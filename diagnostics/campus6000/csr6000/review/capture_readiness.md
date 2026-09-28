# Current two-seed MATLAB capture readiness

The current `integration_v2/candidate` already supplies the application accounting and causal phase evidence required for the corrected 6,000-second seed-131/132 comparison. **No production capture change or new observer is needed.** This is a source/API audit, not an executed MATLAB validation; neither MATLAB nor Octave is installed here. There are 96 candidate MATLAB files. No applicable `AGENTS.md` exists in this candidate or its ancestors.

## Configuration and entry point

The kit uses the exact seed-specific native campus inputs, `csr6000/inputs/s131.csv` (SHA-256 `e10d210590c80cb839442b7847ee6c7e8b8c21d043da5fe5dcf1f2abb402ca7a`) and `s132.csv` (SHA-256 `fa45217f8631f34d203580842d8a1a12cb18c53a3efbe0b702b2e17aaeb30d48`). They import seeds 131 and 132 directly; no MATLAB seed override is needed. The input-binding audit confirms the scenario difference from the original seed-128 CSV is the seed token; configuration provenance differs accordingly. Import the selected file and apply the explicit original capture budgets:

```matlab
config = csr.scenario.importNs3(scenarioPath, struct( ...
    'HistoricalBenchmark', true, 'FlowLimit', 0, 'Backend', 'portable'));
assert(config.Seed == seed); % 131 or 132, already in the selected CSV
config.Trace.Enabled = true;
config.Trace.MaxRecords = 1500000;
config.Trace.MaxPhyRecords = 1500000;
config.Trace.MaxApplicationAdmissionRecords = 100000;
config.MaxEvents = 12000000;
config = csr.scenario.validate(config);
simulation = csr.sim.NetworkSimulation(config);
result = simulation.run();
```

Retain the imported 6,000-second duration, six fixed-destination flows, 300-second traffic start, 0.02-second interval, 285,000 attempts per flow, autonomous routing, historical gated generator, real CSR PHY, continuous timing and current default `Hop.DataQueuedRetryPolicy='actual-tx'`. Pass no `LinkDiagnostics`, `AckServiceDiagnostics` or `TransportTiming` object. The 15% comparison target is an analysis criterion, not a simulator parameter.

`csr.runScenario(config)` is also valid, but direct `NetworkSimulation` construction retains access to `simulation.Scheduler.Now` for the completed-stop receipt. `NetworkSimulation.run` starts all MAC/NWK instances, schedules traffic, and calls the scheduler exactly once through the configured horizon; no post-stop drain is needed.

The candidate contains no `scenarios/` input tree. Therefore `benchmarkSuite` and `tranche25Suite` cannot be called from this candidate alone. Use the direct import above, or bundle their complete hash-bound catalog/plan/input dependencies. Direct import is the smaller harness dependency and uses the same existing importer. Record the imported seed, exact selected input hash and that no seed override occurred.

## Evidence already available

| Requirement | Existing evidence/API | Meaning |
|---|---|---|
| Complete attempted/admitted accounting | `ApplicationAdmissionStatistics` | Every flow's attempts partition into admitted or one blocked gate reason; independent of the detailed trace cap. |
| Complete admitted identities | `ProtocolTrace` rows `app_generate` | Packet ID, source, destination, bytes, DSCP and admitted generation time for every created application. |
| Attempt index for every admitted app | Fixed traffic schedule plus `app_generate.TimeSeconds` | Reconstruct `(round(t*1e9)-start_ns)/interval_ns`; validate integer range and prefix identities. Rejected attempts have no persistent packet ID. |
| Final outcome and first delivery | `csr.analysis.performanceSummary(result)` second output | Existing `applications.csv` columns are unchanged; chronology handles late custody/delivery recovery after an earlier drop. |
| NWK waiting | `network_enqueue`, `hop_admit`, `network_submit`, `relay_accept` | Custody arrival to successful HOP admission for each accepted downstream path. |
| HOP/MAC service and retries | `hop_sent`, `hop_receive`, `hop_retry`, `hop_ack`, `hop_dack`, `hop_dack_expired`, `hop_failed` | Logical DATA actual transmission starts and feedback ownership transitions remain available, including DATA inside aggregates. |
| Final delivery boundary | `app_receive` | Unique final-destination application delivery; subsequent upstream ACK ownership is excluded from delivered latency. |
| Stop boundary | `Scheduler.Now`, `Statistics.Pending`, NWK/HOP node statistics, `Metadata.PendingEvents` | Stop time and aggregate remaining ownership, not a per-application retained-copy inventory. |

`record` retains the original 13-column protocol schema: time, event, node, peer, packet, application bytes, reason, frame kind, sequence, DSCP, queue depth, control type and hop count. These are sufficient for the existing causal-path parser. `app_receive` is emitted only once per application; the complete delivered path follows accepted relay custody, not ACK completion. Preserve raw event order, including equal timestamps.

Current `performanceSummary` explicitly allows an earlier `app_drop` to be recovered by later `relay_accept` or `app_receive`. The new batch parser must use the **final chronological outcome**, not classify every historically observed drop row as a terminal loss. The earlier original-seed audit happened to have no such recoveries; that is not a universal contract.

## Bounded capture and performance

Keep the original 100,000-row admission prefix rather than expanding it to 1,710,000 attempt rows per seed. Complete counters and all admitted identities remain available. The omitted count is expected to be 1,610,000 if all configured attempts execute; prefix state snapshots must be labelled incomplete. Neither inferred blocked-event snapshots nor a full extra attempt log is required for the admitted latency analysis.

| Original seed | Protocol rows | PHY rows | Protocol limit | PHY limit |
|---|---:|---:|---:|---:|
| 131 | 619,363 | 767,054 | 1,500,000 | 1,500,000 |
| 132 | 615,625 | 759,309 | 1,500,000 | 1,500,000 |

Trace arrays are preallocated as MATLAB struct arrays in the constructor; raising their limits increases resident memory. The original limits leave about 2x headroom over the observed original PHY rows, but are not a guarantee for a changed run. Any protocol or PHY omission must fail the completeness gate and retain available evidence; it must not be treated as passing parity. `MaxEvents` is an executed-callback guard, not a traffic cap.

Run the two seeds sequentially under the single user command, export/checkpoint each result, and release its simulation/result before the next seed. This avoids holding two large trace buffers simultaneously. The original MATLAB wall times were approximately 107 and 182 minutes, respectively; they are historical observations, not a promised duration for the corrected candidate or user's machine. No in-simulation progress callbacks are required.

Full-window `AckServiceDiagnostics` would duplicate every protocol callback and every generator attempt into JSON-bearing rows and add inherited feedback traces. Its maximum record budget is 1,000,000. It is unnecessary here and would increase memory, output and truncation exposure. Plain `LinkDiagnostics` similarly adds ACK detail that is not needed for the requested accounting/latency milestone.

## Minimal harness work

1. Copy the exact candidate and campus input into a self-contained kit, bind their hashes, and make a single root command run both seeds independently. Detect path shadowing before execution. Keep completed case receipts so an already completed matching case need not run again after another case fails.
2. Export the existing schemas under each case: `raw/protocol_trace.csv`, `raw/phy_trace.csv`, `raw/application_admission_statistics.csv`, `raw/application_admission_trace.csv`, `raw/summary.json`, node statistics, routes, neighbors and scenario; plus `analysis/applications.csv`, `analysis/performance_summary.csv`, and the existing aggregate/provenance files if the usual plot workflow consumes them. `csr.analysis.exportResults` and `performanceSummary` already provide these.
3. Record candidate/config/scenario hashes, seed, version, start/end UTC, elapsed wall time, stop time, trace row/omission counts and stage status in case receipts. The existing `Artifacts` helpers require MATLAB's standard JVM. Retain `.mat` locally; return CSV/JSON evidence in the output ZIP, as the earlier contracts do.
4. Require stop at 6,000 s, unchanged effective config, 1,710,000 attempts, per-flow counter closure, unique generated/delivered identities, complete protocol/PHY traces, correct admission-prefix accounting and outcome/summary agreement. `researchSummary`/`performanceSummary` already enforce most of this. Do not require `Pending==0` or `DataDrained`: finite-stop work is an outcome, not structural failure.
5. If post-run validation/export fails, retain the completed result's raw evidence and report the exception identifier, message and stack before continuing to the other seed. The existing `ensembleContract` has a partial-export pattern; do not discard a multi-hour run solely because a later check fails.
6. Derive admitted schedule indices and path phases after the run without adding simulator events. Reuse the existing causal-path method, report incomplete or ambiguous paths explicitly, and keep source/relay NWK waits separate from combined post-admission service. Compare native against that combined service; the finer MATLAB actual-TX split is not generally available in the original native evidence.

No new private-state accessor is needed. Aggregate NWK/HOP stop statistics do not prove that every unresolved application's age belongs to a live queued copy. Label it `unresolved_at_cutoff` / `model_pending_status`, not live queue age. A future identity-level custody inventory would be a separate scope.

## Source locations checked

- `+csr/runScenario.m:1`: public dispatch.
- `+csr/+sim/NetworkSimulation.m:39`, `:80`, `:155`, `:225`, `:276`, `:304`, `:347`, `:378`, `:402`, `:440`, `:700`: construction, buffers, run/stop, counters, returned tables, generation, prefix capture, delivery/custody/drop and trace serialization.
- `+csr/+sim/ApplicationGenerator.m:29`: complete per-attempt counter update before trace retention.
- `+csr/+analysis/performanceSummary.m:97`: application outcome reconstruction and recovery chronology.
- `+csr/+analysis/researchSummary.m:26`, `:107`: trace completeness and historical generator/prefix checks.
- `+csr/+analysis/exportResults.m:1`: raw CSV/JSON/MAT output.
- `+csr/+scenario/benchmarkSuite.m:71`: original capture budgets.
- `+csr/+validation/ensembleContract.m:21`: original completed-result/export/failure pattern.
- `+csr/+sim/AckServiceDiagnostics.m:50`, `:64`: optional callback/admission detail duplication.
- `+csr/+nwk/Layer.m:421`, `+csr/+hop/Layer.m:229`: public stop statistics, no per-app copy inventory.

Audit result: **ready for a harness-only two-seed owner kit; no production instrumentation patch recommended.** Runtime completion remains to be established by the user's MATLAB return.
