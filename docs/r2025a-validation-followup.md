# R2025a validation follow-up

## Successful corrected run: Tranche 0 accepted

The owner subsequently reran `run_validation` on MATLAB 25.1.0.2943329
(R2025a): **24 passed, 0 failed, 0 incomplete**, with 1.3764 seconds of test
suite time. The final controlled scenario reported 6 generated/transmitted/
received packets, 0 dropped/pending, 384 received application bytes, delivery
ratio 1, mean latency displayed as 1.1138 s, goodput 307.2 bit/s, and no omitted
trace records. The entry point printed its successful completion message
after the export stage.

Tranche 0's portable R2025a acceptance gate is closed on this owner-reported
execution evidence. This does not establish R2026a support, native wireless
integration or full CSR PHY/MAC/HOP/routing parity. Raw exported files and
runtime source hashes have not been independently inspected.
See `../evidence/matlab-r2025a-acceptance.json`.

## Earlier failed run and correction

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

The correction passed static lint before the successful rerun above. The
`assertSuccess` gate correctly stopped the earlier failed run before the
final scenario/export stage; the integrated scenarios inside the tests did
execute successfully in that earlier run.

The capability probe found no `wirelessNetworkSimulator` symbol on the tested
MATLAB path. The portable foundation does not require it. This result does
not determine installation or license status, and no native integration is
claimed. R2026a execution remains pending.
