# Independent terminal regression review

This is a source and evidence review, not a MATLAB execution. The second returned ZIP establishes the first terminal check: the old HOP clears both queued copies and the candidate retains both copies after one owner failure. The second check stops on a generic assertion; the remaining checks and 330-second replay were not executed.

## Failure cause

The issued helper constructs six anonymous getters before the test runs: `Releases`, `Terminals`, `Deliveries`, `TransmissionTimes`, `TerminalTimes`, and `CancelCalls`. Each captures a value array or scalar, initially empty or zero. Later named callbacks mutate the harness shared variables, while the anonymous getters continue to return their captured initial values. The named `Evidence` callback already observes the shared workspace correctly. Replacing all six with named nested getter callbacks addresses the same problem consistently. Capturing the MAC handle or cleanup registry handle by value is valid because these are handle objects, unlike the mutable arrays and counter.

MathWorks primary references:

- [Anonymous Functions](https://www.mathworks.com/help/matlab/matlab_prog/anonymous-functions.html): the Variables in the Expression section documents capture at handle creation.
- [Nested Functions](https://www.mathworks.com/help/matlab/matlab_prog/nested-functions.html): the Sharing Variables section documents mutation of the shared parent workspace.

## All 16 expectations reviewed

| Check | Source-derived expectation | Review |
|---|---|---|
| Terminal retention | At 10.000001 s, old queue is 0 and candidate queue is 2; each failed DATA owner count is 1. | Actual first case passed in return. |
| Release and cutoff fate | Candidate HOP owner and neighbor outstanding are 0; NSDP release and terminal callback each occur once; MAC copies remain unresolved. | Named getters required. No app-loss inference permitted. |
| Default policy | Old and candidate actual-tx component evidence match; production default stays actual-tx. | Guard applies only to native-provisional retry_exhausted DATA. |
| Real MAC drain | Releasing Track to Search drains both retained copies, with one receiver first delivery and one duplicate; no HOP owner recreation. | Queued copies have same sequence; ACK receiver callback is accepted but is not sent to transmitter. |
| Orphan exact ACK | Clears two DATA copies, leaving failed count 1 and release/terminal counts 1; repeated feedback has no ownership effect. | Independent MAC cleanup is DATA-only. |
| Orphan window ACK | Same ownership and two-copy cleanup result. | ACK bitmap drives sequence cleanup. |
| Orphan window DACK | Same ownership and two-copy cleanup result, with no new DACK hold. | Unknown HOP owner is not recreated. |
| Single DACK | No-window DACK leaves both copies and does not mark Dacked. | Disabled native single-DACK path remains disabled. |
| Window wrap and peer | ACK bit 1 removes sequence 0; DACK bit 2 removes 65535 at peer 2; 65534 and peer 3 sequence 0 remain. | Modulo-65536 calculation and peer predicate are exact. |
| Overlap | Coincident ACK/DACK bit prefers ACK, releases once, acknowledges once. | DACK bitmap excludes ACK bits. |
| Grouped exact ACK | Partial and completed exact ACKs finish HOP routing ownership but retain the grouped MAC routing copy. | DATA-only orphan cleanup cannot remove CONTROL. |
| Grouped window ACK/DACK | DATA window feedback neither completes nor cancels grouped routing ownership. | `allowControl=false`; queue remains one. |
| Rejected retry | MAC rejection at first retry releases owner once with mac_queue_full and calls existing generic cancel once. | Suppression guard is retry_exhausted only. |
| Unmatched sent fallback | At 10.1 s exactly one MAC slot is pending. First unmatched DATA sent adds one scan; repeated sent does not add another. At 13 s only the MAC slot remains. | Scan at 12.100001 s; no confirmed control owners remain. |
| Live DACK | At 2.1 s DACK releases NSDP once but keeps global/neighbor capacity in one hold until 22.100001 s. At 23 s hold expires once. | One retry means 20-second hold, not doubled hold. |
| Control expiry | Explicit sends at 0, 2.1, and 4.2 s cause retries at 2.000001/4.100001 and failure at 8.200001 s. Generic cancellation removes the original queued control copy. | No DATA failure; one generic cancel. |

## Batch requirements

The repair should execute every case with fresh component state. Each case should have an exception boundary, recorded actual and expected evidence, and public callback/event chronology. One failed case must not prevent the other cases from producing evidence. After all cases, an aggregate failure must still block the network replay. This improves diagnostics without weakening any acceptance assertion.

## Final rewritten-helper review

The repaired helper was reviewed line by line. All 16 original acceptance predicates are preserved or strengthened. Cutoff and drain now use their own freshly constructed episodes; all harness folder names are distinct. The six getters are named nested callbacks, and their returned counts are also included in state snapshots. The actual-tx equivalence evidence contains behavioral values only; differing class names, paths, or callback metadata cannot cause false failure.

Per-case exception collection now records failures and continues. The final aggregate error still blocks the 330-second replay. The public callback files contain serializable plain structs, scalar/array values, and cells; they contain no handle objects or function handles. These files describe component callback chronology, not a complete scheduler or PHY trace.

A byte comparison of every MATLAB file in the previous v2 kit versus v3 finds exactly one changed MATLAB file: `+ac/terminalPreflight.m`. The runner, production model, and terminal candidate implementation are unchanged.

No further source-level blocker was found. MATLAB execution is still required; parsing and manual source review cannot certify runtime success.
