# Replay lineage logger checkpoint

This folder preserves a passive MATLAB packet-lineage observer and two no-model qualification gates. It does not change the simulator, production MATLAB paths, the parity baseline, or any previous run. It is not an integrated replay package or a launch authorization.

## Recorded checks

- Selector gate: 5 passed, 0 failed, 0 incomplete on Windows MATLAB R2025a (25.1.0.2943329). Checks mixed control/data bundles, exact membership counting, and malformed aggregate rejection.
- Logger gate: 3 checks passed on Windows MATLAB R2026a Update 5 (26.1.0.3346908), with the pinned runtime on the MATLAB path throughout the call and teardown. Checks original-sink forwarding, filter and exact ID handling, exclusive endpoint and closure, disabled capture, and byte-cap failure.
- Neither check ran a model. The matching 15-node MATLAB replay and cross-engine trace comparison are pending.

All four MATLAB files are kept together to preserve the tested file resolution. The logger gate requires the original, hash-pinned runtime helpers, supplied separately using the caller's local runtime path. It requires its own writable, non-reparse output parent. Do not add this folder to production startup or use it to launch a simulator.
