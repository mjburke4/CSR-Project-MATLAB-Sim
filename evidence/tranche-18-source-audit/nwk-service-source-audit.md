# Tranche 18 NWK/HOP service source audit

Read-only audit of the owner-validated T17 MATLAB tree and native commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. No production edits, MATLAB execution, native execution, or new numerical parity claim.

## Result

**Neither implementation gives locally originated DATA an explicit queue priority over relayed DATA.** Both append DSCP-zero arrivals and insert every positive-DSCP arrival at the head. Both scan beyond a packet blocked by its next hop. NSDP counts select application admission and ACK versus DACK; they are not an extra NWK-to-HOP forwarding gate. The observed node-5 traffic redistribution therefore does not establish a local-priority policy bug.

Several implementation differences must remain visible during T18. Most significantly, the intentionally retained MATLAB retry policy waits for actual retransmission before starting the next timeout, whereas native code retains a provisional timestamp while a retry is queued. This difference was explicitly accepted in Tranche 2 and reaffirmed by the Tranche 6 source audit. Do not silently remove it to improve numerical agreement.

## Bound source identity

| File | SHA256 |
| --- | --- |
| MATLAB `+csr/+nwk/Layer.m` | `7ef09931c83c55697ce96b400ee1d90459a44af4c0527b396829d62ab9125300` |
| MATLAB `+csr/+hop/Layer.m` | `a56cd54fcd8bd863958b1addfc861f16f434ab79e4993fb182936a8b2b454f67` |
| MATLAB `+csr/+sim/NetworkSimulation.m` | `80264e18c050d4dbf2c6e5729076c5dfa602401b4e76053577b6388a77894104` |
| Native `model/csr-nwk-layer.h` | `bc871898c628eec08c82636507cb23cbf6b29d80a3738be18466cb0a9525ecfc` |
| Native `model/csr-hop-layer.h` | `0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b` |

The headers were fetched directly from the pinned GitHub commit. Their local raw bytes reproduce Git blob IDs `0b785ffd690fdb7045ce90145a8261d91891cbdf` and `5e6d03b34f3fb12f17b08f1a35f53c5a5ef7c5bf`, respectively. Copies are in `t18-design/native/`.

## Equal service contracts

| Contract | MATLAB location | Native location | Finding |
| --- | --- | --- | --- |
| Local and relay insertion | NWK `sendApplication` 104–114; `receiveData` 117–157; `enqueueApplication` 454–467 | NWK `Send` 1259–1342; `ReceiveFromHop` 1392–1529 | One DATA queue; zero appends, positive DSCP prepends. No local/relay priority branch. |
| Local application NSDP gate | NWK `applicationState` 356–385 reports own `(source,destination)` count and limit 16 | NWK `CanAdmitApplicationPacket` 428–437 | Admission suppresses application generation at 16 outstanding local-flow owners. Blocked attempts are not generated packets or packet losses. |
| Per-flow ownership | NWK `nsdpCount` 348–354 counts retained matching owners | NWK `GetNsdpCount` 421–425; increments 1290–1291 and 1479–1480 | Counts include submitted DATA awaiting NSDP release; node-5 local flow and each forwarded source have separate counts. |
| Forwarding selection | NWK `pump` 478–501 | NWK `CheckNwkQueue` 2397–2630 | Neighbor-blocked or no-route packet does not head-of-line block another eligible destination. NSDP count itself does not gate forwarding. |
| Permitted final slot | HOP `admission` 67–76 | HOP `GetDataAdmissionSnapshot` 530–549; `CanAcceptDataGlobally` 654–660; `CanSendToHop` 662–706 | `pending <= 16` and `outstanding <= threshold` allow the final transfer to take pending from 16 to 17. |
| NSDP completion does not issue an immediate local queue wake | NWK `releaseFromHop` 397–405 | NWK `DecrementNsdp` 1344–1390 | Both remove/reduce ownership and leave the post-feedback wake to HOP. |

## Differences and their relevance

1. **Known intentional queued-retry timing difference.** MATLAB HOP marks a newly queued retry unconfirmed; native preserves initial confirmation and sets a provisional `lastTxTime`. Further native resend scans can reprocess a retry before MAC transmits it. See MATLAB HOP 459–493, native HOP 4406–4752, `docs/parity-ledger.csv` entry `HOP_queued_retry_timer`, and `docs/tranche-6-source-audit.md` section “Existing deliberate differences to preserve.” Preserve it in T18 and label it in comparative evidence.

   Existing T17 events establish that queued retry residence is long enough to matter as a model distinction: on 4→5, 553 of 1,653 observed retry-to-transmit waits exceed or equal two seconds, 295 exceed or equal four seconds, and the maximum is 22.622 seconds. On 5→1, the corresponding counts are 775 and 773 of 779, with a maximum of 64.391 seconds. This is **not** a native counterfactual or a claim those waits cause the measured delivery difference. Event-ledger details are in `t17-retry-mac-waits.json`.

2. **NWK wake scheduling is not event-identical.** Native local/relay enqueue schedules `CheckNwkQueue` after `CsrOpnetTic()` (NWK 2358–2367). MATLAB `wake` schedules `pump` at the current scheduler time (NWK 415–419). After a HOP +TIC wake, native calls `CheckNwkQueue` directly through its callback (NWK 1233–1238), whereas MATLAB calls NWK `wake` through `NetworkSimulation` 132–133 and inserts another event at that same time. Thus absolute delay and same-time event insertion/coalescing can differ even when ownership-release order agrees. This belongs in the observer evidence; do not introduce a global timing change based only on source inspection. T17’s first generated packet at 300 s is handed to MATLAB HOP at 300 s, versus the native first forwarding record at 300.000000028 s.

3. **Global-capacity scan termination differs.** Native stops the whole queue scan before route lookup when global DATA capacity is exhausted (NWK 2405–2439). MATLAB continues iterating, performing `routeAvailable` before the combined HOP admission check (NWK 483–491). Successful DATA forwarding is still blocked in both. However, MATLAB `Routes.relay → select → noteDestination` can update destination-walk bookkeeping, so arbitrary extra route lookups are not guaranteed observationally inert. The canonical campus’s already-known gateway routes give no evidence that this difference causes its traffic redistribution.

4. **Different queue representations and bounded ownership are deliberate.** Native removes an entry from `m_nwkQueue` at HOP handoff while keeping a separate NSDP count (NWK 2565–2579). MATLAB retains it as `Pending{...}.Submitted=true` until NSDP release (NWK 493–499 and 397–405). MATLAB’s 512-owner custody bound and transactional resend/MAC admission are declared prior differences; raw `PendingCustody` is not comparable to native unsent queue size. Compare native queue length to MATLAB owners with `Submitted=false`. T17’s maximum retained NWK depth was 145, with zero NWK/MAC queue admission rejections, so the 512-owner cap was not exercised in the observed run.

The complete HOP completion-order specialist audit is supplied separately. Existing T9 evidence already covers ACK capacity-before-NSDP, resend cleanup, and a coalesced +TIC HOP wake; T18 should not repeat those controlled arrival-edge tests merely because the campus counts differ.

## Minimum passive observations for T18

Use existing native opt-in admission events where available: `nwk_enqueue`, `nwk_admission`, `nwk_forward`, `nwk_nsdp_release`, and `hop_completion`. Retain event order as well as full-precision time. Join application identities through original source/destination and a generation ordinal; equal seed or unrelated native/MATLAB packet IDs do not establish corresponding RNG histories.

- At DATA enqueue and handoff: node, original source/destination, local-versus-relay, application identity, ingress peer, selected next hop, queue position, unsent queue depth, retained custody depth, and NSDP count for the original flow.
- At admission: accepted or blocked reason; global pending/limit; next-hop outstanding/threshold; resend occupancy. Summarize local and relay service counts separately.
- At ACK, DACK, DACK expiry and final failure: reason, application and HOP sequence, NSDP before/after, capacity before/after, and whether a wake is newly scheduled or already pending.
- At retry enqueue and actual MAC transmission: retry index, last confirmed transmission, queued/unconfirmed state and elapsed MAC wait. Tag the intentionally different retry policy rather than comparing these states as if identical.

Do not add RNG draws, scheduler callbacks or repeated route selection merely to observe state. Native `GetDataAdmissionSnapshot` and `GetNsdpCount` are nonmutating; `CanSendToHop` and `ShouldDack` can create map entries and should not be called solely by observers. MATLAB `HOP.admission` and `NWK.nsdpCount` are nonmutating. Capture already-computed route decisions instead of invoking `Routes.relay` again. Use complete counters and an explicit bounded detailed observation window; report any permitted omission separately from complete accounting.

The bounded question is whether node 5’s local-versus-relayed admission and service share differs materially across seeds after these known distinctions are identified. A discrepancy should be tied to an actual source contract before a production fix or another full campus run is proposed.
