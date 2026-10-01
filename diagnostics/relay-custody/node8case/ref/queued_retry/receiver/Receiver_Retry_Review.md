The N return's new failure is a DATA retry-policy difference. The existing MATLAB configuration selects `Hop.DataQueuedRetryPolicy='actual-tx'`; ns-3 retains a provisional retry timestamp while a retry is queued. MATLAB already contains the corresponding `native-provisional` option. The evidence supports testing that option for this parity case, without rewriting the MAC, receiver, or ACK/DACK implementation.

N accepts 769 physical transmissions and rejects the 770th comparison at 324.753 seconds, node 5 TX130. Its 4,202 random requests match native context and nanosecond timestamps. The new comparator also passes the previous node-8 DACK boundary at 312.143 seconds.

All 5,110 comparable receiver transitions match native per node in time, previous state, current state, and order. The comparison excludes 768 MATLAB Tx→Search completion records, following the same instrumentation boundary as the preceding review: native `SetReceiveState` logs Idle/Search/Track changes while native TX functions update their state directly. Node counts are 818, 643, 886, 684, 894, 569, and 616 for nodes 1, 2, 3, 4, 5, 7, and 8 respectively. This does not imply equality of private queues; the queue difference below arises while receiver transitions still match.

All 97 DATA HOP completion decisions also match in global order, nanosecond time, node, peer, hop sequence, and outcome: 88 ACKs, 8 DACKs, and 1 no-ACK. The eight DACK hold durations and immediate HOP-capacity-release flags match. The first previously stopped DACK reaches node 7 at 312.208292442 seconds, releases its NWK custody, and installs the same 20-second HOP hold. No DACK hold expires within this returned prefix, so eventual hold completion is not covered.

The source-5 queue fork occurs before the physical guard detects it:

| Time (seconds) | Existing evidence |
|---:|---|
| 313.820 | Both transmit source-5 DATA hop sequence 29 for application attempt 11. |
| 315.820000028 | Both enqueue its first retry. Native retains initial-TX confirmation and assigns this provisional timestamp; MATLAB's selected policy clears confirmation. |
| 316.498 | Both transmit sequence 32, scheduling another list-wide resend scan two seconds plus one TIC later. |
| 318.498000028 | Native enqueues a second sequence-29 retry, frame 633. MATLAB's same-time scan fires and immediately returns without enqueue. |
| 320.879 | Both transmit the first queued sequence-29 retry. Native's shared resend entry already records two retries; MATLAB records one. |
| 322.260111114 | Both admit sequence 36, application attempt 250. Native's extra sequence-29 copy is already ahead of it. |
| 322.879000028 | MATLAB now enqueues its second sequence-29 retry, behind sequence 36. Native waits its four-second final-ACK grace after the actual transmission. |
| 324.753 | Native selects sequence 29/frame633; MATLAB selects sequence 36. Radio, timing, preamble, reservation, wire size, and network endpoints still match. |

The native event is directly captured as `FRAME|633|5|5|1|29|...` followed by `INPUT|113930|318498000028|5|enqueue|1|0|1|633` in `mac-input.log`. The expected TX130 fixture identifies frame633. MATLAB ordered observations 718132 and 718133 are the fire and return of event96821 at 318.4980000277778 seconds, with no intervening observation. Both times map to the same nanosecond; this is eligibility and queue ordering, not a timer deadline error.

Native `csr-hop-layer.h:4730–4754` leaves initial transmission confirmation set, increments the retry count, records the enqueue time provisionally, and submits a copy. A later list-wide scan can therefore enqueue another copy before an earlier copy is transmitted. Native `NotifyMacFrameSent` at lines 591–660 replaces that provisional time with the actual transmission time and selects the normal or final-ACK wait. Its diagnostic `transmission=3` at 320.879 reflects the shared retry count; that time is only the second actual wire transmission of this packet.

MATLAB `model/+csr/+hop/Layer.m:482–508` follows the same two-pass scan but sets `Confirmed` after retry admission only for DATA under `native-provisional`. Lines 519–535 implement the existing policy and independent scan timers. The returned `configuration.json` explicitly selects `actual-tx`; lines 742–751 show the supported policy names and default. Both MAC implementations retain insertion order among equal-DSCP DATA (`ReceiverTimerMac.m:169–175`; native `csr-net-device.h:2281–2298`), so the admission order explains the later selection without a MAC fix.

A full DATA enqueue comparison finds one additional exposed instance of the same policy before the stop: native enqueues a second queued retry of source-5 sequence33 at 324.738000028; MATLAB does not. Other nodes' DATA enqueue identities and order agree. Six initial MATLAB DATA enqueues occur at 300.0 seconds versus native 300.000000028; that initial 28-nanosecond difference is masked by matching MAC timing and is not this failure. It does not justify another fix here.

Reproduce the review with `python autonomous_twelfth/receiver/audit_retry_receiver.py`. `retry_receiver_audit.json` records the exact comparisons, chronological evidence, source paths, and input hashes. This audit used existing captures only. No corrected-policy MATLAB continuation has run, and there is no claim yet about 330-second completion, independently generated random streams, the original 6,000-second comparison, or the 15% target.
