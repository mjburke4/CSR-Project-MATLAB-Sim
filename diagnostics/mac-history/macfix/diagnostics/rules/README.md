# Historical MAC slot rule vectors

The batch invokes `run_slot_vectors(root,outputDir)` after putting this directory and the unchanged core on the MATLAB path. The saved oracle was produced by the native `CsrMacCore::PickTxSlot`, `GetActiveNodesForSlotting`, and `GetOpnetSlotRange` methods, with the campus profile `hist-2014-next-tslot-modulo-probe`.

There are **694 comparisons**:

- **544 selections:** each initial integer draw 0–31 against 17 neighbor-counter sets. Sets cover empty and expired reservations, counters outside the range, slot zero, slot 31, modulo wrap, consecutive collisions, duplicate counters, near-full occupancy, and counters observed around the failed packet.
- **6 exhaustion boundaries:** initial draws 0, 30, and 31 with either slots 0–30 occupied or slots 0–31 occupied. Five execute the native exhaustion abort. The sixth demonstrates that slot 31 is selectable when initially free, even with the complete modulo ring occupied.
- **144 range comparisons:** local active-node counts across the coarse-range boundaries, contrasting reported counts, and supervisor reductions around the strict `range - reduction > 1` guard.

The native fixture has completed all 694 cases with no unexpected result. MATLAB comparisons are pending execution; the native fixture result alone is not a MATLAB parity pass.

## Production-code binding

`build_native.py` copies native production headers to a disposable overlay and replaces only the initial integer RNG call inside the historical modulo-probe branch with a checked supplied integer. The existing production friend access sets the inputs and invokes the production method. An inverse-patch assertion verifies that removing that replacement and its declaration restores the exact original MAC header. No selection or collision-probing code is rewritten. Exhaustion cases execute the original abort in separate processes. MATLAB invokes the original public `csr.mac.SlotSelection` methods without modifying the class.

`build-receipt.json` records source and overlay hashes plus the compiler command. `native_reference.csv` is the cross-engine oracle, `native_summary.json` records fixture execution, and `native_cases.log` preserves native case output.

To regenerate from this workspace:

```sh
python3 mac_replay/diagnostics/rules/make_vectors.py
python3 mac_replay/diagnostics/rules/build_native.py --source startup131/environment/csr --engine-build startup131/environment/engine/build
python3 mac_replay/diagnostics/rules/run_native.py
```

This test isolates the slot-selection/range rules. It does not reproduce the ns-3 random stream, queue service, receiver events, countdown phase, or network outcomes. Those belong to the separate common-input MAC scheduling replay in this batch.
