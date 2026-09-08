# Tranche 2 portable acceptance

**Accepted:** the owner-supplied test-results and scenario-summary CSVs pass
the portable MAC/HOP gate. This closes the fixture-repair rerun for Tranche 2
and establishes the working fixed-path MAC/HOP/PHY foundation for Tranche 3.

## Actual owner results

All **145 test methods passed**, with **zero failed and zero incomplete**.
Their recorded durations sum to **23.9557439 seconds**; this is test-method
execution time, not total wall-clock duration of the validation runner.
The suite includes all 38 MAC/HOP unit methods, 15 integrated scenario/custody
methods, nine PHY-state bridge methods, 11 frame-layout methods and 72 earlier
portable regression methods.

| Scenario | Generated | Delivered | Dropped | HOP retries | Observable result |
|---|---:|---:|---:|---:|---|
| Reliable | 6 | 6 | 0 | 0 | Six ACK completions |
| ACK loss | 1 | 1 | 0 | 1 | Five erased ACK receptions; one duplicate suppressed |
| DATA loss | 1 | 1 | 0 | 1 | One erased DATA reception recovered |
| DACK | 1 | 1 | 0 | 1 | One relay custody acceptance and one DACK completion |
| Contention | 6 | 6 | 0 | 2 | Two collision observations and two duplicates; all applications delivered |
| Relay | 6 | 6 | 0 | 1 | Six relay acceptances and 12 hop ACK completions |
| Queue pressure | 20 | 2 | 18 | 0 | All 18 losses attributed to the intentionally bounded queue |
| 500 kbps | 6 | 6 | 0 | 0 | Six ACK completions |
| 1 Mbps | 6 | 6 | 0 | 0 | Six ACK completions |

Every row satisfies `Generated = Received + Dropped + Pending`. All nine rows
report zero `Pending`, `HopPendingData`, `ResendQueueDepth` and `DackHoldCount`.
There are no HOP terminal failures or unconfirmed hop transfers in these
exported fixtures. Per-scenario runtime ranges from 0.5215253 to 3.8838168 s;
these small fixtures do not establish large-network performance.

The deliberately small queue-pressure fixture is successful when its queue
bound is enforced and loss is accounted. Its 18 drops are expected. Collision
observations count affected receiver signals, not unique medium events or
automatic packet losses. Retransmissions in otherwise delivered cases remain
valid protocol activity, not an acceptance failure.

## Provenance and scope

The code checkpoint is associated with the issued Fix1 package at
`e79c5a84955b3e98a37fc469629b6c3d0ba700a0`. R2025a
`25.1.0.2943329` and the portable backend are associated from the immediately
preceding owner console/session. **The two new CSVs do not embed release,
configuration, seed or source hashes**, so those identities are not independently
certified by the files. Test names and scenario cases match the issued runner.

Both supplied CSVs are preserved byte-for-byte, with SHA-256 provenance in
`evidence/tranche-2-portable-acceptance.json`. Per-scenario detailed traces,
MAT files and metadata were not supplied or independently inspected. Passing
test rows provide evidence for their internal assertions; the summary columns
provide direct evidence only for the exported quantities.

The prior **17/17 original ns-3 workflows passed** as reference-side execution.
They were not rerun for this evidence-only acceptance commit. MATLAB was run
by the owner, never in this engineering workspace. R2026a/native execution,
full-network ns-3 numerical comparison and OPNET aggregate agreement remain
unvalidated. This acceptance does not change any intentional parity differences.

## Next engineering step

Prepare the accepted Tranche 2 branch for publication/PR under the repository
authorization rule, then proceed with the cohesive Tranche 3 NWK/control-plane
implementation: neighbor discovery/admission, autonomous ARL routes, reliable
INFO/UPDATE/FLUSH, gateway behavior, no-route custody, route loss and recovery.
Adaptive link-control placement must be resolved before variable-link parity
experiments. The accepted fixed-path network is not yet the full autonomous
research baseline. Battery, supervisory features and BBN routing remain excluded.
