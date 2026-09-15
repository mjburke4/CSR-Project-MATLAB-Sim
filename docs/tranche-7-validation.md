# Run and review the Tranche 7 candidate

The owner run from candidate `28ed878` passed the bounded portable R2025a
gate. See [acceptance](tranche-7-portable-acceptance.md) for results and
remaining limits. To reproduce its exact source snapshot, extract that
frozen candidate ZIP or check out commit `28ed878` in a fresh folder.
In MATLAB R2025a,
change to that folder and run:

```matlab
report = run_tranche7_validation;
```

The default command first executes all current portable tests, 18 retained
load/recovery sweeps and 28 retained scenarios. Their T6/T5-format nested
metadata names the reused harness; **the code executing is this T7 candidate**,
identified by the outer source snapshot. It then executes the campus
6,000-second benchmark and the 1,200/360-second diagnostics. These are
simulated durations, not promised wall-clock times. The accepted laptop run
took 88 minutes overall; reported campus simulation time was 71 minutes
37 seconds, two-node time 2 minutes 50 seconds, and contention time 40
seconds. Runtime on other machines can differ. Peak memory was not measured.

No Python installation, ns-3 installation or OPNET license is needed on the
MATLAB machine. The package includes the reference traces, aggregates and
their production records. Leave the source and reference files unchanged
during the run. Preserve the full candidate folder for later reproduction.

Upload the printed `tranche7_evidence.zip`. The compact archive contains
CSV/JSON and closed logs. MAT objects and nested ZIP files remain in the
local results folder; they are not required for the initial review. A failed
run preserves partial evidence and rethrows its original error. Return that
archive if execution fails; a partial run cannot pass the full gate.

## Optional diagnostic and native runs

A selected diagnostic can be run independently:

```matlab
report = run_tranche7_validation([],struct( ...
    'RunTests',false,'Cases',{{'two_node_admission_1200'}}));
```

It is labeled as a selected run without a regression test gate. It does not
replace the default acceptance run. The catalog does not offer duration,
seed or offered-load overrides under an existing benchmark name; create a
separately named input/reference experiment for those changes.

`IncludeNative=true` requests the existing optional native validation gate.
Default benchmarks use the portable CSR stack. Native clock/transport
integration and R2026a remain separate unvalidated scopes.

## Evidence contracts

The source snapshot binds MATLAB, analysis scripts, BER data, candidate
metadata, all scenario inputs, the catalog and synthetic recipes. A separate
snapshot binds the full ns-3 reference and recovered-input trees. Both must
remain unchanged throughout execution. Reference prerequisites check
completed manifests, exact scenario/profile/window identity, build
provenance and declared file hashes.

Each benchmark exports application/physical accounting, per-node snapshots,
complete protocol and PHY traces, per-application performance records and
per-flow attempt/admission counters. The admission diagnostic trace retains
at most 100,000 records, with an explicit omitted count. This cap does not
stop generation or discard counter updates. Protocol/PHY truncation or
unbalanced ownership is a structural failure. The default evidence budgets
are 1.5 million records for each protocol/PHY trace and 12 million events.

Aggregation uses `[0, stop)` and buckets `[start, end)`, labeled by bucket
end. The common application size is payload plus seven NWK bytes: configured
200-byte campus packets become 185 payload bytes and 192 measured bytes.
Their bare over-air size is 217 bytes. Empty means remain missing; empty
computed counts/rates are zero. Source-proven OPNET missing sentinels are
preserved, including the initial missing sink count/bit sums.

## Returned archive review

Use the unchanged candidate checkout as the source/reference root:

```bash
python3 scripts/analyze_tranche7_return.py --evidence ../tranche7_evidence.zip --output ../tranche7_review
```

The reviewer verifies the archive, source identity, reference identity,
inventories, nested regression evidence and benchmark accounting before
comparing aggregates. Full benchmark coverage and requested passing tests
are required for a full structural gate. Numerical differences are reported
descriptively; a successful comparison process does not certify parity.

The per-case comparator also supports `--matlab-case` and `--reference`
directories for focused review. Exact CLI options and failures can be
inspected with each script's `--help`. Never compare changed MATLAB source
under the original candidate's acceptance identity.
