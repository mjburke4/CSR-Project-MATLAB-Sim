# Autonomous contention: capture and common-input feasibility

25 September 2026. Initial static assessment, updated after native recovery and capture. This reviewer did not run a simulation or edit production source; the parallel native capture team subsequently completed the reference run described below.

## Updated execution status

The pinned native runtime was recovered during this investigation. The passive native 0–330-second capture now passes exact equality against **48,919 canonical rows × 30 fields**. It supplies **4,430 common-input variates**: 928 returned MAC integers, 1,960 actual SYNC thresholds and 1,542 PHY uniforms, plus 70,441 receiver/timer observations. Independent review matched all 928 MAC samples, including times, ranges and ordinals, to the already accepted all-node tape (`native_tape_review.json`). `autonomous/native_capture/receipt.json` is the execution authority; earlier availability notes below describe the recovery prerequisite, not a remaining native blocker.

The new MATLAB kit at `autonomous/kit/autocase/` contains both full-campus cases and the `run_autonomous_tests` entry point, with endogenous receiver availability and feedback. `autonomous/design/instrument_observers.py` provides 35 source-hash-bound passive insertions into copied scheduler/MAC/PHY files; removing those insertions exactly recovers all three production sources. A subsequent full transformation check also reverses all sampler/export edits and recovers all 99 baseline model artifacts exactly (94 unchanged, five declared validation copies). These are static preservation checks, not MATLAB runtime passes. The owner runtime must still execute the diagnostic and its observer equivalence gate.

## Recommendation

Do not issue the previously accepted forced-MAC replay again. Start by comparing the existing all-node native 300–330-second receiver observations, MAC random tape from time zero, and corrected MATLAB protocol/PHY/application-admission tables. If that cannot distinguish a state-machine mismatch from different random histories, the next owner package should contain **one natural short diagnostic and one genuinely coupled common-input experiment**, with the second case enabled only after its native executable and source-bound reference exist.

Keep the original seven-node campus topology for the natural diagnostic and, preferably, the coupled case. The 7→8→2→4 path is the analysis focus, not a reason to delete nodes 1, 3 and 5. Deleting those nodes changes discovery, overhearing, contention, active-node counts, and downstream drain. A reduced four-node experiment is useful as a mechanism demonstration but cannot recreate the original seed-132 autonomous history.

## What the existing code provides

| Requirement | Available | Missing or constrained |
|---|---|---|
| Application attempts and admission gates | `ApplicationGenerator` emits source/attempt identity, accepted/reason, discovery/topology/gateway state, per-flow NSDP and NWK queue size | The long-run table is already sufficient for comparing deterministic attempt schedules and endogenous gating; shared traffic must mean shared **attempts**, not forced equal admissions |
| Ordered MAC/HOP/NWK callback details | Optional `AckServiceDiagnostics(maxRecords,[0 330])` receives full protocol `details` before ordinary trace flattening; preserves `DetailsJSON` and its own `ObservationId` | Observer does not provide a common ordinal across PHY, timer and random events because those callbacks do not enter this observer |
| MAC state / reservation preparation | Production MAC emits `mac_state` with `State` and `mac_prepare` with reservation slot/counter; observer preserves these | State-change cause, timer firing/scheduling/cancellation, queue/neighbor state at all decisions, and raw slot draw are not emitted |
| ACK/DACK admissions, replacements, transmissions | Existing observer inherits `LinkDiagnostics`; full production network generates feedback normally | Trace must also preserve full cumulative control contents, physical aggregate children and per-application semantic identity for robust comparison |
| PHY signal arrival / track / interval / outcome | `SignalEngine` has optional trace callback and state callback; ordinary PHY table retains selected fields | `NetworkSimulation.recordPhy` flattens details and does not feed service observer; raw normal/uniform draw, interval semantics and all state/timer causes are missing |
| Uniform PHY sampling | `Model.allocateErrors` accepts an owned `RandStream` **or scalar supplier function**, including source-style binomial arithmetic | `SignalEngine` currently passes its internal PHY stream directly. Its SYNC threshold is a direct `randn` call |
| Common MAC sampling | Prior validation adapter consumes captured draws | Production `mac.Layer` directly calls `randi`; prior adapter also forces recorded receiver availability and therefore is not an autonomous network driver |
| Common traffic sampling | `ApplicationGenerator.attempt` already accepts a `draw()` callback | Current seed-132 flows all use fixed destinations, so destination randomness is not needed for this scenario; no claim of matching source admission is justified until gates are compared |
| Common stream ownership | MATLAB streams have explicit per-node subsystem mapping | MATLAB `mt19937ar` mapping explicitly does not promise ns-3 stream equivalence; same numeric seed cannot synchronize trajectories |

`NetworkSimulation` constructs `RandomStreams` internally and constructs the production MAC/PHY objects internally. Its optional arguments are the diagnostics observer and `TransportTiming`; there is no current whole-network random-provider injection point. An observer alone cannot turn this into the required common-input experiment.

## Existing native evidence worth reusing

`next_feedback/short_kit/two_case_next/native/seed132/` contains:

- An exact-prefix accepted native run from 0 to 330 seconds; `reference/fidelity.json` binds source commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` and engine commit `6b5cd24ea80713ce16d88575869aedd6f432bdae`.
- MAC inputs, actual random integers, complete queued frames, actual transmitted children and raw wire bytes for **all seven nodes**, from time zero.
- `capture/source5_native.tsv`, despite its name, observes all seven nodes in **[300,330)**. It captures PHY arrival, acquisition, SYNC threshold values, BER interval uniforms, actual receiver-state transitions, MAC service and queue/admission observations. Its observer selects nodes 1,2,3,4,5,7,8.
- One detailed clean receiver boundary snapshot at t=300 for **node 4 only**. That is not a whole-network checkpoint.

The native PHY draw counters advance before 300 seconds, but the draw rows are discarded outside the observer's [300,330) window. The all-node startup PHY tape is therefore unavailable here. Captured MAC inputs cannot supply the missing endogenous PHY/wake history without reintroducing the already tested forced boundary. Starting an autonomous coupled run at t=300 requires all relevant NWK/HOP/MAC/PHY state and event deadlines, not just node-4 idle/search state. Running from time zero is safer and simpler than inventing an incomplete checkpoint.

The prior discovery and receiver replay classes demonstrate exact keyed draw checks and reusable source-bound sampler seams. `DiscoveryReplaySampler` / `Source5ReceiverSampler` insist on capture-local TX identity, interval/component, timestamp and consumption order. They are suitable for a fixed transmitted-signal replay. They are **not** plug-and-play common-random-number providers after autonomous histories diverge: one missing TX or interval must report a divergence, not silently remap or reuse unrelated draws.

## Proposed two-case package

### Case A: natural seed-132 diagnostic

Run the corrected MATLAB model from 0 to 330 seconds with original geometry, traffic attempts, discovery, duty cycle and generator configuration. Preserve the [0,330) random/state chronology or a compact startup stream plus fully detailed [295,330) event stream. Do not stop at 300 and pretend to initialize independently.

Passively record a common observation ordinal with time, event cause, node, original source/destination/attempt identity, HOP sequence, MAC queue/frame identity and physical aggregate identity. Required fields:

1. Application attempt and all gating results; actual NWK/HOP admissions and completions, including source-specific receiver custody.
2. MAC raw draw, draw ordinal, range/profile, active/reported population and neighbor reservations; selected reservation and same-time ordering.
3. MAC/PHY state before/after, transition cause, SYNC presence, tracked/active signal IDs, preparation/holdoff/post-TX flags.
4. Schedule/fire/cancel records for periodic wake, pending-TX wake/idle RTS, sleep, post-TX expiry, slot, holdoff and acquisition; record deadlines and event identities without altering scheduling.
5. Actual SYNC threshold draws and PHY error uniforms with packet/interval/component/range; full generated feedback children and queue replacements.

Observer equivalence gate: when enabled versus disabled with the same MATLAB stream assignment, application/protocol/PHY output, scheduled simulation events and final RNG states must agree; only new diagnostic output and wall time may differ. A compact 0–330 check against the existing 6,000-second return can establish the natural prefix as well, using an explicit cutoff and numeric-time tolerance justified by the existing scheduler representation.

Case A answers why the actual MATLAB first DATA/feedback ordering arose. It does not prove equal-input algorithm equivalence, since native and MATLAB natural random streams differ.

### Case B: genuinely coupled common-input run

Preferred scope is the same campus [0,330), with nodes 7/8/2/4 prioritized in the report. Generate or recapture the complete native exogenous tape from time zero. Supply only traffic attempt times/destination selections, MAC raw draws and PHY random variates; preserve nominal geometry/radio settings and explicit initial state. Both engines must generate their own transmissions, receptions, receiver availability, ACK/DACK bitmaps, cancellation, retries, source gating and custody release.

Use validation-only source-bound adapters or explicit optional sampler injection; preserve the no-injection production behavior. Do **not** import native receiver_state/SYNC, MAC enqueue/cancel or successful-reception events as commands into MATLAB. Those are outcomes to compare in this case.

At each draw request, require semantic match: node/subsystem, ordinal or semantically keyed call, bounds, MAC profile/population or PHY component/interval conditions. On the first mismatch, emit the causal window and stop exact-path comparison; do not continue by blindly consuming the next draw. Comparing different semantic requests with the same ordinal is not valid evidence of a behavior mismatch. Capture IDs must be mapped through canonical application/hop/aggregate lineage, not assumed equal.

Evaluate in order: first differing exogenous draw request; first differing endogenous PHY/state/timer event under equal prior inputs; first differing admission/source mix; effect on 8→2 receipts, 2→4 service and node-2 source-7 custody. The 34-feedback-before-DATA sequence is an assertion to reproduce through the coupled loop, not an injected premise.

If a full native tape cannot be recovered, a new reduced-topology controlled tape is possible only after both executable harnesses exist. Its result must be labeled a controlled mechanism test rather than a reproduction of seed 132. Avoid overriding MAC reservation to a constant, disabling duty cycle, perfecting all PHY receptions, or inserting receiver feedback as a substitute for the missing tape; those changes remove the boundary being investigated.

### Executable intermediate option: control MAC randomness only

Root's all-node draw inventory confirms captured counts of node 1:171, 2:130, 3:148, 4:137, 5:153, 7:78 and 8:111. If a complete startup PHY tape is not ready, the second case can consume this MAC tape while leaving production PHY random streams, PHY state, wake/sleep timers, feedback and traffic admission autonomous. This is a **partial random-input intervention**, not a complete common-input replay.

The existing evidence makes that intervention informative: natural gateway first transmissions differ by one 13-ms slot while earlier receiver states agree; the source-7 initial source-gate difference is downstream of first-feedback timing. The test can show whether matching MAC samples removes the first timing difference and how much of its subsequent causal chain follows. It cannot attribute every later mismatch to protocol logic while PHY random inputs still differ.

Require matching node, ordinal, bounds/profile and semantic draw-request context. Record time differences; do not force a recorded draw timestamp as an endogenous event schedule. A later PHY-induced time difference is evidence to inspect, not permission to replay native receiver availability. Stop consuming the reference tape at the first unsupported or differently scoped draw request and preserve the causal window. Do not silently exhaust the tape and fall back to MATLAB randomness in the same claimed controlled case.

For implementation, a source-bound validation copy of MAC can add an optional integer-sampler callback at the existing `randi` calls, with no-injection fallback executing the exact original call once. The PHY already has a scalar-uniform supplier at `Model.allocateErrors`; the integrated `SignalEngine` still needs a SYNC normal sampler seam and a way to pass the uniform supplier. Do not attempt to spoof the whole `RandStream` API or force queued frame/receiver-state outcomes. A native observer extension covering [0,330) can supply full startup PHY draws; it is preferable to producing serial owner packages for partial and then complete control.

## Native execution feasibility in the current workspace

Checked the current workspace and standard executable paths. `g++`, `git` and `make` are available. `matlab`, `octave`, `cmake` and `ninja` are not on PATH. No ns-3 engine checkout, generated headers, shared libraries, CMake cache or existing native executable was found under the workspace. The packaged native CSR overlay has 17 model/helper headers and the accepted capture driver, but not the ns-3 engine.

`source5_capture/run_bounded_capture.py` documents the exact build dependency: matching Debug ns-3 `build/include/ns3` and `build/lib`, C++23, and libraries `csr,spectrum,buildings,propagation,mobility,antenna,network,stats,core` plus `stdc++exp`. It uses isolated overlays, exact model header hashes, optional Git ancestry checks, and compares all 30 canonical native fields before writing fidelity acceptance. Those gates should be retained when extending the observer to startup and timer causes.

`t25up.zip` contains traces, validation scripts and build logs; inspection found **zero C/C++ source/header members and no engine archive**. It cannot restore the native build by itself. The short kit includes evidence of an earlier `native_restore/engine` build, but that engine is not part of the restored files. Recover the pinned engine and CSR source or a verified built runtime on our side before issuing a coupled test. Do not give Mike an ns-3 build task; his established role remains running a single MATLAB entry point and returning its ZIP. After this inventory, root confirmed direct Git network access and delegated restoration to `autonomous/native_env`; that recovery is in progress and supersedes any inference that the runtime is permanently unavailable.

## Delivery decision

The natural MATLAB diagnostic requires the added passive instrumentation because the original observer was incomplete for raw RNG and timer causes. The fully coupled common-input case now has its **executed and prefix-verified native tape and a concrete MATLAB kit**. Final packaging and parser receipts bind the distributed kit; actual MATLAB execution remains pending. The owner runs one command, `report = run_autonomous_tests;`, and returns the printed ZIP even if case B records an early semantic divergence. Do not present the MATLAB outcome as passed before owner execution. No algorithm correction is justified merely by this observability gap.

The ±15% network acceptance target remains separate. A short exact-path pass establishes the tested causal boundary, not full 6,000-second parity.
