# Run Tranche 9

The original `99fff038` package has now completed owner R2025a execution in
23 minutes 41 seconds, with 514/514 tests and 101/101 contracts passing.
See [portable acceptance](tranche-9-portable-acceptance.md). These instructions
remain the reproduction procedure for that frozen package; no repeat run is
needed for the post-return Python reporting repair.

Extract the prefix-free `csr9.zip` into a fresh, short folder such as
`C:\csr9`. Open MATLAB R2025a in that folder and run:

```matlab
report = run_tranche9_validation;
```

The runner first checks deterministic ACK-service and HOP-capacity contracts
against the recorded ns-3 checkpoints. It then runs all current portable unit
tests and these six unchanged Tranche 8 stimuli:

| Folder | Experiment | Seed | Simulated seconds |
| --- | --- | ---: | ---: |
| `b/c129` | Three-node contention, primary investigation | 129 | 360 |
| `b/c128` | Three-node contention | 128 | 360 |
| `b/c130` | Three-node contention | 130 | 360 |
| `b/c131` | Three-node contention | 131 | 360 |
| `b/c132` | Three-node contention | 132 | 360 |
| `b/a129` | Two-node admission control | 129 | 1,200 |

The `c129` and `a129` cases also repeat with observations disabled. This checks
that tracing leaves the candidate's behavior unchanged. Those comparisons are
separate from measuring the candidate against the accepted Tranche 8 results.

The six cases retain their original scenario names and input hashes. New
service observations cover **300 <= time < 320 seconds**; the simulations still
run to their original stop times and retain the complete existing traces.
The controlled subsystem fixtures prescribe receiver conditions and reservation
occupancy. They test ordering and capacity rules; they are not RF benchmarks.

Allow roughly **15–25 minutes** on the laptop; the accepted owner run took
23 minutes 41 seconds. Progress appears before and after each case. The 1,200-second
admission case is likely to be the longest individual run. The command does
not include the 6,000-second campus benchmark, the older scenario sweep,
OPNET, or native adapters.

New outputs use `results\t9`, one short timestamp/token directory, and compact
case folders. Example:

```text
C:\csr9\results\t9\r260911_120000_a1b2c3d4\b\c129\raw\service_trace.csv
```

Upload the printed **`tranche9_evidence.zip`** when the run finishes. It contains
the contract checkpoints, test outcomes, source/reference hashes, all six
diagnostics and both tracing controls. Large MAT objects remain on the laptop.
If a gate fails, return the partial evidence archive or the error and printed
output directory. Do not combine files from different candidates or runs.

All earlier tranche runners remain available. Keep the accepted `csr8` package
and its evidence when exact reproduction is needed: running an older runner
from `csr9` uses the current candidate implementation.

For a deliberately diagnostic-only run without the unit-test gate:

```matlab
report = run_tranche9_validation([],struct('RunTests',false));
```

The contract and observation checks still run, but that archive cannot satisfy
the full portable acceptance gate. Arbitrary seed, duration, load or observation
window overrides are not accepted under these fixed experiment identities.

After return, review against the frozen candidate checkout:

```bash
python3 scripts/analyze_tranche9_return.py \
  --evidence /path/to/tranche9_evidence.zip \
  --source-root /path/to/frozen-csr9 \
  --output /path/to/new-review
```

The reviewer checks provenance and complete accounting before reporting
before/after and ns-3 comparisons. Structural completion does not automatically
establish numerical equivalence or acceptance.
