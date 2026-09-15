# Tranche 12 return review and callback repair

The first R2025a return is valid evidence of a relay-fixture error. Tranche 12 structural acceptance is pending a rerun. Its clock component completed successfully and can be interpreted independently.

| Check | Verified result |
| --- | --- |
| Runtime | MATLAB R2025a, 25.1.0.2943329, portable backend |
| Archive integrity | 13 artifact hashes; closed 14-member ZIP |
| Source and references | 259 source and 130 reference bindings match the delivered package; unchanged during execution |
| Validated baseline | All 241 source files, including 130 MATLAB files, unchanged |
| MATLAB tests | 63/72 passed; nine relay failures, one of those also incomplete |
| Retained tests | 52/52 passed |
| Clock tests and checks | 8/8 tests; 72/72 checks across six cases |
| Relay execution | All four cases aborted on their first DATA reception |

The NSDP-count callback in `+csr/+validation/relayContract.m` captured the network-layer cell before that layer was assigned. The route-availability callback had the same latent error. The reported 2,649 relay differences compare incomplete traces with completed native runs; they are not a valid measure of service parity or delivery performance.

The repair replaces those captures with nested callbacks that resolve the current network layer when invoked. The HOP capacity query uses the same pattern. Only this one MATLAB file changes; the existing tests, production protocol code, scheduler, PHY, scenario inputs and native references remain unchanged. The repair passed independent source review, MATLAB static parsing and 34/34 Python evidence-checker tests. Repaired MATLAB runtime execution has not yet occurred.

Five clock cases match native exactly. The continuous case arrives one binary64 step later than the anchored tick (4.440892098500626e-16 seconds), producing the expected three differing rows and four counter fields. The separately quantized transport case matches. No global clock change or full-network parity conclusion follows from this diagnostic.

Apply `t12fix.zip` directly over the folder used for the first Tranche 12 run, replacing matching files. In MATLAB run:

```matlab
clear functions
report = run_tranche12_validation;
```

Upload the newly printed `t12.zip`, including any reported differences. The same 72 tests, four 24-second relay cases and six clock cases remain selected. No 6,000-second campus rerun is required for this repair. The next engineering decision is to inspect completed relay delivery, ACK/DACK service and capacity release against the existing native reference.

The original return and candidate are preserved in `evidence/t12r`; the current candidate and `PACKAGE.json` record the repair. Earlier preparation reviews remain historical records of the first candidate.

Provenance:

- Original owner return SHA256: `3a6033f609c24a1cf8a2b5c4183402d8b7b9937e7528104ebb7e81f3b9ea5bd9`
- Original candidate SHA256: `65a6fe4edd6d925ec596fad6c0ec257be483d623616aa7f41bbd9805a6548703`
- Repaired candidate SHA256: `ebf493fc8d34dc7c7819f14e266bf19b99f0f94441a79da38a801cd7f52292c4`
- Repaired fixture SHA256: `b33136349b7ae851927a802461551a5b8fcecb1456a4b42d2467fe0d978aee1e`

No remote repository publication or MATLAB execution was performed during this review.
