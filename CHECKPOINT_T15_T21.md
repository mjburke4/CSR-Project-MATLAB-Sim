# Accepted Tranches 15–21 checkpoint

This checkpoint publishes the accepted portable MATLAB implementation through
Tranche 20 and the completed Tranche 21 analysis. It builds on merged PR #8
(Tranches 6–14), preserving its historical files and evidence. Tranche 22 is
still undergoing owner MATLAB validation and is excluded.

The current implementation is the exact accepted T20 source: **376 bound
files, including 175 MATLAB files**, with **98 pinned reference bindings**.
T20 passed **716/716 portable tests** on MATLAB R2025a
`25.1.0.2943329`. Full 6,000-second campus runs cover seeds 128, 129 and 130;
seed 128 reuses the accepted T19 run and seeds 129/130 are fresh T20 runs.
No MATLAB or native simulation was rerun merely to publish this checkpoint.

## Scope and behavior

| Tranche | Published work and disposition |
| --- | --- |
| 15 | Controlled loss/recovery timing comparison; continuous timing retained. |
| 16 | Real-network timing comparison across three seeds; continuous timing retained. |
| 17 | Full portable regression and unchanged 6,000-second campus baseline validated. |
| 18 | Relay/local admission and service diagnostics, including node 5 and 4→5 retries. |
| 19 | Full-campus queued-retry expiration experiment; `actual-tx` retained as default and `native-provisional` remains opt-in. |
| 20 | Accepted portable regression and full-campus seed variation. |
| 21 | Completed offline trace analysis and revised descriptive ±10% performance target; no source change and no new runtime tests. |

The native CSR pin remains
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. PHY/ECC and continuous timing remain
unchanged. Battery, supervisory-layer and BBN routing work remain outside this
port's scope. The portable MATLAB backend is validated; optional wireless-clock
adapter execution is not newly claimed here.

## Numerical status

Whole-network unique delivery differs from ns-3 by **+0.476%, +0.543% and
−0.059%** for seeds 128, 129 and 130. Under T21's revised ±10% descriptive
target, 13/18 per-flow delivery comparisons and 13/18 mean-delay comparisons
fall within the band. Remaining delivery exceptions are sources 4/5 in seed
128 and sources 5/7/8 in seed 130. Three seeds do not establish statistical
equivalence, and pooled totals do not erase per-seed exceptions.

T21 associated the largest seed-130 discrepancy with different 7→8 adaptive
window histories and node 8 relay backlog. It did not demonstrate a porting
defect or justify a production tuning change. T22's controlled replay is the
next validation step and is not part of this checkpoint.

## Evidence and historical status text

- `evidence/t15/` through `evidence/t19/` preserve the prior owner archives and
  review records already bundled with the accepted installation.
- `evidence/t20/owner.zip` is the unchanged original T20 return. Its SHA-256 is
  `41ee42fd72d3246b005cffa6eb0731aef1f465ac19747be82feb481571a72861`.
- `evidence/t20/acceptance.json` records the accepted T20 gate.
- `evidence/t20/review.zip` preserves the complete T20 review, including its
  larger derived analysis and original return. Keeping the large analysis
  inside its verified ZIP avoids exceeding GitHub's per-file limit.
- `evidence/t21/review.zip` preserves the original T21 diagnostic package;
  `evidence/t21/review/` also exposes its reports, scripts and comparison tables.
- `publication/tranches-15-21.json` identifies this publication's source,
  acceptance and archive bindings.

Candidate JSON files, `START_T15.md` and `T16.md`–`T20.md` are immutable historical handoffs.
Their original “MATLAB execution pending” wording describes when those
packages were issued. The later accepted owner/review records and this status
document give the current disposition. They are not rewritten because their
exact bytes are part of the validated source identity.

Publication creates a new Git commit identity. It does not claim that this
commit ID was executed in MATLAB: file hashes connect the published contents
to the accepted owner runs. All earlier repository-only evidence is retained.
