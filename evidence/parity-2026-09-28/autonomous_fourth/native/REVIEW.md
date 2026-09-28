# Seed 132: missing node-5 Overheard proof

The owner return confirms a specific NWK admission mismatch. At 12.314891086 s, MATLAB creates the deferred Discovery proof but suppresses the separately eligible Overheard proof. The resulting node-5 third transmission at 12.402 s contains 66 bytes in three children; the accepted native capture contains 82 bytes in four children. Both C and D exhibit this same outcome.

| Native/MATLAB child | HOP sequence | Wire bytes | Present in return |
|---|---:|---:|---|
| ACK to node 1 | 1 | 25 | Yes |
| ACK to node 1 | 3 | 25 | Yes |
| Discovery NeighborCheck to node 1, discovery sequence 1 | 3 | 16 | Yes |
| Overheard NeighborCheck to node 1 | 4 | 16 | No |

The native physical TX identifier is 21474836483, node 5 ordinal 3. The incoming aggregate is delivered to node 5 at 12.314891086 s. Its first member ACKs the reciprocal KEY_UPDATE (HOP sequence 2). `NoteKeyUpdateCompletion` calls `EvaluateNeighborAdmission`, which sends the pending Discovery proof and marks `admissionDiscoveryCheckActive`. A following KeyRequest is suppressed because the key was just acknowledged. The subsequent first received NeighborCheck, HOP sequence 3 and subtype Overheard, calls `ProcessHello` → `ProcessNeighborCheck` → `EnsureCheckMessage`. The Discovery-active flag correctly suppresses a Message proof. `ProcessHello` then invokes `EvaluateNeighborAdmission` again. Both keys are complete, the neighbor is inactive and fresh, and no Discovery proof remains pending. Because `overheardValid` is still false, native sends its first Overheard proof immediately despite the active Discovery proof.

This is first-proof eligibility, not an equality-at-retry-deadline occurrence. After sending, native sets the Overheard timestamp to the current time, doubles its initial five-second delay to ten seconds, and schedules its single admission retry for 22.314891086 s. Later not-yet-due evaluations do nothing in native. Exact integer-time `now - when >= delay` has the same deadline-inclusive intent as MATLAB's absolute `now >= when + delay` predicate; arithmetic at later deadlines is outside this occurrence.

MATLAB's `Neighbors.evaluate` instead additionally requires `~entry.CheckActive`. `pendingDiscoveryCheck` invokes `sendCheck('discovery')`, and the shared `sendCheck` sets `CheckActive=true`. This state suppresses the independently eligible Overheard. The returned ordered traces explicitly contain the Discovery send, the incoming Overheard, and subsequent MAC admission of only the Discovery. The actual aggregate is captured in the `mac_state` callback before the TX signature check rejects it; its children were recovered from that callback, not inferred from the divergence record's empty child list.

The narrow observed correction is to remove `CheckActive` from the Overheard **send** predicate. Discovery and Overheard already have separate NWK control owners; MATLAB queue replacement applies only to KEY_REQUEST, so no cancellation or coalescing change is required. Native HOP allocates successive sequences and independently enqueues/resends both proofs. This is a traffic-generation mismatch before MAC packing. Were the smaller aggregate emitted, its 16-byte deficit would also shorten physical receiver occupancy by 16.32 ms at rate 8; delivery and later network consequences remain unmeasured because the strict replay stops before that divergent transmission is injected.

## Adjacent ownership condition tested in the same investigation

An additional concrete source difference concerns the flag that suppresses Message proofs. Native sets `checkMessageActive` only in `EnsureCheckMessage`; `SendNeighborCheck` does not set it for Discovery, Overheard, Verify, or NoPath. MATLAB's shared `sendCheck` sets its corresponding `CheckActive` for all subtypes. Therefore an outgoing Overheard, with no Discovery proof active, can incorrectly suppress the subsequent Message proof in MATLAB.

The new C++ component probe exercises untouched pinned native implementations using public APIs. An authenticated KeyUpdate is generated using `CsrHopSecurityState`, received by the actual HOP layer, and completed by a valid historical bare ACK. The NWK public `ProcessHello` callback then receives Overheard controls. An unattached MAC retains queued frames; its existing null-device guard prevents radio scheduling. The probe does **not** call `Simulator::Run`, create a channel or device, override private state, or execute another network simulation.

| Component setup | On key-send ACK | On first incoming Overheard | On repeated incoming Overheard |
|---|---|---|---|
| No pending Discovery | Send Overheard | Send Message | Send neither |
| Pending Discovery | Send Discovery | Send Overheard; Message suppressed | Send neither |

Both cases passed. They support a separate candidate that sets `CheckActive` only for the Message subtype. Preserve all existing success, failure, reset, stale, and activation clears: native itself clears `checkMessageActive` on every NeighborCheck success/failure, irrespective of subtype. No generalized ownership redesign is justified by these tests. Discovery-active suppression remains independent and unchanged.

## Final candidate review

The final E candidate removes only `CheckActive` from the Overheard send predicate. F adds only the Message-specific flag assignment. The existing MATLAB `elseif ~entry.CheckActive` retry-rescheduling branch is retained, avoiding a second direct timer edit. That baseline branch is not equivalent to native's no-op when not yet due; F changes flag values and can consequently change its reachability. This remains an explicit timer-fidelity limit, not a validated ownership redesign.

All eight candidate transformations reproduce their target bytes and reverse exactly to their stated source bytes, with every declared SHA-256 verified. All 99 baseline model files match the preceding kit. The runner requires the accepted natural source gate, uses separate E and F simulations with nanosecond transport timing, and runs F after a diagnostic stop in E. Existing inline KEY_REQUEST behavior is inherited unchanged, including the failed-admission fallback whose full-queue behavior has not been validated against native. `candidate_scope_review.json` records the exact reviewed hashes and limits; `review_candidates.py` reproduces those static checks. No MATLAB runtime pass is claimed.

## Evidence and reproduction

- `native_causal_excerpt.txt`: source-line-numbered original native log, including enqueue order and TX size.
- `C_timing_causal_excerpt.jsonl`, `D_inline_key_causal_excerpt.jsonl`: original returned ordered observations.
- `returned_causal_summary.json`, `native_expected_tx.json`: complete child accounting and send history.
- `source_excerpts.txt`: relevant native and MATLAB implementations with original line numbers and SHA-256 hashes.
- `check_ownership_probe.cc`, `.log`, `compile_command.json`, `compile.log`: actual component implementation, invocation and successful native results.
- `evidence_receipt.json`: pins, input hashes, scope and extracted native subtype assertions.
- `candidate_scope_review.json`, `review_candidates.py`: final E/F scope, byte comparisons and runner-gate review.

Run `python autonomous_fourth/native/analyze_return.py` to regenerate the extraction. With the pinned native environment restored at `autonomous/native_env`, `python autonomous_fourth/native/run_component_probe.py` rebuilds and executes only the component probe. The CSR pin is `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; ns-3 engine pin is `6b5cd24ea80713ce16d88575869aedd6f432bdae`. Build identity is recorded by the hashed `autonomous/native_env/build.json` input. Native fixture and production sources were not edited. MATLAB candidates have not been executed by this review.
