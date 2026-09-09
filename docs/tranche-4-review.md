# Tranche 4 independent review record

Reviewed on 2026-09-09 against the merged Tranche 3 base. Independent agents
examined source-contract mapping, research layouts and the assembled validation
runner. A final bounded recheck examined the compact evidence archive contract.
These are static engineering reviews, not MATLAB runtime results.

## Findings resolved before packaging

- Relative output directories could produce inventory paths relative to the
  wrong prefix. The runner and inventory helper now canonicalize directories;
  a MATLAB regression checks relative paths.
- A requested native gate could be described as executed when product
  discovery failed before tests ran. Metadata now distinguishes requested,
  attempted, executed and failed states, using only evidence from the current
  unique run directory.
- The compact ZIP omits large MAT objects, but its required inventory initially
  listed them. Case `local_files` and top-level `LocalArtifacts` now record MAT
  objects separately. The required inventories describe the bundled evidence.
  A MATLAB regression checks the exported paths and this distinction. The
  independent final recheck found no remaining blocker in this contract.
- Long-duration overrides now retain the explicit long-run provenance flag.
  Research geometry, discovery stimuli and receive-erasure recovery are labeled
  as synthetic or diagnostic where appropriate.

The comparator's Python tests exercise malformed/incomplete traces, stale
hashes, mismatched profiles, byte conversion, independent packet identities,
late delivery accounting and changed delivery outcomes. All five actual
reference case manifests also passed hash, generation and trace-identity
validation. Synthetic Python fixtures are not MATLAB execution evidence.

## Remaining runtime gate

All 83 MATLAB files pass MISS_HIT using its MATLAB 2022a syntax profile.
All 42 Python tests pass. The initial owner R2025a run subsequently passed
330/331 tests and stopped on evidence path/hash defects. A bounded independent
review found no blocking issue in the fixes described in the
[repair record](tranche-4-r2025a-repair.md). It also requested protection for
a failed diary reopen, which is now included. The corrected 333-method suite,
research exports and shared MATLAB scenarios require a rerun on R2025a and
execution on R2026a. The optional six native tests and 6000-second workload are separate
requested gates. Actual cross-simulator comparisons can start after the shared
MATLAB exports are returned. No full-network parity claim is made.
