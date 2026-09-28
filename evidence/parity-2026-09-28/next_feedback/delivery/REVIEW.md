# Seed 132: node 2 → node 8 feedback delivery audit

The current MATLAB run does **not** lose ACK outcomes between the receiver decision and node-8 completion. Node 2 receives 1,132 DATA applications from node 8, selects 139 ACKs and 993 DACKs, and node 8 records the same 139 ACK and 993 DACK completions for the same application/sequence identities. There are zero DATA duplicates at node 2 and zero receiver-decision/completion mismatches. The lower ACK count therefore already exists at the receiver decision stage in this run.

This narrows the investigation from feedback delivery to node 2's receiver NSDP state and incoming traffic. It does not prove that MATLAB's receiver decision agrees with ns-3 under identical inputs. Small feedback timing differences can still influence later autonomous traffic; the conclusion is specifically that feedback loss or replacement does not explain missing or converted ACK outcomes among these 1,132 received applications.

## Observed decisions and queue events

Scope is corrected seed 132, 300–6000 seconds, node 2 feedback to node 8. After 300 seconds node 2 receives no reliable controls and its only feedback destination is node 8. Therefore each observed ACK/DACK queue update can be associated with the DATA reception in the same callback. All 1,132 receipts have exactly one such update and a matching later node-8 completion.

| Receiver decision | New feedback queue entry | Existing entry replaced | Total decisions | Matching DATA completions |
|---|---:|---:|---:|---:|
| ACK | 56 | 83 | 139 | 139 |
| DACK | 565 | 428 | 993 | 993 |

Node 2's full-run `AckGenerated=164` also contains startup/control ACKs; it must not be compared directly with node 8's DATA-only `Acknowledged=139`. Neither node reports a feedback queue drop.

| Original application source | Receipts at node 2 | ACK choices | DACK choices | ACK fraction |
|---|---:|---:|---:|---:|
| 7 | 911 | 75 | 836 | 8.23% |
| 8 | 221 | 64 | 157 | 28.96% |

`receiver_decisions_and_completions.csv` lists every application identity, hop sequence, reception time, queue event, receiver choice, completion time, and completing transmission. `receiver_decisions_300s_bins.csv` retains the time and source distribution. For example, the first source-8 ACK decision occurs at 301.381275345563 s; the first source-7 ACK decision at 330.626815345563 s. Source-8 DACK receptions end at 3394.57081534556 s, although its later sporadic ACK receipts continue through 5889.40081534556 s. This is an admitted-traffic population difference, not a common-input experiment.

## Reconstructed feedback transmission and processing

The audit mirrors the pinned ACK queue and 64-bit cumulative receive window using the observed DATA receptions and feedback queue updates. It checks every inferred transmitting queue head against the actual `tx_start` peer, sequence, and application-byte count; it joins the physical envelope ID to node 8's `phy_signal_end`; then it predicts DATA completions from each successfully received bitmap and the observed live HOP owners. Every predicted completion matches the trace, including order-independent identity and ACK/DACK outcome.

| Feedback transmission result | Count |
|---|---:|
| Transmissions after 300 s | 3,830 |
| Accepted at node 8 | 3,601 |
| Not acquired | 151 |
| Half duplex | 78 |
| Accepted transmissions that complete at least one new DATA owner | 1,013 |

The remaining accepted transmissions carry repeated or already completed bitmap entries. Of 511 queue replacements, 118 occur before the replaced queue generation's first transmission; all affected receipt outcomes nevertheless reach completion through cumulative feedback. Mean receiver-decision-to-completion time is **0.327511 s**; the largest is **1.562480 s**. These times concern feedback returning upstream after DATA reception, not the delivered application's hop latency or later DACK hold time.

The frame's `Kind` alone is insufficient to identify the completion outcome: 10 ACK outcomes arrive in envelopes labeled DACK, and 7 DACK outcomes arrive in envelopes labeled ACK. `receiveFeedback` uses the individual bitmap bits, with ACK bits taking precedence. For example, application 151 (source 7), sequence 81, gets an ACK choice at 420.209815345563 s; a newer DACK-labeled frame with highest sequence 82 carries its ACK bit and completes it at 421.161295345563 s. Comparing aggregate/frame ACK counts with per-application ACK completions would be misleading.

Node 8's 1,149 DATA admissions to node 2 close as 1,132 feedback completions, 16 failures, and one remaining resend owner. None of the 16 failed identities is among node 2's 1,132 observed successful DATA receptions.

## Code paths and evidence limits

Paths below are relative to `return6000/kit/csr6000/model/` and identify the issued model, not edited production code:

- `+csr/+hop/Layer.m`, lines 321–363: receive sequence and duplicate check, pre-enqueue NSDP test, DACK marking, custody callback and feedback enqueue. The DACK choice uses first reception, nonlocal destination and `NsdpBefore >= NsdpLimit` at line 335.
- `+csr/+hop/Layer.m`, lines 365–398: feedback generation and processing of the 64-bit ACK/DACK masks; DATA completions depend on bits rather than outer `Kind`.
- `+csr/+hop/Layer.m`, lines 442–472: DACK ownership retention versus ACK capacity release and threshold growth.
- `+csr/+hop/Layer.m`, lines 558–589: per-peer DATA bitmap advancement and DACK bit marking.
- `+csr/+mac/Layer.m`, lines 124–168: replacement of the first queued feedback entry to that peer, replacement repeat counter reset, and queue admission.
- `+csr/+mac/Layer.m`, lines 530–549 and 554–580: five-transmission retirement and ACK-first aggregation.
- `+csr/+sim/NetworkSimulation.m`, lines 548–572: an accepted addressed feedback member is passed to HOP. Lines 698–727 show that the ordinary protocol CSV omits `HasAckWindow`, bitmap values, NSDP snapshots and member lists.

The 6,000-second ordinary traces directly provide reception identities, feedback queue-update kind/sequence, transmission envelope IDs, PHY outcomes and completion identities. The queue generations and actual bitmap values in this audit are **reconstructed from production rules**, not directly recorded values. The cross-checks substantially constrain that reconstruction, but they do not substitute for a captured same-state, same-input ns-3/MATLAB receiver comparison.

For that comparison, the next evidence should include receiver pre-enqueue NSDP count, NSDP limit, first/duplicate status, incoming hop sequence and application source, local/relay route and custody outcome, and the resulting ACK/DACK masks. Existing `AckServiceDiagnostics` already preserves `NsdpBefore`, `NsdpAfter`, `FirstReception`, `IsDack` and `DetailsJSON`; its inherited `LinkDiagnostics` records feedback masks and transmission members. Check the earlier short captures for these fields before collecting anything new. A generic additional feedback-delivery experiment is not justified by this audit.

## Reproduction

Run from the recovered workspace:

```text
python3 next_feedback/delivery/audit_feedback.py
```

The script requires the existing corrected seed-132 `protocol_trace.csv` and `phy_trace.csv` under `return6000/data/s132/attempt_001/raw/`. It uses Python's standard library, runs no simulation, and changes no production source. `summary.json`, per-application and per-transmission CSVs, cohort tables and queue replacement records are regenerated. The input ZIP is `out_6000_20260924_152302.zip`, SHA-256 `a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484`.
