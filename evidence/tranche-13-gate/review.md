# Tranche 13 independent review

**Ready for the owner MATLAB run.** No unresolved blocker remains in the reviewed fixture, native reference, or runner. MATLAB execution is still pending; this review does not establish cross-simulator acceptance.

The native archive is closed and all **47 artifact hashes** verify. Independent reconstruction confirms **384 unique generated, admitted, and delivered applications**, **576 unique HOP terminal owners** (556 ACK, 20 DACK custody), and no failed terminal. All **1,592 emitted segments** conserve their exact transmission and pass-ingress/loss observations. Actual loss decisions match the shared policies, and every final NWK, HOP, MAC ACK, and MAC DATA queue is empty.

Source 4 has blocked offers and waiting NWK data while five DACK holds retain capacity. This continues past 20 seconds; waiting queues fall as holds clear, and admissions resume. Native DATA-loss and link-blackout cases each require two DATA retransmissions. The ACK-loss case recovers through later cumulative feedback without a DATA retransmission.

Resolved review findings include exact 64-bit bitmap handling, the native generation event name, explicit mixed-kind recipient-group self-tests, final MAC queue checks, and strict success of the no-loss control. The final MATLAB fixture has **66 structural checks per case (264 total)** and **16 new tests**, alongside the 72 retained tests. Its native imports compare full-width integers as exact text before any floating-point conversion; actual reference maps reach `18446744073709551615`.

The review inspected real production admission and custody callbacks, FIFO offer scheduling, cached TX-start loss decisions, receiver ingress suppression, terminal normalization, source/reference stability checks, partial failure packaging, and short output names. Existing production sources are untouched. The exact reviewed source hashes and audit metrics are in `review.json`.

The four actual loss runs selected singleton groups; the shared grouping helper separately tests mixed-kind companions and independent recipients. The blackout's observed losses are two DATA groups on **5 → 1**; the broader bidirectional link policy is not evidence that every direction was exercised during that interval. All results remain limited to the fixed preconditioned chain with controlled transport, fixed radio settings, and no RF or routing-convergence claim.
