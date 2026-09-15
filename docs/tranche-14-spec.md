# Tranche 14: DATA arrival at the ACK transmit boundary

This focused diagnostic isolates the first service-changing boundary found in the owner's Tranche 13 DATA-loss return. It executes real MAC packing and timing, gateway HOP receive-window updates, NWK delivery callbacks, and ACK queue service. The incoming envelope is reconstructed from the observed mixed ACK/DATA aggregate. Controlled transport timing supplies the before/tie/after experiment; this is not a new RF, source admission, or full-network benchmark.

The original T13 return remains immutable. Its 28 ns native startup phase and the later one-ULP transport-arrival difference are separate observations. Explicit fixture epochs remove the startup phase from this experiment without modifying either scheduler or any production layer.

## Shared cases

The target gateway ACK opportunity is 3.144961 seconds. Every case begins from the same queued inputs and prescribed raw contention tape.

| Case | First mixed-aggregate arrival | When arrival is inserted | Boundary purpose |
| --- | --- | --- | --- |
| `tie_early` | Exact target | Actual source MAC transmission | Equal-time ingress is already queued before the gateway tick is inserted |
| `tie_late` | Exact target | Target minus 2 ns | Equal-time ingress is inserted after the preceding MAC tick has queued the target tick |
| `before` | Target minus 1 ns | Actual source MAC transmission | Reception before ACK service |
| `after` | Target plus 1 ns | Actual source MAC transmission | Reception after ACK service |
| `continuous` | Actual TX time + actual airtime + 1 microsecond | Actual source MAC transmission | Preserve each runtime's normal transport arithmetic |
| `quantized` | Sum of independently rounded TX, airtime and propagation nanoseconds | Actual source MAC transmission | Test a local transport conversion only |

The shared controls should transmit ACK sequence 3/bitmap 7 when reception precedes service, and sequence 2/bitmap 3 when service precedes reception. Continuous and locally quantized outcomes must be measured from actual execution; a rounded nanosecond timestamp alone does not prove a tie. Native source timing uses integer `Time`, whereas MATLAB records the original binary64 time. Strict comparison is retained and any residual is reported separately from structural completion.

## Production behavior exercised

Node 5 enters Search at 2.808 seconds and queues reconstructed ACK and DATA frames. The ACK is sequence 4/bitmap 15, addressed to node 4; DATA is source 5/application 3, HOP sequence 3, addressed to gateway 1. The bare modeled frame sizes are 41 and 48 bytes, for an 89-byte aggregate. Actual MAC selection must emit those segments in that order at 3.12 seconds, using 128 kbps, +33 dBm and a short preamble. Known neighbors are established through public receive/observe APIs and the existing bounded raw-draw seam supplies zero-valued draws with support 0–31. No forced reservation slot is introduced.

The gateway enters Search at 2.832961 seconds. Priming DATA sequences 1 and 2 pass through the real MAC/HOP/NWK receive path and establish delivered identities 1 and 2 and cumulative queued ACK sequence 2/bitmap 3. This input produces the feedback through HOP; the fixture does not enqueue a fabricated gateway ACK. The 300 ms holdoff and 13 ms slot clock provide the real gateway transmit opportunity at 3.144961 seconds. Execution must confirm these opportunities.

The first source transmission is cached unchanged. The boundary experiment schedules the entire mixed envelope once, preserving its segment order. Node 4 receives the companion feedback; node 1 receives DATA sequence 3 and updates the actual HOP ACK window and NWK delivery. In `tie_late`, the cached envelope is armed later; no replacement frame is manufactured. Actual gateway ACK transmission records reveal whether its queue was updated before or after selection.

The default repeated ACK service remains active. Only the initial mixed envelope is subject to the explicit before/tie/after perturbation. Subsequent source ACK-only transmissions and gateway feedback retain successful airtime-plus-propagation transport; only the `quantized` case uses local nanosecond conversion. The horizon is 4 seconds, allowing updated gateway feedback and ACK queues to drain. Source-5 sender HOP custody is not seeded, so receipt of feedback is not evidence of a sender admission or capacity-release improvement.

## Evidence and structural completion

Shared inputs are `scenarios/edge/plan.json`, `cases.csv`, and `draws.csv`. Each of the six cases has 64 prescribed raw draws for each node 1, 4 and 5: 1,152 available values in total, with explicit unused suffixes. Actual consumption, support, ordering and resolution are checked.

`events.csv` records semantic events, actual times as nanoseconds plus 17-significant-digit decimal strings and IEEE 754 hex strings, frame identity, exact uint64 ACK/DACK bitmaps, queue depths and transmission counts. `boundary.csv` records actual mixed TX, actual duration, planned opportunity, arm time, scheduled ingress time and the returned ingress event ID. The planned opportunity is not substituted for actual ACK transmission time, which is logged independently in events.

MATLAB's new tracing wrapper delegates to the unchanged `csr.sim.EventScheduler`; schedule, execute and cancel records identify real local event IDs and parent callbacks. Native evidence records actual ingress `EventId` UIDs; a zero semantic-event scheduler ID means the callback UID is unavailable. Cross-runtime event IDs are not compared as though they were the same namespace. Full-precision values remain strings until validated against their bit representation.

Structural completion requires three unique gateway deliveries per case, the same incoming aggregate identities and order, the expected before/tie/after ACK selection, eventual sequence-3/bitmap-7 feedback, final MAC DATA/ACK queues drained, valid prescribed draw consumption, and preserved source/reference inventories. Numeric and event-order comparisons remain independently visible. Test and checkpoint counts come from the implementation and the resulting evidence, rather than a predeclared success claim.

This tranche adds diagnostic code only. It preserves all 271 T13 source bindings, including 138 MATLAB files. No production MAC, HOP, NWK, global scheduler, PHY/ECC, routing, rate/power policy, or acceptance tolerance is changed. The source pins remain CSR `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` and ns-3 engine `6b5cd24ea80713ce16d88575869aedd6f432bdae`; root checks current main before handoff.

The owner MATLAB run can establish the missing full-precision causal evidence. A successful local transport experiment alone does not establish an improvement to full Tranche 13 service timing; such a change would require a separately reviewed implementation and re-execution of the controlled-loss benchmark.
