# L watchdog and discovery-membership review

The watchdog fires at the correct time. The extra transmission comes from **adding current routing destinations to the discovery work list when the watchdog advances it**. Node 3 learned route 7 after its discovery reports were collected. MATLAB then converts that later routing knowledge into new scan work; native advances only entries already in its discovery table.

The previously reported 116.350-versus-300.001-second MAC draw comparison is therefore an **extra-traffic symptom**, not a 183.651-second timer error. MATLAB consumes the next random draw for its extra management packet; native next needs that draw for application traffic at 300 seconds.

## Direct observed chain

| Time (s) | Node 3 event | Implication |
|---:|---|---|
| 25.385728077 | Receives START from node 1 | Initiator 1 is already excluded from new scan work. |
| 40.385728077 | Local discovery completes; sends DONE containing `[5,1]`, then START to 5 | First explicit membership snapshot; watchdog event 9815 targets 5. |
| 56.340299163 | Receives DONE from 5 containing `[4,3,1]`; sends START final destination 4 via 5 | Membership adds 4; own node 3 is excluded. Old target-5 wait is superseded. New watchdog event 16021 targets 4. |
| 96.268879163 | Receives ROUTING UPDATE for 7 from 5 | Routing sequence 18, advertised capability 1, path `[4,2,8,7]`, cost 29800. This is routing knowledge, not a discovery report. |
| 96.388928077 | Receives a second UPDATE for 7 from 1 | Advertised path `[5,4,2,8,7]`; another routing candidate. |
| 100.385728077 | Old watchdog event 9815 fires and returns without scheduling work | Generation-based invalidation correctly suppresses the stale callback. |
| **116.340299163** | Current watchdog event 16021 fires | Exactly 60 seconds after the DONE receipt and handoff creation. |
| 116.340299163 | MATLAB schedules pump plus a new watchdog; pump enqueues START final destination 7 via 5 | `advanceScan` has refreshed membership from the live route table. |
| 116.350 | MAC draws slot 4 for the extra packet | First recorded random-request time difference. |
| 116.415 | Strict TX guard rejects extra 31-byte SNMP_START | Native node 3 has no corresponding management transmission; its next TX ordinal belongs to DATA at 300.365. |

No observed local-completion or received-DONE membership input to node 3 contains 7 before the stop. Its logged explicit inputs are `[5,1]` and `[4,3,1]`. Private `ScanKnown` was not logged; its composition is supported by these inputs and the reviewed source, while the extra enqueued target is directly observed.

## Timer ownership and numerical checks

The returned event history contains 14 watchdog schedules: 13 through the matched history, plus the successor created by the extra handoff. Every scheduled deadline is 60,000,000,000 nanoseconds after its creation when compared at native clock resolution. Event 16021 was created at 56.340299163 and fires at 116.340299163. The earlier superseded event performs no work. No timing, cancellation, or generation fix is indicated for this failure.

Native `CsrNetLayer::CheckDiscoveryTable` cancels its previous report event and scans existing entries; it marks a selected entry consumed before attempting the send. `SnmpReportTimeout` simply calls that advancement function. Entries requiring discovery come from `CompleteDiscoveryLifecycle` or the nodes advertised in an accepted DONE report; the START initiator is separately registered as already complete (`autonomous/native_env/csr/model/csr-nwk-layer.h:8295`, `:8330`, `:8392`, `:8425–8476`).

The issued MATLAB `advanceScan` instead calls `mergeScanKnown(Routes.reachableDestinations())` every time before choosing the next member (`autonomous_ninth/kit/autocase/+ac/DiscoveryLifecycleNwk.m:892–910`). Removing that refresh leaves local completion and received DONE as explicit membership-population points, while retaining the existing route table for DATA and for finding the next hop of an explicitly listed discovery target.

Unsolicited or duplicate DONE ownership is a separate source-comparison boundary: native calls its advancement function for any accepted DONE, whereas the current MATLAB wait-release guard tests the report source. That branch is not responsible for this recorded failure and is not validated as equivalent by the membership change. Component checks must not portray duplicate-report behavior as full native watchdog-ownership parity.

## Prior fixes verified in the actual return

The earlier KEY_UPDATE delay is cleared: node 4 MAC draw 25 now occurs at **62.870833632**, and its matched KEY_UPDATE transmission occurs at **62.985**. The former SNMP destination mismatch is also cleared: node 5's transmission at **71.942** carries START with both final destination and hop destination **1**, alongside the expected ACK/routing children. Their strict signatures and recorded times match native.

## Files and scope

Run `python autonomous_tenth/receiver/audit_discovery_watchdogs.py` to reproduce the extraction. It writes [watchdog membership audit](watchdog_membership_audit.json), [all returned watchdog schedules](watchdog_history.csv), [management events](management_events.csv), and [route-7 updates](node3_route7_updates.csv), with evidence/source hashes.

This review used existing evidence and source only. It ran no MATLAB or network simulation and changed no production source. The candidate membership rule and public component tests still require owner runtime execution; this review makes no full-run parity claim.
