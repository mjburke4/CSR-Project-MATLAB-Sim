# Tranche 12 callback repair

Extract `t12fix.zip` directly into the same package folder used for the first Tranche 12 run (your working `csr11` folder), replacing matching files. Do not add a subfolder. This patch requires the Tranche 12 update already installed.

In MATLAB, make that folder current and run:

```matlab
clear functions
report = run_tranche12_validation;
```

Upload the new `t12.zip` whose location the runner prints, even if it reports differences. The run still contains 72 MATLAB tests, four 24-second relay/local cases and six clock cases; it does not run the 6,000-second campus benchmark. Results retain the short `results/t12/r...` path.

The first R2025a run passed 63/72 tests. All nine failures came from the relay fixture; one of those nine was also incomplete. All 52 retained tests and eight clock tests passed. All six clock cases passed their 72 checks; the continuous case retained the expected three-row/four-counter difference.

The relay fixture registered two callbacks before the network layer existed. MATLAB captured the incomplete cell array, so the first DATA receive raised `MATLAB:structRefFromNonStruct`. The repair uses nested functions to look up the completed NWK/HOP layer at invocation. Only `+csr/+validation/relayContract.m` changes among the MATLAB files. The validated 241-file baseline, including 130 MATLAB files, native references, scenario inputs, scheduler, PHY, radio settings and test expectations remain unchanged.

The revised fixture passed static parsing, independent source review and all 34 Python evidence-checker tests. Those are not MATLAB runtime results; a new owner run is required before accepting relay completion or interpreting its parity measurements.

The first return and its original candidate are preserved in `evidence/t12r/owner.zip` and `base.json`. The original preparation reviews in `evidence/tranche-12-gate` refer to that first candidate. Current repair findings are in `evidence/t12r`, and the updated candidate and package manifest identify this revision.
