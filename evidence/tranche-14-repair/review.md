# Tranche 14 observer repair: independent review

Approved for the owner MATLAB rerun. This review does not establish MATLAB runtime acceptance or numerical parity.

The uploaded R2025a return has 97/106 tests passing, including all 88 retained tests. All six new diagnostic cases stop in `observe` at the first source ACK, because `Frames.base` includes a fieldless `App` struct for ACK frames. Checking only for the presence of `App` therefore allows an invalid read of `App.SourceId`.

The repair exports application identity only when the frame kind is DATA. This agrees with `Frames.data` and the NWK Delivered callback. ACK and NONE rows retain zero identity. The remaining direct application-field access in selected-member validation is protected by a short-circuit DATA-kind condition. The remaining observer fields either come from the MAC schema or retain field-existence guards.

The strengthened existing MATLAB test checks the actual ACK constructor, requires all six boundary rows, preserves source aggregate DATA identity, and checks zero ACK application identity in transmit and feedback-ingress observations. The delivery and ACK/drain tests now require six boundary rows and the exact ordered case identities before iterating, preventing the empty-boundary passes observed in the failed return. The selected test identities are unchanged: 18 new tests and 88 retained tests, 106 total; 222 structural checks remain.

Independent byte checks confirm all 271 accepted Tranche 13 source files, including 138 MATLAB files, and all 283 original Tranche 14 references are unchanged. Only the new Tranche 14 diagnostic observer and its test class change among MATLAB files. Production MAC/HOP/NWK, EventScheduler, TraceScheduler, PHY airtime, native fixture/generator, shared inputs and the MATLAB runner are unchanged. Exact reviewed hashes are recorded in `review.json`.

No blocking source-review finding remains. The repaired diagnostic must run on MATLAB before ACK-boundary behavior can be accepted; this environment has no MATLAB runtime.
