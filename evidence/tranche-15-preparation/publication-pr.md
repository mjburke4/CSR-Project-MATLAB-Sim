GitHub currently ends at Tranche 5, while the owner is running the later MATLAB implementation and has returned completed Tranche 14 diagnostics. This PR preserves the missing Tranches 6–14 code and evidence as a reviewable checkpoint before the next transport-timing experiment.

Changes:
- Recover all 1,848 files from the exact issued Tranche 14 r2 installation, including T6–T13 acceptance and focused milestone records.
- Add the original successful T14 owner archive, independent review, comparisons and provenance.
- Record the cumulative recovery mapping without inventing original Git identities for archive-based repairs.

Validation:
- All 285 source bindings (144 MATLAB) and 317 reference bindings match the successful owner-returned R2025a run.
- T14 owner execution: 109/109 MATLAB tests, 222/222 structural checks, 6/6 cases and 18/18 delivered identities; final diagnostic queues drained.
- All 271 validated T13 sources, including 138 MATLAB files, remain unchanged by T14.
- Publication adds evidence and documentation without changing validated MATLAB source. No new MATLAB or native execution is claimed.

The continuous-time ACK-boundary case retains a one-ULP arrival-order residual and an extra ACK; the local nanosecond fixture restores its event sequence. Strict differences remain visible. T11–T14 are focused diagnostic milestones, not a full-network acceptance or exact ns-3/OPNET parity claim. PHY/ECC stays unchanged. Tranche 15 is excluded.

See `docs/t6-t14-publication.md`, `evidence/t6-t14-publication.json`, and `evidence/t14-reviewed/README.md` for checkpoint identities, evidence scope and remaining work.
