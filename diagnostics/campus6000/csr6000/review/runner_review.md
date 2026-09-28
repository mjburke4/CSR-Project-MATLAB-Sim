# Independent runner and scoring review — proposed 6,000-second batch

Scope: read-only inspection of `integration_v2/run_next_tests.m`, the archived `routing_recovery/t25/run_tranche25_validation.m`, and the current candidate's `EnsembleCheckpoint`, `tranche25Suite`, `benchmarkSuite`, `ensembleContract`, `Artifacts`, `exportResearchCase`, `exportResults` and `NetworkSimulation` export interfaces. No applicable `AGENTS.md` was found in their workspace ancestors or inspected trees. No simulation or new test series ran. This is a preparation review; the new runner and package have not yet been inspected.

## Main recommendation

Ship a complete, short-root package such as `batch6000/`, with a standalone `run_6000_batch.m`. The normal instruction remains one command:

```matlab
report = run_6000_batch;
```

Bundle the unchanged grouped-routing-corrected candidate, the original hash-bound campus input, a new two-case plan, and the compact native comparison references. No Python, ns-3, old tranche directory, or additional download should be needed on the owner's machine. The cases should execute sequentially, with a separate case function releasing large simulation/result objects before the next case. The review/return workflow can perform detailed causal reconstruction from exported traces here.

## Do not reuse T25 identity and acceptance contracts unchanged

The old checkpoint rigidly requires 404 T23 files, 181 MATLAB files, the original unmodified baseline, a 10% plan, the full portable regression, and reuse of seeds 128–130 to form a five-seed result. Those requirements do not describe the current 96-MATLAB-file candidate or this newly authorized two-case batch. Its `validatePlan`, `identity`, `reusedCases`, `attachCase` and status text cannot simply be called from a new wrapper. Do not weaken these old contracts or relabel old runs to bypass them. Keep production files unchanged and put new plan, receipts and export orchestration in separate harness files.

The minimal integration candidate also lacks the archived benchmark scenario/catalog/evidence tree. The selected new kit imports the native seed-specific CSVs directly with the same historical options. The native-binding review must establish that each differs from the old MATLAB scenario only in the declared seed token. Record actual imported seeds 131/132, with no override; do not carry over the old `imported_seed=128` claim. Preserve the scenario hashes, portable backend, real PHY, autonomous routing, `actual-tx`, historical gated generator, zero flow limit, 6,000-second stop, continuous timing, and no observer/post-stop drain. Record the unchanged trace budgets and event limit as configuration, not as newly tuned behavior. The old `Benchmark` object is reporting metadata and is not required for direct import; its absence must not be mistaken for a production change.

## Provenance and path isolation

- Verify packaged source/data/scenario/reference membership and hashes before the expensive runs, and verify them again before sealing each completed case. Include new runner/helper code in the execution identity, not only the production `+csr` files.
- Bind the new plan's 15% target, seeds, horizons, scenario, current-candidate manifest, native reference manifests and MATLAB runtime. Preserve the native source/engine pins as reference identities; the model's fixed `Metadata.SourceCommit` alone is not the MATLAB candidate identity.
- Record resolved paths for all relevant production and analysis entry points, including NWK, simulation, scheduler, importer, exporter and performance summary. The integration runner checks only HOP, MAC and PHY. Canonicalize Windows paths; restore the caller's path on every exit.
- Avoid silently clearing the user's workspace/classes. Detect conflicting CSR code and produce an explicit actionable error; a clean MATLAB session is the simplest documented recovery if classes from an older kit are already loaded.
- Exclude mutable output/log/ZIP directories from the frozen input inventory. Reject output destinations inside candidate/reference source folders. A relocated kit should not require the original absolute workspace paths.

## Completed-case checkpoints; never partial simulator continuation

The old receipt design has useful properties: one immutable start identity, a completed summary, exact artifact membership/hashes, input stability checks, and a seal written last. Retain those properties with a new schema, but avoid its all-or-nothing preflight: an interrupted seed 132 should not invalidate a completed seed 131.

Only skip a case after verifying a complete receipt, its identity/runtime/config, all required artifact bytes, and its structural completion conditions. A partial/failed directory is not completed evidence and must not be appended to, merged into, or counted with a later attempt. Preserve it under a distinct attempt path; rerun that case from a fresh simulator with the original seed. Select exactly one verified completed attempt per case in the final summary. Do not restore partially executed simulator objects or RNG state.

An explicit existing-output argument is acceptable for safe resume; normal use remains the single command. If automatic resume is implemented, require one unambiguous matching batch identity. Protect against simultaneous invocations with a lock. A stale lock after a crash must not be deleted blindly if another MATLAB process may still be running. Preserve completed receipts even when packaging or a later case fails. Runtime/source/plan changes prevent completed-stage reuse.

Write summaries/manifests/receipts to temporary files and atomically replace their targets where feasible; a receipt becomes authoritative only after all artifact checks succeed. Keep mutable diary logs outside sealed case inventories. Catch and record each case failure, continue to the other independent case where safe, and package the resulting failure/partial evidence. A failed case cannot contribute acceptance metrics.

## Evidence required from each completed case

- Exact 6,000-second scheduler completion and unchanged config; neither a reached event cap nor partial export is success.
- Complete protocol and PHY traces with zero omissions, complete admitted application identities and unique final outcomes, all six sources' aggregate admission counters, and the original explicitly bounded admission-attempt prefix. Do not expand to 1.71 million stored rejected-attempt rows unnecessarily: aggregate counters plus complete admitted generation records support the intended accounting.
- Preserve event order for equal timestamps and sufficient application/peer/HOP sequence fields for causal queue-entry → admission → receipt reconstruction.
- `applications.csv` must close to generated/admitted, delivered, dropped and model-pending totals. Separate final model status from physical queue occupancy. Do not infer native drops from `no_ack`, DACK expiry or reception failures.
- Export source/scenario/reference identities, runtime/release, config, trace row counts, elapsed wall time, structural checks and source stability. `completed` describes successful execution/export; numerical target status is separate.

The old `exportResults` writes both `trace.csv` and `protocol_trace.csv` and a MAT snapshot. Preserve the required protocol CSV; avoid returning duplicate large traces or MAT objects unless they serve a specific review need. A compact return ZIP can contain complete CSV/JSON evidence while recording optional local MAT artifacts separately. ZIP creation must exclude itself and temporary ZIPs, and a final archive must include failures as well as completed cases. Print the exact ZIP path even when numerical differences occur.

Report each case start, completion/export, and checkpoint reuse to the console. Do not introduce simulation-queue progress callbacks solely for a progress display; these would change the event history being measured. Explain beforehand that a long case can run quietly. Do not promise an unverified wall-clock ETA.

## Freeze the 15% scoring interpretation before the owner run

Use the same six sources and the two fresh seeds, with native-reference-relative residual `(MATLAB−native)/native`. Report admissions, unique delivered counts, delivery per scheduled attempt, conditional first-delivered latency, and deadline deliveries with full follow-up. Reuse the declared 60/300/600/1,200-second postprocessing horizons rather than creating additional simulations. Show both all-attempt and admitted denominators for deadline delivery; cohorts remain `[300, 6000−T)`.

Classify each metric/cell against ±15% explicitly. A zero native count cannot support a relative percentage: show absolute counts and a support mismatch when MATLAB is nonzero; a conditional latency with no deliveries remains undefined, never zero or an automatic pass. Native seed 131's absent sources remain visible even if their improved MATLAB reachability is desirable. Unknown native terminal drops/live pending cannot be scored against MATLAB's recorded categories as though native were zero.

Network totals, source weights and matched-attempt sensitivities are supporting diagnostics. They must not replace per-source rows or mask opposite seed effects. Do not infer a universal network pass from a structural completion flag or from selected metrics under 15%; freeze the actual gate membership in the plan or leave the final composite claim for the evidence review. Existing seeds 128–130 may appear as historical context only, not as current-candidate five-seed acceptance. This batch refreshes two histories and makes no statistical-equivalence claim.

## Final package review still needed

Before delivery, independently extract the ZIP to a different short path; verify manifest coverage, the top-level command and all required dependency paths; confirm the production candidate is byte-identical to the selected corrected baseline; inspect resume/failure handling and the plan's 15%/two-case scope; statically check the new MATLAB harness. Clearly record that MATLAB execution remains pending until the owner returns results. None of these preflight checks requires a new simulator run.
