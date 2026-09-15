# Tranche 14 r2: focused diagnostic completed

The owner-returned MATLAB R2025a run passed all **109 tests and 222 structural checks**, with no failures or incomplete tests. All six ACK-boundary cases completed. Each delivered its three prescribed application identities exactly once, for **18/18 deliveries**, and all final diagnostic MAC DATA/ACK queues drained. The run took **129.52 seconds**.

This closes the Tranche 14 diagnostic milestone and verifies the two diagnostic repairs. It does not establish full-network acceptance or exact ns-3 numerical parity. No new MATLAB run or code replacement is needed to complete this review.

## What the boundary test established

The first ACK opportunity is 3.144961 seconds. Its cumulative bitmap reveals whether the gateway processed DATA sequence 3 before choosing that ACK. Sequence 3 / bitmap 7 acknowledges all three prescribed DATA sequences; sequence 2 / bitmap 3 still acknowledges only the first two.

| Case | First MATLAB ACK: sequence / bitmap | First ns-3 ACK: sequence / bitmap | Gateway ACK transmissions: MATLAB / ns-3 | Semantic event sequence and full-precision event times |
| --- | --- | --- | --- | --- |
| Exact tie, ingress inserted earlier | 3 / 7 | 3 / 7 | 5 / 5 | Match |
| Exact tie, ingress inserted later | 2 / 3 | 2 / 3 | 6 / 6 | Match |
| Ingress 1 ns before opportunity | 3 / 7 | 3 / 7 | 5 / 5 | Match |
| Ingress 1 ns after opportunity | 2 / 3 | 2 / 3 | 6 / 6 | Match |
| Continuous transport arithmetic | 2 / 3 | 3 / 7 | 6 / 5 | Differ |
| Local nanosecond transport conversion | 3 / 7 | 3 / 7 | 5 / 5 | Match |

In the continuous case, MATLAB records ingress **one binary64 ULP later than the opportunity: 4.4408920985006262 × 10⁻¹⁶ seconds**, approximately 0.44 femtoseconds. ns-3's integer-nanosecond transport puts ingress exactly at the opportunity, with its earlier insertion taking precedence. MATLAB therefore sends the old cumulative ACK first and transmits the updated ACK **26 milliseconds later**. One additional gateway ACK and one additional prescribed contention draw follow. All prescribed deliveries still complete.

The locally quantized case restores the native event sequence and full-precision event timestamps. This is a fixture transport experiment, not a production timing change or proof of improved sender capacity release. It preserves the global scheduler and PHY/ECC model.

## Why the report still says 28 differences

The total adds unmatched rows from five comparison families. It is not a count of independent defects and is not a percentage of failed tests.

| Comparison | Unmatched rows | Interpretation |
| --- | ---: | --- |
| Semantic events | 11 | Continuous-case event ordering, old first ACK and extra ACK/feedback events |
| Boundary records | 6 | One-ULP aggregate-duration representation residual in every case; continuous also changes arrival and arrival-minus-opportunity |
| Full-precision events | 9 | Overlapping continuous-case timing, ordering and extra-event differences |
| Raw contention draws | 1 | One extra gateway advertisement draw in continuous case |
| Draw usage | 1 | Corresponding gateway consumption increases from 6 to 7 |
| Total | 28 | Strict differences remain visible |

The five matching cases still have a separate duration-field representation difference; they are not byte-identical across every exported table. Local scheduler IDs are retained for within-runtime causality and are not compared across runtimes.

The duration residual is 3.4694469519536142 × 10⁻¹⁸ seconds. Substituting the native duration encoding into otherwise unchanged binary64 transport arithmetic still produces the late arrival. Changing that one duration bit alone is therefore insufficient; the successful comparison case changes the local transport-time conversion.

## Evidence verified

- Exact issued r2 candidate: `4bb51710031ead9d8d7c6b718fb41fd9224156b46076111e4e9c161aebbcc69f`.
- Owner return: `t14(2).zip`, SHA-256 `1b351bc8cf356ace8fe5e60413cba30812b5c3fcb4d71cede29d356102fe4241`.
- Runtime: MATLAB 25.1.0.2943329 (R2025a), portable backend; execution supplied by the owner.
- All 53 inventoried returned artifacts plus archive CRC verified. All 42 per-case files agree with the summary and reconstruct the six aggregate tables exactly.
- All 285 source bindings, including 144 MATLAB files, match the issued candidate. All 317 reference bindings match. Both inventories remained stable during the run.
- All 271 validated Tranche 13 sources, including 138 MATLAB files, remain unchanged.
- Existing native reference provenance rechecked: 67 artifacts, 222 native checks, 327 clean/disabled control checks, 14 native self-tests. No new native or MATLAB execution occurred during this review.

The existing return gate independently reconciled scheduler operations, actual DATA/ACK identities, delivery, queue drain, precision fields, draw consumption and comparison counts against the raw tables. Internal radio selections and receive-window readings remain reported MATLAB checks within the declared fixture scope.

## Next milestone

Test whether a narrowly scoped ns-3-compatible transport-time conversion improves the **continued-traffic DATA/ACK-loss and relay-recovery benchmark**. Compare current continuous arithmetic and the explicit local conversion using identical inputs and prescribed draws; measure ACK timing and overhead, retries, custody, admission-capacity release, delivery and queue drain.

Keep the global scheduler, PHY/ECC and this reviewed source baseline intact. Preserve true before/tie/after ordering, and handle the previously observed native startup phase separately from this one-ULP ingress residual. Promote any production change only after the full controlled-loss/relay evidence demonstrates its effects. Campus, RF interference and routing convergence remain outside this diagnostic result.

## Archive contents

This is a review record, not an installation patch. `owner.zip` preserves the returned evidence. `review.json` is the unchanged return-gate result; `check.py` and `check.json` provide the additional artifact and per-case audit. The independent difference analysis, candidate/readiness bindings, milestone record, parity-ledger addendum and hash manifest preserve the reasoning for the next tranche.
