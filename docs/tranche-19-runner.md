# Tranche 19 owner run

T19 tests whether expiring DATA retries while they remain queued changes capacity release and application admission across the original campus network. The default remains `actual-tx`. The experimental `native-provisional` policy is applied only to the second case; PHY/ECC, continuous timing, original traffic and routing settings are retained. The experimental policy adopts native-inspired queued DATA timeout timing and unmatched-sent fallback scanning. MATLAB terminal cancellation and transactional overload handling remain accepted differences, so this policy does not establish full native retry equivalence.

Copy your accepted, repaired T18 installation to a short local folder such as `C:\csr19`, then overlay the T19 update. The frozen candidate permits changes to only the two declared HOP source files among the 346 accepted T18 source bindings. New tests, runner and analysis files are included. Run from the copied installation:

```matlab
clear functions
report = run_tranche19_validation;
```

Upload `results/t19/t19.zip`. It contains the exact candidate, plan, source/reference inventories, runtime, test results and both cases' raw and derived evidence. The runner retains MAT snapshots locally; those and nested archives are omitted from the return. MATLAB execution and the two long cases remain pending until this command runs on your machine.

The runner executes the full top-level portable test suite, then fresh `a128` and `p128` cases. Each case uses all seven original campus nodes and six flows for 6,000 simulated seconds with seed 128. `a128` uses the default `actual-tx` DATA retry behavior, and `p128` uses `native-provisional`. The reference comparison reuses the pinned native campus evidence because upstream source and input hashes are unchanged. It does not rerun ns-3. Allow roughly twice the time of the earlier full campus gate, plus tests and evidence export; wall time depends on your machine and the changed policy's event load. No observers or progress callbacks are scheduled, so a long simulation may be silent until it returns.

To run stages separately, use the same output directory:

```matlab
out = fullfile(pwd,'results','t19');
report = run_tranche19_validation(out,struct('Phase','tests'));
report = run_tranche19_validation(out,struct('Phase','a128'));
report = run_tranche19_validation(out,struct('Phase','p128'));
report = run_tranche19_validation(out,struct('Phase','finalize'));
```

`all` or any stage command reuses an already completed stage only after verifying its candidate, source, references, MATLAB runtime, receipt and exact evidence bytes. The full gate is complete once all three stages have passed; `finalize` explicitly checks that all three are present. An incomplete stage is never resumed or overwritten. Failed or interrupted attempts remain available for diagnosis, with failure metadata and a ZIP when packaging is possible.

If a later case was interrupted, you can preserve completed stages in a new output directory after the previous MATLAB run has stopped. The example below copies the complete root identity and only stages that have a completed receipt. It leaves the original attempt intact and omits partial stages and the stale active-run lock:

```matlab
old = fullfile(pwd,'results','t19');
fresh = fullfile(pwd,'results','t19_retry');
assert(~isfolder(fresh),'Choose an unused output folder.');
mkdir(fresh);
for name = {'source.json','references.json','candidate.json','plan.json','metadata.json'}
    copyfile(fullfile(old,name{1}),fullfile(fresh,name{1}));
end
for phase = {'tests','a128','p128'}
    if isfile(fullfile(old,phase{1},'receipt.json'))
        copyfile(fullfile(old,phase{1}),fullfile(fresh,phase{1}));
    end
end
report = run_tranche19_validation(fresh);
```

Every copied completed stage is verified again before any new simulation starts. A changed MATLAB release, altered source/reference, damaged receipt or changed artifact prevents reuse; retain the previous attempt and run in a completely new output directory instead. An unrelated nonempty output directory is rejected before log or metadata writes.

T19 retains complete protocol and PHY traces and complete total/per-flow admission counters. The original first 100,000 admission-attempt records remain a prefix of 1,710,000 attempts, with the omitted count explicitly recorded. All admitted application identities and outcome events remain available in the protocol trace. The return review reconstructs HOP ownership and NWK custody from existing events; it does not claim continuous hidden-queue measurements.

Return review compares the default case with the accepted T17 full-campus evidence, both cases with pinned ns-3, and the two MATLAB policies with each other. Whole-run and 300-second delivery/admission comparisons use a descriptive ±5% band; falling outside it is not a structural failure. Existing benchmark exports retain 60-second buckets. Finite-stop pending work is reported without a post-stop drain. A single-seed intervention may change subsequent event order and random-number consumption; it cannot establish performance across seeds or identical packet-level random conditions. Selecting a new default would require review of these results and a useful effect that merits further seed confirmation.
