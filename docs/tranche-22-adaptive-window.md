# Tranche 22 adaptive HOP window contract

## Objective

T21 found different 7→8 adaptive-window histories accompanying the much larger
native node 8 relay backlog in seed 130. Its source audit found matching update
rules, but source inspection and trace reconstruction do not establish that
the two implementations execute the same transitions for identical inputs.
T22 closes that narrower validation gap.

## Cases

Each case creates a fresh actual HOP object and scheduler. No threshold or ACK
accumulator value is assigned by the test. The common action CSV prescribes
public admission attempts, actual transmit notifications, cumulative feedback
and observations. Natural retry and delayed-release timers execute between
those actions.

| Case | Contract question |
| --- | --- |
| clean_growth_boundary | Does every third clean ACK grow the threshold, with an effective window of threshold + 1? |
| retried_third_ack | Does a third ACK grow the threshold before a retried packet resets the ACK accumulator? |
| retried_second_ack | Does a retried second ACK reset partial growth without increasing the threshold? |
| dack_hold_20 | Does DACK release NWK ownership immediately while retaining HOP capacity for the ordinary hold? |
| dack_hold_40 | Does DACK after the final retry double the hold? |
| final_failure_floor | Does natural final failure reduce the threshold once, with a floor of zero? |
| ceiling_global_capacity | Are the threshold ceiling, neighbor capacity and global capacity enforced separately? |
| grouped_feedback_order | Do newest-first bitmap processing, overlapping ACK precedence and repeated feedback agree? |
| seed130_feedback_motif | Does the selected clean-ACK/retried-ACK startup ordering behave identically under controlled conditions? |

There are 364 per-action state observations and additional independently
reasoned milestones in the contract specification. The source-derived motif
comes from the early native seed-130 7→8 history: a ninth clean ACK grows the
threshold to three, followed by an older retried ACK that resets the
accumulator. Timing and surrounding traffic are deliberately reduced and
controlled. It is not a replay of the complete campus realization.

## Architecture and evidence

- `scenarios/t22/` contains the common plan, configuration, actions, contract
  milestones and seed-130 provenance.
- `+csr/+validation/adaptiveWindowContract.m` drives the actual MATLAB HOP
  layer and reads its public state and counters.
- `scripts/ns3/` and the native reference runner contain the C++ fixture and
  the bounded observational access needed for native state snapshots.
- `evidence/t22/native/` records the native build, source changes confined to
  the test fixture, reference checkpoints and validation outcomes.
- `run_tranche22_validation.m` checks source/reference identity, executes
  focused tests and replay, and preserves a return archive even on failure.
- `scripts/analyze_tranche22_return.py` verifies the returned inputs, exact
  test membership, complete state rows, conservation and native comparisons.

The accepted 376 T20 source bindings, including 175 MATLAB files, stay
byte-for-byte unchanged. New files implement the diagnostic. The exact source
and reference inventories are frozen in the T22 candidate. The source pin is
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; the native engine pin is
`6b5cd24ea80713ce16d88575869aedd6f432bdae`.

## Interpretation and decision

Discrete states and counters must match exactly, including neighbor threshold,
ACK accumulator, outstanding DATA, delayed DACK owners, resend depth and
admission permission. Recorded action time has a 1 ns absolute tolerance.
Timer probes stay away from equality boundaries; clock-quantization behavior
was a separate earlier tranche. The campus ±10% target is not a tolerance for
this contract.

The fixture bypasses radio contention and random PHY outcomes. MATLAB uses
decoded bare feedback, while the native fixture supplies authenticated
feedback through its controlled seam. Both execute the production HOP update
logic; this does not establish security-ingress or RF parity. The known
queued-retry expiration distinction remains unchanged and is isolated from
these cases by the prescribed actual transmissions.

If states disagree, the return identifies the first differing action and
fields. A production correction requires reviewing that demonstrated mismatch
and its impact. If states agree, retain the production implementation: the
campus residual remains a difference in event history and workload behavior
until further evidence identifies a specific defect. Do not tune window limits
or PHY parameters solely to fit the three existing campus seeds.

## Validation status

The handoff includes fresh compiled native reference results, Python checker
tests, MATLAB static parsing and independent review. These are preparation
checks. **New MATLAB execution and cross-engine contract acceptance remain
pending on the owner return.** The previously accepted T20 campus results and
716 portable tests are not reclassified or claimed as fresh T22 execution.

The return checker can be run with Python 3 from the installation directory:

```bash
python scripts/analyze_tranche22_return.py --source-root . --evidence path/to/t22.zip --output review-t22
```
