# Node 4 feedback and capacity audit: seed 132

The unequal window at 600 seconds is explained by different successful-ACK/retry histories. Native grows from one to three outstanding DATA slots through two third-ACK completions; MATLAB remains at one because failures and ACKs after retransmissions repeatedly clear its ACK streak. The observed growth rule is the same in both source implementations.

## Exact causal chain

| Engine | Time (s) | Event | Effective DATA window |
|---|---:|---|---:|
| MATLAB | 508.833292444469 | Third ACK, seq83, after one retry | 1 → 2 |
| MATLAB | 528.433000027778 | Seq86 exhausts two retries | 2 → 1 |
| Native | 577.395292444 | Seq70 ACK, no retries; streak becomes 1 | 1 |
| Native | 581.906292444 | Seq71 ACK, no retries; streak becomes 2 | 1 |
| Native | 584.818292444 | Seq72 ACK after one retry: third ACK grows window, then clears streak | 1 → 2 |
| Native | 588.198292444 | Seq73 ACK, no retries; streak becomes 1 | 2 |
| Native | 590.187292444 | Seq74 ACK after one retry clears streak | 2 |
| Native | 592.267292444 | Seq76 ACK, no retries; streak becomes 1 | 2 |
| Native | 595.322292444 | Seq77 ACK, no retries; streak becomes 2 | 2 |
| Native | 596.960292444 | Seq75 ACK after two retries: third ACK grows window, then clears streak | 2 → 3 |

During [528.433000027778, 600), native receives 13 completing ACKs and has two failed owners. MATLAB receives six completing ACKs and has three failed owners, including the opening shrink event. Neither engine receives a completing DACK in that interval. Thus DACK-held capacity does not explain this node's boundary difference.

MATLAB's failures at 528.433, 550.611, and 569.422 seconds each follow three actual DATA transmissions and final expiration four seconds after the last transmission. Their nine DATA attempts all fail at receiver 5: seven `not_acquired`, two `half_duplex`. This is failed DATA reception, with no successful target reception requiring a missing-feedback explanation. The long queued retry delays are real, but none of these owners expires without its third actual transmission.

Native's window-growing seq72 reaches receiver 5 on attempt two, and seq75 on attempt three. Both are ACKed in time. In MATLAB, ACKs for seq93 at 580.112 and seq94 at 588.471 also follow retries; they arrive with shorter ACK streaks, so each clears the streak without growth. `feedback_history.csv` retains every pre-600 feedback event and its streak.

## What was checked

The offline audit checks 64 native and 80 MATLAB node-4 DATA completions. Every native directly traced threshold transition agrees with the documented update order; MATLAB's reconstructed threshold/streak ledger also agrees. Source comparison confirms both production implementations increment/test the ACK streak before resetting it for a retransmitted owner. This is the rule that explains the two native growth events; it is not a defect to remove.

The first observed window inequality after DATA traffic starts is earlier: MATLAB grows to two at 320.632292444469 while native remains at one. Both are back at one immediately after 528.433, before the native growth events above. The 600-second mismatch is therefore path-dependent feedback history, not evidence of a different configured initial window. This audit does not establish which initial random or scheduling decision caused the divergent histories, and it does not match application identities using HOP sequence numbers across engines.

## Batched production HOP regression

`run_hop_window(root, outputDir)` exercises the real `csr.hop.Layer` and `csr.sim.EventScheduler`, exclusively through public APIs. `root/core` must contain the accepted CSR MATLAB core. The native growth inputs and expected states come from `hop_window_oracle.json`, with exact trace event indexes retained. The first eight ACK/retry events are compressed in time; this is a native-history regression oracle, not a common-input native runtime replay.

The runner checks 16 state cases under each queued-retry policy, for 32 cases total: both observed third-ACK growths, failure clearing an existing two-ACK streak, failed-owner shrink and floor clipping, and DACK hold/expiry ownership. Timers create real retries; no private HOP state is changed. It reports `completed`, `pass`, check counts, and state rows. MATLAB is unavailable here, so this runtime regression is prepared but not yet executed. The Python evidence audit did execute successfully.

## Reproduction and scope

Run `python analyze_node4.py`. In the original workspace it refreshes compact extracts from the full archives; in the issued diagnostic folder it uses the supplied compact inputs. `provenance.json` binds the original files. All simulation source remains unchanged. No production fix is justified by this audit. The pending common-input MAC replay tests the remaining scheduling behavior while this short HOP regression covers the window-growth edge in the same user run.
