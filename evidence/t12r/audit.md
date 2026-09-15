# Tranche 12 returned-run independent audit

The returned run is **not accepted**: all four relay cases stopped in the diagnostic NSDP callback. The clock diagnostic is valid and passed. This review changes no simulator, candidate, or reference files.

Owner archive SHA256: `3a6033f609c24a1cf8a2b5c4183402d8b7b9937e7528104ebb7e81f3b9ea5bd9`.

The return binds exactly to the delivered candidate. All 13 archived artifacts, 259 source entries and 130 reference entries verify. Pre-run and post-run snapshots match. The 241-file Tranche 11 baseline, including all 130 MATLAB files, and the 225-file/124-MATLAB-file core baseline are unchanged. Native reference manifests close over 41 relay and five clock artifacts.

MATLAB R2025a (25.1.0.2943329) ran all 72 selected tests: **63 passed, nine failed**. One failed test is also marked incomplete; it is included in the nine. All 52 retained tests and all eight new clock tests passed. The relay class passed three of 12 tests.

| Clock case | Arrival relative to tick | Native result |
| --- | --- | --- |
| tie_early | Exact tie; earlier insertion | Exact |
| tie_late | Exact tie; later insertion | Exact |
| before | One ns before | Exact |
| after | One ns after | Exact |
| continuous | One binary64 ULP after (4.440892098500626e-16 s) | Expected counter residual |
| quantized | Exact tie using test transport quantization | Exact |

All 72 clock checks pass. The continuous control differs from native in three observation rows and four counter fields; all time_ns, queue and transmission fields match. The five shared integer-time cases match exactly. The production global scheduler is unchanged.

All four relay cases report `MATLAB:structRefFromNonStruct` at `relayContract.m` line 103, in `@(a)networks{node}.nsdpCount(a)`. They stop before first application delivery. The 244 observations and ten draws are partial failure traces. The reported 2,649 comparison differences must not be interpreted as delivery performance or accepted parity data.

Repair the diagnostic callback and repeat the bounded T12 run. No complete-tranche acceptance or numerical-parity claim follows from this failed run.
