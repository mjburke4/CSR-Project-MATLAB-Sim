# Tranche 6 validation

The default portable R2025a run at `21c0a3f` completed on 2026-09-10:
380/380 tests and all 18 sweeps passed their structural gates. The
[returned-evidence review](tranche-6-portable-acceptance.md) accepts the bounded
freshness correction and records a 60-second recovery regression. The
instructions below reproduce that gate; native/R2026a and long-run execution
remain separate work.

Extract the candidate into a fresh folder so MATLAB cannot resolve older CSR
classes from a previous package. Start a fresh MATLAB R2025a session, set that
folder as the current folder, and run:

```matlab
report = run_tranche6_validation;
```

Return the printed `tranche6_evidence.zip`. If a test or scenario fails, the
runner preserves partial evidence, reports its directory and rethrows the
original exception. Return that evidence rather than changing acceptance
assertions or retry/freshness settings to make the run pass.

## What runs

The new coordinator invokes the existing Tranche 5 regression harness using
the Tranche 6 source. It runs the full portable test suite, the retained 28
scenario regressions, and all 18 offered-load/recovery sweeps. It writes outer
Tranche 6 metadata with the merged PR #5 base and hashes the complete nested
run. Nested T5-format metadata identifies the harness, not an execution of
the frozen T5 implementation. Candidate source hashes bind both levels.

Full acceptance needs the default gate. For a diagnostic-only rerun after a
failure, the retained options can select a smaller experiment:

```matlab
options = struct('RunTests',false,'Experiments',{{'recovery_freshness'}}, ...
    'Seeds',128,'FreshnessTimeoutSeconds',[60 180 300]);
report = run_tranche6_validation([],options);
```

That three-case run does not replace portable acceptance. Native/R2026a and
6000-second runs are not requested by default. The existing
[Tranche 5 option contract](tranche-5-validation.md) still applies.

## Review the returned evidence

Extract `tranche6_evidence.zip` to a fresh directory, then run:

```bash
python3 scripts/analyze_tranche6_return.py --evidence /path/to/extracted/run --output /path/to/new-review
```

The default baseline is the exact accepted T5 ZIP already included in the
repository. Its SHA-256 must equal
`824cf0f5cb6a735ee896ebc5431be5c72f69d9d95135c8e03311238bd0ca75c1`.
The analyzer verifies both inventories and all nested case/source hashes,
requires identical scenario configurations, and preserves every packet's
delivered/dropped/pending outcome. It checks that PHY/ECC, HOP and MAC source
files still match the accepted baseline. Outputs are `comparison.json`,
`case_comparison.csv` and `application_comparison.csv`.

The analyzer reports internal consistency and descriptive comparisons. It does
not automatically accept the tranche or claim improved/ns-3-equivalent behavior.
Hashes bind artifacts; they do not independently prove runtime authenticity.
Keep the accepted archive and returned evidence unchanged during review.

## Reproduce source reference checks

The reference checkout must be clean at
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. The build must contain the matching
CSR headers and required debug shared libraries. Use new output and build
directories for each execution:

```bash
python3 scripts/run_tranche6_source_contract.py --source /path/to/CSR-Project-NS3-part2 --ns3-build /path/to/ns3/build --output /path/to/new-contract-evidence --build-directory /path/to/new-contract-build
python3 scripts/run_tranche6_ns3_reference.py --source /path/to/CSR-Project-NS3-part2 --ns3-build /path/to/ns3/build --output /path/to/new-outage-evidence
```

Only standalone observation fixtures are compiled; no full engine rebuild is
claimed. The contract fixture uses direct HOP/NWK ingress, while the outage
fixture uses the real physical model. Their manifests record that distinction.
