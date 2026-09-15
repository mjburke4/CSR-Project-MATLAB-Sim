# Tranche 7 independent candidate review

An independent reviewer checked the candidate against pinned ns-3
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. No blocker remains in the reviewed
historical admission, campus MAC selection/population, bare DATA/ACK size,
canonical import, aggregate grid or MATLAB coordinator contracts.

The reviewer confirmed source gate order, persistent topology and gateway
cache behavior, the strict NSDP threshold, admitted-only packet allocation
and the nanosecond stop boundary. The canonical radio ranges remain intact.
The factory correctly handles MATLAB JSON arrays with case-specific fields.

The initial coordinator accepted any nonempty reference directory. This
finding was fixed: it now requires completed case and suite manifests,
the exact source/scenario/profile/window/seed identities, build provenance,
recovered input hashes and declared artifact inventories. Both source and
reference snapshots are checked again at completion.

A second evidence review identified admission trace gaps: per-reason counts,
accepted reason labels, bounded-trace lower bounds, finite flow indices and
interrupt timestamps needed validation. These checks and negative regression
tests were added, including the decimal stop case where floating `ceil`
would miscount attempts.

The Python return/comparison review also corrected MATLAB scientific-notation
byte-count parsing and the inherited T4 live-log inventory exception. It
requires the actual physical/duty-cycle configuration to match the canonical
input, reconciles generation timing and payloads beyond the bounded admission
trace, and reconstructs aggregate buckets from raw application records.
Optional native execution claims require their own recorded status and CSV
evidence. These checks protect structural interpretation of a returned run;
they do not impose cross-simulator numerical tolerances.

The reverse ACK and S0/failure-feedback discrepancy is an explicit retained
model boundary, detailed in [the source audit](tranche-7-source-audit.md).
It limits numerical equivalence and must remain visible in the comparison.

Actual local checks and their final source snapshot are recorded in
`evidence/tranche-7-local-checks.json`: **158/158 Python tests passed and all
103 MATLAB files passed static lint**. The candidate contains 467 portable
MATLAB test methods, including 87 new methods; these are prepared, not run.
The reviewer independently ran the
125-test Python suite at its earlier snapshot and static lint on ten
reviewed MATLAB files. Subsequent reporting/evidence tests are included in
the final local checks, not retroactively attributed to that earlier run.
No MATLAB runtime was available; component source review and static checks
do not establish R2025a execution or benchmark acceptance.
