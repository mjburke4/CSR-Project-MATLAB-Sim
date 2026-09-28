# Short replay results: HOP and MAC pass; receiver harness corrected

The returned MATLAB R2026a Update 5 run used the intended package. All
109 MATLAB file hashes, including all 96 production candidate files, match
the issued v2 ZIP. Both native reference batches remain verified against
the original 8,710 seed-131 and 48,919 seed-132 trace events.

| Check | Returned result | Interpretation |
| --- | --- | --- |
| Source-5 HOP admission | 16/16 admissions match exactly | Passed under the supplied native offer, send and ACK times. |
| Source-5 MAC scheduling | 135/135 transmissions and 153/153 slot draws match; 35 transmissions and 39 draws fall in 300–330 s | Passed under the recorded queue, receiver and draw inputs. |
| Seed-131 discovery receiver | 21/22 selected outcomes match; the single native-positive 4→5 reception is reported as a failure | A replay state-ownership defect invalidates that discrepancy. |
| Seed-132 node-4 receiver | Stopped at 301.628260 s after seven matching decisions | The replay attempted to override a transmission just before its completion callback. The other 248 outcomes were unexecuted. |

## What the passing checks establish

The first-16 HOP fixture supplies 52 boundaries: 16 offers, 20 actual sends
and 16 ACK completions. It reproduces all admission times, application
identities and capacity snapshots. There are four retransmissions and no
pending data at the end. Offer-to-admission waiting matches the native
fixture: mean **9.977604171 s**, maximum **17.761111114 s**.

The broader native node-5 capture records 856 admission probes, of which
830 are denied by per-neighbor capacity and 26 are permitted. Global
capacity is available at every probe. These are repeated checks, not 856
unique applications. The full interval includes 35 local offers and two
relay receptions; the first-16 test does not cover that complete mixed
workload or execute the full production NWK layer.

These results do not justify changing the tested HOP admission or MAC
scheduling rules. The autonomous upstream reception, ACK and capacity-release
history remains the relevant boundary to investigate.

## Why the receiver comparisons need a rerun

The test imported repeated MAC requests to enter Search as independent PHY
inputs. Many were notifications caused by PHY receive or transmit
completion. Preloading those notifications allowed them to run before the
PHY callback that should generate them.

For seed 131, the affected 4→5 reception completes natively at
72.308832444 s. The injected Search action precedes the replay's continuous
completion by 0.469 ns, replacing Track before the receive decision. Three
archived seed-132 positive controls have the same problem, with a 0.365 ns
offset. All 25 recorded outcome comparisons agree on arrival nanoseconds,
collision counts and error counts; only these four success flags differ.
The three controls do not have a captured PHY draw tape and are reported
separately from the primary seed-131 case in v3.

For node 4, a Search refresh at 301.628260 s runs before the same-time
transmit-completion callback and trips the valid ReceiverBusy guard.
The previous input tape also omitted the real Idle-to-Search wake at
300.001 s. Zero matched ACK children in that aborted run is not evidence
that all ten ACKs failed.

## Corrections and next run

The v3 harness derives external wake/sleep inputs from actual state
transitions, retains repeated refresh notifications as audit evidence,
and compares the PHY-owned state transitions as outputs. It adds state
history comparisons and detailed failure diagnostics. It also fixes a
stale MAC report label that said 657–665 seconds; the tested interval and
selectors were already correctly 300–330 seconds.

No production model file, native reference trace, random draw, or expected
packet outcome was changed. The corrected MATLAB execution remains pending;
static and input-binding checks do not establish its behavioral result.

Extract `csr-short-tests-ready-v3.zip`, set MATLAB's Current Folder to
the extracted `two_case_next` folder, and run:

```matlab
report = run_short_tests;
```

Return the generated `out_short_*.zip`. This repeats the four short checks
in one call and preserves the two existing passes as regression checks.
It does not require another 6,000-second simulation. Network parity within
10% remains an open goal.

## Evidence

- Returned archive: `out_short_20260923_174417.zip`, SHA-256
  `55355f63eadb23cc68a546f7f349008761f180b8c29fb20e835df0bdc37a7e0b`.
- Issued v2 archive: `csr-short-tests-ready-v2.zip`, SHA-256
  `73c961bb39733fa7c349d8729fcf79c03933912e6dfd5444599400e39ad7c7c8`.
- The corrected package's `review` folder includes the source/input audit,
  independent source-5 comparisons and receiver failure evidence.
