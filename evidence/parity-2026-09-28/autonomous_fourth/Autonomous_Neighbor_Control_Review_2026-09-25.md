# Seed-132 neighbor-control return review

The two-case return confirms a real startup timing improvement and isolates the next missing control. With nanosecond receiver callbacks and inline KEY_REQUEST admission, MATLAB's first 40 random requests match ns-3 in order, context, value and rounded-nanosecond request time. Its first six physical transmissions pass the semantic checks. Both returned cases then stop at node 5's seventh network transmission: MATLAB packs three frames totaling 66 bytes, while native packs four totaling 82 bytes.

The missing 16 bytes are a specific neighbor check that MATLAB suppresses because another check is active. This is a control-generation difference upstream of the MAC packing code. The related message-proof flag also has a source-level mismatch, so the next package tests these two narrowly scoped changes separately in one command.

## Actual execution and provenance

The owner archive is `out_auto_20260925_133710.zip`, SHA-256 `0e949fe13da40fa02251875d26d6be1ac6ea7637e323bc07d47d46e8c49a5b11`, containing 46 members. MATLAB R2025a 25.1.0.2943329, PCWIN64 executed both cases. Its manifest matches all 156 issued files. Native import preflight and all seven KEY_REQUEST public-API checks passed. Natural case A was reused after its runtime, source, configuration and exact trace gates passed; no new natural simulation occurred.

| Result | C: callback timing only | D: timing + inline KEY_REQUEST |
|---|---:|---:|
| First node-5 KEY_REQUEST TX | 11.648 s | **11.635 s**, matching native |
| First node-3 KEY_REQUEST TX | 11.986 s | **11.973 s**, matching native |
| Matched random contexts and values | 40/40 | 40/40 |
| Requests with different rounded-ns times | 13 | **0** |
| Positions differing in global request order | 4 | **0** |
| Physical transmissions passing semantic checks | 6 | 6 |
| First guarded stop | 12.402 s | 12.402 s |

The 40 samples comprise 11 MAC slot draws, 17 SYNC thresholds and 12 PHY samples. An unconditional comparison confirms no missing, extra or reordered random requests in D through this stop. The previous node-4 payload request now passes with 183 tested bits in both cases.

The inline correction starts node-3/5 MAC preparation at their receive-completion times, 11.500308077 and 11.500311086 s. C waits until 11.505 s. Both use the native reservation counters, 27 and 10, but the different preparation time costs C one 13-ms transmission slot. D corrects that observed timing difference.

C and D nevertheless have the same 36 emitted PHY signal-end decision records after removing time: the same receiver identities, error counts, decisions and reasons. Their ten generated neighbor-control requests also have the same ordered semantic content. Thus the result demonstrates local scheduling parity and a corrected request sequence, not an observed improvement in packet delivery before the common stop.

## The entire 16-byte difference is accounted for

At 12.314891086 s, node 5 receives a gateway aggregate containing an ACK for its KEY_UPDATE, a KEY_REQUEST and an overheard neighbor check. Completing the key exchange queues node 5's deferred discovery response. Processing the incoming overheard check then makes the next overheard proof eligible in native.

| Child at node-5 TX #3, 12.402 s | MATLAB | Native |
|---|---:|---:|
| ACK, HOP sequence 1 | 25 bytes | 25 bytes |
| ACK, HOP sequence 3 | 25 bytes | 25 bytes |
| Discovery check, HOP sequence 3 | 16 bytes | 16 bytes |
| Overheard check, HOP sequence 4 | **Absent** | **16 bytes** |
| Total | **66 bytes** | **82 bytes** |

The failed transmission is node 5's third physical transmission and the seventh attempted transmission across the network. The harness stops at its context check before sending the mismatching aggregate into the channel. Its compact divergence record leaves `children` empty because the parent count check fails first; the preceding complete MAC aggregate record provides the actual three-child inventory above.

With the same rate and preamble, omitting those 16 bytes would shorten the signal by **16.32 ms** at this profile's rate-8 setting. This identifies a concrete way that a missing generated control can change subsequent receiver availability. It is a duration calculation; the strict stop prevents observation of that divergent transmission and its later network effects in this return.

MATLAB `Neighbors.evaluate` requires `~entry.CheckActive` before sending an eligible overheard proof. The queued discovery response has already set this generic flag. Native `EvaluateNeighborAdmission` has no active-proof exclusion on this branch: it checks whether an overheard proof has been sent and whether its deadline has expired. In this captured occurrence, `OverheardValid` is false: the suppressed frame is the **first eligible overheard proof**, not a retry deadline edge. Existing NWK replacement applies only to KEY_REQUEST, so discovery and overheard controls can remain distinct reliable owners.

## Two bounded corrections

**E: restore overheard-proof eligibility.** Retain the timing and inline KEY_REQUEST behavior demonstrated by D. Remove only the extra active-check exclusion from the overheard send predicate. Preserve stale/active-neighbor gates, both key requirements, pending-discovery behavior, backoff, the existing not-yet-due branch and ordinary reliable-control ownership. Native performs no action when the overheard deadline is not due; changing MATLAB's existing retry rescheduling is outside this candidate's scope, and full timer-order equivalence is not claimed.

**F: E plus message-proof flag scope.** MATLAB currently sets `CheckActive` for every check subtype. Native sets `checkMessageActive` only when starting a message proof; discovery has a separate active flag, and sending an overheard proof does not claim message-proof ownership. With no discovery proof active, an outgoing overheard check can therefore wrongly suppress MATLAB's response to a subsequently received overheard check. F sets the existing flag only for subtype `message`, leaving all existing completion/failure resets intact. It introduces no new ownership mechanism.

Keeping E and F separate lets the returned timelines distinguish the captured missing-overheard correction from the related message-response correction. Public-API preflight checks exercise control coexistence, deadlines and flag scope. These are bounded behavior tests; they do not replace the coupled network result. The original 99 model files remain unchanged, with candidate classes and exact reversible transformations recorded separately.

An actual native public-API component probe passed both branches. After real HOP key exchange and its ACK, an incoming overheard check adds an overheard proof when a discovery proof is active, or adds a message proof when only an outgoing overheard proof exists. A repeated incoming check adds neither a duplicate message nor an early overheard retry. The probe uses an unattached MAC to retain queued frames, without a radio device, channel, private-state access or `Simulator::Run`. It validates the native branch behavior, not a new network outcome.

## Run the next batch

Download `autonomous-neighbor-check-tests.zip`, extract into a fresh folder, restart MATLAB and set Current Folder to the extracted `autocase` directory. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including diagnostic stops. E and F each start all seven nodes at zero and run to their first semantic divergence or 330 seconds. A diagnostic stop in E does not prevent F. The accepted natural A is reused when its gates match; C and D are retained as actual historical diagnostic results and are not rerun. No ns-3 command or new 6,000-second MATLAB run is needed from the owner.

On return, verify preflight and provenance first, then check that the earlier matched D prefix remains intact and whether node 5 now produces the expected fourth child at 12.402 s. Compare the next control-generation and receiver-availability differences between E and F. Exact bit-count, draw-context, transmission and unused-input guards remain in place.

## What this does and does not establish

This return supports retaining the existing nanosecond receiver-callback option and inline KEY_REQUEST candidate for the continued investigation. The new neighbor candidates have source-grounded scope, independent review and static validation; their MATLAB runtime results remain pending.

The **±15% full-network target remains open**. Both actual coupled cases stop before application traffic begins at 300 s, so they contain zero application attempts. They cannot measure 6,000-second admission, delivery, unfinished traffic or latency improvements. Those remain the final accounting criteria once the autonomous control paths are sufficiently aligned.

The evidence archive includes the owner return, exact issued and new kits, native observations, reproducible audits, independent source reviews and validation receipts. The unchanged native capture supplies the comparison; no new long network simulation was commissioned for this review.
