# Terminal candidate: full 6,000-second parity measurement

This batch measures the exact candidate that completed the seed-131 0–200-second and seed-132 0–400-second common-input tests in your latest MATLAB return. It runs **seeds 131 and 132 to 6,000 seconds each** and compares them with the original ns-3 references. The agreed target remains **±15% per-source delivered count and delivered-only mean latency**.

## Run

1. Extract the ZIP into a fresh folder with a short local path.
2. Restart MATLAB and set Current Folder to **`csr6000`**.
3. Run:

```matlab
report = run_6000_batch;
```

Return the printed **`out_6000_terminal_*.zip`**, even if a case fails. Both seeds run automatically; a failure in one case does not prevent the other from being attempted. Allow several hours and keep the computer awake. No ns-3 installation, Python, or Parallel Computing Toolbox is required. MATLAB R2025a or later with Java is required.

## Exact scope

The model and all `+ac` files are byte-identical to the validated v2 short-test kit. The selected class is `ac.TerminalSimulation`, including retained DATA copies, late-delivery/custody accounting, and the receiver signal ordering correction. No production model behavior or default policy is changed for this batch. The imported baseline is checked, then only `Hop.DataQueuedRetryPolicy` is selected as `native-provisional` before diagnostic capture settings are applied.

These full runs use **natural MATLAB random streams**, autonomous discovery, admission, and radio interaction. Equal numeric seeds do not pair random draws or admitted application identities across MATLAB and ns-3. No native random tape, receiver state, feedback, routes, transmission schedule, or post-stop drain is supplied. Successful short common-input tests do not establish the outcome of this natural full-run measurement.

The already completed short tests are included as source-bound evidence and are not rerun. The reporting helper checks synthetic outcomes, provisional-drop interpretation, native duplicate deliveries, source weighting, and observation boundaries before either expensive simulation.

## Measurement and unfinished traffic

For every source and seed, the return includes scheduled attempts, admissions and blocked-admission categories, unique deliveries, raw model dropped/pending counts, and all admitted-but-undelivered applications at the 6,000-second cutoff. Complete per-source counters cover all **285,000 scheduled attempts per source**; the individual admission trace is only a bounded 100,000-row prefix, and omitted observations are counted explicitly.

**A raw dropped count is a provisional recorded custody loss.** Retained copies can still deliver or establish later relay custody. Therefore the reporting layer classifies all admitted-but-undelivered applications as unresolved at cutoff, preserves raw dropped/pending labels separately, and does not infer final loss or the number of live queued copies. Unfinished ages are not delivery latencies. The original raw research exporter retains its legacy `DataDrained` field, which checks owner state and is not a complete retained-copy drain proof; use the companion `cutoff_semantics.json` and revised application accounting for this candidate.

The comparison retains all six sources per seed. Native zero-delivery source cells have undefined relative percentages and remain explicitly listed. Native-source-weighted latency uses common delivered source populations with all excluded traffic reported; it is a descriptive aggregate, not a replacement for the per-source target. Fixed-age delivery at 60, 300, 600, and 1,200 seconds uses equal eligible generation windows and both attempted/admitted denominators.

Complete protocol and PHY traces support the returned NWK-waiting versus subsequent MAC/HOP-service decomposition. Omissions in these required traces invalidate completed-case acceptance. The high-volume ordered event recorder stays closed. Existing random-request logging remains enabled. Transport timing capacity is 1,500,000 records; the existing relative-timer diagnostic prefix is bounded at 200,000. Passive service windows remain seed 131 at 0–200 seconds and seed 132 at 600–675 seconds, with explicit supplementary diagnostic omissions. Observation limits do not suppress model execution or redefine the admitted/delivered populations.

## Restart and interpretation

Keep the extracted folder and its output. Running the same command again reuses completed cases only after source, input, plan, runtime, and export hashes match. An interrupted simulation restarts from time zero in a new attempt folder while preserving its earlier files. Local MAT results are retained but excluded from the return ZIP.

`completed` means both simulations and required exports finished. Numerical target results are separate, and batch-level grading is withheld unless both cases complete. Neither two seeds nor a matching pooled mean proves general statistical equivalence. Full-run MATLAB execution and the ±15% outcome are pending your return.
