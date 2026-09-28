# Independent autonomous-kit review

Reviewer scope: current validation-only MATLAB copy at `autonomous/kit/autocase`; no edits to builder-owned files. This is a source review, not a MATLAB execution pass.

## Observation neutrality

Compared the instrumented `+mac/Layer`, `+phy/SignalEngine`, `+phy/Model`, `+sim/EventScheduler` and `+sim/NetworkSimulation` against the corrected 6,000-second model.

- MAC/PHY boundary observations read owned scalar/struct state and write ordered records. They do not call receiver callbacks, schedule or cancel events, poll a receiver, or consume randomness. `onCleanup` records return state without injecting simulator events.
- Scheduler observation calls surround the existing schedule/cancel/fire/return operations. The ordering comparator, event IDs, heap operations and callback order are unchanged.
- Natural MAC wraps exactly one original `randi` call using the original stream and bounds.
- Natural SYNC keeps the expression `mean + sqrt(variance) * randn(original_stream)` with one draw on the original SYNC stream.
- Natural PHY preserves zero-bit/zero-probability and probability-one no-draw branches; otherwise it calls one original `rand` and the unchanged `sampleSourceBinomial` implementation. The production header/payload bit calculations remain unchanged.
- The read-only stream creation/key map introduces no shared random consumption; original stream assignment is key-based and creation-order independent.

No static observer-neutrality defect was found. The included natural-case comparison must still demonstrate equality with the corrected MATLAB prefix in the owner's MATLAB runtime.

## Semantic draw context

The consumed native PHY fixture has source TX identity, receiver, draw ordinal, interval ordinal, header/payload component, bits and BER. The sampler checks these categorical/count fields and declared probability tolerance. Native interval ordinals increment for every positive error interval, including intervals consuming no draw, matching the MATLAB signal interval count approach.

Request/interval timestamps are endogenous diagnostics and are deliberately not forced onto the native schedule. This preserves the ability to find a timing/state divergence. Exact interval bit-count differences must cause a diagnostic stop rather than substitution or silent continuation.

Two preliminary issues were sent to the builder before issue:

1. Source-plus-TX-ordinal identity alone cannot establish packet lineage if a different same-size packet occupies the same ordinal. A native semantic TX signature check is needed before supplying that transmission's PHY values.
2. MAC low/high alone does not check the promised selected-profile/local-population/reservation context. The builder is adding context from the production call site. Reported population must be logged but need not be a gate for profile 4: that profile uses local population, and the initial reported value is 1 in MATLAB versus 0 in native.

A further runtime blocker was identified and corrected before issue: the instrumented `NetworkSimulation.run` reads `Streams.MappingVersion`, but the initial wrapper did not expose it. The revised provider now exposes mapping version 2. The MAC request context now checks profile, local population, reservation counter/slot and state; reported population is recorded but excluded for this fixed local-population profile. The TX signature addition was reviewed after enrichment: ordered parent/child fields, DATA source/destination/flow/attempt identity and byte count, routing section bytes, SNMP fields, and ACK/DACK bitmap hex are now checked before supplying PHY values. Generation and event times remain diagnostic outputs. The issued fixture schema includes all required lineage columns, populated on all 150 DATA signatures. Hex/node-list fields are explicitly imported as strings. No remaining static blocker was found in the reviewed observer/sampler/runner seams; MATLAB execution remains pending.

The runner was also reviewed: B is skipped if the natural exact-table prefix gate fails, and a common-input divergence preserves partial tables and ordered evidence without claiming a parity pass.

## Root investigation report

Chronology, receiver-state inference qualifiers and unchanged ±15% criterion agree with the receiver audit. The phrase “three active neighbors” was identified for correction to “local active-node count of three”: the count includes the node itself. No new receiver algorithm fix is supported by the audited actual histories.

## Final source review receipt

`kit_review_receipt.json` records the exact hashes reviewed, fixture row counts and populated DATA lineage gate. It is a static review receipt and does not claim MATLAB execution. The common-input case requires complete native draw and TX-signature usage at 330 s; unused suffixes fail the diagnostic completion gate.
