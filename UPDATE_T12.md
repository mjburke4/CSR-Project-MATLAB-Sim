# Small Tranche 12 update

**Existing Tranche 12 installation:** apply `t12fix.zip` in place and follow `FIX_T12.md`. The instructions below describe the original Tranche 11-to-12 installation; its relay fixture requires the r1 repair.

`t12up.zip` is a small update for the repaired Tranche 11 package that produced the successful 52-test return. Extract it directly into that existing package folder and replace the matching files. Do not create an extra subfolder. It adds Tranche 12 and its references while retaining every earlier source file.

For a fresh installation, extract the complete `csr12.zip` into a short folder such as `C:\CSR\csr12` instead. In MATLAB make the chosen package folder current and run:

```matlab
report = run_tranche12_validation;
```

Upload the new `t12.zip` whose path MATLAB prints. See `START_T12.md` for the four 24-second relay/local cases, six clock cases and 72 MATLAB tests. The continuous clock control is expected to retain a recorded difference; upload complete evidence regardless of numerical differences. The first Tranche 12 run found a relay fixture construction error; execution of the repaired candidate is pending.
