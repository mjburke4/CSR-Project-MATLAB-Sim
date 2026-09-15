# Tranche 12 repaired return: independent integrity review

**Verified: the repaired run completes the focused diagnostic milestone. Strict numerical parity and full-protocol acceptance remain unclaimed.**

Owner archive SHA256: `266a47c167e9b2d50d47abcd77a349b8f474334c9e9742d7abc8cca22547633d`.
Executed repaired candidate SHA256: `ebf493fc8d34dc7c7819f14e266bf19b99f0f94441a79da38a801cd7f52292c4`.

The immutable original package plus delivered repair reconstructs the owner candidate. All 1,598 package payload entries match their manifest and the local repair tree. All 13 returned artifact hashes, 259 source bindings and 132 reference bindings verify with closed inventories and identical pre-run/post-run snapshots. Native manifests close over 41 relay and five clock artifacts.

All 241 Tranche 11 baseline source files, including all 130 MATLAB files, remain unchanged. The core 225-source/124-MATLAB-file baseline also remains unchanged. The repair changes only the new relay diagnostic MATLAB file.

MATLAB R2025a (25.1.0.2943329) completed 72/72 selected tests with zero failures or incomplete tests: 12 relay tests, eight clock tests and 52 retained tests. All four relay cases completed and all 164 relay checks pass. Raw events confirm 120 admitted and 120 delivered application identities, 180 release callbacks and zero final HOP pending owners, DACK holds, resends, waiting data, data custody or pair NSDP counts.

All 332 consumed draws match their prescribed raw tape values and ordinal sequence; all 12 usage records account for supplied, consumed and unused entries. Bootstrap controls are separately retained: node 1 has two, node 4 has two and node 5 has three queued controls per case. Zero remaining data custody must not be described as zero queues of every kind.

All 72 clock checks pass. The five shared integer-time cases match native exactly. The continuous case retains the expected one-binary64-ULP arrival residual, producing three differing observation rows and four counter-field differences. The global scheduler is unchanged.

The returned metadata correctly reports completed focused diagnostics with strict native matching false and full acceptance/numerical parity false. Event and draw differences require separate residual analysis; their presence does not imply failed application delivery.

This independent audit uses Python standard-library ZIP, CSV, JSON and hash parsing, without importing the project acceptance checker. It inspects actual owner-run MATLAB evidence and does not claim a new MATLAB or ns-3 execution.

The fixture uses prescribed random draws, fixed radio settings, preconditioned routes and neighbors, and controlled successful addressed transport. It does not establish real RF/PHY, security-admission, route-convergence, stochastic-population, full-generator or campus parity.
