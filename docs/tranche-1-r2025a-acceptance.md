# Tranche 1 portable R2025a acceptance

**Accepted on owner-reported MATLAB execution evidence, recorded 2026-09-08.**
The owner ran `run_tranche1_validation` on MATLAB
`25.1.0.2943329 (R2025a)`, release `2025a`, using the portable backend.
All **72 tests passed**, with zero failures or incomplete tests, followed by
successful completion of all nine PHY scenarios and the runner's final
success message. Test-suite elapsed time was **4.6861 seconds**.

The run is associated with the delivered implementation commit
`3f63b811d51dc8e93548586cc7e6994981adac13`, referencing CSR ns-3
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. No runtime source hash was supplied.
Evidence is the owner's pasted console output; exported MAT/CSV/JSON files
have not been independently inspected. No MATLAB execution occurred in the
assistant workspace. Structured evidence is in
`evidence/tranche-1-r2025a-acceptance.json`.

| Scenario | Generated | Received | Dropped | Pending | Physical received | Overheard | Collision observations | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 6 | 6 | 0 | 0 | 12 | 6 | 0 | 0.031542 |
| overhearing | 6 | 6 | 0 | 0 | 12 | 6 | 0 | 0.040698 |
| collision | 2 | 0 | 2 | 0 | 0 | 0 | 2 | 0.020355 |
| mixed_rate | 2 | 1 | 1 | 0 | 1 | 0 | 2 | 0.012476 |
| weak | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0026509 |
| band_mismatch | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0.003455 |
| closure | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0.0024139 |
| high_rate_500 | 6 | 6 | 0 | 0 | 12 | 6 | 0 | 0.029417 |
| high_rate_1000 | 6 | 6 | 0 | 0 | 12 | 6 | 0 | 0.029765 |

Runtimes are displayed values from this single run, not performance benchmarks.
All fixtures conserve intended packet custody:
`generated = received + dropped + pending`. The passing tests additionally
check physical accounting, airtime,
error/ECC boundaries, repeatability, trace limits and finite-horizon custody.
`Collisions` counts completed receiver/signal observations with overlap; it
does not count unique collision pairs or require every affected packet to fail.
Clean and overhearing use the same traffic configuration and are not independent
statistical replications.

The original controlled fixture also passed: six generated/transmitted/received,
zero dropped/pending, 384 application bytes, delivery ratio 1, displayed mean
latency 1.1138 seconds, and goodput 307.2 bit/s. Its six physical receives and
zero overheard observations belong to controlled transport; the clean CSR PHY
fixture above has twelve physical receives and six overheard observations.

## What this accepts

The integrated portable PHY/channel/traffic foundation is operational on the
reported R2025a installation. All five `TestCppBerReference` methods passed,
covering 400 independently generated original C++ reference vectors for BER
curves, collision samples, quantization and rate intervals. Curve comparisons
use the tests' absolute tolerance of 2e-14; this is distinct from the earlier
300,632 exact C++ versus converted-data checks performed outside MATLAB.

The installed path did not expose `wirelessNetworkSimulator`, `wnet.Node` or
`wirelessPacket`. The portable gate completed without those symbols. Adapter
implementation flags are capability descriptions, not proof of native execution.

## Remaining scope and next tranche

R2026a portable execution and the five native tests remain unvalidated. Full
native CSR packet transport, equivalent MATLAB/ns-3 network scenario comparisons,
and MATLAB/OPNET aggregate comparisons remain outstanding. Existing source-side
ns-3 smoke success and MATLAB reference-vector success do not establish full
network parity.

The receiver remains awake and each sender uses FIFO serialization. Operational
MAC/HOP queues, access, slots/reservations, ACK/DACK, retries and duty cycling are
the next cohesive implementation tranche; autonomous routing follows in T3.
This accepts Tranche 1's portable endpoint, not the full CSR research baseline.
No implementation change or repeat R2025a run is required by this result.
