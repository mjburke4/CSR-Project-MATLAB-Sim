# Tranche 5 publication provenance

The recovered branch at `a514e6de` omitted the reporting repair and acceptance
archive. Its candidate recovery also retained older content at five paths.
This publication restores the exact original candidate, then republishes the
exact reporting-repair and acceptance trees. No new MATLAB behavior was introduced.

| Stage | Original commit | Published commit | Verification |
| --- | --- | --- | --- |
| validated MATLAB baseline | `536b288d765a7b18007ff7898eaf3f2e173d9e58` | `db2bd08da5ef016244787116b8f2755aeb175399` | Identical Git tree `af86dc6be4059ec77061fe1c1fe4ed8ce1b324fd` |
| Python-only reporting repair | `7109ae06fefcbbf91446aee3b4826c47084db5ba` | `9c0e55e917abdf63946742cc3f8cb37e056d3305` | Identical Git tree `d8ecaf971c7e3744e6d09af648649d42d30f0301` |
| accepted evidence and review | `1f515648de89c950a8bc6beccfb6a0f815a82eb9` | `5153b74b52da6ec517438942d5fa977189020eaa` | Identical Git tree `c3f351d9c45a87e7ddeb242c497df4b4553c43a9` |

## Recovery correction

The five restored paths are:

- `+csr/+validation/Artifacts.m`
- `README.md`
- `docs/parity-ledger.csv`
- `evidence/source-baseline.json`
- `tests/TestResearchEvidence.m`

The two MATLAB files contain the already-validated source-snapshot coverage
and its tests. Restoring their exact original bytes is necessary to preserve
the validated baseline. The recovered commit's claim of complete archive-byte
preservation was incorrect; the identical candidate tree above is the corrected
publication boundary.

## Accepted artifacts and verification

The full original `1f51564` acceptance tree is preserved, including the untouched
return ZIP, source-bound candidate, test and sweep exports, initial reporting
failure, repaired analysis, five application comparisons, and independent
integrity/outcome reviews. See
[the machine-readable publication record](../evidence/tranche-5-publication-provenance.json)
for all paths and the archive checksum.

Publication review verified all 550 archive inventory entries and 116 source
hashes, including 88 MATLAB files. The Python suite was rerun: **75/75 passed**.
A separate read-only reviewer checked the archive, source identities, acceptance
hashes and reported totals. Three published Git trees match the original trees
exactly, including file bytes and modes. The final provenance-only commit adds
this document and the publication JSON; accepted evidence remains untouched.

The owner's accepted portable R2025a run remains **367/367 tests**, **18 sweeps**
and **5/5 shared application comparisons**. No MATLAB or ns-3 execution was
performed for this publication. No MATLAB rerun is needed for the Python repair.

## Status and remaining engineering work

Historical acceptance files deliberately retain original commit IDs, local paths,
timestamps, and statements such as “no PR is open” or “recorded locally.”
Those describe the original acceptance time. This publication record supplies
the current original-to-published mapping; use the branch's GitHub PR for live
review status. Main is not merged by this publication task.

Measured sweep totals remain **336/357 delivered**, **21 retry-exhaustion drops**
and **zero applications pending**. Three cases retain controls queued at the
stop boundary. Outage detection and stale-route retry/custody behavior remain
the next engineering target, with PHY/ECC preserved.

The 48 execution-machine MAT files were not supplied for independent inspection.
Native/R2026a, 6,000-second workloads and full protocol timing parity remain
separate gates. The five comparisons reuse retained ns-3 reference evidence;
high-rate extensions are separately labeled. Battery, supervisory behavior and
BBN routing remain excluded.
