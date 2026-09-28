# Independent audit of the E/F owner return

Both cases resolve the previous missing-control aggregation mismatch and reach the same new guard failure at 14.534 seconds. The observed network outputs of E and F are identical throughout this prefix. No model was edited and no additional simulation was run for this audit.

## Global prefix, including the stopping request

The comparison includes every native random request through the rejected request, event 3402. Both cases request the same 97 samples in exactly the same global order and at the same rounded-nanosecond times as native. The first 96 consume their native values and pass independently repeated semantic-context checks; request 97 consumes no value and differs only in `active_nodes`.

| Check | E | F |
|---|---:|---:|
| Consumed MAC / SYNC / PHY samples | 20 / 44 / 32 | 20 / 44 / 32 |
| Additional rejected MAC requests | 1 | 1 |
| Missing or extra earlier request identities | 0 | 0 |
| Global request-order or rounded-time differences | 0 | 0 |
| Recorded interval/component ns differences | 0 | 0 |
| Verified physical transmission contexts | 16 | 16 |

All 16 earlier physical transmissions match native order, rounded timing and the existing semantic transmission guards. Native has a seventeenth transmission at 14.534 seconds, but its event 3403 occurs **after** the rejected random request. MATLAB stops before that continuation; it is not an unexplained omission from an earlier event population.

The stopping request is node 1's eighth MAC draw. MATLAB reports three active nodes; native reports two. Profile, receiver state, reservation state, reported population and bounds 0–31 agree. This demonstrates a population-context difference even though this particular draw's numerical bounds are equal. It does not establish when the underlying state first diverged or justify ignoring the field.

## Previous mismatch resolved

Node 5's third transmission at 12.402 seconds now passes with four children and 82 wire bytes. The ordered children are two 25-byte ACKs, a 16-byte Discovery check and a 16-byte Overheard check. Both checks originate at node 5 at 12.314891086 seconds. This directly verifies the missing Overheard control and restores the aggregate that previously had only three children and 66 bytes.

## What F adds in this return

Eleven diagnostic files, including the complete 13,386-row ordered-event log, random requests, protocol/PHY traces and feedback/service traces, are byte-identical between E and F. Both generate the same 15 neighbor-control requests and no Message check.

The three captured incoming Overheard controls cannot distinguish F's Message-only flag behavior. From the public control/ACK/activation order, nodes 5 and 3 still have Discovery proofs outstanding when they receive Overheard; node 1 is already active when it receives Overheard. Those independent gates suppress a Message in either variant. This is an inference from the captured lifecycle and unchanged gate code, not a direct observation of private neighbor flags. F's distinguishing Message branch passed its component preflight, but this network prefix provides no additional behavioral validation of that branch.

These results establish bounded progress through startup, not full receiver-state equality or the ±15% performance target. The run still ends before the original application sources start at 300 seconds. The next causal comparison belongs at the neighbor activation/population transition preceding node 1's failed draw, using the existing capture.

Reproduce with `python autonomous_fifth/review/audit_prefix.py`. `ef_audit.json`, `global_random_comparison.csv`, `global_tx_comparison.csv` and `received_overheard_gate_history.csv` preserve the evidence, causal cutoff and input hashes.
