# Autonomous seed-132 return: findings and harness repair

25 September 2026 · Native means the ns-3 C++ reference · Network target remains ±15%

**The natural MATLAB diagnostic passed. The common-input case stopped on a harness error before consuming its first native random value.** This return strengthens the explanation for the autonomous differences, but it does not yet test network behavior under shared random inputs.

The reviewed input is `out_auto_20260925_124644.zip`, SHA-256 `68050a440c5dbb8c6cbde373e26d806228836aa7d87f6c188adc8ee76dce0b9c`. Its 29 archive members pass the ZIP integrity check. The returned source manifest exactly matches all 119 files bound in the issued kit. Execution was MATLAB R2025a, version 25.1.0.2943329, PCWIN64.

## Natural capture passed in MATLAB

The owner run completed to 330 seconds in approximately 5.1 minutes. Its three baseline tables are byte-identical to the bundled corrected 6,000-second reference prefix over `0 ≤ time < 330`:

| Table | Rows | Result |
|---|---:|---|
| Protocol | 12,200 | Exact match |
| PHY | 12,198 | Exact match |
| Application attempts/admissions | 9,000 | Exact match |

This is actual MATLAB runtime evidence that the passive diagnostic changes preserved the original natural prefix. The independent offline audit also compares every CSV field and verifies the hashes. The service observer captured all 20,365 in-window records with no omissions and complete cancellation pairs.

## Random choices are now directly observed

The previous report inferred the first MATLAB discovery slot from transmission timing. The new draw log confirms it directly:

| Request | MATLAB slot | ns-3 slot |
|---|---:|---:|
| Gateway discovery, 10.01 s | 10 | 11 |
| Node 7 initial application contention, 300.001 s | 19 | 6 |
| Node 8 initial application contention, 300.001 s | 10 | 18 |

The node-7 and node-8 requests have matching slot bounds, profile, local active population, MAC state, and own reservation state. Their prior draw counts already differ: node 7 is at MAC draw 40 in MATLAB versus 45 in native, and node 8 is at 70 versus 56. These are comparisons at corresponding semantic events, not assertions that equal ordinals or complete network states match.

The gateway's reported population differs by one, but the fixed MAC profile does not use that field. Its relevant slot-selection inputs match. Equal numeric seeds therefore cannot be used as evidence of identical realized random inputs.

## Receiver availability and the first traffic race

The passive state records directly confirm the MATLAB states previously inferred at application startup: node 2 is Idle; nodes 4, 7 and 8 are Search. The native reference has node 2 in Search and node 4 in Idle.

Node 8's first MATLAB DATA transmission starts at 300.144 s with a long preamble. The direct neighbor snapshot records its last reception from node 2 at 268.730555 s: an age of 31.413 s, beyond the applicable 20 s freshness threshold. That threshold uses a local active-node count of three, including self.

The resulting receiver history directly shows node 7's countdown frozen at eight for **95 Track-state slot ticks**, from 300.157 through 301.379 s. Node 7 eventually transmits at 301.496 s. Native node 7 transmits first at 300.092 s, creating a different sequence of receptions and feedback at node 8.

| First source-7 application | MATLAB, s | ns-3, s |
|---|---:|---:|
| DATA transmission starts | 301.496000 | 300.092000 |
| ACK releases source custody | 302.029292 | 300.547292 |
| Replacement application admitted | 302.040000 | 300.560000 |

These records connect different realized contention and receiver histories to the first differing admission. They do not establish that a random-choice difference alone explains every later receiver event or the entire 6,000-second latency gap.

## All short-window admission decisions close against custody

The audit reconstructs each source's custody count from its recorded admissions and source-custody releases. All 9,000 attempts have the expected count, and every admission decision matches the same `NSDP < 16` rule. There are 226 paired attempt outcomes that differ between engines, each explained by the state supplied to that gate.

| MATLAB source | Attempts | Admitted | Blocked by custody limit | Source custody released | Still in source custody at 330 s |
|---|---:|---:|---:|---:|---:|
| 2 | 1,500 | 29 | 1,471 | 13 | 16 |
| 3 | 1,500 | 60 | 1,440 | 44 | 16 |
| 4 | 1,500 | 24 | 1,476 | 8 | 16 |
| 5 | 1,500 | 26 | 1,474 | 10 | 16 |
| 7 | 1,500 | 37 | 1,463 | 21 | 16 |
| 8 | 1,500 | 31 | 1,469 | 15 | 16 |

Source custody release is not synonymous with gateway delivery. These counts describe the source admission gate, not an end-to-end delivery or latency population. The offered schedules remain identical and consume no traffic RNG draws.

## Why the common-input case stopped

At 10.01 s, the first MAC request reads a row whose `component` field is correctly blank: `component` applies to PHY header/payload draws. MATLAB imports that blank as a missing string. The original `Streams.take` converted it to a character vector unconditionally, raising `MATLAB:string:CannotConvertMissingElementToChar`.

The return contains one attempted native draw, **zero consumed native draws**, zero verified physical transmissions, and no common-input application traffic. A default “no mismatch recorded” flag in that incomplete summary is not a successful comparison.

The repair is confined to the diagnostic harness. It normalizes valid empty text and explicitly types imported fixture columns, while requiring the applicable numeric and text fields for each random purpose and packet kind. A missing PHY component remains an error; no component, draw, receiver state, or packet outcome is invented. Network model and native fixture bytes remain unchanged.

## Continue the existing test

Use the separately packaged repaired kit. It retains the accepted natural-case evidence with source and data hashes, reruns the exact prefix comparison on those saved tables, and reuses that result only on the same MATLAB runtime. A different runtime performs a fresh natural case. Reuse is explicitly reported as an accepted prior run; it is not presented as a new simulation.

The same command launches the remaining common-input investigation:

```matlab
report = run_autonomous_tests;
```

Restart MATLAB and run from the newly extracted `autocase` folder. Return the printed `out_auto_*.zip`, including any diagnostic stop. The repair includes a small import regression preflight. Local syntax and source reviews do not substitute for execution in MATLAB; the repaired common-input case remains pending the owner run.

No production behavior fix is supported by this return. The next meaningful result is the first semantic difference, or the matched prefix, from the repaired autonomous common-input case. The ±15% full-network performance target remains unmet.
