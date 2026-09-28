# Autonomous MATLAB kit — independent static review

Reviewed by the autonomous-traffic audit task on 25 September 2026. Scope: offered traffic, semantic identity of shared random inputs, natural-prefix fidelity, failure evidence, and output packaging. This is a source/fixture review; no MATLAB execution or runtime pass is claimed.

## Findings addressed

1. The first draft matched PHY input to sender/transmission ordinal without a physical-content guard. The revised provider verifies ordered physical children, addresses, HOP sequence, rate, power, preamble, lengths, reservation, DSCP, complete ACK/DACK bitmaps and grouped targets before assigning the native transmission identity. DATA additionally requires source flow and attempt identity; native engine-local application IDs are not compared. The native fixture now includes these lineage fields and required-schema assertions prevent silently skipping them.
2. The first draft matched MAC samples by bounds alone. The revised provider also checks profile, local active-node count, reservation counter/slot, and MAC state. Reported population is diagnostic for the pinned profile, which does not use it. Neighbor state is captured for subsequent explanation of slot resolution.
3. The first summary listed only streams requested by MATLAB, hiding an entirely unrequested native stream. The revised summary uses the union of reference and requested channels, records unused samples and physical transmissions, and requires tape exhaustion for complete case-B status. It does not run extra events merely to consume a suffix.
4. The initial archived report would have shown `archive_completed=false` even inside a successfully created ZIP. The revised embedded report describes that archive construction follows it; the actual creation result and hash are recorded beside the ZIP. Case/error evidence remains in the returned ZIP.

## Scope checks

- The original seed-132 scenario is imported with historical gating and no admitted-packet cap. All seven nodes remain, and all six original source flows attempt destination 1 from 300 seconds at 20 ms intervals. Only the simulation stop and evidence budgets change.
- Case A uses each original MATLAB owned random stream and one original scalar draw per source call. It does not force admissions, transmissions, receptions, receiver availability, or feedback.
- Case A compares all values of the protocol, PHY and application-admission tables against the corrected owner's existing return in `[0,330)`. Reference fixture sizes are 12,200 protocol rows, 12,198 PHY rows and 9,000 admission rows. The 330-second endpoint is excluded explicitly. Case B is skipped if that gate fails.
- Case B injects requested random samples only. Endogenous state transitions and the NSDP application gate execute normally. A semantic mismatch is preserved as expected/actual diagnostic evidence before an unrelated sample is consumed. Request-time and interval-time differences are recorded as outcomes instead of injected as event schedules.
- DATA packet identity uses the original flow/attempt, not source/destination/size alone. Generation time is recorded separately. The fixed offered-attempt schedule already determines the corresponding intended generation time.
- ROUTING and SNMP comparisons use decoded semantics. Native compatibility-envelope crypto bytes are retained for reference; the kit does not claim byte-for-byte physical-envelope equality with the MATLAB behavior/size model.
- On a simulation divergence, the runner preserves ordered observations, random requests, the first-divergence record, partial raw tables, observer data, and error details. It attempts to produce one return ZIP even after a case error. No drain or extra simulation is executed to finish partial outcomes.
- The source/provenance checks bind resolved MATLAB files and verify issued hashes before and after running. The runner uses a new output directory and restores the caller's MATLAB path/folder.
- Completion is explicitly separate from the ±15% full-network target. A context mismatch can be the intended diagnostic result; unexpected harness failures remain separately labeled. A different MATLAB release is subject to the same strict natural-prefix gate.

No remaining blocker was identified in this reviewed scope after the above revisions. Final package-manifest verification and MATLAB syntax checks belong to the kit builder. The required runtime check is still the user's MATLAB execution, beginning with case A; the static review cannot establish instrumentation passivity or case-B numerical parity.
