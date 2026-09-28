# Independent review of the new batch runner and analysis helper

The new `csr6000/run_6000_batch.m` and `private/batch_case_analysis.m` were inspected without executing MATLAB or a simulation. This review covers the code version after the corrections below; final packaged hashes and the synthetic preflight still require the final package review.

## Findings resolved during review

1. **Native duplicate final deliveries would have stopped seed 132 analysis.** The initial helper required `delivery_event_count` to equal a delivered boolean. The bound seed-132 reference contains four uniquely delivered applications with two proven delivery events each. The helper now accepts positive integer event counts for delivered identities and exactly zero for unresolved identities, preserves event and duplicate counts separately, and continues to use unique first delivery for latency. This was a confirmed input-dependent runtime blocker, corrected before the owner run.
2. **Output paths could overlap immutable inputs or the kit ancestor.** The runner now rejects the kit itself, its ancestors, and model/input/reference/private subdirectories as output destinations. The normal `out_6000` directory remains valid.
3. **The runner needed an explicit stop-boundary observation.** It now constructs `csr.sim.NetworkSimulation` directly, runs once, reads and asserts `Scheduler.Now == 6000`, and releases the simulation instance. It does not add observers, progress events, or a drain.
4. **Post-run reporting failure could lose a costly result.** The runner now saves a local v7.3 result checkpoint before analysis/export, retains it on failure, and exports partial raw evidence where possible. A failed attempt remains unaccepted; only a completely sealed attempt is reused. The temporary checkpoint is removed only after the canonical export has produced its own local MAT result.

## Reviewed behavior

- New schema and plan identity describe exactly seeds 131/132, 6,000 seconds and a 15% analysis target. The old T25 five-seed/10%/404-file contract is not reused.
- Seed-specific native scenarios are imported directly. Actual imported seeds are 131/132, with no old seed-128 override claim. The independent native binding audit owns input equivalence to the original MATLAB scenario apart from the seed token.
- Input manifests cover production, data, scenario, reference and runner files. The model inventory is exact. Source/input stability is rechecked before completion; runtime and complete plan hash identify reusable cases.
- The operating-system file lock protects one output directory and releases on MATLAB exit. Each invocation and attempted case receives a distinct directory. Unsealed attempts are preserved and restarted from time zero; no partial simulator state is treated as complete.
- A completed case is reused only when its completion identity and full CSV/JSON/log inventory verify. Each final batch summary selects one completed attempt per seed; historical attempts remain distinguishable. Mutable invocation logs are outside sealed case inventories.
- Run and export exceptions remain separate from numerical target results. The other seed is attempted after a handled case failure. The return ZIP contains complete or partial CSV/JSON/log evidence and excludes local MAT snapshots and the archive itself.
- Source admission counters close against all 285,000 scheduled attempts per source. Delivered latency uses unique first delivery. Model-pending status does not claim physical queue occupancy; native unresolved status does not claim known terminal loss or live pending.
- Fixed-age windows are half-open `[300,6000−T)` with integer-nanosecond eligibility and separate scheduled-attempt/admitted denominators. Each included generation has complete deadline follow-up. Different horizons are different cohorts.
- Zero native counts and missing delivered populations remain undefined relative comparisons. Common-source weighting is explicitly descriptive, and no aggregate parity claim is set true by case completion or selected passing metrics.
- Common NWK/post-admission phase reconstruction is deferred to the returned complete protocol trace, rather than introducing new simulation instrumentation or claiming a native retry-only decomposition that the original trace cannot support.

No additional confirmed MATLAB runtime blocker or accounting error was found in this inspection. The ordinary MATLAB table, manifest, receipt and JSON shape handling was reviewed statically; actual execution remains unverified until MATLAB runs the package's preflight and owner cases. A clean MATLAB session is documented, avoiding claims that path checks alone prove old class definitions have been unloaded.
