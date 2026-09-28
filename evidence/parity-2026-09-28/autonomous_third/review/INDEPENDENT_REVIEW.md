# Independent review of the third autonomous return

The coupled run now reaches a real PHY arithmetic mismatch, but that is not the earliest scheduling difference visible in the capture. The existing evidence supports investigating both source-level causes together before another owner run. No simulator or model was changed for this review.

## What matched, and the limit of that match

The first gateway transmission passes the full physical-transmission context check. Six requested random samples pass their per-node/per-purpose context checks: two MAC slot samples, three synchronization thresholds and the node-4 header-error sample. The seventh MATLAB request stops at 11.500323527005154 seconds on payload bit count alone: MATLAB 184, native 183. BER is identical, and every recorded rounded-nanosecond interval/component boundary is identical.

These six matches are **not a complete global native draw prefix**. An unconditional comparison of all requests through the stopping timestamp finds nine native requests versus seven MATLAB requests, of which six passed and one was rejected. Native already requested node 3's first MAC slot at 11.500308077 seconds and node 5's at 11.500311086 seconds. MATLAB had not requested either by its stopping time. The provider deliberately keys requests by node, purpose and ordinal and keeps their timing endogenous, so the bit-count exception is the first failing context guard, not a proof that all earlier network behavior matched.

## The one-bit difference

Native's raw component observer shows the payload starts at 11.476863527005154 seconds and closes at the native callback time 11.500323527000001 seconds. MATLAB closes it at the raw signal end, 11.500323527005154 seconds. The approximately 5.15-picosecond difference falls on opposite sides of an integer when the duration is multiplied by the operational rate, `4 / 0.000510`, and truncated. Rounding both times for the comparison log hides this distinction. Native mixes raw signal geometry with its nanosecond callback clock; rounding every signal field would therefore be a different implementation.

This is an actual arithmetic difference, but this occurrence does not demonstrate a delivery change:

- The captured payload uniform, 0.45559117029490032, and BER, 0.015116561887016548, produce **two payload errors for both 183 and 184 bits** under an independent transcription of the existing inverse-binomial formula.
- The matched header sample produces two errors, so either payload count gives four total errors.
- Both captures already have node 4 idle, untracked and rejected for the first gateway packet. Native's `rx_prior_stage` explicitly reports `rejected=1` and `missed_by_state=1`; MATLAB reports the same state and flags before the failing calculation. Error allocation cannot rescue that prior rejection.

This local conclusion must not become a general one-bit tolerance. All 1,542 native PHY sample rows reproduce the source truncation from their raw component-duration products. Of those products, 1,317 lie within one nanosecond of an integer-bit boundary; 896 are on the lower side, comprising 378 headers and 518 payloads. In a bounded sensitivity calculation, changing each of those native counts to the adjacent integer changes the same-uniform error sample in six cases. That calculation is a numerical sensitivity audit, not a prediction of actual MATLAB counts, later delivery changes or a recommendation to round.

## Earlier post-receive scheduling difference

Both engines accept the first gateway DISCOVER at nodes 3 and 5 and generate a KEY_REQUEST. Their resulting MAC preparation states differ:

| Receiver | Native after reception | MATLAB after KEY_REQUEST admission |
|---|---|---|
| 3 | At 11.500308077 s, preparation active, reservation counter 27 | At 11.50030807737306 s, one queued packet, preparation inactive, counter −1 |
| 5 | At 11.500311086 s, preparation active, reservation counter 10 | At 11.500311086063823 s, one queued packet, preparation inactive, counter −1 |

MATLAB already has its next slot callbacks scheduled for 11.505 seconds. Node 3 schedules its zero-delay `pump` callback as observation 4969, returns the PHY to Search at 4978, returns from `endSignal` at 4987, fires `pump` at 4988, and only then enqueues the KEY_REQUEST at 4991. Node 5 follows the same order. The resulting `schedulePending` call sees an existing slot event and an expired holdoff, so it does not start preparation immediately. Native has the queued packet when its return-to-Search callback triggers preparation. The captures establish the preparation-state difference; its eventual transmission or delivery effect remains unmeasured because the coupled run stops before the next slot. Source inspection should establish the proper NWK/HOP control-admission and receive-completion order before changing generic MAC enqueue semantics.

## Recommended next step

Treat this as one bounded receive-completion investigation with two parallel checks: reproduce native callback-time arithmetic while retaining raw signal geometry, and resolve the accepted-DISCOVER → KEY_REQUEST admission → MAC preparation order at nodes 3 and 5. Keep exact bit-count and transmission-context guards. Validate both source-grounded changes against the existing captured cases before resuming the same coupled run. Neither forced receiver availability, copied bit counts, a timing tolerance, nor a blanket one-bit allowance would establish the missing behavior.

`review_bit_boundary.py` reproduces this review from the returned logs and original native observations. `bit_boundary_review.json` preserves the matched requests, the two earlier unrequested native draws, both engines' preparation-state evidence and the six sensitivity cases. `global_draw_schedule_comparison.csv` compares every native request through the stopping timestamp. `phy_bit_boundary_inventory.csv` contains the full 1,542-row arithmetic inventory. These are read-only calculations; no new MATLAB execution, network simulation or ±15% parity result is claimed.
