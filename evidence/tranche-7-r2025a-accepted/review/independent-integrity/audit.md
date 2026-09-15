# Independent Tranche 7 return audit

**Result: passed.** No production return-review code was imported or executed.

Archive SHA-256: `ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655`. Candidate: `28ed878f5673e308047cbea7878b933697d932f3`.

Verified 691 outer artifact hashes; 2750 declared artifact hash/size bindings in total; 155 source/input files, including 103 MATLAB code files; and 50 pinned reference files. Source and reference snapshots remained stable. Archive CRC and path checks passed.

The returned MATLAB R2025a 25.1.0.2943329 records contain 467 unique passing tests, 18 completed retained sweeps and 28 retained fixed cases. No MATLAB was executed on the review host.

All retained sweep application outcomes match the earlier Tranche 6 return: 357 generated, 334 delivered, 23 dropped, zero pending. Each of the nine benchmark flows delivered data. Application and physical-observation partitions balance, and raw protocol event counts match the exported application records.

All common Statistics fields also match exactly across 47 retained raw summaries (18 sweep, 28 fixed and one foundation summary). The sole added statistics field is OmittedApplicationAdmissionRecords, zero in all 37 applicable summaries.

| Case | Admitted | Delivered | Dropped | Pending | Runtime, seconds |
|---|---:|---:|---:|---:|---:|
| campus_multihop_6000 | 12382 | 11727 | 401 | 254 | 4297.452 |
| two_node_admission_1200 | 11395 | 11385 | 0 | 10 | 170.460 |
| three_node_contention_360 | 954 | 928 | 0 | 26 | 40.251 |

The full returned run spans 5283.187 seconds (88 minutes 3.187 seconds).

Recommendation: accept the bounded portable R2025a benchmark milestone with these qualifications:

- Only seed 128 for the three benchmarks; no statistical-equivalence claim.
- Archived OPNET output is available only for campus and was not rerun.
- All cases retain finite-stop application and HOP/NWK custody work; pending is not a terminal loss.
- Campus admission diagnostic trace stores only 100000 of 1710000 attempts; all per-flow counters and application/protocol/PHY records are retained.
- MAT objects and three nested ZIPs remain excluded by the declared execution-machine archive policy.
- No R2026a/native execution occurred; optional adapter capability probes do not establish native integration.
- Numerical agreement and full protocol equivalence are not established by these checks.

The legacy T3 field named `MatlabSourceFiles` binds 107 `.m` files because it also includes four archived OPNET inputs. The executed MATLAB code set is 103 files, matching the candidate. No discrepancy was found.
