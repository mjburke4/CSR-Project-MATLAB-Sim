# Tranche 14 candidate handoff

**Repair r2:** The second R2025a run passed all 88 retained tests but failed while concatenating case-name columns. The earlier ACK logging correction remains included. Text columns now have explicit string types, and three independent table tests run before the diagnostic. Per-case evidence is saved before concatenation. See `FIX_T14.md`; the corrected MATLAB runtime remains pending.

The successful fresh Tranche 13 run delivered all 384 application identities and completed all 576 successful custody terminals. Its DATA-loss case still differed in service timing: MATLAB sent an older cumulative ACK at the first affected boundary, with four additional feedback transmissions and a maximum application delivery delay of 408.760 ms relative to the pinned native reference. Tranche 14 isolates that boundary before selecting a production timing change.

The new MATLAB diagnostic and matching native fixture use actual MAC selection, receiver HOP updates and gateway NWK delivery. Six cases place a real mixed ACK/DATA envelope before, at or after the 3.144961-second ACK opportunity, including both equal-time insertion orders. Separate cases preserve continuous transport arithmetic or convert transport times to integer nanoseconds locally. Full-precision decimal and hexadecimal timestamps preserve differences hidden by nanosecond-rounded logs; scheduler records identify actual insertion and execution order.

Native execution completed all six cases, with 222 protocol checks and all 18 prescribed application identities delivered. DATA arriving first produces ACK sequence 3/bitmap 7 immediately. Service occurring first produces the older sequence 2/bitmap 3, followed by the updated feedback. The two late cases produce six gateway ACK transmissions; the four other native cases produce five. All final MAC DATA and ACK queues drain. An additional 14 native self-tests pass, and 327 retained checkpoints match byte-for-byte between clean source and a build with the diagnostic seam disabled. The native check inventory and MATLAB check inventory are independently defined; their equal counts do not assert identical checkpoint rows.

MATLAB execution remains pending. The owner command selects 109 MATLAB tests: three independent table-conversion tests, 18 boundary/observer/export tests and all 88 retained Tranche 13 tests. Its six primary cases each run for four simulated seconds and produce 222 structural checks. Static parsing is preparation evidence only. Python code audits returned files, source and reference bindings, exact timestamps, scheduler causality and protocol observations; it does not execute or replace the MATLAB simulation tests.

The package preserves all 271 source bindings from the successful Tranche 13 return, including all 138 MATLAB files. Six MATLAB files make up the new diagnostic: its fixture, scheduler observer, typed table helper, two test classes and runner. The observer delegates to the existing scheduler without changing its times, priorities or event queue. Production MAC, HOP, NWK, PHY/ECC and global clock behavior remain unchanged.

The native source was inspected for this tranche at CSR commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, with ns-3 engine `6b5cd24ea80713ce16d88575869aedd6f432bdae`. Native dependencies were rebuilt from fresh checkouts. Build provenance records the fresh outputs; it does not assert that they are byte-identical to the older native build. Candidate, input, reference, preparation and package inventories bind the delivered files.

For the installation where you just ran Tranche 14, overlay `t14fix2.zip` directly into that package folder and replace matching files. Earlier runners remain available. The repair requires no file deletions.

```matlab
clear functions
report = run_tranche14_validation;
```

Upload the new `t14.zip` printed by the runner, even if it reports a failure or comparison differences. Results use `results/t14/rYYMMDD_HHmmss_xxxx`. Your prior 88-test portion took approximately 91 seconds; total Tranche 14 wall time is not yet measured.

This is a receiver ACK-service diagnostic with prescribed transport and reconstructed sender input. It does not seed sender DATA custody, test source admission improvement, run the campus benchmark, execute OPNET, or establish full-network/numerical parity. Exact full-precision differences remain visible even when structural checks pass. The next decision is to review the owner trace, establish whether the suspected one-ULP boundary actually changes ACK service, and only then choose and validate any production transport change against the controlled-loss benchmark.
