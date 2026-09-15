# Tranche 14 logger repair

Your R2025a return ran all 106 selected tests: 97 passed and 9 failed, with two of the failed tests also marked incomplete. All 88 retained tests passed. Every boundary case stopped at the first source MAC transmission because the new diagnostic logger tried to read `frame.App.SourceId` from an ACK. ACK frames contain an empty `App` structure and have no application identity. This was a defect in the new diagnostic.

The interrupted cases did not reach the gateway ACK opportunity. The reported 406 comparison differences reflect missing observations and incomplete runs; they cannot establish an ns-3 parity discrepancy.

The repair reads application identity only for DATA observations. ACK observations retain source/application identity zero, while preserving their actual HOP sender, receiver, sequence and bitmaps. The existing aggregate regression test now checks the real ACK constructor's empty application structure and the identities exported for ACK and DATA. Two delivery/queue tests also require all six cases before checking their rows, so an empty diagnostic cannot pass those tests. The selected suite remains 106 tests, including all 88 retained tests, and six four-second boundary cases with 222 structural checks.

All 271 validated Tranche 13 source files, including 138 MATLAB files, remain unchanged. Only the two new Tranche 14 MATLAB files containing the diagnostic and its tests are repaired. The production MAC/HOP/NWK code, scheduler, timing arithmetic, PHY/ECC, shared input plan, prescribed draws and native references remain unchanged.

Extract `t14fix.zip` directly into the same package folder where you just ran Tranche 14, replacing matching files. Make the package folder current in MATLAB and run:

```matlab
clear functions
report = run_tranche14_validation;
```

Upload the newly generated `t14.zip` from the printed path, including if any test fails. The runner uses a new short result folder. The failed archive and original candidate/source bindings are preserved in the repair provenance.

The corrected MATLAB code has been reviewed and statically checked; its runtime result remains pending. This repair does not establish Tranche 14 acceptance or numerical parity. The next required evidence is a completed owner run showing the actual DATA ingress and ACK transmissions.
