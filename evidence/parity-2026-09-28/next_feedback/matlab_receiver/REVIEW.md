# Seed 132: MATLAB node 2 receiver policy and node 8 feedback outcomes

## Finding

The observed 139 ACK and 993 DACK completions on 8→2 are already fully explained by node 2's receiver decisions. All **1,132 unique DATA receipts** predict the emitted feedback kind from the reconstructed **pre-enqueue, per-original-(source,destination) NSDP custody count**. All 1,132 then complete at node 8 with the same ACK/DACK classification and the same packet/HOP sequence. There is no observed classification change or permanently missing completion among accepted receipts in this run.

This closes the narrow hypothesis that the lower ACK completion count is caused by accepted DATA being converted from ACK to DACK, or never completed, somewhere in feedback delivery/processing. It does **not** prove identical ACK frame transmission history: cumulative feedback can complete earlier DATA and the full ACK/DACK bitmaps are not exported.

| Original source | 8→2 admissions | Node 2 receipts | Receiver ACK / DACK | Mean / max pre-receipt NSDP | No-receipt failures | Unfinished hop |
|---|---:|---:|---:|---:|---:|---:|
| 7 | 926 | 911 | 75 / 836 | 75.91 / 163 | 14 | 1 |
| 8 | 223 | 221 | 64 / 157 | 19.76 / 37 | 2 | 0 |
| Total | 1,149 | 1,132 | 139 / 993 | — | 16 | 1 |

All ACK-classified receptions have pre-receipt NSDP ≤15; all DACK-classified receptions have NSDP ≥16. The NSDP count includes submitted HOP custody, not just packets still waiting in NWK. A DACK accepts custody and subsequently delays sender capacity release; it is not a receiver discard.

Mean receipt-to-node-8-completion intervals are 0.3226 seconds for source 7 and 0.3479 seconds for source 8. These intervals alone do not prove a feedback delivery path or provide the counterfactual effect of feedback on later admissions.

## Early and sustained congestion

During **[300,330) seconds**, node 2 enqueues 29 local source-2 applications, admits 16 to its HOP sender, and finishes 13 through ACK. Node 2 receives 15 source-8 applications from node 8 and classifies all 15 as ACK; only one of those has been admitted onward to HOP and none has completed that onward hop by 330 seconds. Source 7 has not yet arrived at node 2.

The first source-8 DACK is at **331.367815345563 seconds**, incoming HOP sequence 31, MATLAB packet 102, with NSDP 16 before and 17 after arrival. Node 2 has 34 total custody owners before this arrival; the decision correctly uses the 16 source-8 owners rather than the aggregate 34.

The first source-7 DACK is at **346.330815345563 seconds**, incoming sequence 49, packet 109, with NSDP 16 before and 17 after. Source 7 later has **665 consecutive DACK-classified receipts between 420.521815345563 and 4485.73881534556 seconds**, spanning approximately 4,065 seconds, with per-flow NSDP between 16 and 163. This is the major sustained backlog episode in the receiver history. “Consecutive” here is per source's received-packet sequence, not continuous transmission or proof that NSDP never dips between arrivals.

Source 8's longest such sequence is 87 DACK-classified receipts between 1128.72281534556 and 3394.57081534556 seconds, NSDP 16–37.

`receiver_service_100s_bins.csv` provides [300,330) plus 100-second interval summaries for original sources 2, 7, and 8: node-2 enqueue/admission/completion counts, incoming 8→2 receipt and feedback-choice counts, and mean/max receiver NSDP at arrival. All intervals are left closed and right open.

## Method and verification

Run from the recovered workspace:

```bash
python3 next_feedback/matlab_receiver/audit_receiver.py
```

The script reads all 615,508 protocol records, independently rebuilds node-2 custody using every positive-byte `network_enqueue` and `network_custody_release`, and tracks `network_submit` separately. All 1,532 emitted enqueue depths, 1,498 releases, and 1,500 submit-owner conditions close. Final node-2 custody is 34 applications: 16 source 2, 17 source 7, and one source 8; 32 are waiting and two submitted.

For each incoming DATA receipt, the code saves custody state before that packet's enqueue. Production `receiveData` selects DACK using this pre-enqueue count, then invokes the relay NWK callback, queues feedback, and emits `hop_receive`. The ordered trace lets the audit associate its same-time `mac_enqueue` or `mac_ack_replace` with that receipt. No `hop_no_route`, custody refusal, or duplicate DATA reception occurs at node 2; final counters independently confirm this. Consequently every audited `hop_receive` has exactly one own enqueue earlier in the callback.

Production semantics used:

- `+csr/+hop/Layer.m`, `receiveData`: `first && ~local && before >= NsdpLimit` selects DACK when feedback is required; default limit is 16.
- `+csr/+nwk/Layer.m`, `nsdpCount`: counts pending custody with matching original source and destination, including submitted owners.
- `+csr/+hop/Layer.m`, `receiveFeedback`: ACK/DACK bitmap bits can complete several outstanding DATA sequences; ACK bits take precedence where both bitmaps contain a bit.
- `+csr/+mac/Layer.m`, `enqueue`: newer cumulative feedback replaces queued feedback for that peer.

Trace indices in the ledgers are one-based **data record indices**, excluding the CSV header. They are not native event indices and do not align identities across engines.

## Evidence limits and next comparison

These are exact within-run observational checks against the supplied production source semantics, not a MATLAB common-input execution test. NSDP fields, replay-window first/duplicate flags, and ACK/DACK bitmap envelopes are absent from the exported protocol CSV. Their omission limits physical-frame attribution, but does not prevent this first-reception classification audit because full custody, emitted feedback kind, and application completion identities are available.

The companion native raw-trace audit (`../native_receiver/`) now also closes the same receiver rule and subsequent completion classifications for all **1,245 first DATA receipts: 300 ACK and 945 DACK**. Native source 7 contributes 759 receipts (114 ACK / 645 DACK), and source 8 contributes 486 (186 / 300). Thus the remaining ACK count difference is present in the receiver's arrival populations and pre-arrival custody states. Changing the timer, DACK hold arithmetic, or receiver threshold is not justified by this result.

The histories are already different at the first source-8 reception: MATLAB **301.381275345563 seconds** versus native **316.963815346 seconds**. Native's first DACK is at **346.850815 seconds** for source 7 and **349.918815 seconds** for source 8; MATLAB's corresponding threshold crossings occur at 346.330815 and 331.367815 seconds. These ordinal comparisons locate differences in the traffic history; they are not same-state, same-input pairs or proof of a code defect. The next causal analysis should connect the receiver backlog to incoming service and the node-2 onward drain history.

The lower source-8 population must remain visible: it contributes only 221 of 1,132 incoming receipts here. A pooled ACK rate alone combines different flow proportions and per-flow congestion states.

## Outputs

- `receiver_decisions.csv`: 1,132 pre-custody/feedback decision rows.
- `link_8_2_application_outcomes.csv`: all 1,149 admitted HOP applications, including 16 no-receipt failures and one unfinished owner.
- `node2_custody_events.csv`: complete enqueue/submit/release trajectory.
- `node2_service_events.csv`: node-2 enqueue/admit/ACK/DACK/failure trajectory by original source.
- `receiver_service_100s_bins.csv`, `receiver_300s_bins.csv`: time summaries.
- `flow_summary.csv`, `arrival_nsdp_histogram.csv`, `consecutive_dack_runs.csv`: receiver population summaries.
- `summary.json`: all checks, raw input hashes, caveats, and numerical results.

No simulation or production edit was performed.
