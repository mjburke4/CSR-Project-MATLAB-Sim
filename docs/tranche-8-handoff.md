# Tranche 8: small multiseed and feedback diagnostics

This is the preparation record for the original and repaired candidates.
The owner run at `89b62e7` has now passed its portable diagnostic gate; see
the [portable acceptance](tranche-8-portable-acceptance.md) for the current
results, remaining limits and next milestone.

The original `010793b` candidate failed owner MATLAB initialization because
its derived CSVs populated `scenario` on node and flow rows. The replacement
corrects that input schema, adds an independent importer-contract regression,
and regenerates the ns-3 references against the new hashes. The
[input repair](tranche-8-input-repair.md) and
[repair checks](../evidence/tranche-8-repair-checks.json) supersede the original
candidate's release-preparation checks. MATLAB source is unchanged.

The objective is to separate seed variation from feedback-policy differences
before modifying ACK behavior. This candidate starts at T7 acceptance commit
`68e18181d90b27e5cfaa11f4537595c2e6640809`. Source main was rechecked and
remains ns-3 `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree
`b611b233fb369569b98f0914ece24d029ccc2f42`.

## Executed ns-3 results

The 1,200-second two-node admission fixture and 360-second three-node
contention fixture each ran at seeds 128–132. Derived inputs change only
the experiment identity and seed; their recipe and parent hashes remain
bound in the fixed [plan](../scenarios/link_diagnostics/plan.json).

| Seed | Two-node admitted | Two-node delivered | Contention admitted | Contention delivered |
| --- | ---: | ---: | ---: | ---: |
| 128 | 11,380 | 11,364 | 946 | 914 |
| 129 | 11,234 | 11,227 | 854 | 822 |
| 130 | 11,412 | 11,396 | 948 | 916 |
| 131 | 11,334 | 11,330 | 903 | 883 |
| 132 | 11,383 | 11,375 | 952 | 920 |

Mean delivered counts are 11,338.4 and 891, with sample standard deviations
66.70 and 41.29 (CV 0.59% and 4.63%). These are descriptive ns-3 results
for five seeds. Matched MATLAB seed variation and cross-simulator differences
await the owner return. Unmatched ns-3 application sends are reported as such;
the trace does not certify their terminal dropped-versus-pending ownership.

The final reference passes 130 declared file checks and 32 complete gzip
roundtrips. All ten observer-on/off comparisons pass application/statistics
trace and admission equality; the two seed-128 cases also pass pristine
runner controls and reproduce the accepted T7 ns-3 anchors. These comparisons
do not establish full packet-event or protocol parity between simulators.

A fresh standalone runner was compiled against the hash-verified preserved
ns-3 engine libraries (engine commit
`6b5cd24ea80713ce16d88575869aedd6f432bdae`). The engine was not rebuilt.
Preliminary outputs failed integrity checks and were quarantined. The
complete suite was regenerated in an isolated directory, copied, and
independently verified. Their cause remains unestablished; the
[recovery record](../evidence/tranche-8-ns3-reference-recovery.json) retains
the failed hashes and the final checks. Only the final verified reference is
part of the candidate.

## ACK rate and power findings

There are 61,472 feedback constructions/selections and 12,460 actual
transmitted feedback members across the ten cases. Queue replacement and
repeat transmission mean these counts describe different stages.

All ordinary DATA ACKs select and actually transmit at rate key 128
(the 128-kbps profile), +33 dBm. Their selections match the incoming DATA
radio settings. The 139 actual feedback members whose aggregate rate differs
from their selected rate are exact-window control ACKs, sent during startup
by 58.683 seconds, before applications start at 300 seconds. None is an
ordinary DATA ACK override. No DACK occurs in these direct-to-gateway cases.

Observed peers are known, their S0 is always −103 dBm, and HOP failure counts
are zero. The sampled path losses are about 123.167 and 135.208 dB. With the
source limits and 12-dB margin, the source formula chooses key 128 for the
shorter link and key 8 for the longer cross-peer control link, both at the
rounded +33-dBm power. HOP failure count contributes to link cost; it is not
a direct term in these speed and power expressions.

For the ordinary DATA links sampled here, the ns-3 result coincides with
MATLAB's existing copied receive rate and configured node power. That does
not establish equivalence for unknown peers, varying S0, failure-state
changes, or relayed DACK. It also does not explain or bound the campus's
17.10% flow-8 difference at seed 128. No ACK-policy correction is justified
by this evidence alone. Full per-case, per-flow and packet-weighted delay
results are in the [feedback findings](../evidence/tranche-8-ns3-feedback-findings.json).

## MATLAB candidate and verification

`csr.sim.LinkDiagnostics` observes existing feedback decisions after MAC
admission and actual feedback members at aggregate transmission. Its rows
include queue replacement/retention, semantic ACK identity, rate and power,
received context and available peer state. It reports truncation and
correlation failures explicitly. MATLAB does not have all source link-control
inputs: missing peer S0 and HOP failure state are labeled unavailable.
The ns-3 selection stage precedes MAC admission, so raw selection counts are
not compared as if the observation stages were identical.

`NetworkSimulation` accepts an optional observer; its default behavior and
configuration stay intact. `exportResults` adds `link_decisions.csv` and
`actual_feedback.csv` only when observations are present. HOP/MAC/NWK policy,
PHY/ECC and data files remain unchanged. The source inventory now includes
the ns-3 observer header. The shared Python reviewer gains header membership
and an explicit alternative case-directory argument; its T7 defaults remain
unchanged.

`linkDiagnosticSuite` verifies the ten fixed inputs. The runner executes
portable tests, ten observed cases and two seed-128 unobserved controls.
The controls compare statistics, configuration and twelve existing CSVs.
The return reviewer checks source/reference stability, all inventories and
traces, accounting, observer correlation, and the original T7 MATLAB anchor.
It then reports per-flow and per-seed comparisons, keeping packet-weighted
latency separate from means of populated bucket means.

Current Python tests, MATLAB source-preservation checks and the independent
review are recorded in [repair checks](../evidence/tranche-8-repair-checks.json).
The [original local checks](../evidence/tranche-8-local-checks.json) preserve
the preparation evidence for `010793b`; those tests missed the input schema
mistake and do not certify the repaired source snapshot.
**MATLAB and Octave are unavailable here: no T8 MATLAB execution or acceptance
is claimed.** R2025a owner execution is the next gate; R2026a and native
adapters remain separate. Structural failures block that acceptance, and
numerical differences remain measured findings without a post-hoc tolerance.

## Short paths and next milestone

The package has no enclosing directory. Extract `csr8.zip` into `C:\csr8`
and run `report = run_tranche8_validation;`. Results use `results\t8`, a
23-character run folder and compact `b\a128`/`b\c128` case folders; controls
use `c\a128`/`c\c128`. Full experiment names remain in metadata. Existing
hash-bound historical source paths are preserved. See the
[run instructions](tranche-8-validation.md) for the return archive and runtime
estimate.

After the MATLAB return, compare paired seeds and the observed feedback
choices before choosing a policy change. If the remaining question concerns
campus relaying, the next targeted experiment should exercise a relay and
the missing link-state range. Repeating all five long campus runs is not
part of this candidate. Retain the accepted T7 package and its returned
evidence to reproduce that baseline.
