# Tranche 5 validation and handoff

Tranche 5 adds repeatable load and route-recovery sweeps, application-level
diagnostics, and analysis across seeds. It builds on merged Tranche 4 MATLAB
commit `7edaab558f4f00290d11e0681d883364141d547c` and retains ns-3 source pin
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. It does not change the accepted
PHY, MAC, HOP or NWK protocol implementation.

MATLAB execution of this new candidate remains pending. Static checks and
the prior Tranche 4 R2025a acceptance are not execution evidence for Tranche 5.
The default gate is portable MATLAB R2025a at work, then R2026a at home. The
portable implementation needs neither the native Wireless Network Simulator
nor Python. Keep MATLAB's standard JVM enabled for raw-byte SHA-256 hashing.

## Run the candidate

Extract the complete ZIP into a fresh folder and open its repository root in
MATLAB. Run:

```matlab
report = run_tranche5_validation;
```

The runner first executes the complete Tranche 4 regression, including all
currently discovered portable tests, the five shared ns-3 input cases, six
default research cases and retained Tranche 2/3 scenarios. It then executes
18 new sweep cases: three seeds for each of three offered-load multipliers
and three route-freshness values. Runtime depends on the machine and the
resulting control activity; allow longer than the earlier single-seed run.
Progress prints before every sweep case.

| Experiment | Default values | Seeds | Cases |
| --- | --- | --- | --- |
| `offered_load` | `LoadMultipliers = [1 2 4]` | `[128 129 130]` | 9 |
| `recovery_freshness` | `FreshnessTimeoutSeconds = [60 180 300]` | `[128 129 130]` | 9 |

The layouts remain controlled research fixtures. Their link-closure and
failure policies are carried in each archived configuration. They do not
claim to reproduce the historical OPNET campus experiment. The sweep plan
records the exact case list, seeds, parameter values, generated application
count and total simulated duration before execution starts.

Every invocation creates a unique directory under
`results/tranche5_validation/`. At completion, upload the printed
**`tranche5_evidence.zip`**. Do not combine files from separate runs.

## Options

Select an output root or a smaller diagnostic sweep:

```matlab
report = run_tranche5_validation('results/my_tranche5_run');

options = struct('RunTests',false,'Seeds',128, ...
    'Experiments',{{'offered_load'}},'LoadMultipliers',[1 2]);
report = run_tranche5_validation([],options);
```

`RunTests=false` records that this run did not execute the regression tests.
It is useful after a full regression for focused investigation and does not
satisfy the default acceptance gate.

The 6000-second workload requires an explicit option. This adds one long-run
case per requested seed to the other selected experiments:

```matlab
report = run_tranche5_validation([],struct('IncludeLongRun',true));
```

For a separately recorded, single-seed long-only run after the regression:

```matlab
options = struct('RunTests',false,'Experiments',{{}}, ...
    'Seeds',128,'IncludeLongRun',true);
report = run_tranche5_validation([],options);
```

Supported sweep options are `Seeds`, `Experiments`, `LoadMultipliers`,
`FreshnessTimeoutSeconds` and `IncludeLongRun`. Seeds must be distinct
integers from 0 through `2^32-1`, with at most 20 seeds. Load multipliers are
distinct integers from 1 through 8; freshness timeouts are distinct integers
from 30 through 600 seconds, with at most eight values. A plan may contain
at most 200 cases. Empty `Experiments` is valid only for an explicitly
requested long run. Unknown options and duplicate selections fail before
the runner creates an evidence directory.

On R2026a with the required native simulator products, request the separate
native tests through the nested Tranche 4 runner:

```matlab
report = run_tranche5_validation([],struct('IncludeNative',true));
```

Native testing remains a separate gate. It covers the optional clock adapter
and packet probe, and does not establish integrated native CSR radio-packet
transport. A requested native failure stops the run and preserves portable
evidence. If `IncludeNative=true` is combined with `RunTests=false`, the
Tranche 4 shared/research cases still execute before the native tests; only
the portable test suite and its retained Tranche 2/3 regressions are skipped.

## Evidence and interpretation

The default completed run means structural checks and requested execution
finished. It does not assert universal delivery, zero control-retry failures,
empty queues at the stop time, or numerical parity with ns-3. The finite-stop
application identity and accounting checks must balance. Delivery outcomes,
latency, queue ownership, retries and route churn remain measurements.

| File or directory | Contents |
| --- | --- |
| `validation_metadata.json` | Runtime/release, options, status, regression and native statuses, test counts, source snapshots and artifact hashes |
| `sweep_plan.json`, `sweep_cases.csv` | Planned cases and parameter/seed identities |
| `scenario_summary.csv` | Structural accounting for completed sweep cases |
| `performance_summary.csv` | One diagnostic row per completed case, including explicit experiment, parameter, value and seed |
| `sweep/<CaseId>/` | Config, complete protocol/PHY traces, node/route/neighbor tables, original research-case manifest |
| `diagnostics/<CaseId>/` | `performance_summary.csv` plus `applications.csv`, with one row per generated application |
| `regression/` | The nested Tranche 4 run and its retained portable/shared/research/native evidence |

Performance diagnostics describe available trace evidence. Missing events
or clocks are represented by explicit availability flags and unavailable
numeric values; they are not fabricated timing observations. Control-owner
drainage does not imply that every MAC feedback queue is empty. Interpret
drainage fields according to the scope stored in the diagnostic row.

Diagnostics are exported outside each original research-case directory, so
its manifest remains valid. Final source inventories must match exactly.
The top-level `Artifacts` inventory hashes every CSV, JSON and closed log in
the evidence ZIP except `validation_metadata.json` itself, which is excluded
to avoid self-reference. Archive membership is checked against that inventory
before packaging. Large MAT result objects are listed as `LocalArtifacts`
and remain on the execution machine; nested evidence ZIPs are also omitted.

A failed test or structural check retains its original MATLAB exception and
the completed case evidence. The runner attempts to package the partial run
even if reporting fails. A partial run is not an accepted run; return its
ZIP and console failure for diagnosis.

## Review gate and next step

The review should verify the returned archive hashes and source snapshots,
full requested regression success, exact planned/completed case identities,
application accounting, diagnostics, and behavior across seeds. Analyze
control-retry exhaustion, recovery delay, pending ownership and saturation
without turning them into undocumented pass/fail thresholds. Three default
seeds provide a bounded sensitivity check, not broad statistical certainty.

This tranche does not rerun or expand ns-3 numerical comparisons. The nested
Tranche 4 shared inputs remain available for its existing application-level
comparison tool. Full protocol timing, broad 6000-second behavior, R2026a
execution and native transport integration remain distinct gates.

Implementation is concentrated in `csr.scenario.researchSweep`,
`csr.analysis.performanceSummary`, `run_tranche5_validation` and the offline
sweep analysis script. After the returned default evidence is reviewed, the
next engineering work should target a measured dominant discrepancy or
runtime bottleneck, with optional long-run and R2026a results informing its
priority. Battery, supervisory logic and BBN routing remain outside scope.
