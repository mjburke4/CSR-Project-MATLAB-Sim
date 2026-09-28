# MAC scheduling history recheck — seed 132

This package repairs the validation wrapper error found in `out_mac_20260923_090933.zip`. It preserves all 99 accepted production-core files, every replay input, and all native reference bytes. The grouped-routing cancellation difference remains unfixed and is not hidden by this repair.

Extract this new ZIP to a short local folder such as `C:\csr\macfix`, start a fresh MATLAB session there, and run:

```matlab
report = run_mac_history_recheck;
```

Return the printed **`out_mh_....zip`**, even if a comparison fails. No Python, ns-3 build, or extra MATLAB toolbox is required. Keep the original kit separately; do not overlay this onto another candidate or bypass a binding check.

The command runs the focused cancellation-wrapper regression first, then the scheduling history for nodes 2, 4 and 8 through 665 seconds. The comparison interval remains 657–665 seconds, with the full preceding warmup. It skips the already accepted 694 reservation cases and 32 HOP-window cases. The original four-group `run_mac_batch` entrypoint is retained for optional use but is not needed for this recheck; its grouped-retry group is still expected to report the confirmed production difference.

## Why the replay stopped

A received cancellation bitmap can match no queued frame. MATLAB iterates a `for` loop by columns; the empty column returned by `unique` could therefore call production cancellation with an empty sequence. The wrapper now iterates `1:numel(sequences)` and passes a scalar selected sequence. Zero matches produce zero calls. Production cancellation, the MAC scheduler, receiver tape, queue selection and native reference values are unchanged.

## Current evidence

The original R2025a return passed all 694 reservation cases and 236 HOP-window checks across 32 cases. Both grouped-retry cases completed and confirmed that MATLAB removes the queued retry while native retains it. Before the wrapper exception, all 41 observed transmissions and 51 raw draws matched native exactly. No node reached the target comparison interval, so full MAC scheduling parity remains unresolved.

The repair has source/manifest checks and a new MATLAB regression. MATLAB has not been executed in the preparation environment; the repaired runtime result remains pending. Receiver availability is supplied as common input and the fixture uses native integer nanoseconds. Even a successful recheck does not establish autonomous receiver/MAC-loop or full-network ±10% parity.

`repair_provenance.json` records the parent kit and returned run identities. `RUN_FILES.json` binds the repaired runner and its exact inputs. `PACKAGE_FILES.json` binds the complete issued package. Optional developer verification: `python verify_bundle.py`.
