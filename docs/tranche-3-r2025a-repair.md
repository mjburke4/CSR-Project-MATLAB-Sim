# Tranche 3 R2025a results and repairs

**Final result: accepted portable Tranche 3.** The owner run of `ff7859a`
passed 289/289 tests with zero failures/incompletes and completed all eight
T3 plus nine T2 scenario exports. The 74 source hashes and test CSV hash match
the validated package. See [acceptance](tranche-3-portable-acceptance.md).
The sections below retain the prior failure and repair checkpoints as history.

## First rerun: 287/289 passing

The owner reran candidate `16d469f` on MATLAB R2025a `25.1.0.2943329`.
The supplied console and CSV agree: **289 methods, 287 passed, two failed and
two incomplete**. Both incomplete methods are the two failures. CSV test time
sums to 112.2300692 seconds, matching the console's rounded 112.2301 seconds.

All ten `TestNwkScenarios` methods passed, exercising autonomous convergence,
custody, routing-control loss, route recovery, gateway selection, transit
policy, high rates, reproducibility and exports inside the regression suite.
Neighbors passed 20/20, network configuration 11/11 and routing codec 11/11,
confirming the previous reported causes no longer block this run.

The two remaining errors occurred in `TestNwkLayer`:

- `simultaneousActivationsUseIndependentForwardSnapshots`
- `discoveryCompletionRefreshesLinksAndRequestsSnapshots`

The callback log is an N-by-1 struct array. `{added.Kind}` produces a row,
while `arrayfun(...,added)` preserves the column shape. Combining those masks
with `&` implicitly expands them into an N-by-N matrix, causing logical
indices outside the log's bounds. The filters now use one scalar predicate per
entry. The route-request helper already checks the control kind. The same
pattern in `routingPartialAckRetryWaitsForLaterEventAndKeepsBytes` was also
corrected; its `find(...,1)` had concealed the shape mismatch in this run.

This correction changes only `tests/TestNwkLayer.m` among MATLAB files. All
protocol assertions remain, and there are still 289 portable methods. The
specific mixed-mask pattern was checked across repository MATLAB files.
Static lint passes; repaired MATLAB execution is pending.

The [rerun evidence](../evidence/tranche-3-r2025a-rerun-1.json) records the exact
class counts, error origins and CSV hash. The
[CSV](../evidence/tranche-3-r2025a-rerun-1-test-results.csv) is retained byte-for-byte.
Release and revision association come from the owner's console; runtime source
hashes and validation metadata were not supplied. The initial failed run below
is preserved as history.

Despite the passing scenario methods, `assertSuccess` stopped the runner before
its later separate nine Tranche 2 and eight Tranche 3 scenario export loops.
Run the complete validation command again from a fresh extraction and MATLAB
session. Acceptance requires every method and the later export loops to finish.

## Initial run: 215/286 passing

The owner ran `run_tranche3_validation` on MATLAB R2025a
`25.1.0.2943329`, using the portable backend. The supplied complete console
transcript reports **286 methods: 215 passed, 71 failed and 70 incomplete**,
with 25.4242 seconds of test time. Incomplete methods are a subset of failures.
Portable Tranche 3 acceptance remains pending.

| Finding | Affected methods | Repair |
|---|---:|---|
| Logical options rejected by numeric range validation | 70 incomplete: 18 Neighbors, 11 NetworkConfig, 31 NwkLayer, 10 NwkScenarios | Validate a real scalar logical or numeric 0/1 directly, then normalize to logical |
| Zero-hop decoded path has shape 1-by-0 instead of canonical `[]` (0-by-0) | 1 completed RoutingCodec failure | Preserve initialized `[]` for zero hops; allocate a row vector only for nonzero hops |

The first defect occurred in `Neighbors.neighborConfig` while constructing
the network objects. `validateattributes` accepted `logical` as a declared
type but rejected the `>=` comparison attribute for that type. Defaults use
logical values, so the same constructor error blocked all four suites above.
Invalid, fractional, nonfinite, complex and nonscalar inputs remain rejected;
numeric zero and one remain supported.

The codec correction changes only the MATLAB representation of an empty path.
The existing strict roundtrip assertion is unchanged. A new literal-wire test
covers all three accepted empty input shapes and requires the same canonical
decoded record. Two new neighbor tests cover accepted logical/numeric inputs,
admission and freshness behavior, and rejection before scheduling. The repaired
portable suite therefore contains **289 prepared methods**.

All other reported methods passed, including PHY, HOP, MAC, route selection
and nine of the ten original codec methods. The runner stopped at the suite's
`assertSuccess`, before the later Tranche 2 and Tranche 3 scenario export loops.
Those exports and autonomous routing convergence have not passed this gate.

The source revision is associated with `fda305e` from the issued ZIP name,
matching console paths and test count. Runtime source hashes, the test CSV and
validation metadata were not supplied, so that association is not independently
verified. The structured [initial-run evidence](../evidence/tranche-3-r2025a-initial-run.json)
records the complete transcript's SHA-256, class outcomes and failed methods.
Machine-specific console paths are not copied into the repository.

No MATLAB or Octave execution occurred in this workspace. The repair received
static review and lint; a new MATLAB run is required. Earlier ns-3 workflow
results remain source-side evidence and were not rerun for these MATLAB
validation/representation corrections. No routing policy, RF model, wire
layout, retry timing or acceptance assertion was relaxed.

Extract the replacement full package into a fresh folder. Open MATLAB in its
project root with the standard JVM enabled, then run:

```matlab
run_tranche3_validation
```

Return the console output and
`results/tranche3_validation/regression/tests/test_results.csv`, together with
`results/tranche3_validation/validation_metadata.json`. If execution completes,
also return `results/tranche3_validation/scenario_summary.csv` and preserve the
per-scenario exports. R2026a portable and six native tests remain separate gates.
