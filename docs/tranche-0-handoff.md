# Tranche 0 handoff — candidate awaiting MATLAB execution

## Objective and capabilities

Create the integrated foundation for an empty MATLAB repository. The candidate
contains three-node direct transport, validated configuration, 24-bit CSR IDs,
logical DATA sizing, exact seven-rate/long-short timing, controlled propagation
and loss, stable FIFO event scheduling/cancellation, per-node/subsystem RNG,
bounded traces, counters, exports and a single validation command.

Same-node transmission serialization is test infrastructure. MAC access,
ACK/DACK/retry reliability, dynamic routes, interference/BER/ECC and security
remain unimplemented. No native wireless adapter is claimed.

## Architecture/files

- `+csr`: `Node`, logical packet, `Simulation`, `runScenario`.
- `+csr/+sim`: scheduler, RNG streams, runtime capabilities, optional isolated
  wireless scheduler probe.
- `+csr/+phy`: exact rate/airtime and explicitly controlled link channel.
- `+csr/+scenario`, `+csr/+analysis`: config/fixture and MAT/CSV/JSON export.
- `tests`: 24 MATLAB test methods across scheduler, RNG, PHY timing and
  integrated foundation tests; `run_validation.m` records actual outcomes.
- `docs`, `evidence`, `AGENTS.md`: release boundary, source map, parity ledger,
  validation provenance, independent review and continued project instructions.

## Tests and versions

Fresh ns-3 Python checks passed: 289 utility tests and 51 release-classifier
probes. MISS_HIT 0.9.44 static lint passed all 20 MATLAB files using its R2022a
language profile; this is syntax/static checking only.

**MATLAB R2025a: not executed. MATLAB R2026a: not executed.**
No ns-3 C++ run occurred here. The source publication historically records
38/38 executable workflows for the retained source tree.

Independent review found two MATLAB test/table edge cases; both were fixed
and singleton/empty results have a prepared regression. No remaining blocker
was identified in the scoped static review. MATLAB acceptance remains open.

## Comparisons and known discrepancies

Reference: ns-3 main `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Exact rate and
airtime constants and bare envelope arithmetic were checked against current
source and its fixtures. This is not an executed MATLAB/ns-3 differential
comparison. No MATLAB/OPNET aggregate comparison occurred.

Current ns-3 retains documented OPNET residuals and the current PHY/ECC behavior.
Keep that implementation as the initial PHY reference; the reverted BER timing
experiment is deferred. All unimplemented subsystems and intentional T0
infrastructure differences are visible in `parity-ledger.csv`.

## Acceptance and next tranche

From the repository root run `run_validation` in MATLAB. Expected controlled
fixture counts are 6 generated/transmitted/received, 0 dropped/pending and 384
received application bytes. Collect `results/validation/` and retain actual
release information. Run on both releases when available; no need to block
R2026a development on an unavailable work-machine installation.

Next: Tranche 1, integrated PHY/channel/traffic plus a separate native R2026a
adapter. In parallel map MAC/HOP and build deterministic differential fixtures.
This candidate is suitable for a clearly labeled draft PR after owner
authorization; it is not a runtime-validated merge recommendation.

Remote push, PR creation, merge and branch deletion have not been performed.
