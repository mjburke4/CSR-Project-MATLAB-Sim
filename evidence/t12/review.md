# Tranche 12 focused milestone verified

The repaired Tranche 12 run passed all 72 MATLAB tests on the portable R2025a backend (25.1.0.2943329). All 120 unique applications were delivered, all 164 relay-service checks passed, and all 72 clock checks passed. The first-run callback defect is resolved by the returned runtime evidence.

This verifies the focused relay/local service milestone. It does not establish exact numerical trace parity, a full regression acceptance gate, or campus/RF parity. The runner correctly keeps those broader acceptance flags false.

## Application service and capacity

The four cases use the same preconditioned 4 → 5 → 1 route, prescribed contention draws, nominal 128-kbps radio profile and +33-dBm power. Actual NWK custody, HOP feedback and MAC service execute, with controlled successful addressed transport.

| Case | Unique applications delivered | Hop release callbacks | DACK holds at 16 s | DACK holds at 24 s |
| --- | ---: | ---: | ---: | ---: |
| Relay only | 20/20 | 40 | 0 | 0 |
| Local only | 20/20 | 20 | 0 | 0 |
| Mixed relay/local | 40/40 | 60 | 4 | 0 |
| Mixed, source draw sequences swapped | 40/40 | 60 | 1 | 0 |
| Total | 120/120 | 180 | 5 | 0 |

Both implementations deliver the same application identities in the same recorded order. ACK/DACK bitmaps, radio settings, admission/custody counters, MAC state and contention choices agree at corresponding observations, subject to the five intermediate HOP-list samples discussed below. The returned traces contain 2,344 relay observations and 332 contention draws. All 332 raw and resolved draw values agree; the 12 draw-usage rows agree exactly.

There are no application drops and no outstanding DATA custody, resend entries or DACK holds at the final 24-second checkpoint. The observed 16-second and 24-second DACK counts match native. These exports do not observe the exact hold-expiration instants. Bootstrap control work remains excluded from service and separately reported; an empty DATA state does not mean that every control queue is empty.

## Why strict comparison still reports differences

The 1,898 differing relay rows comprise 1,566 event rows and 332 draw rows. Every one has MATLAB's timestamp exactly 28 ns earlier than native. The other 778 event timestamps match exactly. The existing one-nanosecond comparison tolerance was preserved.

Native NWK queues schedule their first processing through `CsrOpnetTic()` (28 ns); MATLAB schedules its NWK wake at the current simulation time. Source review supports this as the origin of the consistent service-clock phase offset. It did not change observed application delivery, event order, frame contents or contention choices in these cases.

Five of those event rows also differ in `resend_queue` and `dack_holds`, all during DACK release callbacks. MATLAB installs the hold and removes the resend entry before calling the NWK release observer; native calls its NSDP observer before moving the entry. Total reserved HOP capacity and NWK custody agree, and post-ingress observations agree. This is a real intermediate callback-order difference; the completed experiment shows no resulting service effect. Keep it documented for future callback-sensitive tests rather than claiming the entire state trace is identical.

The independent clock fixture again passes all eight tests and 72 checks. Five shared-time cases match native exactly. The continuous case retains the expected three differing observation rows, involving four counter fields, from a one-binary64-step arrival offset of approximately 4.44 × 10⁻¹⁶ seconds. Only the separate quantized transport case uses integer-nanosecond timing; the global scheduler is unchanged.

## Evidence and disposition

The return contains 13 inventoried artifacts plus its metadata. All 259 source bindings and 132 reference bindings match the repaired candidate and remain stable across the run. All 241 earlier source bindings, including 130 validated MATLAB files, are unchanged. The returned source inventory contains 135 MATLAB files, including the five Tranche 12 additions.

- Owner return: `t12(1).zip`, SHA256 `266a47c167e9b2d50d47abcd77a349b8f474334c9e9742d7abc8cca22547633d`.
- Repaired candidate SHA256: `ebf493fc8d34dc7c7819f14e266bf19b99f0f94441a79da38a801cd7f52292c4`.
- Repaired fixture SHA256: `b33136349b7ae851927a802461551a5b8fcecb1456a4b42d2467fe0d978aee1e`.
- Native source pin: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

The review bundle preserves the original owner ZIP, source/reference snapshots, candidate, project-gate result, independent integrity and residual reviews, and an updated parity-ledger snapshot. The delivered simulator source and acceptance checker were not modified during this review. No new MATLAB or ns-3 execution was performed by the reviewer, and no remote publication was performed.

No additional Tranche 12 repair or rerun is indicated by these results. Keep the current repaired MATLAB files.

## Recommended next milestone

Use the same short three-node chain for controlled DATA-loss, ACK-loss and brief relay-outage/recovery cases, while continuing application demand through capacity release. Compare duplicate suppression, retransmission ownership, ACK versus DACK decisions, resend limits and source admission recovery against native. In particular, exercise whether the intermediate callback ordering matters when capacity remains contested.

Keep transport losses deterministic and separate from PHY/ECC changes. Reinspect and pin current native main when beginning that new behavior tranche. After this bounded recovery milestone, decide which larger campus and multiple-seed cases merit the longer laptop run. This completed fixture did not exercise route convergence, neighbor authentication, RF collisions, half-duplex receive losses or the full production traffic generator.
