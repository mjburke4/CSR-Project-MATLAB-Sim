# T22 independent interpretation

The returned controlled adaptive-window contract passes. All **364 action checkpoints across nine cases** agree with the pinned native reference in all **15 discrete state/counter fields** (5,460 comparisons). All **38 independently specified milestones**, comprising 142 field assertions, pass; all 1,820 per-row conservation/range checks pass. The largest recorded action-time difference is 2×10⁻¹⁵ seconds, below the declared 1 ns tolerance. This is a numeric representation difference, not a measurement of physical timing precision.

The owner executed **89/89 focused tests** in six classes on MATLAB R2025a (25.1.0.2943329). The recorded run spans 56.610 seconds. The accepted full portable regression from T20 was not rerun. The independent script reads the original owner ZIP and native CSV directly and does not import the issued return checker.

## What the result establishes

For the prescribed common inputs, the implementations agree on clean-ACK window growth; growth-before-reset on a retried third ACK; partial-accumulator reset; ordinary and doubled DACK capacity holds; final-failure threshold reduction and its zero floor; neighbor and global admission limits; grouped ACK/DACK processing and duplicate-feedback handling; and the reduced seed-130 startup motif. NSDP release and later DACK capacity release remain distinct and reconcile exactly.

This closes T21's specific uncertainty about executing the adaptive-window transitions under identical feedback. It supports retaining the production implementation, actual-tx default, continuous timing and current PHY/ECC. There is no demonstrated window-update defect to patch.

## Limits for campus parity

T22 prescribes the feedback arriving at the sender. It does not test the receiver's process for selecting ACK versus DACK, natural radio contention, routing, cross-engine random draws, or a complete campus realization. The seed-130 motif is reduced and deliberately controlled. Explicit actual-TX notifications isolate the previously accepted queued-retry expiration distinction. MATLAB's decoded bare feedback and the native authenticated fixture exercise production HOP updates through different ingress seams; security-ingress equivalence is outside this result.

There is no new delivery or delay measurement. The T21 ±10% campus screen therefore remains unchanged: network delivery passes for all three seeds; individual delivery and mean-delay comparisons each pass 13/18. Different adaptive-window histories in those runs remain observed facts, but T22 does not establish the root cause of their different input histories or rule out every other implementation difference. No full-campus rerun is needed to accept this tranche.

## Next useful bounded question

If continuing behavior investigation, compare **receiver pressure → ACK/DACK generation** through actual NWK/HOP objects under an identical short schedule of relay arrivals, local application attempts and downstream ownership releases. Observe source-7 relay NSDP crossing 15→16→17 at node 8, source-8's separate local quota, the pre-enqueue pressure used to select feedback, duplicate reception/reassessment, and the feedback bitmaps emitted as capacity drains. Allow ownership counts to arise from real admissions and releases rather than assigning the counters.

T22 verifies how received feedback changes the window; this proposed contract would verify how that feedback is produced. Existing MATLAB tests cover pieces using a mocked NSDP count, so the useful addition is the integrated comparison with the pinned native implementation. Require exact decisions and conservation under declared timing semantics, reporting known wake-order differences explicitly. Promote a production change only for a demonstrated mismatch. No new campus run or threshold/PHY tuning is proposed from this passing result.

Original owner archive SHA-256: `37863a70ef46c2889b3f945bcc2d3cfbe548115f1c349136488cc56357a9f6af`.
