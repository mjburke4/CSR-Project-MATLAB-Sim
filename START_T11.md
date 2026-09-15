# Tranche 11: matched contention and ACK service

**Revision r1:** the original run exposed a missing ACK-power default in the diagnostic harness. See `FIX_T11.md` for the repair and rerun instructions. All recorded event/draw prefixes matched ns-3; the completed replay and 52 tests still require execution.

This milestone runs four **8-second** controlled MAC/HOP experiments and **52 focused MATLAB tests**, including 21 new tests and 31 retained tests. It does not rerun the 6,000-second campus benchmark.

Extract the package into a short folder, for example **`C:\CSR\csr11`**. In MATLAB, make that folder current and run:

```matlab
report = run_tranche11_validation;
```

Upload the **`t11.zip`** whose complete path MATLAB prints at the end. Results use short directories under `results/t11`. The archive contains the executed source hashes, MATLAB test results, raw contention draws, service events and reference comparisons. A recorded replay difference is useful diagnostic evidence; upload the archive even if the two trajectories differ. If execution fails, the runner also attempts to package the partial evidence.

## What the experiment tests

Nodes 2 and 3 each offer four applications to gateway 1. The real MAC selects and counts down its reservations, and the real HOP layer generates ACKs, tracks outstanding DATA and releases capacity. Each simulator receives the same explicit integer draws **before** its normal reservation-avoidance logic. These inputs replace randomness only inside the validation fixture.

| Case | Source 2 draws | Source 3 draws | Gateway draws | Additional condition |
| --- | --- | --- | --- | --- |
| `ab` | Alternate 3, 7 | Alternate 9, 1 | 1 | Base service sequence |
| `ba` | Alternate 9, 1 | Alternate 3, 7 | 1 | Swap source sequences |
| `slow` | Alternate 3, 7 | Alternate 9, 1 | 28 | Later gateway ACK opportunity |
| `track` | Alternate 3, 7 | Alternate 9, 1 | 1 | Gateway in Track from 0.25 to 0.65 seconds |

The trace follows each offer and admission, actual DATA/ACK transmission, controlled frame arrival, HOP capacity-release callback, deferred wake and next admission. It also records queue state, ACK windows, reservation state and radio settings. Comparing full ordered traces reveals the first disagreement even when final delivery totals match.

The transmission duration is computed by each implementation. The fixture delivers actual emitted frames successfully at the computed transmission end plus one microsecond. It deliberately models no RF errors, collisions, overhearing or half-duplex reception losses. A small synthetic application driver uses the real HOP admission gate; production NWK admission and routing are outside this experiment. Matching this replay would support its prescribed MAC/HOP behavior, not full radio or campus parity.

## Baseline and interpretation

The **124 accepted Tranche 10 MATLAB files are preserved**. New test classes supply the replay draws through the existing stream interface. PHY/ECC, radio policy, routing and the normal random-stream implementation remain as accepted. All earlier tranche runners are included for continuity; their frozen original packages identify their exact accepted source snapshots.

The ns-3 source is pinned to `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Its replay uses two explicitly recorded test-only hooks: one supplies raw draws, and one supplies controlled transport. The comparison retains the distinction between that instrumented fixture and the unchanged native build.

This package is a candidate awaiting your MATLAB execution. The preparation environment does not contain MATLAB; native reference runs and Python report checks are recorded separately from the MATLAB tests you will run.

If the initial service chain agrees under these controls, the next investigation is the campus **4 → 5 → 1** path, including service sharing between locally generated and relayed traffic. If it differs, first inspect the earliest divergent event before changing production policy.
