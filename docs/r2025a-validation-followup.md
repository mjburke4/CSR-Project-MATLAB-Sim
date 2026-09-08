# R2025a validation follow-up

The owner ran `run_validation` on MATLAB 25.1.0.2943329 (R2025a) and reported
20 passes, four failures, and zero incomplete tests. All eight integrated
foundation, five PHY/timing, and five RNG tests passed. The two remaining
scheduler tests also passed.

All five failed assertions across four scheduler tests compare `PendingCount`:
the numerical counts agree, but `containers.Map.Count` returns `uint64` and
the assertions expect `double`. Normalize the public count getter:

```matlab
count = double(obj.Active.Count);
```

This keeps event IDs and internal map keys as `uint64`. It changes no event
ordering, cancellation, pending-work ownership, or test expectations. An
independent review checked every consumer; the only non-test consumer is
`Metadata.PendingEvents`. Existing tests exercise this correction directly.

The corrected candidate passed static lint, but has not yet run in MATLAB.
Rerun `run_validation` from the repository root. Its `assertSuccess` gate
correctly stopped the reported run before the final scenario/export stage;
the integrated scenarios inside the tests did execute successfully.

The capability probe found no `wirelessNetworkSimulator` symbol on the tested
MATLAB path. The portable foundation does not require it. This result does
not determine installation or license status, and no native integration is
claimed. R2026a execution remains pending.
