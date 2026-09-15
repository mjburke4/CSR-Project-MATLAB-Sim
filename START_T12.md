# Tranche 12: service sharing on 4 → 5 → 1

**Revision r1:** If Tranche 12 is already installed, apply `t12fix.zip` in place and follow `FIX_T12.md`. The first return identified a relay-fixture callback construction error; the repair requires a new MATLAB run. The clock component passed independently.

This milestone compares relay-only, local-only and mixed application traffic on a fixed three-node chain. Node 4 sends through node 5 to gateway 1; node 5 also generates its own applications. The question is how node 5 shares admission capacity and radio service between those two sources.

The runner executes **72 focused MATLAB tests** (20 new and 52 retained), four 24-second relay/local cases and six small clock-boundary cases. The new fixtures contain 164 relay-service checks and 72 clock checks.

Extract **csr12.zip** into a short folder such as **`C:\CSR\csr12`**. In MATLAB, make that folder current and run:

```matlab
report = run_tranche12_validation;
```

Upload the **`t12.zip`** whose complete path MATLAB prints at the end. Results use short subdirectories under `results/t12`. Upload the evidence even when the native comparison reports differences. The runner retains diagnostic failures and partial test results, and attempts to package them before reporting an execution error.

## Relay and local traffic

Four **24-second** cases use prescribed contention draws. Application offers stop at 16 seconds; a snapshot at that point and the final snapshot expose temporary DACK holds and their later expiration.

| Case | Node 4 | Node 5 | Purpose |
| --- | --- | --- | --- |
| `relay` | 20 applications | No local applications | Isolate relayed traffic |
| `local` | No applications | 20 local applications | Isolate node 5's own traffic |
| `mix` | 20 applications | 20 local applications | Exercise shared service |
| `sw` | 20 applications | 20 local applications | Swap source draw sequences |

The finite source driver applies the existing admission-limit rule of 16 using the actual NWK admission state. It replaces the normal traffic generator for these controlled offers. Applications accepted by NWK pass through its production queue and relay-custody handling, HOP flow control, MAC transmission, real ACK processing and capacity release. The trace retains original source identity, node 5's waiting and custody counts, per-source outstanding counts, MAC queues, reservations and radio settings. It separately records HOP capacity held by DACKs, which can remain reserved after application custody has been released.

The network starts with explicitly established neighbors and a fixed route. Security admission and route convergence are outside this experiment. Bootstrap routing controls are kept out of radio service under declared fixture settings, and each implementation's remaining control work is reported separately. Their control queues are not asserted to be equivalent.

Radio service is fixed at 128 kbps and +33 dBm. The fixture delivers actual addressed frames successfully at source-computed transmission end plus one microsecond. It does not model RF errors, collisions, overhearing or half-duplex receive losses. These controls isolate application and relay service; they do not establish full campus or radio parity.

## Clock-boundary diagnostics

Separate small cases use the real scheduler and MAC to examine packet arrival before, at and after a slot tick. They retain continuous-time scheduling alongside an explicit integer-nanosecond transport option. This investigates the Tranche 11 ordering residual without changing the production scheduler, the existing MAC clock or the validated Tranche 11 fixture.

The continuous case intentionally preserves the known clock-order difference. Its three differing observation rows can produce `ClockMatchesNative=false` while all clock tests pass; the other five cases separately require matching integer-time behavior. The relay comparison remains an open measurement for your MATLAB run.

## Baseline and evidence

All 241 source files recorded in the successful Tranche 11 owner run, including 130 MATLAB files, are preserved. This includes the 225-file / 124-MATLAB-file Tranche 10 accepted baseline. The runner checks both snapshots before execution and verifies source and reference stability afterward. Earlier tranche runners remain included.

The source ns-3 commit is pinned to `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Native reference preparation and Python evidence checks are recorded separately from the MATLAB execution performed on your machine. A completed differing trace remains diagnostic evidence; exact replay matching and full-network parity are separate conclusions.

Native preparation completed all 120 applications and 180 hop-by-hop NSDP releases. The mixed native cases have four and one DACK holds at 16 seconds, respectively, and none at 24 seconds. All six native clock cases passed their 72 checks. These are native reference results. The first MATLAB R2025a return passed all 72 clock checks but aborted the relay cases on a fixture callback error. MATLAB execution of this repaired candidate remains pending; see `FIX_T12.md`.

This package does not require the 6,000-second campus benchmark. Preserve `t12.zip` so the first difference can be inspected before any production policy change is considered.
