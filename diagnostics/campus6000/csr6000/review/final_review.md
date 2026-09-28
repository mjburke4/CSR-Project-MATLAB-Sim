# Independent final code review

**Disposition: no remaining confirmed blocker found; ready to package for the owner run. MATLAB execution remains pending.**

This review inspected the new top-level runner, reporting helper, synthetic preflight, actual bundled native CSV schemas and duplicate-delivery counts, and the recorded static/source-binding preflight. No MATLAB execution or network simulation was performed by this reviewer. The final ZIP manifest and relocation check are separate packaging gates.

Reviewed files:

| File | SHA-256 |
|---|---|
| `run_6000_batch.m` | `99f704b51f8f3b3e87b32c96398c17a337a47f6cac7c13e277c7801e3f0bcb22` |
| `private/batch_case_analysis.m` | `687ceb51347e901e1aa2c4a8f83ecd88a809fedbbe88d52b47e7e2aa8d8ee3cd` |
| `private/batch_analysis_selfcheck.m` | `03c15018d59d762a9b1dde97b17d52c1b5bb4d6827e3de80f57a2af2cbcdfc85` |

The standalone command executes only the two authorized 6,000-second cases, sequentially, with a 15% reporting target. It imports the bound seed-specific scenarios directly, preserves production model/data files, uses no new observer/progress events or post-stop drain, and explicitly checks the scheduler stop. It does not invoke the incompatible historical T25 five-seed/10% checkpoint contract.

The runner checks frozen source/input/helper bytes, resolves twelve CSR entry points to the packaged model, and restores the caller's environment. It saves a completed result locally before reporting, preserves failed attempts, verifies sealed case bytes and exact plan/runtime before reuse, and packages CSV/JSON/log evidence even when a handled case or comparison fails. A numerical discrepancy does not invalidate a completed simulation. The operating-system lock is released on MATLAB exit; partial attempts are never resumed as simulator state or counted as accepted completions.

One confirmed blocker was found and fixed: the initial helper incorrectly rejected the four proven duplicate final deliveries in the seed-132 native ledger. The final helper accepts positive integer event counts for a delivered identity, retains duplicate events separately, and scores unique first-delivered applications. The synthetic preflight now includes a duplicate event and exercises both actual native reference CSVs before any expensive simulation. Output-path protection and explicit stop observation were also corrected during review.

The synthetic fixture's assertions were checked independently: nine MATLAB applications partition as seven delivered, one recorded drop and one pending; source-3 mean/p95 are 476/1,160 seconds; common weights are 5/6 and 1/6; exact 60-second delivery equality is included while generation at 5,940 seconds is excluded; the 1,200-second cohort excludes generation at exactly 4,800 seconds. Its custody-age checks do not assert physical queue occupancy. These checks are statically reviewed and will execute in MATLAB as the owner's preflight; they have not already passed a MATLAB runtime here.

The analysis preserves all six sources, undefined native-zero comparisons, complete attempt denominators, distinct admitted denominators, and four half-open fixed-age windows. Native unresolved identities remain distinct from known drops or live pending. Common-source weighting is a descriptive diagnostic, not an acceptance shortcut. Case completion, per-metric target results, and an overall network-parity claim are separate. Full trace-based NWK/subsequent-service analysis remains explicitly pending the independent return review.

The included `preflight.json` reports 96 unchanged production MATLAB files, successful static syntax checks for the three new files, bound scenario/reference inputs and zero newly executed simulations. The current batch can establish results for seeds 131/132 only; it cannot renew the historical five-seed claim. No production correction is part of this package.
