# Tranche 5 descriptive sweep report

`scripts/analyze_research_sweep.py` validates a completed Tranche 5 evidence
directory and summarizes variation across its distinct seeds. It does not run
MATLAB, compare ns-3 traces, or establish acceptance or numerical equivalence.
Python 3.10 or later is sufficient; no third-party packages are required.

After the MATLAB runner finishes, extract `tranche5_evidence.zip` and pass the
directory containing its top-level `validation_metadata.json`:

```text
python scripts/analyze_research_sweep.py --evidence PATH_TO_EXTRACTED_EVIDENCE --output results/tranche5_analysis
```

The output directory must be outside the input evidence directory. Direct ZIP
input is intentionally unsupported. Extraction and any validation of a downloaded
archive happen before this tool runs.

| Output | Contents |
| --- | --- |
| `sweep_analysis.json` | Evidence status and metadata hash, recorded source pin and stability, test/native status, grouped statistics, and interpretation limits |
| `seed_observations.csv` | One observation per experiment, parameter value and distinct seed, with case identity and measured metrics |
| `group_statistics.csv` | One row per experiment, parameter value and metric: seed count, finite count, missing count, mean, sample standard deviation, minimum and maximum |

Exit code 0 means internally consistent completed evidence was summarized.
The report status is `descriptive_summary_completed`; both
`matlab_acceptance_established` and `cross_simulator_equivalence_established`
remain false. Invalid, incomplete or contradictory evidence returns exit code 2
and writes `invalid_evidence`. On failure, the tool replaces its own two CSV
outputs with header-only files, so stale successful results cannot be mistaken
for the current outcome. It leaves unrelated output files untouched.

## Evidence contract

The top-level metadata schema must be
`csr-matlab-tranche-5-validation-v1`, with completed status, recorded MATLAB
execution and recorded source stability. The analyzer requires matching initial
`SourceFiles` and final `SourceFilesFinal` path/hash maps, then checks every
case's source map against them. Source maps include MATLAB code, Python
analysis scripts, candidate metadata, BER data and shared inputs as selected by
the runner. This checks recorded consistency; source code need not be present
in the extracted evidence directory.

Every exported CSV, JSON and log file except the top-level metadata itself
must appear exactly once in `Artifacts`, exist under the evidence directory,
and match its SHA-256 and byte count. Nested regression metadata is included.
Recorded CSV row counts are also verified. Absolute paths, traversal paths,
duplicate paths and symlinks resolving outside the evidence directory are
rejected. Local MAT objects and ZIP archives are outside the exported inventory
contract. The root metadata cannot hash itself; its actual hash is recorded in
the analysis result for subsequent review.

The analyzer independently reconstructs the Cartesian product requested by
`sweep_plan.json` options: offered-load multipliers and recovery-freshness
timeouts across the selected seeds, plus optional 6000-second cases. It then
requires exact identity agreement among the reconstructed set, `plan.Cases`,
`sweep_cases.csv`, metadata `Cases`, and `performance_summary.csv`. Both
planned/completed case counts and run options must agree with the plan. Missing
cases, duplicate identities and different seed sets cannot silently reduce the
work that counts as complete. MATLAB scalar structs and scalar numeric seeds
are supported, including a one-seed long-run-only plan.

For each case it checks:

- The recorded case-manifest hash, completed execution, structural status,
  source snapshot, source commit, scenario and seed.
- The original case's file inventory against both actual files and the
  top-level artifact inventory, including hash-bound `summary.json`, research
  summary and complete protocol/PHY trace files.
- Declared `Config.Research.Sweep` experiment, parameter, value and seed;
  `Config.Name`, duration and source commit must match the case and summary.
- The per-case diagnostic row must equal its aggregate performance row;
  application diagnostics must be present in the artifact inventory.
- Generated, received, dropped and pending application accounting, core
  counters, zero omitted trace records, and consistency of drain flags with
  the exported ownership counts.

These are evidence and declared-identity checks. The analyzer does not rerun
the simulator, reconstruct each application from the traces, or independently
prove that only the selected physical/protocol parameter changed. The MATLAB
builder, structural checks and diagnostic exporter own those implementation
contracts. Hashes bind supplied files to each other; they do not independently
prove where or how the run executed.

## Test and native execution status

A completed `RunTests=false` experiment is a valid descriptive input. It is
explicitly reported as `tests.status: not_run`; all test counts must be zero
and no test-pass claim is allowed. This is not portable acceptance.

When tests were requested, the recorded counts must describe a complete passing
run and agree with the uniquely named tests in the hash-bound test-results CSV.
The requested regression must have completed. Requested native execution must
also report attempted, executed and passed. Unrequested native execution cannot
carry a result. No native-packet transport capability or parity is inferred
from these flags.

## Descriptive statistics and interpretation

Grouping uses `(Experiment, Parameter, Value)`. Each seed contributes one
equally weighted observation. Different values retain separate groups and the
same planned seed set. Metrics include application delivery ratio, per-run
latency p95 and maximum, HOP data/control retransmissions, NWK/HOP control
failures, neighbor deactivations, route changes, transmissions and finite-stop
ownership counts. Drain Boolean means are fractions of seed runs that drained
the corresponding exported ownership domain.

The sample standard deviation uses `n-1`, with `n` equal to the finite
observation count. It is null when fewer than two finite values exist. Empty,
null or nonfinite latency measurements remain null in JSON and empty in CSV;
they are excluded from finite statistics and counted in `MissingCount`. They
are never replaced by zero. Required counts must be finite nonnegative
integers. A delivery ratio must agree with received/generated counts when any
applications were generated; zero generation requires an absent ratio.

A mean of three per-run latency p95 values is a mean of three quantiles, not
a pooled packet p95. Neither three seeds nor any other configured seed count
establishes confidence, equivalence or convergence. Matching seed identities
also do not guarantee identical random draws after event ordering changes.

`ControlsDrained` covers HOP and NWK control ownership. The unchanged simulator
does not export the current MAC feedback-queue depth, so these metrics cannot
establish complete MAC quiescence. Pending applications, control failures and
route churn remain measured outcomes; they are not automatically evidence
integrity failures. Airtime and CPU time are not inferred by this analyzer.

## Verification

```text
python -m unittest discover -s scripts/tests -p test_analyze_research_sweep.py -v
```

The 24 synthetic Python tests cover statistics, scalar MATLAB JSON shapes,
test/native status, missing values, malformed and corrupted evidence, missing
or duplicate cases, a truncated plan, source/config disagreement, ownership
accounting and output safety. They establish analyzer behavior only. Actual
Tranche 5 MATLAB execution and its descriptive results are still pending.
