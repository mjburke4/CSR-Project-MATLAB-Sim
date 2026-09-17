# Tranche 20 owner run

T20 compares the unchanged `actual-tx` default over three full-campus seeds. Seed 128 is reused from the accepted T19 `a128` evidence; only seed 129 and seed 130 are newly simulated. The experimental T19 `p128` case is excluded. All 358 accepted T19 source bindings, including all 170 MATLAB files, remain unchanged. New runner, contract and review files are added.

Copy your accepted T19 installation into a short local folder such as `C:\csr20`, then overlay the T20 update. Run from that folder in the exact accepted MATLAB R2025a build `25.1.0.2943329`:

```matlab
clear functions
report = run_tranche20_validation;
```

Upload `results/t20/t20.zip`. Full portable regression runs first, followed by the two fresh 6000-second cases. Budget several hours; the prior default case took about 58 minutes, and new seeds may differ. MATLAB runtime validation remains pending until you execute the runner. Each run retains the original seven campus nodes, six flows, PHY/ECC, routing, timing, trace budgets and original CSV. Only `Config.Seed` changes after import; native references record their separately derived seed-only CSVs honestly. Original Benchmark metadata remains unchanged.

The runner requires exactly the parent runtime capabilities record, including release/build, before execution; changing MATLAB versions would confound this seed-only comparison. A different release requires a separately designed comparison rather than a fresh output folder. No observers or progress callbacks are scheduled, so simulations may be silent for a substantial period.

To run stages separately, use the same output directory:

```matlab
out = fullfile(pwd,'results','t20');
report = run_tranche20_validation(out,struct('Phase','tests'));
report = run_tranche20_validation(out,struct('Phase','s129'));
report = run_tranche20_validation(out,struct('Phase','s130'));
report = run_tranche20_validation(out,struct('Phase','finalize'));
```

`all` or any stage command reuses an already completed stage only after verifying its candidate, source, references, MATLAB runtime, receipt and exact evidence bytes. The full gate is complete once all three stages have passed; `finalize` explicitly checks that all three are present. An incomplete stage is never resumed or overwritten. Failed or interrupted attempts remain available for diagnosis, with failure metadata and a ZIP when packaging is possible.

If a later case was interrupted, you can preserve completed stages in a new output directory after the previous MATLAB run has stopped. The example below copies the complete root identity and only stages that have a completed receipt. It leaves the original attempt intact and omits partial stages and the stale active-run lock:

```matlab
old = fullfile(pwd,'results','t20');
fresh = fullfile(pwd,'results','t20_retry');
assert(~isfolder(fresh),'Choose an unused output folder.');
mkdir(fresh);
for name = {'source.json','references.json','candidate.json','plan.json','metadata.json'}
    copyfile(fullfile(old,name{1}),fullfile(fresh,name{1}));
end
for phase = {'tests','s129','s130'}
    if isfile(fullfile(old,phase{1},'receipt.json'))
        copyfile(fullfile(old,phase{1}),fullfile(fresh,phase{1}));
    end
end
report = run_tranche20_validation(fresh);
```

Every copied completed stage is verified again before any new simulation starts. An altered source/reference, damaged receipt or changed artifact prevents reuse; retain the previous attempt. Use a completely new output directory only with an intact frozen installation and the required parent runtime. An unrelated nonempty output directory is rejected before log or metadata writes.

Complete protocol and PHY traces and admitted-application identities are retained, with complete admission/blocked counters. The original first 100000 admission attempts remain a prefix of 1710000 attempts per run. MAT snapshots stay local and are omitted from the return archive.

Return review authenticates reused `a128` with its original T19 source and runtime identity, then compares every MATLAB seed with its corresponding pinned ns-3 reference. It reports each seed, every flow, mean/range, mean per-seed residuals and pooled ratios separately. The ±5% target is descriptive; it is not a structural pass/fail test or evidence of statistical equivalence. Three seeds are an initial variability screen, not a confidence-interval claim. Matching seed numbers do not imply common random numbers between engines. Archived OPNET aggregate data remains contextual only.
