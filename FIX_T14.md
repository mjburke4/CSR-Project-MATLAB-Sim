# Tranche 14 repair r2: stable observation tables

The second R2025a return again passed all 88 retained tests. All 18 Tranche 14 tests failed during class setup because the diagnostic could not concatenate its case-name columns. The archive contains no per-case observations, so reaching the second console label does not establish that the first case passed. The zero difference count was an unpopulated result, not a parity measurement.

The previous repair corrected ACK application-field logging but missed this table-conversion problem. The new repair makes every text field a single string value per row across events, boundaries, checks, contention draws, usage and scheduler records. It preserves numeric, logical and uint64 column types, including zero-row and one-row tables. Reference text is explicitly imported as strings, preserving complete hexadecimal timestamps during indexing and comparison. The earlier ACK correction remains included.

Three independent MATLAB tests exercise differing case-name lengths, fixed-width hexadecimal timestamps, empty/single/multiple records, actual scheduler and replay-stream outputs, and exact uint64 CSV export. The runner executes these first. If they fail, it stops early and packages the failure. The remaining 106 tests and six four-second cases follow when that preflight passes, for 109 tests total. The structural contract remains 222 checks.

Each attempted case now saves its six CSV tables and result record under short folders `edge/c1` through `edge/c6` before cross-case concatenation. An incomplete diagnostic prints that no parity conclusion is available instead of displaying a misleading zero-difference result.

Extract `t14fix2.zip` directly into the same package folder you just used, replacing matching files. This cumulative update includes both repairs and requires no file deletions. Make that folder current in MATLAB and run:

```matlab
clear functions
report = run_tranche14_validation;
```

Upload the newly generated `t14.zip`, including if the run stops early. Results remain under the short `results/t14` run folders.

All 271 validated Tranche 13 source files, including all 138 MATLAB files, remain unchanged. The repair affects only new diagnostic/export/test code and its runner; production MAC/HOP/NWK behavior, EventScheduler, ReplayStreams, PHY/ECC, shared inputs, native references and timing arithmetic are unchanged. Source review and static checks are preparation only: the repaired MATLAB runtime and Tranche 14 acceptance remain pending.

MathWorks documents that `struct2table` infers homogeneous arrays when field sizes are compatible, and cell arrays otherwise; this explains why changing case-name width exposed the failure. Explicit string columns remove that inference from these observation tables. See [struct2table documentation](https://www.mathworks.com/help/matlab/ref/struct2table.html). Converting each character row to a string preserves one whole text value, including an empty callback string; see [string conversion documentation](https://www.mathworks.com/help/matlab/ref/string.html).
