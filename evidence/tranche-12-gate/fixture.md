# Independent Tranche 12 fixture review

**Passed the native fixture and source review. MATLAB execution remains pending.**

Verified all 41 files in the closed native reference manifest, all three shared input bindings, the four fixture/generator source bindings, 24 pinned native source files, and nine native shared libraries. All 241 returned Tranche 11 source bindings remain unchanged, including 130 MATLAB files. Disabled hooks reproduce all 255 retained native control checkpoints byte for byte; six native fail-closed tests pass.

The actual native reference contains 2,344 semantic events, 332 consumed raw draws, 120 delivered applications and 180 real hop-by-hop NWK release callbacks. Every delivered source/ID appears on its required DATA leg(s), including both 4 → 5 and 5 → 1 for original source 4. All raw ordinals and supports match the shared tapes, including the zero-consumption node-4 tape in the local-only case. No direct 4 → 1 transmission occurs.

| Native case | Applications | DACK holds at 16 s | Holds at 24 s | Final DATA/capacity queues |
|---|---:|---:|---:|---|
| relay | 20 | 0 | 0 | Empty |
| local | 20 | 0 | 0 | Empty |
| mix | 40 | 4 | 0 | Empty |
| sw | 40 | 1 | 0 | Empty |

The five actual native `hop_capacity_release` records with reason `dack_expiry` independently show those holds expiring between 16 and 24 seconds. The final zero values are not produced by a fixture cleanup operation. The pending = resend + DACK-hold invariant applies at stable checkpoints, not inside the intentionally intermediate NSDP release callback.

The fixture retains real NWK queue insertion, relay custody, HOP handoff and wake callbacks. Its finite application driver applies the existing NSDP-16 rule using real NWK state; the production ApplicationGenerator is not invoked. Native NWK is unmodified. The isolated native overlay changes only the raw MAC draw hook, controlled addressed transport hook, and a read-only getter of the real DACK list. MATLAB uses unchanged production MAC/HOP/NWK classes, with test adapters and inherited validated replay streams.

Preconditioning establishes the same usable selected next hops. Native static route metrics/self-capabilities and MATLAB serialized UPDATE metrics/self-capabilities are not claimed equivalent; fixed radio limits and one eligible next hop isolate the intended queue-service comparison. Bootstrap control service is disabled explicitly, and MATLAB retained control owners are disclosed separately. This is not security-admission, route-convergence, RF, or campus parity evidence.

An early MATLAB draft initialized unused node-index positions 2/3 to −1 while the final-state test expected zero. The final reviewed source initializes unused positions to zero and keeps failure sentinels for actual nodes. Other mechanical checks cover actual callback ownership, ACK power defaulting at the adapter, source identity preservation, aggregate ingress grouping, draw annotation, and complete trajectory comparison. Static review cannot establish MATLAB execution.

The native NWK queue's one-TIC delay is 28 ns while the current MATLAB queue schedules at the same time. That difference remains observable; neither the fixture nor comparison silently adds a compensating delay. Exact relay replay may therefore expose a systematic timing residual even when structural service passes. The separate clock diagnostics help characterize event-order sensitivity without changing the accepted scheduler.
