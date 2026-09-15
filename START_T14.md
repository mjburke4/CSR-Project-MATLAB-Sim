# Tranche 14: DATA arrival at an ACK opportunity

This diagnostic investigates the first service-changing event boundary found in the successful Tranche 13 return. It uses the real receiver MAC/HOP/NWK processing and a reconstructed mixed ACK/DATA aggregate to determine which cumulative ACK is actually transmitted. It records full-precision event times and insertion order.

This is the corrected Tranche 14 candidate. For the installation where you just ran Tranche 14, extract `t14fix2.zip` directly into that package folder, replacing matching files. Do not create an extra nested folder. See `FIX_T14.md` for the table-conversion and logger corrections and the failed-run reviews.

Make that package folder current in MATLAB and run:

```matlab
clear functions
report = run_tranche14_validation;
```

Upload the new `t14.zip` at the path printed by the runner, including if the run reports a failure or numerical differences. Results use short folders under `results/t14`. The runner preserves completed results and attempts to package partial failures.

The six boundary cases each run for four simulated seconds. They exercise arrival just before the ACK opportunity, exactly at it with earlier or later insertion, just after it, using continuous airtime arithmetic, and using nanosecond transport timing in one separate comparison case. The production scheduler and PHY/ECC remain unchanged. The reconstructed sender input is not a sender-admission or custody experiment.

The selected suite runs 109 MATLAB tests: three independent record-table tests first, all 88 Tranche 13 tests, and 18 boundary tests. The first three tests run before the simulation cases and stop the run early if the table conversion fails. The primary diagnostic has 222 structural checks across six cases. It does not run the 6,000-second campus benchmark. Your prior 88-test portion took about 91 seconds on R2025a; the new total runtime remains unmeasured until this run.

All 271 source files captured in the successful Tranche 13 return, including 138 MATLAB files, remain unchanged. Earlier tranche runners are retained. This package is a diagnostic candidate: its new MATLAB runtime results must be reviewed from your returned archive before a focused pass is established.

See `docs/tranche-14-spec.md` for the exact shared inputs and evidence contract, and `UPDATE_T14.md` for preparation results and scope.
