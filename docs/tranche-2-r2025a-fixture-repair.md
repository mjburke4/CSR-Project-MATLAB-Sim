# Tranche 2 R2025a result and fixture repair

**Historical failure and repair record.** The subsequent owner rerun passed
145/145 tests and all nine scenario summaries. Portable acceptance is recorded
in [Tranche 2 acceptance](tranche-2-portable-acceptance.md).

The owner ran `run_tranche2_validation` on MATLAB R2025a
`25.1.0.2943329`, using the portable backend without wireless simulator symbols.
The supplied console transcript and `test_results.csv` agree:

| Outcome | Observed result |
|---|---|
| Portable suite | 145 methods: **121 passed, 24 failed, 18 incomplete** |
| Test duration | 28.7179 seconds reported by MATLAB |
| MAC/HOP integrated scenarios | **12/12 passed** |
| Integrated custody regressions | **3/3 passed** |
| PHY/MAC state bridge | **9/9 passed** |
| HOP modeled frame layouts | **11/11 passed** |
| Original T0/T1 methods | **72/72 passed** in this run |
| HOP unit methods | 7 passed, 13 failed |
| MAC unit methods | 7 passed, 11 failed |
| Separate nine-scenario export | Not reached: the suite's `assertSuccess` stopped execution |

The 18 incomplete methods are a subset of the 24 failed methods. This is useful
integrated runtime evidence, but the whole Tranche 2 acceptance gate remains
open at this initial checkpoint. No native R2026a or full-network ns-3 numerical parity is implied.

## Diagnosis and correction

The fixture callbacks appended to shared nested-function logs. Their anonymous
observers, such as `@() frames` and `@() transmissions`, retained values from
fixture creation, so tests read empty arrays after the protocol had operated.
The HOP NSDP/route readers and MAC SYNC reader similarly retained their initial
values despite later changes in the fixture.

Both fixtures now use named nested getters. These read the same shared state
that their callbacks and setters update. HOP observation getters, NSDP and
route availability are repaired; MAC transmission observation and SYNC are
repaired. Existing protocol/timing assertions remain in place, with two added
frame-count assertions in the existing HOP retry test. There are still 145
portable test methods. No CSR protocol, PHY or scenario implementation changed.

This follows MATLAB's documented [anonymous function capture](https://www.mathworks.com/help/matlab/matlab_prog/anonymous-functions.html)
and [nested function shared variables](https://www.mathworks.com/help/matlab/matlab_prog/nested-functions.html).
Production callbacks were audited for the same pattern: mutable state is read
through handle objects; immutable event arguments are intentionally captured.

## Evidence and limits

The associated implementation candidate is local commit
`ad5704094e14c8182d1c3f6c2f15c6313705cf2f`, inferred from the issued package,
test names/count and owner path. The runtime did not report a source hash, so
this revision association is not independently certified. The original
test-results CSV is preserved byte-for-byte at
`evidence/tranche-2-r2025a-initial-test-results.csv`; a structured summary and
hashes of both supplied inputs are in `evidence/tranche-2-r2025a-initial-run.json`.

The repaired files passed static review and lint before handoff. MATLAB had
not rerun the repair at that checkpoint; the later owner run is now accepted.
No MATLAB execution occurred in this workspace. The previous 17/17
ns-3 workflow results remain reference-side evidence; they were not rerun for
this test-fixture-only correction.

Extract the revised full package into a fresh folder and rerun:

```matlab
run_tranche2_validation
```

Return the console output and `results/tranche2_validation/tests/test_results.csv`.
If the suite passes, also retain `results/tranche2_validation/scenario_summary.csv`
and the per-scenario exports. Any remaining failure will be assessed from the
new live observations rather than bypassed or reclassified as passing.
