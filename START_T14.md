# Tranche 14: DATA arrival at an ACK opportunity

This diagnostic investigates the first service-changing event boundary found in the successful Tranche 13 return. It uses the real receiver MAC/HOP/NWK processing and a reconstructed mixed ACK/DATA aggregate to determine which cumulative ACK is actually transmitted. It records full-precision event times and insertion order.

For the existing installation used for your successful fresh Tranche 13 run, extract `t14up.zip` directly into that package folder, replacing matching files. Do not create an extra nested folder. For a separate complete installation, extract `csr14.zip` into a short directory such as `C:\CSR\csr14`.

Make that package folder current in MATLAB and run:

```matlab
clear functions
report = run_tranche14_validation;
```

Upload the new `t14.zip` at the path printed by the runner, including if the run reports a failure or numerical differences. Results use short folders under `results/t14`. The runner preserves completed results and attempts to package partial failures.

The six boundary cases each run for four simulated seconds. They exercise arrival just before the ACK opportunity, exactly at it with earlier or later insertion, just after it, using continuous airtime arithmetic, and using nanosecond transport timing in one separate comparison case. The production scheduler and PHY/ECC remain unchanged. The reconstructed sender input is not a sender-admission or custody experiment.

The selected suite runs 106 MATLAB tests: all 88 Tranche 13 tests, including its controlled-loss/recovery cases, plus 18 new boundary tests. The primary diagnostic has 222 structural checks across six cases. It does not run the 6,000-second campus benchmark. Your prior 88-test portion took about 91 seconds on R2025a; the new total runtime remains unmeasured until this run.

All 271 source files captured in the successful Tranche 13 return, including 138 MATLAB files, remain unchanged. Earlier tranche runners are retained. This package is a diagnostic candidate: its new MATLAB runtime results must be reviewed from your returned archive before a focused pass is established.

See `docs/tranche-14-spec.md` for the exact shared inputs and evidence contract, and `UPDATE_T14.md` for preparation results and scope.
