# Tranche 17 specification and handoff

## Objective and decision

Run the entire top-level portable MATLAB regression and the original
`campus_multihop_6000` benchmark on the exact reviewed Tranche 16 source base.
This closes the execution gap between focused timing investigations and the
long campus workload before selecting a further behavior change.

The corrected Tranche 16 return review passed 129 owner MATLAB tests, twelve
network cases and 192 structural checks. It verified 304 source files and 453
references. Its reviewer-only repair passed 97 Python tests and is preserved
with the original owner ZIP under `evidence/t16`. No MATLAB source was changed
to repair the review. All six continuous/nanosecond pairs retained the same
application outcomes, admission counts, retries, feedback, transmissions and
observed ownership. Serialized latency differences around 1e-13 seconds and
wall-clock runtime differences remain observations. Default continuous timing
is retained; the controlled Tranche 15 benefit is not generalized to production.

Tranche 16 admitted-network totals were 34,056 MATLAB versus 33,987 ns-3
deliveries for the admission cases (+0.203%), and 2,770 versus 2,652 for the
contention cases (+4.449%). These are three-seed aggregates, not a shared-RNG
experiment or proof of population parity. Finite-stop pending applications were
retained in the report, with no application drops in those bounded cases.

## Workload and provenance

| Item | Frozen choice |
| --- | --- |
| Upstream ns-3 main | `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` |
| Engine source | `6b5cd24ea80713ce16d88575869aedd6f432bdae` |
| Campus | Seven nodes, IDs 1, 2, 3, 4, 5, 7, 8 |
| Horizon and seed | 6,000 seconds; seed 128 |
| Traffic | Original campus CSV and historical OPNET gated generator; 1,710,000 scheduled attempts |
| Model | Portable scheduler, real CSR PHY, autonomous routing, continuous receive timing |
| Diagnostics | No observer or injected transport timing; unchanged PHY/ECC |
| Budgets | 12,000,000 events; 1,500,000 protocol and PHY records each; 100,000 admission records |
| Comparison | Original pinned ns-3 campus reference and archived OPNET aggregates; 60-second bins |
| Native MATLAB tests | Excluded from this portable gate |

`evidence/tranche-17-main-check.json` records the live source inspection and
recovery. MATLAB public main is the merged Tranches 6–14 checkpoint at
`ec829f04f4ab8c8af4f6e9a53e07c1273cab2590`; the unpublished Tranche 15/16 update
archives reconstruct the owner-validated local source. The upstream
`SourceCommit` field identifies ns-3, not a MATLAB Git commit. The candidate
and exact file snapshots identify the MATLAB implementation.

The exact Tranche 16 candidate SHA256 is
`f22a893457fd7927342ed7fa176c1e227d387f6a6be3631fd0204f9a53bc1a36`;
the owner ZIP SHA256 is
`4fbfb17ba654bee0a137f1fc2d3ac3f65a091bf936d6c44589b1db9db1f4be60`.
The baseline snapshot SHA256 is
`90b5506f4fdb54f64ae7dac61c0e48df9da2253a8408a4b50b3ad30309ac1905`.
Every one of those 304 source files, including 155 MATLAB files, must remain
unchanged. No Tranche 17 source publication or merge is part of this handoff.

## Architecture

- `run_tranche17_validation.m` orchestrates tests, campus and finalization into
  one fixed output directory and packages success or partial failure evidence.
- `+csr/+scenario/tranche17Suite.m` selects the existing benchmark without
  changing its traffic, duration, trace budgets or model configuration.
- `+csr/+validation/ReleaseCheckpoint.m` validates frozen inputs and seals
  completed stages. Reuse requires identical candidate, full source inventory,
  full reference inventory, MATLAB runtime, and artifact hashes.
- `+csr/+validation/campusReleaseContract.m` executes the unchanged network,
  enforces finite-stop structural accounting and exports raw and aggregate data.
- `tests/TestCampusReleaseGate.m` covers the new orchestration contracts using
  small fixtures; it does not repeat the expensive campus run inside regression.
- `scripts/analyze_tranche17_return.py` independently validates returned
  inventories, exact full regression membership, phase receipts and campus
  structure, and generates MATLAB/ns-3/OPNET comparison results.
- `scenarios/t17/plan.json` and `evidence/tranche-17-candidate.json` freeze the
  scope and input identities before owner execution.

The candidate lists every portable test by file and method. Both the runner
and return review reject missing, duplicate, failed or incomplete test results.
The numerical test count and source inventory are recorded in the frozen
candidate and preparation report, rather than used as an acceptance shortcut.

## Evidence and acceptance boundaries

Both stages persist a completed receipt. Finalization verifies and packages
those receipts without replaying simulation. Receipts permit reusing completed
work across sessions; they do not provide simulator checkpoint/restart. A
partial, failed, altered or mismatched stage cannot be treated as completed.

Review requires ordered, complete protocol and PHY records and reconciled
generated/delivered/dropped/pending application counts. Complete admission
counters partition all attempts; the bounded admission trace is explicitly
allowed to omit the tail. The report distinguishes these permitted omissions
from forbidden protocol/PHY omissions. Pending applications and ownership at
the fixed horizon are censored measurements, not automatic failures or grounds
to drain the network artificially. MAC feedback queue depth is not exported;
reported control-drain fields cannot prove all MAC control queues are empty.

The campus comparison reports per-node and per-flow distributions, service
pressure, delay and aggregate residuals. Seed equality is not RNG equality.
OPNET offers archived aggregates, not packet/path/retry truth. No new native or
OPNET execution is claimed, and no numerical discrepancy is silently converted
into a structural pass criterion. Full numerical/statistical parity remains
open even if portable tests and campus structural review pass.

## Verification and next step

This environment has no MATLAB or Octave, so runtime execution is pending.
Preparation uses exact baseline/reference hashing, new Python checker tests,
independent source review and update-application verification. The reproducible
preparation record is under `evidence/tranche-17-preparation`.

The owner should follow `T17.md` and return `results/t17/t17.zip`. Review uses:

```text
python scripts/analyze_tranche17_return.py --evidence PATH_TO_t17.zip --source-root . --output PATH_OUTSIDE_THE_EVIDENCE
```

Once that return is checked, use the current campus delivery distribution and
service counters to select a bounded follow-up discrepancy. The earlier campus
flow redistribution and seed-129 early-contention gap remain candidates; this
handoff does not assume either has improved or justify a global timing change.
Battery, supervisory behavior and BBN routing remain outside the baseline.
