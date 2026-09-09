# Running the Tranche 4 candidate

Use base MATLAB R2025a at work or R2026a at home. The portable run does not
require the Wireless Network Simulator or Python. Keep MATLAB's standard JVM
enabled for raw-byte SHA-256 provenance.

Extract the candidate ZIP and make its repository root the current MATLAB
folder. Run:

```matlab
report = run_tranche4_validation;
```

The runner creates a unique directory below `results/tranche4_validation/`.
It retains the prior portable suite and Tranche 2/3 scenario checks, then runs
all five shared ns-3 inputs and six research layouts. Every case exports its
configuration, counters, protocol/PHY traces, routes and neighbors. A
`scenario_summary.csv` is updated after each completed case.

At completion, upload the printed **`tranche4_evidence.zip`**. It contains the
CSV, JSON and log files needed for review and application comparison. The
larger `results.mat` objects remain in their original case directories and
are explicitly listed as local-only files. The top-level metadata includes
source hashes, runtime/release, options, test counts and case-manifest hashes.

If a test or structural check fails, the runner retains the exception and
all completed case evidence and attempts to package the partial run. Do not
replace that record with an earlier successful CSV. Each invocation creates
a new directory, so rerunning does not overwrite the previous evidence.

## Research and compatibility options

Use a chosen output root:

```matlab
report = run_tranche4_validation('results/my_tranche4_run');
```

Request three research seeds. Shared reference cases retain their CSV seed:

```matlab
report = run_tranche4_validation([],struct('Seeds',[128 129 130]));
```

Add the explicit 6000-second research workload:

```matlab
report = run_tranche4_validation([],struct('IncludeLongRun',true));
```

Run only the shared exports after a complete regression run, when diagnosing
a comparison. The metadata records that tests were not executed in this run:

```matlab
options = struct('RunTests',false,'ResearchScenarios',{{}});
report = run_tranche4_validation([],options);
```

Select a single shared case with `SharedScenarios`, for example
`struct('SharedScenarios',{{'two_node_8'}})`. An empty selection means all five.
An empty `ResearchScenarios` selection means no research layouts. Names must
be distinct; misspelled options and unsupported selections fail explicitly.

On R2026a with the required native simulator products available, append the
six optional native tests:

```matlab
report = run_tranche4_validation([],struct('IncludeNative',true));
```

Native tests validate the optional clock adapter and separate packet probe.
They do not establish integrated native CSR radio-packet transport. Missing
products fail the requested native gate; the metadata preserves the portable
results and distinguishes an attempted native run from completed tests.

## Comparison and interpretation

After returning the evidence ZIP, compare each shared case to its matching
archived ns-3 manifest. Python 3.10+ is sufficient on a machine where Python
execution is available:

```text
python scripts/compare_matlab_ns3.py --matlab PATH_TO_RUN/shared/two_node_8 --ns3 evidence/tranche-4-ns3-reference/two_node_8/manifest.json --output results/comparison/two_node_8
```

The tool checks hashes, profiles, settings, trace completeness, byte mapping,
application identities and internal accounting before comparing outputs.
Its default exit code 0 means valid comparison evidence; inspect
`comparison.json` for `application_match` or `application_differences`.
Add `--require-application-equality` to turn generation/delivery differences
into exit code 1. Invalid evidence returns 2. Latencies remain numeric
diagnostics because the two simulators use different random streams.

The ordinary shared cases are two nodes at 8/128 kbps and a three-node,
two-hop line at 8 kbps. The 500/1000-kbps cases are separate extensions.
Research layouts are synthetic and do not claim to reproduce the historical
OPNET campus input. See [scenario mapping](tranche-4-scenario-import.md),
[research layouts](tranche-4-research-scenarios.md), and
[comparison contract](tranche-4-comparison.md).
