# Tranche 10 failure: independent evidence and budget audit

The failure is a structural blocker in retained case **27/29, `research_mesh_6_seed_128`**, before sweeps, diagnostics or campus. The supplied console log confirms 279 MAC, 154 receiver and 101 retained ACK checkpoints passed. The runner advanced through the unit-test gate and 26 retained cases before the event cap stopped the six-node mesh. No full returned archive or failing simulation state is available yet.

## Accepted mesh comparison

| Archive | Simulated duration | MaxEvents | Wall time | Applications | OTA transmissions | Pending scheduler events |
|---|---:|---:|---:|---|---:|---:|
| Tranche 6 R2025a | 900 s | 2,000,000 | 59.8085751 s | 15/15 delivered, no drops/backlog | 1,183 | 6 |
| Tranche 7 R2025a | 900 s | 2,000,000 | 59.8014808 s | 15/15 delivered, no drops/backlog | 1,183 | 6 |

Both accepted runs have 5,915 receiver observations, 19,472 protocol rows, 20,851 PHY rows and no omitted protocol/PHY records. The current `researchNetwork.m` hash is **903f78913a0e7c0d06e9adeeafe30af8b82703dd2cbd1c40705ef6a6644a372a**, identical to the accepted T7 source hash. Tranche 9's returned archive contains no mesh run.

**The prior archives do not record executed scheduler callback counts.** `performanceSummary.m` explicitly sets `ExecutedEventsAvailable=false`. Trace row counts and pending events therefore cannot establish the total old event count. The failure is consistent with a newly exposed timing loop or an altered workload, but the console log alone cannot distinguish them. Raising the cap is not justified by these records.

## The earlier Tranche 4 message is expected

`TestResearchEvidence.failedRunPreservesOriginalErrorUnderRelativeOutputRoot` (lines 108–128) deliberately asks `run_tranche4_validation` for `unknown_case`, expects `csr:validation:Catalog`, and checks that failed metadata and `tranche4_evidence.zip` survive. Its printed “Tranche 4 failed” warning is expected negative-test output, separate from the later mesh failure.

## Existing failure capture and shortest useful rerun

The full runner catch writes the original identifier/message and packages all completed evidence. It does not retain the failing mesh object: the handle is local to `csr.runScenario` and `result` is assigned only after successful completion. The existing partial ZIP should preserve test results, all contract records and 26 completed cases, but cannot reveal the failing mesh clock, callback or queue state.

Run only the unchanged factory `csr.scenario.researchNetwork('mesh_6',struct('Seed',128))` through an explicitly retained `csr.sim.NetworkSimulation` handle, once, with duration 900 and MaxEvents 2,000,000. A wrapper catch can record the scheduler's public `Now`, `nextTime()` and `PendingCount`, every MAC snapshot/counter, HOP stats and NWK stats/routes/neighbors. Include exact config and source hashes. Use a short path such as `results/m10/r...` and package only this diagnostic result.

The next callback itself is private. A failure-only read-only scheduler diagnostic method or enriched limit exception can expose its `func2str`, time and event ID without changing event order or RNG draws. This is preferable to broad tracing or a limit increase when the callback cause remains unproven. Do not chunk `scheduler.run`: the cap resets per call, so that would weaken this guard. No need to repeat 26 completed scenarios or campus merely to reproduce the mesh.

No MATLAB runtime was used in this review, and no source files were edited. Full archive paths, hashes and exact record counts are in `evidence-audit.json`.
