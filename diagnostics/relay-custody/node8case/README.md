# Repaired diagnostic candidate (15 October 2026)

This directory contains the current repaired MATLAB diagnostic implementation.
The repository root `+csr` is unchanged; root entrypoints do not select this candidate.
Native reference: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

Run focused component tests in a fresh MATLAB session:
```matlab
cd diagnostics/relay-custody/node8case/repaired-tests
report = run_repaired_checks;
```
The tests use synthetic public component callbacks and compact arithmetic fixtures.
They do not start the autonomous two-seed batch. Results are written locally and
excluded from Git. A fresh test-output directory is required for reruns.

`CURRENT_SOURCE_MANIFEST.json` binds current `+ac` and `model` bytes. The older
`FILES.json`, `ref`, and `review` are retained historical evidence, not current
validation. `run_node8_tests` now stops with an explicit historical-runner message:
its old 1200-second manifest and provenance contract cannot validate this candidate.
The original runnable kit remains in Git history before this change.

Repairs include synchronous ACK-triggered NWK work, separate NWK-local and HOP DATA queue
scheduling ownership, retained MAC acquisition ownership, native periodic-wake arithmetic,
and bounded passive trace storage. Receiver storage changes preserve timing and
radio calculations; PHY/ECC algorithms are not modified.

See `../../../evidence/repaired-parity-2026-10-15/RESULTS.txt` (from repository root:
`evidence/repaired-parity-2026-10-15/RESULTS.txt`) for exact accepted scope.
The complete 6000-second native-input replay matches admissions, deliveries and
local DATA failures; it is not autonomous random-stream parity. The newly authorized
autonomous seed 131/132 results remain pending. No autonomous latency improvement
is claimed.
