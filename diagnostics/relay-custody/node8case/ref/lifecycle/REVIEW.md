# Discovery lifecycle and reliable key-response review

The returned K run exposes two independent behavioral differences. The strict stop is a wrong SNMP handoff destination at 71.942 seconds. Its source cause occurs earlier, when node 5 handles a second discovery requester while already active at 41.202171086 seconds. Separately, native admits a reliable KEY_UPDATE response during a receive callback at 62.870833632 seconds; MATLAB defers it through the NWK pump and misses the same preparation boundary. Do not interpret the later strict stop as proof that all preceding callback times were identical.

## SNMP destination mismatch

The stopped third child is native frame 233: source 5, outer HOP destination 1, embedded SNMP final destination 1, START command 1, sequence 0 and 31 modeled bytes. The raw native packet hex independently encodes both destination fields as 1. MATLAB has outer destination 4 and final destination 2. The packet type, command, source, size and other compared fields agree. These destination fields affect routing and discovery behavior; this is not a transport-label comparison exception.

The observed native chronology establishes the source cause:

| Time (s) | Native node 5 event | Relevant state |
|---:|---|---|
|40.900359163 |Receives START from 3 while idle |Adds discovery entry 3 as not needed; starts discovery |
|41.202171086 |Receives START from 1 while active |Retains requester 1 for a DONE report; does not mark 1 complete |
|55.900359163 |Completes discovery |Appends needed entries 4 then 1; reports DONE to 3 and 1; hands off to 4 |
|71.827352444 |Receives DONE from 4 |Appends needed entry 2; first pending entry is 1 |
|71.942 |Transmits the pending START |Both HOP and final destination are 1 |
|131.827352444 |Later watchdog expires |Next handoff is 2 via 4; its transmission occurs at 132.288 |

`ReceiveSnmpFromHop` always retains a new requester in its completion list, but calls `MarkDiscoveryNotNeeded(source)` only inside the idle-start branch. Active duplicate START requests deliberately leave that requester's later discovery eligibility unchanged. MATLAB retains the requester correctly but adds its source to `ScanRequested` unconditionally. Thus source 1 was suppressed at 41.202 seconds. When DONE 4 arrives, MATLAB selects 2 instead of 1. The native pending order `[1,2]` versus MATLAB `[2]` is a source reconstruction supported by the observed receive/append/handoff events, not a private runtime state dump.

The narrow correction is to move the existing requester mark into the idle/new-session branch, before `startDiscovery`, while retaining active requesters for completion reports. No routing, list-order, watchdog, SNMP payload or comparison change is needed for this defect.

## SNMP sibling coverage and limits

All 36 captured native SNMP packets were checked against raw packet bytes: 28 START and 8 DONE, all non-ACKed with outer sequence 0, DSCP 0 and 31 modeled bytes. Twenty STARTs have different HOP and final destinations. This is deliberate: native chooses a discovery next hop but preserves the final address, then discards a decoded SNMP whose final destination is beyond that one hop. It does not forward it further. MATLAB already models this contract; preserving both strict destination checks is essential.

Only eight START packets reach NWK in this capture; the node 5/source 1 event is the sole active duplicate. Seven of eight transmitted DONE packets reach NWK, and every delivered DONE source matches the pending native handoff target. The largest completion-requester list is 2. Two adjacent source differences are therefore recorded, but not folded into this correction:

- Native requester capacity is 10; MATLAB's list is unbounded. This limit is not approached here.
- Native DONE handling always invokes the next discovery-table check, canceling/replacing its watchdog; MATLAB has additional scan/waiting gates. No delivered DONE in this capture exercises the nonmatching-source branch.

The earlier 41.202-second incorrect requester mark predates the separate62.87-second key-response timing drift. The SNMP mismatch is consequently not explained away by that later drift.

## Reliable KEY_UPDATE response ownership

At62.870833632 seconds, native node 4 successfully decodes node 2 KEY_REQUEST sequence 3 while Track, from physical TX 8589934594 / frame 184. The receive callback immediately calls NWK `NoteKeyRequestReceived` → `SendKeyUpdate` → HOP `SendKeyUpdate`. Native MAC data depth changes 0→1 before `ReturnToSearchAfterReceive`; that Search transition activates preparation and draws MAC ordinal 25 immediately. MATLAB's delayed owner submission instead draws at 62.881 seconds, and the independent receiver review finds a subsequent 13 ms TX shift. Its detailed returned-history analysis is separately recorded under `autonomous_ninth/receiver/`.

Native ownership and timing are explicit:

1. NWK synchronizes key state and suppresses an already complete or active key send. A valid new response calls HOP synchronously. The reciprocal response after receiving KEY_UPDATE is also synchronous.
2. HOP allocates the shared per-destination sequence, builds a reliable unicast with DSCP 7, preserves security metadata, and applies ordinary link-control radio selection.
3. HOP installs a resend copy before handing the frame to MAC. It is not a no-ACK control and must not borrow SNMP radio settings.
4. The initial ACK/resend clock starts on the actual MAC sent confirmation, not at queue admission. Native ACK completion then clears the appropriate key-send ownership.

Across the complete accepted capture there are 14 generated KEY_UPDATEs, 14 distinct transmitted frames and 14 successful acknowledged completions. All transmitted key updates are 62 bytes, reliable and DSCP 7; no KEY_UPDATE retransmission or resend-queue overflow is observed. Immediate submission belongs at the new key-control owner boundary, not in a generic MAC pump or a flush of other queued controls/application traffic.

The isolated candidate extends the prior fresh KEY_REQUEST path to reliable KEY_UPDATE, registers its NWK owner before any sending callback, preserves the reliable HOP admission gate and normal radio/ACK options, re-finds the owner after possible synchronous completion, and retains the baseline wake fallback for blocked or failed admission. This preserves existing MATLAB ownership guarantees while correcting the observed synchronous-send boundary.

There is a specific retained saturation limit: native `EnqueueResend` rejects tracking when full but still allows the caller to forward the frame to MAC, without rolling back its sequence. MATLAB `CanSendControl` gates the send before that point. The proposed candidate retains that baseline gate and fallback; it does not claim native parity under full resend/MAC queues. The observed node 4 response has an empty MAC queue and no saturation evidence.

## Validation scope

`audit_lifecycle.py` checks the 36 raw SNMP records, 8 START receives, 7 delivered DONEs and 14 key-send/transmit/completion identities, and extracts the native node 4 receive/preparation boundary. `lifecycle_audit.json` retains the full inventory and source-reconstructed state distinction. `source_path_proof.json` includes exact pinned source excerpts and hashes.

No new native network or component simulation was necessary: the actual native callback, table-append, handoff, send and completion records already exercise the relevant source branches. MATLAB public component preflights and the L continuation are still owner-side. This review makes no 15% network-parity or completed-prefix timing claim.
