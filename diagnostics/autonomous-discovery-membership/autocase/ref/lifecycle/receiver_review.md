# KEY_UPDATE ordering: first recorded K timing divergence

The first random-request time difference is caused by **deferring a newly generated KEY_UPDATE until after PHY has returned from Track to Search**. Native admits the response while still Track. Both MAC implementations already start preparation on Track→Search when a frame is pending; MATLAB's queue is still empty at that transition. Its next slot tick starts preparation 10.166368 ms later, and the resulting KEY_UPDATE transmission is one 13-ms slot late.

This is independent of the separately identified SNMP scan-state mismatch. The SNMP state difference predates this event; “first” here means the first recorded random-request time divergence, not the first differing protocol state.

## Direct chronology

At 62.870833632 seconds, node 4 successfully receives node 2's KEY_REQUEST. Both sides are Track, have no pending ACK/data, have no preparation active, and have an unassigned reservation (`counter=-1`). Post-TX ACK waiting is active.

| Step | Native evidence | MATLAB K evidence |
|---|---|---|
| Deliver KEY_REQUEST | Receiver Track with MAC data depth 0, event 28523 | Receiver Track, order 144123; accepted receive at 144125 |
| Generate KEY_UPDATE response | MAC depth becomes 1 while still Track, by event 28529 | Schedules same-time `pump` event 19156, order 144128; neighbor send report at 144129 |
| Return to Search | Pending response present at events 28533–28535 | Queue remains empty at orders 144137–144140 |
| Admit response to MAC | Already admitted before Search | `pump` runs after receive callback returns; MAC enqueue at order 144147 |
| Choose slot 8, draw 25 | Immediately at 62.870833632, event 28537 | Next slot tick, 62.881; order 144200 |
| Transmit response | 62.985 | 62.998 |

The transmission is the same matched semantic packet: source 4, destination 2, KEY_UPDATE, HOP sequence 1, 62 modeled bytes, short preamble, source TX ordinal 21 (`native_semantic_tx_id=17179869205`). The difference is **13,000,000 ns in transmission time**, following **10,166,368 ns in slot-selection time**. The slot draw value and checked semantic context agree.

## Ten observed KEY_UPDATE generation contexts

All ten generated updates in K are enqueued after the corresponding Track→Search transition. The table explains why this scheduling choice first exposes an unassigned-slot delay at node 4→2. The masking descriptions identify observed conditions; they are not a corrected-run result.

| Time (s) | Response | Data / ACK depth before return | Counter | Preparation active | Condition |
|---:|---|---:|---:|---|---|
| 11.676831086 | 1→5 | 0 / 0 | 2 | No | Carried reservation; no new slot draw needed |
| 11.799711086 | 5→1 | 0 / 1 | -1 | No | ACK already pending |
| 12.014828077 | 1→3 | 2 / 1 | 11 | Yes | Existing traffic and preparation |
| 12.314888077 | 3→1 | 0 / 1 | 10 | No | ACK pending; carried reservation |
| 26.977339163 | 3→5 | 0 / 1 | 26 | Yes | Existing ACK and preparation |
| 27.710719163 | 5→3 | 0 / 2 | 5 | Yes | Existing ACKs and preparation |
| 42.694832444 | 5→4 | 0 / 2 | 13 | Yes | Existing ACKs and preparation |
| 43.102212444 | 4→5 | 0 / 1 | -1 | No | ACK already pending |
| **62.870833632** | **4→2** | **0 / 0** | **-1** | **No** | **Empty queue and unassigned reservation expose delay** |
| 63.084713632 | 2→4 | 0 / 1 | -1 | No | ACK already pending |

## Source path and targeted repair

Native HOP handles an authenticated KEY_REQUEST synchronously and invokes its NWK callback (`csr-hop-layer.h:2915–2938`). `CsrNetLayer::NoteKeyRequestReceived` calls `SendKeyUpdate` directly (`csr-nwk-layer.h:4306–4334`). The reciprocal update path also calls `SendKeyUpdate` directly (`:4338–4353`). `SendKeyUpdate` establishes the HOP resend owner, then calls `m_mac->EnqueueTxFrame` before returning (`csr-hop-layer.h:1977–2031`). These source files are under `autonomous/native_env/csr/model/`.

Native `SetReceiveState` starts preparation immediately for Track→Search with pending traffic (`csr-mac-core.h:191–199`). `ReturnToSearchAfterReceive` uses that transition and retains active post-TX waiting (`csr-net-device.h:1215–1251`). MATLAB already expresses the same preparation rule in `ReceiverTimerMac.m:733–735`; it does not need a new MAC rule.

In the authoritative issued K kit, `ac.ControlWireNwk.queueControl` has a synchronous branch only for new nonreliable KEY_REQUESTs (`autonomous_eighth/kit/autocase/+ac/ControlWireNwk.m:537`). Reliable KEY_UPDATE takes the generic `wake` path, which schedules `pump` at the current time (`:416–419`). “Same timestamp” still means a later callback, so it loses the Track→Search boundary. `ac.PopulationNeighbors.sendKeyUpdate` creates the new reliable update during receive (`:320–330`), but its callback does not submit that owner synchronously.

The bounded correction is to admit **only the newly created reliable KEY_UPDATE owner** through the existing HOP/MAC interface before returning from the receive callback. Preserve control queue limits, the reliable HOP-capacity check, owner registration before callback entry, relookup after synchronous callback return, and the original deferred retry path when admission is blocked or rejected. Do not flush unrelated pending control owners. The HOP's own `sendControl` already installs the resend owner before MAC enqueue and rolls back sequence/ownership on rejection (`model/+csr/+hop/Layer.m:113–166`).

No MAC post-TX-wait change is indicated. With synchronous Track enqueue, Track→Search starts preparation while waiting stays active, as native does. In the current delayed path, the subsequent slot tick calls `cancelPostTxWait` before preparing; that cancellation is a downstream consequence of the missing earlier admission. The actual transmission should retain its existing wait-cancellation responsibility.

## Component checks and boundaries

The public-interface component checks should exercise the exposed empty-queue/unassigned-reservation Track case, an already pending ACK, a carried reservation, blocked HOP capacity, MAC admission rejection, and synchronous owner completion/reentrancy. Confirm owner/sequence rollback and deferred retry behavior on rejection, and verify unrelated control owners are not pumped early. The independent SNMP correction can run in the same next controlled case.

No corrected network continuation was run here, and no production code was changed. The source chain supports the synchronous KEY_UPDATE repair, while the returned evidence establishes the specific 62.870833632-second failure and its first shifted transmission. It does not establish full-run delivery/latency parity or justify making all control types synchronous.

Reproduce the evidence extraction:

```bash
python autonomous_ninth/receiver/audit_key_update_order.py
```

Artifacts: [JSON audit](key_update_order_audit.json), [ten-case table](key_update_masking_cases.csv), [MATLAB chronology](matlab_first_divergence_context.jsonl), and [native chronology](native_first_divergence_context.csv). The audit includes source/evidence hashes and asserts the first differing random-request key and the matched first shifted TX signature.
